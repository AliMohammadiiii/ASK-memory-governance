"""Prompt-rendering wrapper for turn-level memory extraction."""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, cast

from jinja2 import Template

from ..inference.llm import LLM, LLMResponse, StructuredLLM
from .schema import EvidenceSpan, ExtractedItem, ExtractionOutput

_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}", re.MULTILINE)
_DEGREE_RE = re.compile(
    r"\bI\s+graduated\s+with\s+a\s+degree\s+in\s+([^,.!?;]+)",
    re.IGNORECASE,
)
_NEW_PROPER_POSSESSION_RE = re.compile(
    r"\bmy\s+new\s+([A-Z][A-Za-z0-9'&.-]*(?:\s+[A-Z0-9][A-Za-z0-9'&.-]*){0,4})\b"
)
_GOT_PROPER_ITEM_RE = re.compile(
    r"\b(?:the|a|an|my)\s+"
    r"([A-Z][A-Za-z0-9'&.-]*(?:\s+[A-Z0-9][A-Za-z0-9'&.-]*){0,4})"
    r"\s+I\s+got\s+(yesterday|today|last\s+(?:week|month|year))\b",
    re.IGNORECASE,
)
_PLACEHOLDER_TEXTS = {
    "one short canonical sentence",
    "one short sentence",
}
# Start-anchored detector for items that are questions or requests to the
# assistant rather than durable user assertions. Anchored at the *start* so a
# declarative turn carrying a real fact ("I just got it from Best Buy for $350,
# what a steal, right?") is preserved while a pure question/request ("Which one
# do you think is best?", "Can you plan a class about ...") is dropped. The
# extraction prompt already forbids these; small local models emit them anyway.
_NON_ASSERTION_START_RE = re.compile(
    r"^\s*(?:"
    r"can you|could you|would you|will you|please|"
    r"write|plan|provide|generate|create|draft|list|brainstorm|recommend|"
    r"explain|describe|suggest|tell me|give me|help me|show me|"
    r"do you|does|did you|are there|is there|what|which|why|how|who|where|when"
    r")\b",
    re.IGNORECASE,
)
POSTPROCESSOR_VERSION = "extractor_postprocessor_v2"


def _is_non_assertion(text: str) -> bool:
    """True for question/request-shaped items that carry no user assertion."""
    return bool(_NON_ASSERTION_START_RE.match(text))


class _TraceLLM:
    """Proxy that records raw LLM responses while preserving the LLM protocol."""

    def __init__(self, inner: LLM) -> None:
        self.inner = inner
        self.model_id = inner.model_id
        self.responses: list[LLMResponse] = []

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        seed: int = 0,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        response = self.inner.generate(
            prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            seed=seed,
            stop=stop,
        )
        self.responses.append(response)
        return response


class Extractor:
    """Render a Jinja prompt and parse an `ExtractionOutput` via `StructuredLLM`."""

    def __init__(
        self,
        llm: StructuredLLM,
        prompt_template: str,
        *,
        log_path: str | Path | None = None,
    ) -> None:
        self.llm = llm
        self.prompt_template = prompt_template
        self.log_path = Path(log_path) if log_path is not None else None
        # Guards the append-only trace file when turns extract concurrently
        # (orchestrator §5 fix 1). Cheap and uncontended in the serial default.
        self._trace_lock = threading.Lock()

    @classmethod
    def from_template_file(
        cls,
        llm: StructuredLLM,
        prompt_path: str | Path,
        *,
        log_path: str | Path | None = None,
    ) -> Extractor:
        return cls(
            llm=llm,
            prompt_template=Path(prompt_path).read_text(encoding="utf-8"),
            log_path=log_path,
        )

    def extract(
        self,
        turn: Any,
        window: tuple[Any | None, Any | None],
        *,
        max_new_tokens: int = 512,
        temperature: float = 0.0,
        seed: int = 0,
    ) -> ExtractionOutput:
        """Extract candidate memories from one turn with optional ±1 context."""
        turn_payload = _turn_to_payload(turn)
        prev_payload = _turn_to_payload(window[0]) if window[0] is not None else None
        next_payload = _turn_to_payload(window[1]) if window[1] is not None else None
        prompt = self.render_prompt(turn_payload, (prev_payload, next_payload))

        tracer = _TraceLLM(self.llm.inner)
        traced_llm = StructuredLLM(tracer, max_repair_tokens=self.llm.max_repair_tokens)
        parse_trace: dict[str, Any] = {}
        try:
            output = traced_llm.generate_json(
                prompt,
                ExtractionOutput,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                seed=seed,
                trace=parse_trace,
            )
        except Exception as exc:
            output = self._recover_output(tracer.responses)
            if output is None:
                if not tracer.responses:
                    # No model response means provider/transport unavailability,
                    # not a semantic "no memory" judgment. Trace it and let the
                    # orchestrator continue without caching a fabricated empty
                    # extraction; resumed runs can then retry this turn.
                    self._write_trace(
                        prompt,
                        tracer.responses,
                        None,
                        seed,
                        temperature,
                        error=f"extractor unavailable before any response: {exc}",
                        parse_trace=parse_trace,
                    )
                    raise
                output = empty_extraction_output(
                    "extractor output could not be parsed; treated as no extractable content"
                )
                self._write_trace(
                    prompt,
                    tracer.responses,
                    output,
                    seed,
                    temperature,
                    error=f"fallback_empty after structured parse error: {exc}",
                    parse_trace=parse_trace,
                )
                return output
            raw_output = output
            output = _postprocess_output(output, turn_payload)
            self._write_trace(
                prompt,
                tracer.responses,
                output,
                seed,
                temperature,
                raw_output=raw_output,
                error=f"recovered after structured parse error: {exc}",
                parse_trace=parse_trace,
            )
            return output
        raw_output = output
        output = _postprocess_output(output, turn_payload)
        self._write_trace(
            prompt,
            tracer.responses,
            output,
            seed,
            temperature,
            raw_output=raw_output,
            parse_trace=parse_trace,
        )
        return output

    def render_prompt(
        self,
        turn: Mapping[str, Any],
        window: tuple[Mapping[str, Any] | None, Mapping[str, Any] | None],
    ) -> str:
        schema_json = json.dumps(ExtractionOutput.model_json_schema(), indent=2)
        return Template(self.prompt_template).render(
            turn=turn,
            prev_turn=window[0],
            next_turn=window[1],
            schema_json=schema_json,
        )

    def _write_trace(
        self,
        prompt: str,
        responses: list[LLMResponse],
        output: ExtractionOutput | None,
        seed: int,
        temperature: float,
        *,
        raw_output: ExtractionOutput | None = None,
        error: str | None = None,
        parse_trace: Mapping[str, Any] | None = None,
    ) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "prompt": prompt,
            "responses": [r.to_dict() for r in responses],
            "raw_validated_output": raw_output.model_dump() if raw_output is not None else None,
            "validated_output": output.model_dump() if output is not None else None,
            "postprocessor_enabled": True,
            "postprocessor_version": POSTPROCESSOR_VERSION,
            "parse_path": (parse_trace or {}).get("parse_path"),
            "repair_used": (parse_trace or {}).get("repair_used"),
            "first_parse_error": (parse_trace or {}).get("first_error"),
            "repair_parse_error": (parse_trace or {}).get("repair_error"),
            "seed": seed,
            "temperature": temperature,
        }
        if error is not None:
            record["error"] = error
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self._trace_lock:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(line)
                fh.write("\n")

    @staticmethod
    def _recover_output(responses: list[LLMResponse]) -> ExtractionOutput | None:
        """Recover from common LLM omissions while still returning the strict schema."""
        for response in reversed(responses):
            data: Any = None
            match = _JSON_OBJECT_RE.search(response.text)
            if match is not None:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    data = None
            if not isinstance(data, dict):
                # Unterminated/truncated JSON: salvage completed items rather
                # than dropping the whole turn's extraction.
                data = _salvage_truncated_items(response.text)
            if not isinstance(data, dict):
                continue
            items = data.get("items")
            if not isinstance(items, list):
                continue
            data["no_extractable_content"] = len(items) == 0
            if "coverage_note" not in data:
                data["coverage_note"] = None if items else "no extractable user memory"
            try:
                return ExtractionOutput.model_validate(data)
            except Exception:
                continue
        return None


def empty_extraction_output(reason: str) -> ExtractionOutput:
    """Conservative fallback when an extractor model emits unrecoverable JSON."""
    return ExtractionOutput(
        items=[],
        no_extractable_content=True,
        coverage_note=reason[:240],
    )


def _salvage_truncated_items(text: str) -> dict[str, Any] | None:
    """Recover the complete leading ``items`` objects from truncated JSON.

    A large extraction can exhaust the model's output-token budget mid-array,
    leaving unterminated JSON (``finish_reason=length``) that ``json.loads``
    rejects wholesale. Rather than discard every fact from the turn, walk the
    ``items`` array with a string-aware brace scanner, keep each fully-formed,
    individually-valid object, and drop only the final incomplete one.
    """
    match = re.search(r'"items"\s*:\s*\[', text)
    if match is None:
        return None
    i = match.end()
    n = len(text)
    salvaged: list[Any] = []
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i >= n or text[i] == "]":
            break
        if text[i] != "{":
            break
        depth = 0
        in_str = False
        esc = False
        obj_end = -1
        j = i
        while j < n:
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    obj_end = j
                    break
            j += 1
        if obj_end == -1:
            # Trailing object was cut off: stop and keep what completed.
            break
        chunk = text[i : obj_end + 1]
        try:
            candidate = json.loads(chunk)
            ExtractedItem.model_validate(candidate)
        except (json.JSONDecodeError, ValueError):
            break
        salvaged.append(candidate)
        i = obj_end + 1
    if not salvaged:
        return None
    return {
        "items": salvaged,
        "no_extractable_content": False,
        "coverage_note": "recovered partial items from truncated extractor JSON",
    }


def _postprocess_output(output: ExtractionOutput, turn: Mapping[str, Any]) -> ExtractionOutput:
    """Filter local-model artifacts and add high-precision user facts.

    Small instruction-tuned local models sometimes copy the prompt's example
    text or emit confidence-0 request paraphrases. Those rows bloat controller
    state and can hide the actual fact needed by LongMemEval. Keep this layer
    conservative: drop obvious prompt artifacts, then add only deterministic
    facts whose surface form is explicit in the current user turn.
    """
    cleaned: list[ExtractedItem] = []
    seen: set[str] = set()
    for item in output.items:
        text = item.text.strip()
        if not text:
            continue
        if text.lower() in _PLACEHOLDER_TEXTS:
            continue
        if _is_non_assertion(text):
            # Question/request paraphrase, not a durable user assertion.
            continue
        # Only drop strictly-negative (invalid) confidence. A model-emitted
        # 0.0 on an otherwise valid item must NOT be silently discarded: small
        # models parrot the prompt template's example confidence (historically
        # 0.0), which previously sank every `stable_pref` extraction (MGP-6 T1
        # recall = 0.0). Placeholder/paraphrase rows are already filtered above
        # by _PLACEHOLDER_TEXTS and empty-text checks.
        if item.extraction_confidence < 0.0:
            continue
        key = text.casefold()
        if key in seen:
            continue
        cleaned.append(item.model_copy(update={"text": text}))
        seen.add(key)

    for item in _rule_based_items(turn):
        key = item.text.casefold()
        if key in seen:
            continue
        cleaned.append(item)
        seen.add(key)

    if not cleaned:
        return ExtractionOutput(
            items=[],
            no_extractable_content=True,
            coverage_note=output.coverage_note or "no high-confidence extractable user memory",
        )
    return ExtractionOutput(
        items=cleaned,
        no_extractable_content=False,
        coverage_note=output.coverage_note,
    )


def _rule_based_items(turn: Mapping[str, Any]) -> list[ExtractedItem]:
    content = str(turn.get("content") or "")
    session_id = str(turn.get("session_id") or "")
    turn_idx = int(turn.get("turn_idx") or 0)
    items: list[ExtractedItem] = []

    for match in _DEGREE_RE.finditer(content):
        degree = match.group(1).strip()
        if not degree:
            continue
        text = f"User graduated with a degree in {degree}."
        items.append(
            ExtractedItem(
                text=text,
                type_guess="episodic_fact",
                evidence_span=EvidenceSpan(
                    session_id=session_id,
                    turn_idx=turn_idx,
                    char_start=match.start(),
                    char_end=match.end(),
                ),
                extraction_confidence=1.0,
                negation_marker=False,
                hedge_marker=False,
                polarity_subject="user",
            )
        )
    for match in _NEW_PROPER_POSSESSION_RE.finditer(content):
        item = match.group(1).strip()
        if not item:
            continue
        text = f"User has a new {item}."
        items.append(
            ExtractedItem(
                text=text,
                type_guess="episodic_fact",
                evidence_span=EvidenceSpan(
                    session_id=session_id,
                    turn_idx=turn_idx,
                    char_start=match.start(),
                    char_end=match.end(),
                ),
                extraction_confidence=0.95,
                negation_marker=False,
                hedge_marker=False,
                polarity_subject="user",
            )
        )
    for match in _GOT_PROPER_ITEM_RE.finditer(content):
        item = match.group(1).strip()
        when = match.group(2).strip()
        if not item:
            continue
        article = "an" if item[:1].casefold() in {"a", "e", "i", "o", "u"} else "a"
        text = f"User got {article} {item} {when}."
        items.append(
            ExtractedItem(
                text=text,
                type_guess="episodic_fact",
                evidence_span=EvidenceSpan(
                    session_id=session_id,
                    turn_idx=turn_idx,
                    char_start=match.start(),
                    char_end=match.end(),
                ),
                extraction_confidence=0.95,
                negation_marker=False,
                hedge_marker=False,
                polarity_subject="user",
            )
        )
    return items


def _turn_to_payload(turn: Any) -> dict[str, Any]:
    if isinstance(turn, Mapping):
        return dict(turn)
    if is_dataclass(turn) and not isinstance(turn, type):
        return asdict(cast(Any, turn))
    payload: dict[str, Any] = {}
    for key in ("turn_id", "session_id", "turn_idx", "role", "content", "timestamp"):
        if hasattr(turn, key):
            payload[key] = getattr(turn, key)
    if not payload:
        raise TypeError(f"unsupported turn object: {type(turn)!r}")
    return payload
