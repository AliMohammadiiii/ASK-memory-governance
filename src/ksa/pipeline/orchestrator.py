"""Controller pipeline orchestration for M3-W10.

The orchestrator is intentionally explicit: extraction, prior lookup, relation
classification, scorecard decision, memory mutation, retrieval, and audit
logging are all separate steps so an `action_log` row can be inspected without
rerunning the model.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
import time
from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ..audit import ActionLogWriter
from ..baselines.base import BaselineAnswer
from ..baselines.embeddings import Embedder, TurnEmbedder
from ..baselines.flat_vector_store import (
    FlatVectorStore,
    RetrievedItem,
)
from ..baselines.flat_vector_store import (
    MemoryItem as RetrievalMemoryItem,
)
from ..classifier import CandidateMemory, PriorMemory, RelationOutput
from ..controller.active import (
    DEFAULT_SCORECARD_CONFIG,
    FeatureSnapshot,
    ScorecardConfig,
    ScorecardDecision,
    c,
    decide,
    e,
    f,
    r,
    rho,
)
from ..controller.computation import (
    ComputedAnswer,
    ComputeIntent,
    RetrievedEvidence,
    _event_phrases,
    _question_item_phrases,
    _question_month,
    _question_relative_window,
    _token_in_text,
    classify_compute_intent,
    compute_answer,
    format_computation_block,
    parse_any_date,
)
from ..controller.temporal import (
    collect_dated_memories,
    format_iso,
    is_temporal_question,
    reference_date,
)
from ..data.longmemeval import LongMemEvalSession, LongMemEvalTurn, memory_session_ids
from ..extraction import EvidenceSpan, ExtractedItem, ExtractionOutput, empty_extraction_output
from ..inference.llm import LLM
from ..memory import (
    ActionLogEntry,
    ControllerAction,
    MemoryStatus,
    MemoryType,
    connect,
    get_lineage,
    init_schema,
    insert_active,
    retrieve_active,
    supersede,
)
from ..memory import (
    MemoryItem as DBMemoryItem,
)

DEFAULT_SYSTEM_PROMPT = (
    "Answer the question using only the retrieved memory and dialog below. "
    "First reason briefly under a 'WORK:' line: quote the relevant retrieved "
    "lines with their dates, enumerate matching items, and do any arithmetic "
    "explicitly, in at most 8 short lines. Then output the answer on its own "
    "final line in exactly this format:\n"
    "FINAL: <answer>\n"
    "The text after 'FINAL:' must be only the requested value, name, date, "
    "number, or short phrase, not a surrounding sentence. If a retrieved line "
    "directly answers the question, copy the complete minimal answer span from "
    "that line instead of paraphrasing or shortening it. Preserve necessary "
    "qualifiers from the evidence, such as 'each way', old or new names, store "
    "names, and full dates. For "
    "where questions, return a place, store, or organization, not a time or "
    "event; for the current location of an object, use the most recent memory "
    "and name the room or place (for example 'in my bedroom'), not only a "
    "position relative to furniture. "
    "For when questions, return the most specific date or time available. "
    "For total, difference, count, date, or order questions, list each "
    "operand with its source line in the WORK section, then compute and return "
    "the final requested value; do not return an "
    "intermediate number unless it is the final answer. "
    "For 'how many' questions, enumerate in the WORK section every distinct "
    "matching item or event across ALL retrieved memories (different names, "
    "places, or dates mean different items), then return the count of that "
    "enumeration. "
    "Prefer the most specific matching memory over a vague one. When the same "
    "fact appears with more than one value, prefer the value from the memory "
    "with the most recent timestamp. "
    "Each retrieved memory line shows its date "
    "in parentheses; for 'which happened first/earliest/latest' or order "
    "questions, compare those dates and name the matching event; for "
    "'what ... before/after' questions, find the dated target memory and name "
    "the matching memory immediately before or after it; for 'how many "
    "days/weeks/months between' questions, find both dated memories and return "
    "the difference. "
    # docx §4 fix 2a: numbers in digits so the answer matches numeric golds and
    # the digit-normalizing judge guard ("4", not "four").
    "When the final answer is a number, count, or amount, write it using digits "
    "(for example '4', not 'four'; '$1,300', not 'one thousand three hundred "
    "dollars'). "
    "Do not convert missing evidence into zero, false, or none. Evidence about "
    "a related but different entity, item type, person, time window, or attribute "
    "does not answer the question. If the requested category is not supported, "
    "answer 'FINAL: Unknown' even when a nearby category is supported. "
    "Do not repeat the question. Answer 'FINAL: Unknown' only "
    "when no retrieved evidence is relevant to the question."
)

# docx §4 fix 1: single-session-preference gold answers are preference PROFILES
# ("The user would prefer ... They may not prefer ..."), not direct answers to
# the surface question. On the 200-239 run this competency went 0/3 because the
# answerer answered the question literally. This template redirects it to emit a
# preference profile grounded in the user's stated interests/constraints. The
# competency label is part of the dataset input, so selecting on it is
# benchmark-legitimate (docx §4 rec 1).
PREFERENCE_SYSTEM_PROMPT = (
    "You are answering a PREFERENCE question about the user. Do NOT answer the "
    "question literally and do NOT give a direct list of suggestions. Instead, "
    "using only the retrieved memory and dialog below, infer and describe the "
    "KIND of response the user would prefer. "
    "First reason briefly under a 'WORK:' line (at most 6 short lines): gather "
    "the user's DURABLE, recurring signals relevant to this question — their "
    "main equipment or brand ecosystem, possessions, ingredients, goals, and "
    "stated likes/dislikes — not only their single most recent purchase or the "
    "latest message. Then output the answer on its own final line in exactly "
    "this format:\n"
    "FINAL: <preference profile>\n"
    "The text after 'FINAL:' must be one or two sentences that begin 'The user "
    "would prefer ...', name the user's key relevant possessions / brands / "
    "ingredients / goals, and frame the preferred suggestions as building on or "
    "being compatible with that broader ecosystem or theme (not just one latest "
    "item). Center the profile on the specific subject the question names (for "
    "example the homegrown ingredients, the photography setup, or the phone) and "
    "make that subject the primary basis of the preference. Then add what they "
    "would NOT prefer ('They may not prefer ...', e.g. off-ecosystem, "
    "incompatible, generic, or low-quality options). Use ONLY names, brands, "
    "products, and specifics that appear verbatim in the retrieved lines — never "
    "invent a name, pet, product, or detail; if the evidence is general, keep "
    "the preference general rather than inventing specifics. Answer 'FINAL: "
    "Unknown' only when no retrieved evidence reveals any relevant preference."
)

# docx §4 fix 3: escalate-on-Unknown instead of re-sending a near-identical
# prompt. The old retry re-ran the same 9B on the same context and returned
# Unknown again (200-239 failures 87f22b4a, 778164c6, where the evidence WAS in
# context). This version forces a committed best guess: it may only abstain when
# the fact is genuinely absent, not when it is merely hard to locate.
ANSWER_RETRY_SYSTEM_PROMPT = (
    DEFAULT_SYSTEM_PROMPT + " IMPORTANT: your previous final answer was 'Unknown' even though "
    "retrieved memory was available. The answer is almost certainly present in "
    "the retrieved lines — re-read every retrieved item and its neighboring "
    "context slowly, and in the WORK section list each candidate evidence line "
    "(with its date) that could bear on the question before deciding. You MUST "
    "commit to your single best-supported answer; partial or approximate "
    "evidence still requires a concrete FINAL answer, not 'Unknown'. Return "
    "'FINAL: Unknown' ONLY if, after this careful re-reading, no retrieved line "
    "mentions the subject of the question at all."
)

# docx §4 fix 4: aggregation scaffold for count/sum questions. The small model
# reliably ENUMERATES matching mentions but mis-adds/mis-counts them over a 30k
# context (200-239 multi-session went 54.5%). We turn counting into structured
# extraction: list each distinct mention as JSON, then dedup + count/sum in code.
AGGREGATION_SCAFFOLD_PROMPT = (
    "You extract a structured list of matching items for a counting/summing "
    "question. Read the retrieved memory lines and the question, then output "
    "ONLY a JSON array (no prose, no code fence). Each element is an object:\n"
    '  {"session": "<session:turn from the [..] tag>", '
    '"value": <number or null>, "item": "<short label of the distinct thing>"}\n'
    "Include one element for EACH distinct matching mention across ALL lines. "
    "The session field MUST copy an exact session:turn tag from the supporting "
    "line; never invent a tag. Exclude lines that merely share generic words but "
    "do not describe the entity, event, or quantity asked about. "
    "Two mentions are the same item only if they refer to the same thing "
    "(same name/place/date); otherwise list them separately. For 'how much/"
    'total\' questions put the amount in "value" (digits only, no currency '
    "symbol); for 'how many' questions \"value\" may be null. If nothing "
    "matches, output [].\n\n"
    # Sentinel placeholders (not str.format fields) because the template above
    # contains literal JSON braces; substitution uses str.replace at the call site.
    "Question: __QUESTION__\n\n"
    "Retrieved memory:\n__MEMORY__\n\n"
    "JSON array:"
)

# Matches the final-answer line of the two-stage (WORK -> FINAL) answer
# contract. Case-insensitive, tolerates 'FINAL ANSWER:', markdown bold
# wrappers, and leading list markers; the LAST match wins so a model that
# repeats the scaffold mid-reasoning still parses correctly.
_FINAL_ANSWER_RE = re.compile(
    r"^[\s*#>\-]*\**\s*FINAL(?:\s+ANSWER)?\s*[:\-]\s*(.+?)\s*\**\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_HISTORICAL_QUERY_RE = re.compile(
    r"\b(?:initially|originally|previously|formerly|earlier|prior|beforehand)\b"
    r"|\bat\s+first\b|\bused\s+to\b|\bbefore\s+(?:it|that|then|the\s+(?:change|update|move))\b",
    re.IGNORECASE,
)
_SUPERSEDED_HISTORY_TAG = "[SUPERSEDED HISTORICAL VERSION]"

# Injected into the answer system prompt ONLY when the historical-query gate
# fired and tagged lineage rows can therefore appear in the context. Keeping it
# out of DEFAULT_SYSTEM_PROMPT means current-state questions never see (or pay
# tokens for) lineage instructions, and the tag string in a prompt is a
# reliable marker that history-aware retrieval actually activated.
HISTORY_LINEAGE_INSTRUCTION = (
    " A line tagged '[SUPERSEDED HISTORICAL VERSION]' is retained "
    "lineage, not current state: use it only when the question explicitly asks "
    "for an initial, original, previous, earlier, or before-change value. For a "
    "current or unqualified question, ignore tagged historical versions and use "
    "the newest active value. Never combine a historical and current value into "
    "one answer. If the question contains a false stale premise, reject the "
    "premise and state only the current value without repeating the stale value."
)


def _requests_historical_memory(question: str) -> bool:
    """Return whether a question explicitly requests a superseded state.

    The gate intentionally excludes bare words such as ``old`` and ``first``:
    "my old sneakers" can ask for their current location, while "which event
    happened first" is ordinary temporal reasoning rather than version recall.
    """
    return bool(_HISTORICAL_QUERY_RE.search(question or ""))


def _extract_final_answer(text: str) -> str:
    """Extract the short answer from a two-stage WORK/FINAL completion.

    Fallbacks, in order, when no FINAL line is present (e.g. the model ignored
    the scaffold or the completion truncated before the final line):
    1. a completion short enough to already be a bare answer is returned as-is;
    2. otherwise the last non-empty line is used (the answer is conventionally
       last), with any trailing punctuation-only wrapper stripped.
    """
    raw = (text or "").strip()
    if not raw:
        return raw
    matches = _FINAL_ANSWER_RE.findall(raw)
    if matches:
        return matches[-1].strip().strip("*").strip()
    if len(raw) <= 100 and "\n" not in raw:
        return raw
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return lines[-1] if lines else raw


_PROMPT_DIR = Path(__file__).resolve().parents[1] / "baselines" / "prompts"

# --- Prompt-budget guard (M4W13 context-saturation fix) --------------------
# Background: on the failed-slice T4 runs some answer prompts filled the entire
# Ollama context window (`prompt_tokens >= num_ctx`), so the model had no room
# to generate and returned a single truncated token (e.g. session 852ce960
# answered "$" instead of "$400,000"). The fix is a *pre-send* budget guard
# that trims retrieved context until the estimated prompt leaves room for the
# answer. It never trims the question or the dialogue turns.
#
# Token estimation here is APPROXIMATE on purpose. Real BPE tokenization of the
# English-plus-JSON memory text runs ~3.5-4 chars/token; we divide by a
# deliberately LOW value so the estimate is an UPPER bound on the true token
# count and the guard errs toward trimming. `_PROMPT_BUDGET_MARGIN_TOKENS`
# absorbs chat-template / role-wrapper overhead the raw string cannot see.
#
# docx §4 fix 7: on the 200-239 run the char-based estimate UNDER-counted by
# ~30% (one answer call reached ~42k actual prompt tokens against a 31,744-token
# budget without being trimmed) because memory JSON is dense in short tokens
# (IDs, numbers, punctuation) that tokenize to more pieces than len/3.3 implies.
# We now (a) prefer a real tokenizer when one is importable, and (b) apply a
# safety multiplier to the char fallback so the estimate stays an upper bound.
_CHARS_PER_TOKEN_ESTIMATE = 3.3
_TOKEN_ESTIMATE_SAFETY = 1.4
_PROMPT_BUDGET_MARGIN_TOKENS = 256
_MIN_RESERVED_OUTPUT_TOKENS = 256
# Raised 512 -> 768 with the two-stage WORK/FINAL answer contract: the model
# now spends tokens on visible reasoning before the FINAL line, and a
# truncation before FINAL loses the answer entirely.
_MAX_RESERVED_OUTPUT_TOKENS = 768
# Never trim below this many of the highest-scoring retrieved items: dropping
# everything would defeat the point of retrieval, and an answer grounded on the
# top few hits is far better than a saturated one-token reply.
_BUDGET_FLOOR_ITEMS = 3
# Approximate per-item template overhead (score/role/date wrapper) in tokens.
_PER_ITEM_OVERHEAD_TOKENS = 16


def _load_token_encoder() -> Any | None:
    """Best-effort real tokenizer for prompt-budget estimation (docx §4 fix 7).

    tiktoken's cl100k_base is a close BPE proxy for the chat models we route to
    and counts dense JSON far more accurately than a char ratio. Optional: if
    tiktoken is not installed the char fallback (with a safety multiplier) is
    used, so this adds no hard dependency to the acceptance run.
    """
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # noqa: BLE001 — any import/lookup failure -> char fallback
        return None


_TOKEN_ENCODER = _load_token_encoder()


def _estimate_prompt_tokens(text: str) -> int:
    """Conservative (upper-bound) token estimate for a rendered prompt string.

    Uses a real BPE tokenizer when available (with a small margin for the
    chat-template wrapper the raw string cannot see); otherwise falls back to a
    char ratio scaled by a safety multiplier so it stays an upper bound.
    """
    if _TOKEN_ENCODER is not None:
        try:
            return int(len(_TOKEN_ENCODER.encode(text)) * 1.05) + 1
        except Exception:  # noqa: BLE001
            pass
    return int(len(text) / _CHARS_PER_TOKEN_ESTIMATE * _TOKEN_ESTIMATE_SAFETY) + 1


@dataclass(frozen=True)
class MemoryProvenance:
    session_id: str
    turn_idx: int
    timestamp: str | None
    candidate_id: int


@dataclass(frozen=True)
class PipelineDecision:
    candidate_id: int
    session_id: str
    turn_idx: int
    candidate_text: str
    candidate_type: str
    action: ControllerAction
    prior_memory_id: int | None
    resulting_memory_id: int | None
    rationale: str
    relation: str | None = None
    s_rev: float | None = None
    s_abs: float | None = None


@dataclass(frozen=True)
class PipelineRunSummary:
    decisions: list[PipelineDecision]
    action_counts: dict[str, int]
    retrieved_session_ids: list[str]
    leakage_count: int
    action_log_path: str | None
    memory_item_count: int


@dataclass(frozen=True)
class CandidateContext:
    candidate_id: int
    item: ExtractedItem
    session_id: str
    turn_idx: int
    turn_id: str
    timestamp: str | None
    source_turn: str


def build_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_PROMPT_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )


def turn_payload(
    session: LongMemEvalSession,
    turn: LongMemEvalTurn,
    turn_idx: int,
) -> dict[str, Any]:
    return {
        "turn_id": f"{session.session_id}:{turn_idx}",
        "session_id": session.session_id,
        "turn_idx": turn_idx,
        "role": turn.role,
        "content": turn.content,
        "timestamp": turn.timestamp,
    }


def relation_label(output: RelationOutput | None) -> str | None:
    if output is None:
        return None
    return str(output.relation_to_prior_state)


def classify_relation(
    classifier: Any,
    candidate: CandidateContext,
    prior: DBMemoryItem,
    prior_provenance: MemoryProvenance | None,
    *,
    max_new_tokens: int,
    temperature: float,
    seed: int,
) -> RelationOutput:
    return classifier.classify(
        CandidateMemory(
            text=candidate.item.text,
            type_guess=candidate.item.type_guess,
            source_turn=candidate.source_turn,
            session_id=candidate.session_id,
            turn_id=candidate.turn_id,
            timestamp=candidate.timestamp,
        ),
        PriorMemory(
            text=prior.text,
            type=prior.type.value,
            memory_id=str(prior.id) if prior.id is not None else None,
            timestamp=prior_provenance.timestamp if prior_provenance is not None else None,
        ),
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        seed=seed,
    )


def feature_snapshot(
    candidate: CandidateContext,
    prior_payload: Mapping[str, Any] | None,
    relation: RelationOutput | None,
) -> FeatureSnapshot:
    candidate_payload = candidate.item.model_dump()
    candidate_payload["timestamp"] = candidate.timestamp
    candidate_payload["source_turn"] = candidate.source_turn
    if relation is not None:
        candidate_payload["relation_output"] = relation
    return FeatureSnapshot(
        c=c(candidate_payload),
        e=e(candidate_payload, prior_payload or {}),
        f=f(candidate_payload),
        r=_controller_relation_signal(candidate_payload, prior_payload or {}, relation),
        rho=rho(candidate.item.type_guess),
    )


def _controller_relation_signal(
    candidate_payload: Mapping[str, Any],
    prior: Mapping[str, Any],
    relation: RelationOutput | None,
) -> float:
    if relation is None:
        # No prior means there is no same-slot contradiction to resolve.
        return 1.0
    if relation.relation_to_prior_state == "unclear" and relation.logical_relation == "independent":
        # Independent memories of the same type are safe to keep/admit; they
        # are not ambiguous revisions of the compared prior.
        return 1.0
    return r(candidate_payload, prior)


def prior_payload(prior: DBMemoryItem, provenance: MemoryProvenance | None) -> dict[str, Any]:
    return {
        "text": prior.text,
        "type": prior.type.value,
        "memory_id": prior.id,
        "timestamp": provenance.timestamp if provenance is not None else None,
    }


@dataclass
class ControllerOrchestrator:
    """End-to-end controller baseline with lineage-preserving supersession."""

    llm: LLM
    extractor: Any
    classifier: Any
    corpus: Mapping[str, LongMemEvalSession] = field(default_factory=dict)
    embedder: Embedder | None = None
    config: ScorecardConfig = field(default_factory=lambda: DEFAULT_SCORECARD_CONFIG)
    k: int = 5
    seed: int = 0
    # 512 -> 768 with the WORK/FINAL contract (see _MAX_RESERVED_OUTPUT_TOKENS).
    max_new_tokens: int = 768
    extraction_max_new_tokens: int = 512
    relation_max_new_tokens: int = 128
    action_log_path: Path | None = None
    append_action_log: bool = False
    extraction_cache_path: Path | None = None
    relation_cache_path: Path | None = None
    prompt_template: str = "controller_cot.j2"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    progress: bool = False
    memory_prefilter_top_k: int | None = None
    raw_turn_fallback: bool = False
    retrieval_neighbor_window: int = 0
    include_assistant_context: bool = False
    include_raw_user_context: bool = False
    answer_retry_on_unknown: bool = False
    prior_top_k: int = 1
    prior_similarity_threshold: float = 0.0
    temporal_scaffold: bool = False
    computation_answerer: bool = False
    retrieval_query_augmentation: bool = False
    deterministic_numeric_supersede: bool = False
    # --- relation-classifier cascade (4B fast path -> 9B escalation) --------
    # When `classifier_escalation` is set, the primary (small/fast) classifier
    # runs first; decision-critical or uncertain items are re-classified by the
    # larger model. This spends the big model only where Supersede/Abstain are
    # actually at stake. See _should_escalate.
    classifier_escalation: Any = None
    escalation_extraction_confidence: float = 0.75
    escalation_marker_burden: float = 0.35
    escalation_relations: tuple[str, ...] = ("contradict", "supersede", "unclear")

    # --- docx v7 fixes (all opt-in; defaults keep prior behavior byte-stable) ---
    # §4 fix 1: emit a preference PROFILE for single-session-preference questions.
    per_competency_answer_prompt: bool = False
    # §4 fix 3: optional stronger model for the escalate-on-Unknown retry pass.
    answer_escalation_llm: Any = None
    # §4 fix 5: don't blindly trust a deterministic computation bypass — also run
    # the LLM answer and reconcile; and gate the bypass on a confidence floor.
    verify_computation_bypass: bool = False
    computation_bypass_min_confidence: float = 0.0
    # §4 fix 6: rebuild an enumerated assistant list verbatim before indexing the
    # Nth item (the list is split across retrieval chunks otherwise).
    ordinal_list_reconstruction: bool = False
    # §4 fix 4: for count/sum questions with no confident deterministic answer,
    # ask the model to LIST matching mentions as JSON, then dedup + count/sum in
    # code (arithmetic the 9B gets wrong), feeding the result to the answerer.
    aggregation_scaffold: bool = False
    # §5 fix 1: extract a session's turns concurrently (independent per turn); the
    # ordered Keep/Supersede/Abstain decisions still run sequentially afterward.
    extraction_concurrency: int = 1
    # Publication runs must fail/retry a session when extraction is unavailable
    # or unrecoverably unparseable; otherwise outages become silent missing data.
    fail_on_extraction_error: bool = False
    # §5 fix 3: a content-keyed cache shared across runs/ranges/systems, read at
    # startup in addition to the per-run cache (writes stay per-run, merged later).
    shared_extraction_cache_path: Path | None = None
    # §5 fix 4: cap + rerank the answer context (smaller, cleaner context helps
    # the 9B). 0 disables the extra cap (the num_ctx budget guard still applies).
    answer_context_max_tokens: int = 0
    answer_context_rerank: bool = False
    # Query-gated lineage retrieval. Superseded rows are surfaced only for
    # explicit historical-state questions and are visibly tagged in the prompt.
    # This remains off by default so current-state/MGP-6 behavior is unchanged.
    history_aware_retrieval: bool = False
    history_retrieval_k: int = 4
    # During prompt-budget trimming, reserve early capacity for evidence from
    # distinct sessions before admitting additional chunks from the same one.
    # Zero disables the diversity pass and preserves the v7 ordering.
    answer_context_session_cap: int = 0
    # §5 fix 6: chunk user turns before the extraction prefilter embeds them, so
    # a long turn's tail is not lost to the embedder's 256-token truncation.
    prefilter_chunk_turns: bool = False

    BASELINE_NAME: str = "controller"

    def __post_init__(self) -> None:
        self.embedder = self.embedder or TurnEmbedder(device="cpu")
        self._env = build_jinja_env()
        self._template = self._env.get_template(self.prompt_template)
        self._action_log_started = self.append_action_log
        self._next_log_id = _next_jsonl_id(self.action_log_path) if self.append_action_log else 1
        self._next_candidate_id = 1
        self._last_summary: PipelineRunSummary | None = None
        # Guards the extraction cache dict/counters/file when turns are extracted
        # concurrently (§5 fix 1). A no-op cost when extraction_concurrency == 1.
        self._extraction_lock = threading.Lock()
        if self.action_log_path is not None:
            parent = self.action_log_path.parent
            self.extraction_cache_path = (
                self.extraction_cache_path or parent / "extraction_cache.jsonl"
            )
            self.relation_cache_path = self.relation_cache_path or parent / "relation_cache.jsonl"
        self._extraction_prompt_fingerprint = _fingerprint(
            getattr(self.extractor, "prompt_template", type(self.extractor).__qualname__)
        )
        self._extraction_model_id = _component_model_id(self.extractor)
        self._relation_prompt_fingerprint = _fingerprint(
            "|".join(
                [
                    str(getattr(self.classifier, "stage1_template", "")),
                    str(getattr(self.classifier, "stage2_template", "")),
                    type(self.classifier).__qualname__,
                ]
            )
        )
        self._relation_model_id = _component_model_id(self.classifier)
        self._escalation_model_id = (
            _component_model_id(self.classifier_escalation)
            if self.classifier_escalation is not None
            else None
        )
        if (
            self.classifier_escalation is not None
            and self._escalation_model_id
            and self._escalation_model_id == self._relation_model_id
        ):
            # Repeating the same deterministic model cannot add capacity and
            # doubled most v7 relation calls. Preserve the primary result.
            self.classifier_escalation = None
            self._escalation_model_id = None
        self._relation_escalations = 0
        self._relation_escalation_eligible = 0
        self._extraction_uncached_failures = 0
        self._last_history_query_detected = False
        self._last_history_candidate_count = 0
        self._last_history_retrieved_count = 0
        self._extraction_cache: dict[str, ExtractionOutput] = {}
        self._relation_cache: dict[str, RelationOutput] = {}
        self._extraction_cache_hits = 0
        self._extraction_cache_misses = 0
        self._relation_cache_hits = 0
        self._relation_cache_misses = 0
        self._load_persistent_caches()

    @property
    def last_summary(self) -> PipelineRunSummary | None:
        return self._last_summary

    def answer(self, session: LongMemEvalSession) -> BaselineAnswer:
        conn = connect(":memory:")
        init_schema(conn)
        provenance: dict[int, MemoryProvenance] = {}
        decisions: list[PipelineDecision] = []
        log_cm = self._open_log()
        t0 = time.perf_counter()
        cache_hits_before = self._extraction_cache_hits
        cache_misses_before = self._extraction_cache_misses
        uncached_failures_before = self._extraction_uncached_failures
        relation_cache_hits_before = self._relation_cache_hits
        relation_cache_misses_before = self._relation_cache_misses
        try:
            if log_cm is not None:
                log_cm.__enter__()

            # Build prior memory from the allowed memory corpus. The current
            # session is not ingested before retrieval, which is the
            # anti-leakage invariant measured below.
            memory_ids = memory_session_ids(session)
            unresolved_memory_ids = [sid for sid in memory_ids if sid not in self.corpus]
            supporting_sessions = self._supporting_sessions_from_ids(memory_ids)
            prefilter_turns = self._prefilter_memory_turns(session, supporting_sessions)
            prefilter_selected = (
                sum(len(turns) for turns in prefilter_turns.values())
                if prefilter_turns is not None
                else None
            )
            prefilter_total = (
                sum(
                    1
                    for support in supporting_sessions
                    for turn in support.turns
                    if turn.role == "user"
                )
                if prefilter_turns is not None
                else None
            )
            self._log_progress(
                f"{session.session_id}: start; memory_sessions={len(memory_ids)} "
                f"resolved={len(supporting_sessions)} unresolved={len(unresolved_memory_ids)}"
            )
            if prefilter_turns is not None:
                self._log_progress(
                    f"{session.session_id}: memory_prefilter selected="
                    f"{prefilter_selected}/{prefilter_total} user_turns"
                )

            for support_i, support in enumerate(supporting_sessions, start=1):
                selected_for_session = (
                    prefilter_turns.get(support.session_id, set())
                    if prefilter_turns is not None
                    else None
                )
                if prefilter_turns is not None and not selected_for_session:
                    continue
                self._log_progress(
                    f"{session.session_id}: ingest memory_session "
                    f"{support_i}/{len(supporting_sessions)} {support.session_id} "
                    f"turns={len(support.turns)}"
                )
                self._process_session(
                    conn,
                    support,
                    provenance,
                    decisions,
                    log_cm,
                    progress_label=f"{session.session_id}: memory {support_i}/{len(supporting_sessions)}",
                    allowed_user_turn_idxs=selected_for_session,
                )

            self._log_progress(f"{session.session_id}: retrieve and answer")
            retrieved = self._retrieve(conn, provenance, session)
            computed = self._compute_answer(session, retrieved)
            # §4 fix 5: gate the deterministic bypass on a confidence floor, and
            # in verify mode do NOT bypass the LLM — run it and reconcile below.
            computation_bypass_eligible = bool(
                computed
                and computed.safe_to_bypass_llm
                and float(computed.confidence) >= float(self.computation_bypass_min_confidence)
            )
            verify_bypass = computation_bypass_eligible and self.verify_computation_bypass
            computation_bypass_used = (
                computation_bypass_eligible and not self.verify_computation_bypass
            )
            computation_verify_disagreed = False
            # §4 fix 1: preference questions need a preference-profile answer.
            effective_system_prompt = self._effective_system_prompt(session)
            # Lineage instructions only when the historical gate fired (set in
            # _retrieve above); current-state prompts stay lineage-free.
            if self._last_history_query_detected:
                effective_system_prompt = effective_system_prompt + HISTORY_LINEAGE_INSTRUCTION

            # Prompt-budget guard: keep the answer prompt strictly under the
            # answerer's context window so the model always has room to
            # generate (see _budget_trim_for_answer). The deterministic bypass
            # never calls the LLM, so its prompt is left untrimmed and is only
            # used for token accounting.
            num_ctx, reserved_output_tokens, prompt_budget_tokens = self._answer_token_budget()
            # §5 fix 4: optionally cap the answer context below num_ctx so the
            # small model sees a tighter, reranked context.
            if self.answer_context_max_tokens and self.answer_context_max_tokens > 0:
                prompt_budget_tokens = (
                    min(prompt_budget_tokens, self.answer_context_max_tokens)
                    if prompt_budget_tokens > 0
                    else self.answer_context_max_tokens
                )
            if computation_bypass_used:
                answer_retrieved = retrieved
                budget_debug: dict[str, Any] = {
                    "prompt_trimmed": False,
                    "memory_items_before_trim": len(retrieved),
                    "memory_items_after_trim": len(retrieved),
                    "estimated_prompt_tokens": None,
                    "estimated_prompt_tokens_before_trim": None,
                }
            else:
                # §5 fix 4: rerank retrieved by score (question-similarity) so
                # the highest-signal items survive the cap.
                trim_input = (
                    self._rerank_for_answer(retrieved) if self.answer_context_rerank else retrieved
                )
                answer_retrieved, budget_debug = self._budget_trim_for_answer(
                    session, trim_input, computed, prompt_budget_tokens
                )
                # Run the model-assisted enumerator only on the evidence that
                # will actually fit in the answer prompt. The v7 path ran it on
                # the much larger pre-trim pool, which amplified distractors and
                # could exceed the answerer's intended context budget.
                if computed is None and self.computation_answerer and self.aggregation_scaffold:
                    computed = self._aggregation_scaffold(session, answer_retrieved)
                    if computed is not None:
                        first_trim_debug = budget_debug
                        answer_retrieved, scaffold_trim_debug = self._budget_trim_for_answer(
                            session,
                            answer_retrieved,
                            computed,
                            prompt_budget_tokens,
                        )
                        scaffold_trim_debug["memory_items_before_trim"] = first_trim_debug[
                            "memory_items_before_trim"
                        ]
                        scaffold_trim_debug["estimated_prompt_tokens_before_trim"] = (
                            first_trim_debug["estimated_prompt_tokens_before_trim"]
                        )
                        scaffold_trim_debug["prompt_trimmed"] = bool(
                            first_trim_debug["prompt_trimmed"]
                            or scaffold_trim_debug["prompt_trimmed"]
                        )
                        budget_debug = scaffold_trim_debug
                if budget_debug["prompt_trimmed"]:
                    self._log_progress(
                        f"{session.session_id}: prompt-budget trim "
                        f"{budget_debug['memory_items_before_trim']}->"
                        f"{budget_debug['memory_items_after_trim']} items; "
                        f"est_tokens {budget_debug['estimated_prompt_tokens_before_trim']}->"
                        f"{budget_debug['estimated_prompt_tokens']} "
                        f"(num_ctx={num_ctx} reserved_out={reserved_output_tokens} "
                        f"budget={prompt_budget_tokens}; token estimate is approximate)"
                    )

            prompt = self._render_prompt(
                session,
                answer_retrieved,
                system_prompt=effective_system_prompt,
                computed_answer=computed,
            )
            answer_retry_used = False
            answer_retry_original_text: str | None = None
            final_prompt = prompt
            answer_llm_calls: list[dict[str, Any]] = []
            if computation_bypass_used and computed is not None:
                answer_text = computed.answer
                answer_raw_text = answer_text
                prompt_tokens = max(1, len(prompt.split()))
                completion_tokens = max(1, len(answer_text.split()))
                generation_latency_ms = 0.0
                model_id = "deterministic/computation-aware"
            else:
                resp = self.llm.generate(
                    prompt,
                    max_new_tokens=self.max_new_tokens,
                    temperature=0.0,
                    seed=self.seed,
                )
                answer_raw_text = resp.text.strip()
                answer_text = _extract_final_answer(answer_raw_text)
                prompt_tokens = resp.prompt_tokens
                completion_tokens = resp.completion_tokens
                generation_latency_ms = resp.latency_ms
                model_id = resp.model_id
                answer_llm_calls.append(dict(resp.metadata))
                # §4 fix 5: reconcile a verify-mode deterministic result with the
                # LLM's answer. On agreement, emit the canonical deterministic
                # form; on disagreement, keep the LLM answer (the deterministic
                # subset selection was likely wrong, e.g. 85fa3a3f: $120 vs $50).
                if verify_bypass and computed is not None:
                    if _answers_equivalent(answer_text, computed.answer):
                        answer_text = computed.answer
                        model_id = f"{model_id}+computation-verified"
                    else:
                        computation_verify_disagreed = True
                        model_id = f"{model_id}+computation-override"
                # Retry on an exact 'Unknown', an empty answer, OR a degenerate
                # bare-symbol answer like '$' (all signal a non-answer; the last
                # is the silent-truncation case from session 852ce960 that the
                # original 'Unknown'-only trigger missed). The retry re-renders
                # the already budget-trimmed context, so it does not re-saturate
                # the window. The trigger checks the PARSED final answer, not
                # the raw completion, so WORK-section text never masks an
                # 'Unknown' final line. §4 fix 3: the retry uses a commit-forcing
                # system prompt and, when configured, a stronger escalation model.
                needs_retry = _answer_needs_retry(answer_text)
                if self.answer_retry_on_unknown and needs_retry and answer_retrieved:
                    answer_retry_used = True
                    answer_retry_original_text = answer_raw_text
                    retry_llm = self.answer_escalation_llm or self.llm
                    retry_system_prompt = ANSWER_RETRY_SYSTEM_PROMPT
                    if self._last_history_query_detected:
                        retry_system_prompt = retry_system_prompt + HISTORY_LINEAGE_INSTRUCTION
                    final_prompt = self._render_prompt(
                        session,
                        answer_retrieved,
                        system_prompt=retry_system_prompt,
                        computed_answer=computed,
                    )
                    retry_resp = retry_llm.generate(
                        final_prompt,
                        max_new_tokens=self.max_new_tokens,
                        temperature=0.0,
                        seed=self.seed,
                    )
                    prompt_tokens += retry_resp.prompt_tokens
                    completion_tokens += retry_resp.completion_tokens
                    generation_latency_ms += retry_resp.latency_ms
                    answer_raw_text = retry_resp.text.strip()
                    answer_text = _extract_final_answer(answer_raw_text)
                    model_id = retry_resp.model_id
                    answer_llm_calls.append(dict(retry_resp.metadata))

            # Flag the silent-truncation failure mode for downstream analysis:
            # a one-token (or empty) answer whose prompt nearly filled num_ctx
            # means the window saturated and there was no room to answer. With
            # the budget guard above this should no longer occur, so a True here
            # is a signal that num_ctx is genuinely too small for the question.
            answer_saturated = bool(
                num_ctx is not None
                and not computation_bypass_used
                and completion_tokens <= 1
                and prompt_tokens >= int(num_ctx) - reserved_output_tokens
            )
            answer_looks_truncated = bool(
                answer_saturated
                or (not computation_bypass_used and answer_text == "")
                or (not computation_bypass_used and _looks_degenerate_answer(answer_text))
            )
            self._log_progress(
                f"{session.session_id}: prompt_budget "
                f"est_tokens={budget_debug.get('estimated_prompt_tokens')} "
                f"num_ctx={num_ctx} reserved_out={reserved_output_tokens} "
                f"budget={prompt_budget_tokens} "
                f"items {budget_debug.get('memory_items_before_trim')}->"
                f"{budget_debug.get('memory_items_after_trim')} "
                f"trimmed={budget_debug.get('prompt_trimmed')} "
                f"assistant_ctx={self.include_assistant_context} "
                f"neighbor_window={self.retrieval_neighbor_window} "
                f"answer_len={len(answer_text)} truncated={answer_looks_truncated} "
                f"retry={answer_retry_used} (token estimate approximate)"
            )

            # After answer construction, process the current session so the
            # controller smoke log includes the current update decisions while
            # the answer prompt stays leakage-free.
            self._log_progress(
                f"{session.session_id}: update current session turns={len(session.turns)}"
            )
            self._process_session(
                conn,
                session,
                provenance,
                decisions,
                log_cm,
                progress_label=f"{session.session_id}: current",
            )

            action_counts = _action_counts(decisions)
            retrieved_session_ids = [r.item.session_id for r in retrieved]
            answer_context_session_ids = [r.item.session_id for r in answer_retrieved]
            answer_context_item_refs = [
                {
                    "session_id": r.item.session_id,
                    "turn_idx": r.item.turn_idx,
                    "role": r.item.role,
                    "text_sha256": _fingerprint(r.item.text),
                }
                for r in answer_retrieved
            ]
            supporting_id_set = set(session.supporting_session_ids)
            retrieved_supporting = supporting_id_set & set(retrieved_session_ids)
            answer_context_supporting = supporting_id_set & set(answer_context_session_ids)
            support_denominator = len(supporting_id_set)
            leakage_count = sum(1 for sid in retrieved_session_ids if sid == session.session_id)
            cache_hits = self._extraction_cache_hits - cache_hits_before
            cache_misses = self._extraction_cache_misses - cache_misses_before
            uncached_failures = self._extraction_uncached_failures - uncached_failures_before
            relation_cache_hits = self._relation_cache_hits - relation_cache_hits_before
            relation_cache_misses = self._relation_cache_misses - relation_cache_misses_before
            self._log_progress(
                f"{session.session_id}: done; retrieved={len(retrieved)} "
                f"leakage={leakage_count} extraction_cache="
                f"{cache_hits}/{cache_hits + cache_misses} hits relation_cache="
                f"{relation_cache_hits}/{relation_cache_hits + relation_cache_misses} "
                f"hits actions={action_counts}"
            )
            self._last_summary = PipelineRunSummary(
                decisions=list(decisions),
                action_counts=action_counts,
                retrieved_session_ids=retrieved_session_ids,
                leakage_count=leakage_count,
                action_log_path=str(self.action_log_path) if self.action_log_path else None,
                memory_item_count=len(retrieve_active(conn)),
            )

            return BaselineAnswer(
                session_id=session.session_id,
                text=answer_text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=generation_latency_ms + (time.perf_counter() - t0) * 1000.0,
                raw_prompt=final_prompt,
                seed=self.seed,
                model_id=model_id,
                baseline=self.BASELINE_NAME,
                extras={
                    "k": self.k,
                    "n_retrieved": len(retrieved),
                    "n_answer_context": len(answer_retrieved),
                    "smrr_status": "not_computed_longmemeval_lacks_gold_supersession",
                    "stale_retrieval_count": 0,
                    "smrr_denominator": 0,
                    "retrieval_session_ids": retrieved_session_ids,
                    # Explicit pre/post-trim telemetry. Historical v7 reports
                    # treated the legacy retrieval_session_ids field as prompt
                    # coverage even though it is measured before budget trim;
                    # use answer_context_* for the evidence actually shown.
                    "retrieval_session_ids_before_trim": retrieved_session_ids,
                    "answer_context_session_ids": answer_context_session_ids,
                    "answer_context_item_refs": answer_context_item_refs,
                    "retrieval_supporting_sessions_before_trim": sorted(retrieved_supporting),
                    "answer_context_supporting_sessions": sorted(answer_context_supporting),
                    "retrieval_support_coverage_before_trim": (
                        None
                        if support_denominator == 0
                        else len(retrieved_supporting) / support_denominator
                    ),
                    "answer_context_support_coverage": (
                        None
                        if support_denominator == 0
                        else len(answer_context_supporting) / support_denominator
                    ),
                    "retrieval_turn_idxs": [r.item.turn_idx for r in retrieved],
                    "current_session_leakage_count": leakage_count,
                    "action_counts": action_counts,
                    "action_log_path": str(self.action_log_path) if self.action_log_path else None,
                    "memory_session_ids": list(memory_ids),
                    "unresolved_memory_ids": unresolved_memory_ids,
                    "supporting_session_ids": list(session.supporting_session_ids),
                    "extraction_cache_hits": cache_hits,
                    "extraction_cache_misses": cache_misses,
                    "extraction_cache_size": len(self._extraction_cache),
                    "extraction_uncached_failures": uncached_failures,
                    "relation_cache_hits": relation_cache_hits,
                    "relation_cache_misses": relation_cache_misses,
                    "relation_cache_size": len(self._relation_cache),
                    "relation_model_id": self._relation_model_id,
                    "relation_escalation_model_id": self._escalation_model_id,
                    "relation_escalations": self._relation_escalations,
                    "relation_escalation_eligible": self._relation_escalation_eligible,
                    "memory_prefilter_top_k": self.memory_prefilter_top_k,
                    "memory_prefilter_selected_turns": prefilter_selected,
                    "memory_prefilter_total_user_turns": prefilter_total,
                    "answer_retry_used": answer_retry_used,
                    "answer_retry_original_text": answer_retry_original_text,
                    "answer_raw_text": answer_raw_text,
                    "answer_final_line_parsed": answer_raw_text != answer_text,
                    "answer_llm_calls": answer_llm_calls,
                    "controller_prior_top_k": self.prior_top_k,
                    "question_date": session.question_date,
                    "computation_answerer": self.computation_answerer,
                    "computation_intent": computed.intent.value if computed else None,
                    "computation_answer": computed.answer if computed else None,
                    "computation_confidence": computed.confidence if computed else None,
                    "computation_safe_to_bypass": (
                        computed.safe_to_bypass_llm if computed else False
                    ),
                    "computation_bypass_used": computation_bypass_used,
                    "computation_bypass_eligible": computation_bypass_eligible,
                    "computation_bypass_verified": verify_bypass,
                    "computation_verify_disagreed": computation_verify_disagreed,
                    "answer_system_prompt_variant": (
                        "preference"
                        if effective_system_prompt is PREFERENCE_SYSTEM_PROMPT
                        else "default"
                    ),
                    # --- prompt-budget guard (M4W13) ---
                    "question": session.question,
                    "prompt_num_ctx": num_ctx,
                    "prompt_reserved_output_tokens": reserved_output_tokens,
                    "prompt_generation_budget_tokens": prompt_budget_tokens,
                    "prompt_estimated_tokens": budget_debug.get("estimated_prompt_tokens"),
                    "prompt_estimated_tokens_before_trim": budget_debug.get(
                        "estimated_prompt_tokens_before_trim"
                    ),
                    "prompt_token_estimate_is_approximate": True,
                    "prompt_memory_items_before_trim": budget_debug.get("memory_items_before_trim"),
                    "prompt_memory_items_after_trim": budget_debug.get("memory_items_after_trim"),
                    "prompt_trimmed": bool(budget_debug.get("prompt_trimmed", False)),
                    "prompt_assistant_context_included": self.include_assistant_context,
                    "prompt_neighbor_window": self.retrieval_neighbor_window,
                    "prompt_session_diversity_cap": self.answer_context_session_cap,
                    "history_query_detected": self._last_history_query_detected,
                    "history_candidate_count": self._last_history_candidate_count,
                    "history_retrieved_count": self._last_history_retrieved_count,
                    "answer_text_length": len(answer_text),
                    "answer_looks_truncated": answer_looks_truncated,
                    "prompt_artifact": "raw_prompt (inline in this record)",
                },
            )
        finally:
            if log_cm is not None:
                log_cm.__exit__(None, None, None)
            conn.close()

    def _open_log(self) -> ActionLogWriter | None:
        if self.action_log_path is None:
            return None
        mode = "w" if not self._action_log_started else "a"
        self._action_log_started = True
        return ActionLogWriter(self.action_log_path, baseline=self.BASELINE_NAME, mode=mode)

    def _supporting_sessions(self, session: LongMemEvalSession) -> list[LongMemEvalSession]:
        return self._supporting_sessions_from_ids(memory_session_ids(session))

    def _supporting_sessions_from_ids(
        self,
        memory_ids: Iterable[str],
    ) -> list[LongMemEvalSession]:
        out: list[LongMemEvalSession] = []
        seen: set[str] = set()
        for sid in memory_ids:
            if sid in seen:
                continue
            support = self.corpus.get(sid)
            if support is not None:
                out.append(support)
                seen.add(sid)
        return out

    def _prefilter_memory_turns(
        self,
        query_session: LongMemEvalSession,
        supporting_sessions: list[LongMemEvalSession],
    ) -> dict[str, set[int]] | None:
        """Return top-k memory user turns to send through LLM extraction.

        Full controller ingestion extracts every user turn in every haystack
        session. That is the exact path, but it is too slow for Colab/T4 HF
        sanity runs because one question can require hundreds of generation
        calls. This optional prefilter keeps the corrected haystack corpus
        boundary while using cheap dense retrieval to choose the most relevant
        user turns before expensive extraction/classification.
        """
        if self.memory_prefilter_top_k is None or self.memory_prefilter_top_k <= 0:
            return None

        items: list[RetrievalMemoryItem] = []
        for support in supporting_sessions:
            for idx, turn in enumerate(support.turns):
                if turn.role != "user":
                    continue
                # §5 fix 6: the embed server truncates at max_seq_length (256),
                # so a long user turn embedded whole loses its tail and can be
                # under-ranked here. When prefilter_chunk_turns is on, embed
                # sentence/line chunks (each tagged with the same turn_idx) so a
                # fact anywhere in the turn can rank; default embeds the whole
                # turn (byte-stable with prior runs).
                chunks = _chunk_text(turn.content) if self.prefilter_chunk_turns else [turn.content]
                for chunk in chunks:
                    items.append(
                        RetrievalMemoryItem(
                            text=chunk,
                            role=turn.role,
                            session_id=support.session_id,
                            turn_idx=idx,
                            timestamp=turn.timestamp,
                        )
                    )
        if not items:
            return {}

        store = FlatVectorStore(embedder=self.embedder or TurnEmbedder(device="cpu"))
        store.add(items)
        query_text = query_session.question
        if not query_text.strip() and query_session.turns:
            query_text = "\n".join(
                turn.content for turn in query_session.turns if turn.role == "user"
            )
        # When chunking, multiple chunks of one turn may rank; retrieve a larger
        # candidate pool and collapse to unique (session, turn) until we have
        # memory_prefilter_top_k distinct turns.
        search_k = (
            self.memory_prefilter_top_k * 4
            if self.prefilter_chunk_turns
            else self.memory_prefilter_top_k
        )
        retrieved = store.search(query_text, search_k)
        selected: dict[str, set[int]] = {}
        n_unique = 0
        for hit in retrieved:
            turns_for_session = selected.setdefault(hit.item.session_id, set())
            if hit.item.turn_idx not in turns_for_session:
                if self.prefilter_chunk_turns and n_unique >= self.memory_prefilter_top_k:
                    continue
                turns_for_session.add(hit.item.turn_idx)
                n_unique += 1
        return selected

    def _log_progress(self, message: str) -> None:
        if not self.progress:
            return
        print(f"[{self.BASELINE_NAME}] {message}", flush=True)

    def _load_persistent_caches(self) -> None:
        # §5 fix 3: read a content-keyed cache shared across runs/ranges/systems
        # first, then the per-run cache (identical keys resolve to identical
        # outputs, so precedence is immaterial). Extraction keys already include
        # the model id + prompt fingerprint, so sharing across systems is safe.
        self._load_extraction_cache_file(self.shared_extraction_cache_path)
        self._load_extraction_cache_file(self.extraction_cache_path)
        self._load_relation_cache_file(self.relation_cache_path)
        if self.action_log_path is not None:
            parent = self.action_log_path.parent
            self._load_extraction_trace_file(parent / "extraction_trace.jsonl")
            self._load_relation_trace_file(parent / "relation_trace.jsonl")
        if self.progress and (self._extraction_cache or self._relation_cache):
            self._log_progress(
                "loaded persistent caches: "
                f"extraction={len(self._extraction_cache)} "
                f"relation={len(self._relation_cache)}"
            )

    def _load_extraction_cache_file(self, path: Path | None) -> None:
        if path is None or not path.exists():
            return
        for row in _iter_jsonl(path):
            key = row.get("key")
            output = row.get("output")
            if not isinstance(key, str) or not isinstance(output, Mapping):
                continue
            try:
                self._extraction_cache[key] = ExtractionOutput.model_validate(output)
            except Exception:
                continue

    def _load_relation_cache_file(self, path: Path | None) -> None:
        if path is None or not path.exists():
            return
        for row in _iter_jsonl(path):
            key = row.get("key")
            output = row.get("output")
            if not isinstance(key, str) or not isinstance(output, Mapping):
                continue
            try:
                self._relation_cache[key] = RelationOutput.model_validate(output)
            except Exception:
                continue

    def _load_extraction_trace_file(self, path: Path) -> None:
        if not path.exists():
            return
        for row in _iter_jsonl(path):
            output = row.get("validated_output")
            prompt = row.get("prompt")
            if not isinstance(output, Mapping) or not isinstance(prompt, str):
                continue
            model_id = _trace_model_id(row.get("responses"))
            if model_id is not None and model_id != self._extraction_model_id:
                continue
            turn = _current_turn_from_extraction_prompt(prompt)
            if turn is None:
                continue
            try:
                self._extraction_cache[self._extraction_key(turn)] = (
                    ExtractionOutput.model_validate(output)
                )
            except Exception:
                continue

    def _load_relation_trace_file(self, path: Path) -> None:
        if not path.exists():
            return
        for row in _iter_jsonl(path):
            candidate = row.get("candidate")
            prior = row.get("prior")
            output = row.get("output")
            if (
                not isinstance(candidate, Mapping)
                or not isinstance(prior, Mapping)
                or not isinstance(output, Mapping)
            ):
                continue
            model_id = _trace_model_id(row.get("stage1_responses")) or _trace_model_id(
                row.get("stage2_responses")
            )
            if model_id is not None and model_id != self._relation_model_id:
                continue
            try:
                self._relation_cache[
                    self._relation_key_from_parts(
                        candidate_text=str(candidate.get("text") or ""),
                        candidate_type=str(candidate.get("type_guess") or ""),
                        candidate_source_turn=str(candidate.get("source_turn") or ""),
                        candidate_timestamp=candidate.get("timestamp"),
                        prior_text=str(prior.get("text") or ""),
                        prior_type=str(prior.get("type") or ""),
                        prior_timestamp=prior.get("timestamp"),
                    )
                ] = RelationOutput.model_validate(output)
            except Exception:
                continue

    def _process_session(
        self,
        conn: sqlite3.Connection,
        session: LongMemEvalSession,
        provenance: dict[int, MemoryProvenance],
        decisions: list[PipelineDecision],
        log_writer: ActionLogWriter | None,
        progress_label: str | None = None,
        allowed_user_turn_idxs: set[int] | None = None,
    ) -> None:
        turns = list(session.turns)
        # Collect the eligible user turns (in order) so extraction and the
        # ordering-critical decision loop can be separated (§5 fix 1).
        eligible: list[tuple[int, LongMemEvalTurn, dict[str, Any], tuple[Any, Any]]] = []
        for idx, turn in enumerate(turns):
            if turn.role != "user":
                continue
            if allowed_user_turn_idxs is not None and idx not in allowed_user_turn_idxs:
                continue
            payload = turn_payload(session, turn, idx)
            prev_payload = turn_payload(session, turns[idx - 1], idx - 1) if idx > 0 else None
            next_payload = (
                turn_payload(session, turns[idx + 1], idx + 1) if idx + 1 < len(turns) else None
            )
            eligible.append((idx, turn, payload, (prev_payload, next_payload)))

        # Phase 1 — extraction. Turns are independent, so extract them
        # concurrently when configured; the cache/counters/file are guarded by
        # self._extraction_lock. Sequential when extraction_concurrency <= 1, so
        # default runs are byte-identical.
        outputs = self._extract_turns(eligible, progress_label, session)

        # Phase 2 — decisions. Keep/Supersede/Abstain MUST run sequentially in
        # turn order for correct lineage, so this loop is never parallelized.
        for idx, turn, payload, _window in eligible:
            output = outputs[idx]
            for item in output.items:
                candidate = CandidateContext(
                    candidate_id=self._next_candidate_id,
                    item=item,
                    session_id=session.session_id,
                    turn_idx=idx,
                    turn_id=payload["turn_id"],
                    timestamp=turn.timestamp,
                    source_turn=turn.content,
                )
                self._next_candidate_id += 1
                self._process_candidate(conn, candidate, provenance, decisions, log_writer)

    def _extract_turns(
        self,
        eligible: list[tuple[int, Any, dict[str, Any], tuple[Any, Any]]],
        progress_label: str | None,
        session: LongMemEvalSession,
    ) -> dict[int, ExtractionOutput]:
        """Extract every eligible turn, concurrently when configured (§5 fix 1)."""
        total = len(eligible)
        prefix = progress_label or session.session_id
        concurrency = max(1, int(self.extraction_concurrency))
        if concurrency <= 1 or total <= 1:
            outputs: dict[int, ExtractionOutput] = {}
            for seen, (idx, _turn, payload, window) in enumerate(eligible, start=1):
                if self.progress and (seen == 1 or seen == total or seen % 10 == 0):
                    self._log_progress(
                        f"{prefix}: extract user_turn {seen}/{total} {session.session_id}:{idx}"
                    )
                outputs[idx] = self._extract_turn(payload, window)
            return outputs
        if self.progress:
            self._log_progress(
                f"{prefix}: extract {total} user_turns concurrently "
                f"(workers={min(concurrency, total)})"
            )
        outputs = {}
        with ThreadPoolExecutor(max_workers=min(concurrency, total)) as pool:
            futures = {
                pool.submit(self._extract_turn, payload, window): idx
                for idx, _turn, payload, window in eligible
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                outputs[idx] = fut.result()
        if self.progress:
            self._log_progress(f"{prefix}: extracted {total} user_turns")
        return outputs

    def _extract_turn(
        self,
        payload: Mapping[str, Any],
        window: tuple[Mapping[str, Any] | None, Mapping[str, Any] | None],
    ) -> ExtractionOutput:
        # Lock only the cache read/write/counters; the (slow) LLM call runs
        # outside the lock so concurrent extraction (§5 fix 1) actually overlaps.
        key = self._extraction_key(payload)
        with self._extraction_lock:
            cached = self._extraction_cache.get(key)
            if cached is not None:
                self._extraction_cache_hits += 1
                return cached
            self._extraction_cache_misses += 1
        failed = False
        try:
            output = self.extractor.extract(
                payload,
                window,
                max_new_tokens=self.extraction_max_new_tokens,
                temperature=0.0,
                seed=self.seed,
            )
        except Exception as exc:
            if self.fail_on_extraction_error:
                raise
            # Local models can occasionally emit unrecoverable structured output
            # drift. Treat that turn as empty so one bad extraction does not kill
            # an expensive Colab run.
            output = empty_extraction_output(
                f"extractor failed for {payload['session_id']}:{payload['turn_idx']}; "
                "treated as no extractable content"
            )
            failed = True
            self._extraction_uncached_failures += 1
            if self.progress:
                self._log_progress(
                    f"{payload['session_id']}:{payload['turn_idx']} "
                    f"extractor fallback after {type(exc).__name__}"
                )
        if (
            self.fail_on_extraction_error
            and output.no_extractable_content
            and "could not be parsed" in (output.coverage_note or "").casefold()
        ):
            raise RuntimeError(
                f"unrecoverable extraction for {payload['session_id']}:"
                f"{payload['turn_idx']}: {output.coverage_note}"
            )
        if self.raw_turn_fallback:
            output = self._with_raw_turn_fallback(output, payload)
        if failed:
            # A resume must retry this source turn after a provider, transport,
            # or unrecoverable extractor failure. Persisting the synthetic empty
            # fallback would silently turn an outage into durable no-memory data.
            return output
        with self._extraction_lock:
            # Another thread cannot have computed this same key (keys are unique
            # per turn within a session), but guard the shared dict/file anyway.
            self._extraction_cache[key] = output
            self._append_extraction_cache(key, output)
        return output

    def _with_raw_turn_fallback(
        self,
        output: ExtractionOutput,
        payload: Mapping[str, Any],
    ) -> ExtractionOutput:
        raw = self._raw_turn_fallback_item(payload)
        if raw is None:
            return output
        items = list(output.items)
        if raw.text.casefold() not in {item.text.casefold() for item in items}:
            items.append(raw)
        return ExtractionOutput(
            items=items,
            no_extractable_content=False,
            coverage_note=(
                "raw user turn fallback added"
                if output.items
                else "raw user turn fallback after empty extractor output"
            ),
        )

    def _raw_turn_fallback_item(self, payload: Mapping[str, Any]) -> ExtractedItem | None:
        content = str(payload.get("content") or "").strip()
        if not content:
            return None
        return ExtractedItem(
            text=content,
            type_guess="episodic_fact",
            evidence_span=EvidenceSpan(
                session_id=str(payload["session_id"]),
                turn_idx=int(payload["turn_idx"]),
                char_start=0,
                char_end=len(content),
            ),
            extraction_confidence=0.75,
            negation_marker=False,
            hedge_marker=False,
            polarity_subject="user",
        )

    def _extraction_key(self, payload: Mapping[str, Any]) -> str:
        return _cache_key(
            {
                "kind": "extraction_v4",
                "model": self._extraction_model_id,
                "prompt": self._extraction_prompt_fingerprint,
                "raw_turn_fallback": bool(self.raw_turn_fallback),
                "raw_turn_fallback_scope": "always_when_enabled",
                "session_id": str(payload["session_id"]),
                "turn_idx": int(payload["turn_idx"]),
                "content": str(payload["content"]),
                "timestamp": payload.get("timestamp"),
                "max_new_tokens": int(self.extraction_max_new_tokens),
                "seed": int(self.seed),
            }
        )

    def _append_extraction_cache(self, key: str, output: ExtractionOutput) -> None:
        if self.extraction_cache_path is None:
            return
        _append_jsonl(
            self.extraction_cache_path,
            {
                "key": key,
                "output": output.model_dump(),
            },
        )

    def _process_candidate(
        self,
        conn: sqlite3.Connection,
        candidate: CandidateContext,
        provenance: dict[int, MemoryProvenance],
        decisions: list[PipelineDecision],
        log_writer: ActionLogWriter | None,
    ) -> None:
        prior, relation, prior_map = self._select_prior_relation(
            conn,
            candidate,
            provenance,
        )

        features = feature_snapshot(candidate, prior_map, relation)
        decision = decide(features, candidate.item.type_guess, self.config)
        resulting_id = self._execute_decision(
            conn,
            candidate,
            prior,
            decision,
            provenance,
            relation,
        )
        prior_id = _require_id(prior) if prior is not None else None
        pipeline_decision = PipelineDecision(
            candidate_id=candidate.candidate_id,
            session_id=candidate.session_id,
            turn_idx=candidate.turn_idx,
            candidate_text=candidate.item.text,
            candidate_type=candidate.item.type_guess,
            action=decision.action,
            prior_memory_id=prior_id,
            resulting_memory_id=resulting_id,
            rationale=decision.rationale,
            relation=relation_label(relation),
            s_rev=decision.s_rev,
            s_abs=decision.s_abs,
        )
        decisions.append(pipeline_decision)
        self._write_decision(log_writer, candidate, decision, prior_id, resulting_id)

    def _classify_relation(
        self,
        candidate: CandidateContext,
        prior: DBMemoryItem,
        prior_provenance: MemoryProvenance | None,
    ) -> RelationOutput:
        key = self._relation_key(candidate, prior, prior_provenance)
        cached = self._relation_cache.get(key)
        if cached is not None:
            self._relation_cache_hits += 1
            return cached
        self._relation_cache_misses += 1
        output = classify_relation(
            self.classifier,
            candidate,
            prior,
            prior_provenance,
            max_new_tokens=self.relation_max_new_tokens,
            temperature=0.0,
            seed=self.seed,
        )
        model_used = self._relation_model_id or "primary"
        # Cascade: re-classify decision-critical / uncertain items with the
        # larger escalation classifier. The fast model still handles the bulk
        # (clear support/independent, high confidence, no markers).
        if self.classifier_escalation is not None:
            self._relation_escalation_eligible += 1
            if self._should_escalate(candidate, output):
                self._relation_escalations += 1
                output = classify_relation(
                    self.classifier_escalation,
                    candidate,
                    prior,
                    prior_provenance,
                    max_new_tokens=self.relation_max_new_tokens,
                    temperature=0.0,
                    seed=self.seed,
                )
                model_used = self._escalation_model_id or "escalation"
        self._relation_cache[key] = output
        self._append_relation_cache(key, output, model_used=model_used)
        return output

    def _should_escalate(self, candidate: CandidateContext, base_output: RelationOutput) -> bool:
        """Escalation predicate (maps the controller features c, r, rho).

        Escalate to the larger relation model when the fast model lands on a
        decision-critical or ambiguous label, when extraction confidence is
        low, or when the candidate carries negation/hedge markers — i.e. exactly
        the cases that move Supersede/Abstain.
        """
        relation = str(base_output.relation_to_prior_state)
        if str(base_output.logical_relation) == "independent" and relation == "unclear":
            # The downstream scorecard already treats independent+unclear as a
            # safe Keep. It is not a decision-critical ambiguity.
            return False
        if relation in self.escalation_relations:
            return True
        conf = getattr(candidate.item, "extraction_confidence", None)
        if conf is not None and float(conf) < self.escalation_extraction_confidence:
            return True
        if self._marker_burden(candidate) > self.escalation_marker_burden:
            return True
        return False

    @staticmethod
    def _marker_burden(candidate: CandidateContext) -> float:
        """Fraction of negation/hedge markers present on the candidate item."""
        markers = (
            bool(getattr(candidate.item, "negation_marker", False)),
            bool(getattr(candidate.item, "hedge_marker", False)),
        )
        return sum(markers) / len(markers)

    def _relation_key(
        self,
        candidate: CandidateContext,
        prior: DBMemoryItem,
        prior_provenance: MemoryProvenance | None,
    ) -> str:
        return self._relation_key_from_parts(
            candidate_text=candidate.item.text,
            candidate_type=candidate.item.type_guess,
            candidate_source_turn=candidate.source_turn,
            candidate_timestamp=candidate.timestamp,
            prior_text=prior.text,
            prior_type=prior.type.value,
            prior_timestamp=(prior_provenance.timestamp if prior_provenance is not None else None),
        )

    def _relation_key_from_parts(
        self,
        *,
        candidate_text: str,
        candidate_type: str,
        candidate_source_turn: str,
        candidate_timestamp: Any,
        prior_text: str,
        prior_type: str,
        prior_timestamp: Any,
    ) -> str:
        return _cache_key(
            {
                "kind": "relation_v2",
                "model": self._relation_model_id,
                "prompt": self._relation_prompt_fingerprint,
                "escalation_model": (
                    self._escalation_model_id if self.classifier_escalation is not None else None
                ),
                "escalation_extraction_confidence": float(self.escalation_extraction_confidence),
                "escalation_marker_burden": float(self.escalation_marker_burden),
                "escalation_relations": list(self.escalation_relations),
                "candidate_text": candidate_text,
                "candidate_type": candidate_type,
                "candidate_source_turn": candidate_source_turn,
                "candidate_timestamp": candidate_timestamp,
                "prior_text": prior_text,
                "prior_type": prior_type,
                "prior_timestamp": prior_timestamp,
                "max_new_tokens": int(self.relation_max_new_tokens),
                "seed": int(self.seed),
            }
        )

    def _append_relation_cache(
        self, key: str, output: RelationOutput, *, model_used: str | None = None
    ) -> None:
        if self.relation_cache_path is None:
            return
        row: dict[str, Any] = {
            "key": key,
            "output": output.model_dump(),
        }
        if model_used is not None:
            # Cascade audit trail: which model produced this relation label.
            row["model_used"] = model_used
        _append_jsonl(self.relation_cache_path, row)

    def _find_prior(
        self,
        conn: sqlite3.Connection,
        candidate: CandidateContext,
        provenance: Mapping[int, MemoryProvenance],
    ) -> DBMemoryItem | None:
        # Default-preserving path: the thesis-comparable controller still uses
        # the newest active same-type memory from another session. Quality mode
        # opts into semantic top-k through _select_prior_relation().
        memory_type = MemoryType(candidate.item.type_guess)
        active = retrieve_active(conn, memory_type)
        eligible = [
            item
            for item in active
            if item.id is not None
            and provenance.get(item.id) is not None
            and provenance[item.id].session_id != candidate.session_id
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda item: _require_id(item))

    def _select_prior_relation(
        self,
        conn: sqlite3.Connection,
        candidate: CandidateContext,
        provenance: Mapping[int, MemoryProvenance],
    ) -> tuple[DBMemoryItem | None, RelationOutput | None, dict[str, Any] | None]:
        if self.prior_top_k <= 1:
            prior = self._find_prior(conn, candidate, provenance)
            if prior is None:
                return None, None, None
            prior_id = _require_id(prior)
            prior_provenance = provenance.get(prior_id)
            relation = self._classify_relation(candidate, prior, prior_provenance)
            return prior, relation, prior_payload(prior, prior_provenance)

        support_choice: tuple[DBMemoryItem, RelationOutput, dict[str, Any]] | None = None
        for prior, similarity in self._semantic_prior_candidates(conn, candidate, provenance):
            # Latency + correctness gate: only spend a (2-stage) relation LLM
            # call on a prior the embedder considers genuinely related. Below the
            # threshold the pair is semantically unrelated, so the classifier
            # would almost always return "independent" anyway — skipping it both
            # cuts the dominant per-question cost and avoids the small model
            # hallucinating a "support"/"contradict" label on an unrelated pair.
            if similarity < self.prior_similarity_threshold:
                continue
            prior_id = _require_id(prior)
            prior_provenance = provenance.get(prior_id)
            deterministic = self._deterministic_supersede_relation(
                candidate, prior, prior_provenance
            )
            if deterministic is not None:
                return prior, deterministic, prior_payload(prior, prior_provenance)
            relation = self._classify_relation(candidate, prior, prior_provenance)
            label = relation_label(relation)
            payload = prior_payload(prior, prior_provenance)
            if label in {"contradict", "supersede"}:
                return prior, relation, payload
            if label == "support" and support_choice is None:
                support_choice = (prior, relation, payload)
        if support_choice is not None:
            return support_choice
        return None, None, None

    def _deterministic_supersede_relation(
        self,
        candidate: CandidateContext,
        prior: DBMemoryItem,
        prior_provenance: MemoryProvenance | None,
    ) -> RelationOutput | None:
        """Same-slot numeric conflicts route to Supersede without an LLM call.

        The 3.8B relation classifier reliably labels '$350,000 pre-approved
        from Wells Fargo' vs '$400,000 pre-approved from Wells Fargo' as
        support (the sentences look alike), so the stale value survives and the
        answerer quotes it. The shared-anchor + differing-number + newer-
        timestamp gate is precise enough to decide in code; everything else
        still goes through the classifier.
        """
        if not self.deterministic_numeric_supersede:
            return None
        if prior_provenance is None:
            return None
        cand_date = parse_any_date(candidate.timestamp)
        prior_date = parse_any_date(prior_provenance.timestamp)
        if cand_date is None or prior_date is None or cand_date <= prior_date:
            return None
        if not _same_slot_numeric_conflict(candidate.item.text, prior.text):
            return None
        return RelationOutput(
            logical_relation="contradict",
            temporal="newer",
            same_subject=True,
            relation_to_prior_state="supersede",
            stage1_rationale=(
                "deterministic: same fact slot (shared anchor tokens) with different numeric values"
            ),
            stage2_rationale=(
                f"deterministic: candidate dated {cand_date.isoformat()} is newer "
                f"than prior dated {prior_date.isoformat()}"
            ),
        )

    def _semantic_prior_candidates(
        self,
        conn: sqlite3.Connection,
        candidate: CandidateContext,
        provenance: Mapping[int, MemoryProvenance],
    ) -> list[tuple[DBMemoryItem, float]]:
        memory_type = MemoryType(candidate.item.type_guess)
        active = retrieve_active(conn, memory_type)
        eligible = [
            item
            for item in active
            if item.id is not None
            and provenance.get(item.id) is not None
            and provenance[item.id].session_id != candidate.session_id
        ]
        if not eligible:
            return []
        store = FlatVectorStore(embedder=self.embedder or TurnEmbedder(device="cpu"))
        indexed: list[RetrievalMemoryItem] = []
        by_object_id: dict[int, DBMemoryItem] = {}
        for item in eligible:
            src = provenance[_require_id(item)]
            retrieval_item = RetrievalMemoryItem(
                text=item.text,
                role="user",
                session_id=src.session_id,
                turn_idx=src.turn_idx,
                timestamp=src.timestamp,
            )
            indexed.append(retrieval_item)
            by_object_id[id(retrieval_item)] = item
        store.add(indexed)
        hits = store.search(candidate.item.text, k=min(int(self.prior_top_k), len(indexed)))
        out: list[tuple[DBMemoryItem, float]] = []
        seen: set[int] = set()
        for hit in hits:
            prior = by_object_id.get(id(hit.item))
            if prior is None:
                continue
            prior_id = _require_id(prior)
            if prior_id in seen:
                continue
            seen.add(prior_id)
            out.append((prior, float(hit.score)))
        return out

    def _execute_decision(
        self,
        conn: sqlite3.Connection,
        candidate: CandidateContext,
        prior: DBMemoryItem | None,
        decision: ScorecardDecision,
        provenance: dict[int, MemoryProvenance],
        relation: RelationOutput | None,
    ) -> int | None:
        if decision.action == ControllerAction.ABSTAIN:
            return None

        if decision.action == ControllerAction.SUPERSEDE:
            if prior is None:
                return None
            prior_id = _require_id(prior)
            new_id = supersede(conn, _db_item(candidate), prior_id=prior_id)
            provenance[new_id] = _provenance(candidate)
            return new_id

        # KEEP admits the candidate as a memory item. We only skip insertion
        # when the candidate is a near-verbatim duplicate of the compared prior
        # (true redundancy). The previous rule dropped *any* candidate the
        # classifier rated non-"independent" against the prior; because
        # `_find_prior` returns the newest same-type item from another session
        # (often semantically unrelated), a spurious "support" label silently
        # discarded genuine new facts — 44/226 lost on the m4w13 LongMemEval
        # smoke run. Dropping only exact-text duplicates preserves distinct
        # memories while still avoiding redundant rows.
        if prior is not None and _is_duplicate_text(candidate.item.text, prior.text):
            return None
        new_id = insert_active(conn, _db_item(candidate))
        provenance[new_id] = _provenance(candidate)
        return new_id

    def _write_decision(
        self,
        writer: ActionLogWriter | None,
        candidate: CandidateContext,
        decision: ScorecardDecision,
        prior_id: int | None,
        resulting_id: int | None,
    ) -> None:
        if writer is None:
            return
        entry = ActionLogEntry(
            id=self._next_log_id,
            timestamp=datetime.now(UTC),
            action=decision.action,
            candidate_text=candidate.item.text,
            rationale=decision.rationale,
            session_id=candidate.session_id,
            baseline=self.BASELINE_NAME,
            candidate_type=MemoryType(candidate.item.type_guess),
            candidate_id=candidate.candidate_id,
            prior_memory_id=prior_id,
            resulting_memory_id=resulting_id,
            feature_c=decision.features.c,
            feature_e=decision.features.e,
            feature_f=decision.features.f,
            feature_r=decision.features.r,
            feature_rho=decision.features.rho,
            s_rev=decision.s_rev,
            s_abs=decision.s_abs,
            theta_sup=decision.theta_sup,
            theta_abs=decision.theta_abs,
        )
        writer.write(entry)
        self._next_log_id += 1

    def _retrieve(
        self,
        conn: sqlite3.Connection,
        provenance: Mapping[int, MemoryProvenance],
        session: LongMemEvalSession,
    ) -> list[RetrievedItem]:
        embedder = self.embedder
        if embedder is None:  # Defensive for objects restored without __post_init__.
            raise RuntimeError("controller embedder is not initialized")
        store = FlatVectorStore(embedder=embedder)
        items: list[RetrievalMemoryItem] = []
        active_memories = retrieve_active(conn)
        for memory in active_memories:
            if memory.id is None:
                continue
            src = provenance.get(memory.id)
            if src is None or src.session_id == session.session_id:
                continue
            items.append(
                RetrievalMemoryItem(
                    text=memory.text,
                    role="user",
                    session_id=src.session_id,
                    turn_idx=src.turn_idx,
                    timestamp=src.timestamp,
                )
            )
        # Opt-in: a large share of LongMemEval answers live in ASSISTANT turns
        # (the whole single-session-assistant competency; ~32% of the dev slice),
        # which the user-only memory pipeline can never capture. When enabled we
        # add raw assistant turns from the allowed memory corpus to the retrieval
        # pool so the answerer can ground on them. Default off, so MGP-6 and the
        # validated controller runs are unchanged.
        if self.include_assistant_context:
            items.extend(self._assistant_context_items(session))
        if self.include_raw_user_context:
            items.extend(self._raw_user_context_items(session))
        store.add(items)
        retrieved = store.search(session.question, k=self.k)

        # The controller preserves superseded rows for auditability, whereas B4
        # destructively deletes them. Surface that lineage only when the query
        # explicitly asks for a historical state. A separate top-k guarantees
        # that the relevant predecessor is not crowded out by the active/raw
        # retrieval pool; every such row carries a conspicuous status tag.
        history_items = self._historical_context_items(conn, active_memories, provenance, session)
        if history_items and self.history_retrieval_k > 0:
            history_store = FlatVectorStore(embedder=embedder)
            history_store.add(history_items)
            history_hits = history_store.search(
                session.question,
                k=min(int(self.history_retrieval_k), len(history_items)),
            )
            seen = {(hit.item.session_id, hit.item.turn_idx, hit.item.text) for hit in retrieved}
            for hit in history_hits:
                key = (hit.item.session_id, hit.item.turn_idx, hit.item.text)
                if key in seen:
                    continue
                seen.add(key)
                retrieved.append(RetrievedItem(item=hit.item, score=hit.score, rank=len(retrieved)))
                self._last_history_retrieved_count += 1

        context_items = items + history_items
        if self.include_raw_user_context:
            retrieved = self._ensure_user_role_quota(session, store, retrieved)
            retrieved = _append_lexical_complement(
                session.question, context_items, retrieved, cap=8
            )
        if self.retrieval_query_augmentation:
            retrieved = self._augment_retrieval(session, store, items, retrieved)
        if self.retrieval_neighbor_window <= 0 or not retrieved:
            return retrieved
        return _expand_retrieval_neighbors(
            retrieved,
            context_items,
            window=self.retrieval_neighbor_window,
            corpus=self.corpus,
        )

    def _historical_context_items(
        self,
        conn: sqlite3.Connection,
        active_memories: Iterable[DBMemoryItem],
        provenance: Mapping[int, MemoryProvenance],
        session: LongMemEvalSession,
    ) -> list[RetrievalMemoryItem]:
        """Build tagged predecessor rows for an explicit history query only."""
        self._last_history_query_detected = bool(
            self.history_aware_retrieval and _requests_historical_memory(session.question)
        )
        self._last_history_candidate_count = 0
        self._last_history_retrieved_count = 0
        if not self._last_history_query_detected:
            return []

        out: list[RetrievalMemoryItem] = []
        seen_ids: set[int] = set()
        for active in active_memories:
            if active.id is None:
                continue
            for historical in get_lineage(conn, active.id)[:-1]:
                if historical.id is None or historical.id in seen_ids:
                    continue
                if historical.status is not MemoryStatus.SUPERSEDED:
                    continue
                src = provenance.get(historical.id)
                if src is None or src.session_id == session.session_id:
                    continue
                seen_ids.add(historical.id)
                out.append(
                    RetrievalMemoryItem(
                        text=f"{_SUPERSEDED_HISTORY_TAG} {historical.text}",
                        role="user",
                        session_id=src.session_id,
                        turn_idx=src.turn_idx,
                        timestamp=src.timestamp,
                    )
                )
        self._last_history_candidate_count = len(out)
        return out

    def _assistant_context_items(self, session: LongMemEvalSession) -> list[RetrievalMemoryItem]:
        """Raw assistant turns from the allowed memory corpus (anti-leakage safe)."""
        items: list[RetrievalMemoryItem] = []
        supporting = self._supporting_sessions_from_ids(memory_session_ids(session))
        for support in supporting:
            if support.session_id == session.session_id:
                continue
            for idx, turn in enumerate(support.turns):
                if turn.role != "assistant":
                    continue
                if not (turn.content or "").strip():
                    continue
                # Chunk long assistant turns. Embedding a 1-3k-char multi-topic
                # turn as a single vector makes it match broadly but imprecisely,
                # so it both crowds out short user-fact turns and buries the
                # actual fact in the answer prompt. Sentence/line chunks let the
                # fact-bearing snippet rank and answer on its own merits.
                for chunk in _chunk_text(turn.content):
                    items.append(
                        RetrievalMemoryItem(
                            text=chunk,
                            role="assistant",
                            session_id=support.session_id,
                            turn_idx=idx,
                            timestamp=turn.timestamp,
                        )
                    )
        return items

    def _raw_user_context_items(self, session: LongMemEvalSession) -> list[RetrievalMemoryItem]:
        """Raw user turns from the allowed memory corpus (anti-leakage safe).

        The extraction prefilter caps how many user turns reach the LLM
        extractor (32 of ~240 on the T4 profile), so a fact the prefilter
        ranked 40th — e.g. "my previous role as a marketing specialist" against
        the question "What was my previous occupation?" — never becomes a
        memory item and the answerer sees nothing. Adding the raw user turns to
        the retrieval pool restores answer-time recall without any extra LLM
        extraction calls; extracted memory items still rank first when both
        match.
        """
        items: list[RetrievalMemoryItem] = []
        supporting = self._supporting_sessions_from_ids(memory_session_ids(session))
        for support in supporting:
            if support.session_id == session.session_id:
                continue
            for idx, turn in enumerate(support.turns):
                if turn.role != "user":
                    continue
                if not (turn.content or "").strip():
                    continue
                for chunk in _chunk_text(turn.content):
                    items.append(
                        RetrievalMemoryItem(
                            text=chunk,
                            role="user",
                            session_id=support.session_id,
                            turn_idx=idx,
                            timestamp=turn.timestamp,
                        )
                    )
        return items

    def _ensure_user_role_quota(
        self,
        session: LongMemEvalSession,
        store: FlatVectorStore,
        retrieved: list[RetrievedItem],
        *,
        quota: int = 4,
    ) -> list[RetrievedItem]:
        """Guarantee the top user-asserted statements survive assistant chunks.

        With raw user turns AND chunked assistant turns in one pool, verbose
        assistant prose dominates the top-k for bookish/expository questions
        and crowds out the user's own statement — which is the gold evidence
        source for every *-user competency. A small dedicated quota of the
        best user-role hits keeps them in the prompt without re-ranking the
        baseline list.
        """
        have = sum(1 for hit in retrieved if hit.item.role == "user")
        if have >= quota:
            return retrieved
        out = list(retrieved)
        seen = {(hit.item.session_id, hit.item.turn_idx, hit.item.text) for hit in out}
        needed = quota - have
        for hit in store.search(session.question, k=max(self.k * 4, 40)):
            if hit.item.role != "user":
                continue
            key = (hit.item.session_id, hit.item.turn_idx, hit.item.text)
            if key in seen:
                continue
            seen.add(key)
            out.append(RetrievedItem(item=hit.item, score=hit.score, rank=len(out)))
            needed -= 1
            if needed == 0:
                break
        return out

    def _augment_retrieval(
        self,
        session: LongMemEvalSession,
        store: FlatVectorStore,
        items: list[RetrievalMemoryItem],
        retrieved: list[RetrievedItem],
    ) -> list[RetrievedItem]:
        """Question-aware extra retrieval passes for aggregation/temporal asks.

        Single-query top-k retrieval systematically under-covers questions
        whose answer is *distributed*: a count over five sessions, a sum over
        two purchases, an order over three dated events, or an event located by
        "four weeks ago" rather than by topic. Three additive passes close
        that gap; every added item is appended after the base hits so the
        baseline ranking is preserved.
        """
        question = session.question or ""
        intent = classify_compute_intent(question)
        aggregation_intents = {
            ComputeIntent.COUNT_EVENTS,
            ComputeIntent.NUMERIC_SUM,
            ComputeIntent.NUMERIC_AVERAGE,
            ComputeIntent.NUMERIC_DIFF,
            ComputeIntent.CHRONOLOGICAL_ORDER,
            ComputeIntent.DATE_DIFF,
            ComputeIntent.RELATIVE_TIME,
        }
        if intent not in aggregation_intents and not is_temporal_question(question):
            return retrieved
        out = list(retrieved)
        seen = {(hit.item.session_id, hit.item.turn_idx, hit.item.text) for hit in out}

        def _append_hits(hits: Iterable[RetrievedItem], cap: int) -> None:
            added = 0
            for hit in hits:
                key = (hit.item.session_id, hit.item.turn_idx, hit.item.text)
                if key in seen:
                    continue
                seen.add(key)
                out.append(RetrievedItem(item=hit.item, score=hit.score, rank=len(out)))
                added += 1
                if added >= cap:
                    return

        # Pass 1 — widen the main query for distributed-answer questions.
        if intent in aggregation_intents:
            _append_hits(store.search(question, k=self.k + 8), cap=6)

        # Pass 2 — per-entity queries: each event/item phrase named in the
        # question gets its own search so no entity is crowded out.
        phrases = _event_phrases(question) + _question_item_phrases(question)
        for phrase in phrases[:4]:
            if not phrase.strip():
                continue
            _append_hits(store.search(phrase, k=3), cap=2)

        # Pass 3 — calendar-window pass: "N weeks/months ago" or "in <month>"
        # selects items by date, which topical similarity cannot do. The date
        # window FILTERS; dense similarity to the question RANKS inside it
        # (a busy haystack can have a dozen sessions on the boundary day).
        window_candidates = self._calendar_window_items(
            question, items, seen, question_date=session.question_date, cap=24
        )
        if window_candidates:
            dense_rank = {
                (hit.item.session_id, hit.item.turn_idx, hit.item.text): float(hit.score)
                for hit in store.search(question, k=min(len(items), 256))
            }
            window_candidates.sort(
                key=lambda item: (
                    -(
                        dense_rank.get((item.session_id, item.turn_idx, item.text), 0.0)
                        + (0.05 if item.role == "user" else 0.0)
                    )
                )
            )
            for item in window_candidates[:4]:
                seen.add((item.session_id, item.turn_idx, item.text))
                out.append(RetrievedItem(item=item, score=0.30, rank=len(out)))
        return out

    def _calendar_window_items(
        self,
        question: str,
        items: list[RetrievalMemoryItem],
        seen: set[tuple[str, int, str]],
        *,
        question_date: str | None = None,
        cap: int = 4,
    ) -> list[RetrievalMemoryItem]:
        qdate = parse_any_date(question_date)
        stamps: list[date] = []
        for item in items:
            parsed = parse_any_date(item.timestamp)
            if parsed is not None:
                stamps.append(parsed)
        ref = qdate or (max(stamps) if stamps else None)
        if ref is None:
            return []
        window = _question_relative_window(question, ref)
        month = _question_month(question)
        scored: list[tuple[float, RetrievalMemoryItem]] = []
        for item in items:
            if (item.session_id, item.turn_idx, item.text) in seen:
                continue
            item_date = parse_any_date(item.timestamp)
            if item_date is None:
                continue
            if window is not None:
                target, tolerance = window
                if qdate is not None:
                    # Exact reference: narrow band around question_date - delta.
                    distance = abs((item_date - target).days)
                    if distance > tolerance:
                        continue
                    anchor_distance = distance
                else:
                    # Proxy reference (newest session). The true question date
                    # is later than every session, so the asked-about event can
                    # sit anywhere in [ref - delta, ref]; prefer the newest.
                    if not (target - timedelta(days=tolerance) <= item_date <= ref):
                        continue
                    anchor_distance = abs((ref - item_date).days)
                score = float(tolerance + 30 - anchor_distance + (2 if item.role == "user" else 0))
            elif month is not None:
                if item_date.month != month:
                    continue
                score = 2.0 if item.role == "user" else 1.0
            else:
                continue
            scored.append((score, item))
        scored.sort(key=lambda pair: -pair[0])
        return [item for _, item in scored[:cap]]

    def _answer_token_budget(self) -> tuple[int | None, int, int]:
        """Return (num_ctx, reserved_output_tokens, safe_prompt_budget_tokens).

        `num_ctx` is None when the LLM backend does not expose a context window
        (the FakeLLM in tests, for example), in which case the guard is a no-op
        and the prompt is sent unchanged.
        """
        num_ctx = getattr(self.llm, "num_ctx", None)
        reserved = max(
            _MIN_RESERVED_OUTPUT_TOKENS,
            min(int(self.max_new_tokens), _MAX_RESERVED_OUTPUT_TOKENS),
        )
        if num_ctx is None:
            return None, reserved, 0
        budget = int(num_ctx) - reserved - _PROMPT_BUDGET_MARGIN_TOKENS
        return int(num_ctx), reserved, max(budget, 0)

    def _effective_system_prompt(self, session: LongMemEvalSession) -> str:
        """Select the answer system prompt for this question (docx §4 fix 1)."""
        if self.per_competency_answer_prompt:
            competency = (getattr(session, "competency", "") or "").lower()
            if "preference" in competency:
                return PREFERENCE_SYSTEM_PROMPT
        return self.system_prompt

    def _rerank_for_answer(self, retrieved: list[RetrievedItem]) -> list[RetrievedItem]:
        """Order retrieved items by descending score (docx §5 fix 4).

        Neighbor-window expansion and raw-context injection append items in
        provenance order, not similarity order; reranking by score first means a
        tighter answer-context cap keeps the highest-signal hits. Stable sort, so
        equal-score items keep their original relative order.
        """
        return sorted(retrieved, key=lambda r: -float(r.score))

    def _session_diverse_answer_order(self, retrieved: list[RetrievedItem]) -> list[RetrievedItem]:
        """Prioritize cross-session coverage before repeated same-session chunks.

        LongMemEval's aggregation and temporal questions require evidence from
        several sessions. Neighbor expansion can otherwise give one dense hit
        dozens of equally scored chunks and consume most of a trimmed prompt.
        User/extracted evidence retains priority over assistant prose; within
        each role group, the first ``answer_context_session_cap`` items from a
        session precede that session's overflow.
        """
        cap = int(self.answer_context_session_cap)
        ranked = sorted(
            retrieved,
            key=lambda item: (
                1 if item.item.role == "assistant" else 0,
                -float(item.score),
            ),
        )
        if cap <= 0:
            return ranked

        out: list[RetrievedItem] = []
        for assistant_group in (False, True):
            group = [item for item in ranked if (item.item.role == "assistant") is assistant_group]
            counts: dict[str, int] = {}
            overflow: list[RetrievedItem] = []
            for item in group:
                session_id = item.item.session_id
                count = counts.get(session_id, 0)
                if count < cap:
                    out.append(item)
                    counts[session_id] = count + 1
                else:
                    overflow.append(item)
            out.extend(overflow)
        return out

    def _budget_trim_for_answer(
        self,
        session: LongMemEvalSession,
        retrieved: list[RetrievedItem],
        computed: ComputedAnswer | None,
        budget_tokens: int,
    ) -> tuple[list[RetrievedItem], dict[str, Any]]:
        """Trim retrieved context so the rendered answer prompt fits the budget.

        Trimming priority (noisiest first), never touching the question or the
        dialogue turns: assistant-role context is dropped before user/extracted
        facts, and within each group the lowest-scoring items go first — which
        is also where neighbor-expanded and raw-context items land. At least
        `_BUDGET_FLOOR_ITEMS` of the highest-scoring hits are always kept. The
        surviving items are returned in their original retrieval order so the
        prompt stays byte-stable apart from the removals.
        """
        n_before = len(retrieved)
        # Guard disabled (no context window exposed, e.g. FakeLLM) or nothing to
        # trim: return unchanged without rendering, so behavior is byte-stable.
        if budget_tokens <= 0 or n_before == 0:
            return retrieved, {
                "prompt_trimmed": False,
                "memory_items_before_trim": n_before,
                "memory_items_after_trim": n_before,
                "estimated_prompt_tokens": None,
                "estimated_prompt_tokens_before_trim": None,
            }
        full_prompt = self._render_prompt(session, retrieved, computed_answer=computed)
        est_before = _estimate_prompt_tokens(full_prompt)
        debug: dict[str, Any] = {
            "prompt_trimmed": False,
            "memory_items_before_trim": n_before,
            "memory_items_after_trim": n_before,
            "estimated_prompt_tokens": est_before,
            "estimated_prompt_tokens_before_trim": est_before,
        }
        if est_before <= budget_tokens:
            return retrieved, debug

        base_tokens = _estimate_prompt_tokens(
            self._render_prompt(session, [], computed_answer=computed)
        )

        ordered = self._session_diverse_answer_order(retrieved)
        kept: list[RetrievedItem] = []
        used = base_tokens
        for item in ordered:
            cost = _estimate_prompt_tokens(item.item.text) + _PER_ITEM_OVERHEAD_TOKENS
            if len(kept) < _BUDGET_FLOOR_ITEMS or used + cost <= budget_tokens:
                kept.append(item)
                used += cost
        if self.answer_context_session_cap > 0:
            # Keep the diversity/priority order so any final corrective drops
            # remove the lowest-priority tail rather than an arbitrary original
            # retrieval tail.
            trimmed = list(kept)
        else:
            keep_ids = {id(item) for item in kept}
            trimmed = [item for item in retrieved if id(item) in keep_ids]

        # The per-item additive estimate ignores template separators, so verify
        # against a real render and drop from the tail until it truly fits.
        while len(trimmed) > _BUDGET_FLOOR_ITEMS:
            est = _estimate_prompt_tokens(
                self._render_prompt(session, trimmed, computed_answer=computed)
            )
            if est <= budget_tokens:
                break
            trimmed = trimmed[:-1]

        est_after = _estimate_prompt_tokens(
            self._render_prompt(session, trimmed, computed_answer=computed)
        )
        debug.update(
            prompt_trimmed=len(trimmed) != n_before,
            memory_items_after_trim=len(trimmed),
            estimated_prompt_tokens=est_after,
        )
        return trimmed, debug

    def _render_prompt(
        self,
        session: LongMemEvalSession,
        retrieved: list[RetrievedItem],
        *,
        system_prompt: str | None = None,
        computed_answer: ComputedAnswer | None = None,
    ) -> str:
        turn_dicts = [{"role": t.role, "content": t.content} for t in session.turns]
        retrieved_dicts = [
            {
                "score": r.score,
                "role": r.item.role,
                "session_id": r.item.session_id,
                "turn_idx": r.item.turn_idx,
                "timestamp": r.item.timestamp,
                "text": r.item.text,
            }
            for r in retrieved
        ]
        return self._template.render(
            system_prompt=system_prompt or self.system_prompt,
            retrieved_memory=retrieved_dicts,
            turns=turn_dicts,
            question=session.question,
            temporal_block=self._temporal_block(session, retrieved),
            computation_block=format_computation_block(computed_answer),
            conflict_block=_conflict_block(retrieved, session.question),
        )

    def _temporal_block(self, session: LongMemEvalSession, retrieved: list[RetrievedItem]) -> str:
        """Additive scaffolding for temporal questions (roadmap P4).

        Surfaces event dates parsed from the memory text (not just the session
        timestamp) plus a reference 'today' proxy, so the answerer does not have
        to parse/sort/subtract dates itself — the step it most often gets wrong.
        Returns "" unless enabled and the question is temporal, so default runs
        are byte-for-byte unchanged. Never overrides the model.
        """
        if not self.temporal_scaffold or not is_temporal_question(session.question):
            return ""
        pairs = [(r.item.timestamp, r.item.text) for r in retrieved]
        dated = collect_dated_memories(pairs)
        qdate = parse_any_date(session.question_date)
        if not dated and qdate is None:
            return ""
        ref = reference_date(pairs)
        lines = [
            "----- NORMALIZED EVENT DATES (parsed from the memories above; "
            "use these for order/duration; a date inside the text is the event "
            "date, not when it was discussed) -----"
        ]
        if qdate is not None:
            lines.append(f"Question/reference date: {format_iso(qdate)}")
        elif ref is not None:
            lines.append(
                f"Reference date (most recent; treat as 'today' for 'ago'/"
                f"'last week'): {format_iso(ref)}"
            )
        seen: set[tuple[str, str]] = set()
        for d in dated:
            key = (d.iso_date, d.text[:80])
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"{d.iso_date}: {d.text[:160]}")
            if len(lines) >= 22:
                break
        return "\n".join(lines)

    def _compute_answer(
        self,
        session: LongMemEvalSession,
        retrieved: list[RetrievedItem],
    ) -> ComputedAnswer | None:
        if not self.computation_answerer:
            return None
        evidence = [
            RetrievedEvidence(
                session_id=r.item.session_id,
                turn_idx=r.item.turn_idx,
                role=r.item.role,
                text=r.item.text,
                timestamp=r.item.timestamp,
                score=float(r.score),
            )
            for r in retrieved
        ]
        # docx §4 fix 6: for "the Nth item of the list" questions, add the FULL
        # (unchunked) assistant turns that carry an enumerated list, so the
        # deterministic solver can index item N even when retrieval only pulled
        # a fragment of the list.
        if self.ordinal_list_reconstruction and (
            classify_compute_intent(session.question) is ComputeIntent.ORDINAL_LIST_ITEM
        ):
            evidence.extend(self._ordinal_list_evidence(session))
        computed = compute_answer(
            session.question,
            evidence,
            question_date=session.question_date,
        )
        return computed

    def _aggregation_scaffold(
        self, session: LongMemEvalSession, retrieved: list[RetrievedItem]
    ) -> ComputedAnswer | None:
        """LLM-lists mentions -> code counts/sums them (docx §4 fix 4).

        Never bypasses the answerer (safe_to_bypass_llm=False): the computed
        value is injected as a strong hint and the answer LLM stays the arbiter.
        """
        intent = classify_compute_intent(session.question)
        if intent not in (ComputeIntent.COUNT_EVENTS, ComputeIntent.NUMERIC_SUM):
            return None
        if not retrieved:
            return None
        lines = []
        valid_sources: set[str] = set()
        for hit in retrieved:
            tag = f"{hit.item.session_id}:{hit.item.turn_idx}"
            valid_sources.add(tag)
            date = f" ({hit.item.timestamp})" if hit.item.timestamp else ""
            lines.append(f"[{tag}]{date} {hit.item.text}")
        prompt = AGGREGATION_SCAFFOLD_PROMPT.replace("__QUESTION__", session.question).replace(
            "__MEMORY__", "\n".join(lines)
        )
        try:
            resp = self.llm.generate(
                prompt, max_new_tokens=self.max_new_tokens, temperature=0.0, seed=self.seed
            )
        except Exception:  # noqa: BLE001 — scaffold is best-effort
            return None
        items = _parse_json_array(resp.text)
        if not items:
            return None
        is_sum = intent is ComputeIntent.NUMERIC_SUM
        seen: set[str] = set()
        kept: list[dict[str, Any]] = []
        for obj in items:
            if not isinstance(obj, dict):
                continue
            source = str(obj.get("session", "")).strip()
            if source not in valid_sources:
                continue
            label = str(obj.get("item", "")).strip().lower()
            value = _coerce_number(obj.get("value"))
            normalized_label = _normalize_for_dedup(label)
            dedup_key = f"{source}|{normalized_label}|{value}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            kept.append({"source": source, "item": label, "value": value})
        if not kept:
            return None
        if is_sum:
            values = [k["value"] for k in kept if k["value"] is not None]
            if not values:
                return None
            total = sum(values)
            answer = _format_scaffold_number(total)
            computation = (
                "Aggregation scaffold summed "
                + " + ".join(_format_scaffold_number(v) for v in values)
                + f" = {answer} over {len(values)} distinct mention(s)."
            )
        else:
            answer = str(len(kept))
            computation = (
                f"Aggregation scaffold counted {len(kept)} distinct mention(s): "
                + ", ".join(k["item"] for k in kept if k["item"])[:200]
            )
        return ComputedAnswer(
            answer=answer,
            intent=intent,
            evidence=[],
            computation=computation,
            confidence=0.7,
            safe_to_bypass_llm=False,
        )

    def _ordinal_list_evidence(self, session: LongMemEvalSession) -> list[RetrievedEvidence]:
        """Full assistant turns containing a numbered list (docx §4 fix 6)."""
        out: list[RetrievedEvidence] = []
        for support in self._supporting_sessions_from_ids(memory_session_ids(session)):
            if support.session_id == session.session_id:
                continue
            for idx, turn in enumerate(support.turns):
                if turn.role != "assistant":
                    continue
                content = turn.content or ""
                # Cheap gate: at least two "N. " markers => an enumerated list.
                if len(_NUMBERED_ITEM_MARKER_RE.findall(content)) >= 2:
                    out.append(
                        RetrievedEvidence(
                            session_id=support.session_id,
                            turn_idx=idx,
                            role="assistant",
                            text=content,
                            timestamp=turn.timestamp,
                            score=0.0,
                        )
                    )
        return out


def _db_item(candidate: CandidateContext) -> DBMemoryItem:
    return DBMemoryItem(
        id=None,
        type=MemoryType(candidate.item.type_guess),
        text=candidate.item.text,
        confidence=candidate.item.extraction_confidence,
        status=MemoryStatus.ACTIVE,
    )


def _provenance(candidate: CandidateContext) -> MemoryProvenance:
    return MemoryProvenance(
        session_id=candidate.session_id,
        turn_idx=candidate.turn_idx,
        timestamp=candidate.timestamp,
        candidate_id=candidate.candidate_id,
    )


def _require_id(item: DBMemoryItem) -> int:
    if item.id is None:
        raise ValueError("memory item has no id")
    return item.id


def _action_counts(decisions: Iterable[PipelineDecision]) -> dict[str, int]:
    counts = {"Keep": 0, "Supersede": 0, "Abstain": 0}
    for decision in decisions:
        counts[decision.action.value] = counts.get(decision.action.value, 0) + 1
    return counts


_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
# "1. ", "2) ", "10. " list markers — a cheap detector for enumerated assistant
# lists (docx §4 fix 6 ordinal reconstruction).
_NUMBERED_ITEM_MARKER_RE = re.compile(r"(?:^|\n)\s*\d{1,3}[.)]\s+")


def _chunk_text(text: str, *, max_chars: int = 320, min_chars: int = 12) -> list[str]:
    """Split a long turn into sentence/line chunks for precise retrieval.

    Greedy-packs sentences (and newline-delimited list items) up to ``max_chars``
    so each retrieval unit is a focused snippet rather than a multi-topic wall of
    text. Short turns pass through as a single chunk.
    """
    text = (text or "").strip()
    if len(text) <= max_chars:
        return [text] if text else []
    pieces = [p.strip() for p in _SENT_SPLIT_RE.split(text) if p and p.strip()]
    chunks: list[str] = []
    buf = ""
    for piece in pieces:
        if len(piece) > max_chars:
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(piece), max_chars):
                chunks.append(piece[i : i + max_chars])
            continue
        if not buf:
            buf = piece
        elif len(buf) + 1 + len(piece) <= max_chars:
            buf = f"{buf} {piece}"
        else:
            chunks.append(buf)
            buf = piece
    if buf:
        chunks.append(buf)
    return [c for c in chunks if len(c) >= min_chars] or ([text[:max_chars]] if text else [])


_QUESTION_STOPWORDS = {
    "about",
    "all",
    "and",
    "any",
    "are",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "many",
    "much",
    "the",
    "that",
    "this",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
    "your",
}


def _lexical_tokens(text: str) -> set[str]:
    return {
        tok
        for tok in re.findall(r"[a-z]+", text.casefold())
        if len(tok) > 2 and tok not in _QUESTION_STOPWORDS
    }


def _append_lexical_complement(
    question: str,
    items: list[RetrievalMemoryItem],
    retrieved: list[RetrievedItem],
    *,
    cap: int = 8,
) -> list[RetrievedItem]:
    """IDF-weighted exact-token complement to dense retrieval.

    MiniLM places 'What was my previous occupation?' nowhere near 'my previous
    role as a marketing specialist at a small startup', so dense top-k misses
    the gold turn entirely. Rare shared surface tokens ('previous') recover
    exactly these cases; common tokens contribute almost nothing through the
    IDF weight. Additive and capped, so the dense ranking is untouched.

    v4-run changes (session 38146c39, 'chocolate chip cookies' vs the
    turbinado-sugar turn that never surfaced): cap raised 3 -> 8, and
    assistant-role items now participate at a 0.7 weight (user turns still
    win ties) — the answer to an entity question frequently lives in an
    assistant turn that names the entity verbatim.
    """
    q_tokens = _lexical_tokens(question)
    if not q_tokens:
        return retrieved
    cand_items = [item for item in items if item.role in ("user", "assistant")]
    if not cand_items:
        return retrieved
    # Morphology-tolerant overlap ('worked' must hit 'working on a diorama'),
    # via the same cheap variant set the computation solvers use.
    df: dict[str, int] = {}
    item_overlaps: list[set[str]] = []
    for item in cand_items:
        text_l = item.text.casefold()
        overlap = {tok for tok in q_tokens if _token_in_text(tok, text_l)}
        item_overlaps.append(overlap)
        for tok in overlap:
            df[tok] = df.get(tok, 0) + 1
    n_docs = len(cand_items)
    seen = {(hit.item.session_id, hit.item.turn_idx, hit.item.text) for hit in retrieved}
    scored: list[tuple[float, RetrievalMemoryItem]] = []
    for item, overlap in zip(cand_items, item_overlaps):
        if not overlap:
            continue
        score = sum(math.log(1.0 + n_docs / df[tok]) for tok in overlap)
        if item.role == "assistant":
            score *= 0.7
        if score <= 0.0:
            continue
        if (item.session_id, item.turn_idx, item.text) in seen:
            continue
        scored.append((score, item))
    scored.sort(key=lambda pair: -pair[0])
    out = list(retrieved)
    for score, item in scored[:cap]:
        seen.add((item.session_id, item.turn_idx, item.text))
        out.append(RetrievedItem(item=item, score=0.25, rank=len(out)))
    return out


_NUMERIC_VALUE_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?")
# Conversational filler that two unrelated purchase/update sentences share
# anyway; excluded so shared-anchor counting keys on real entities.
_GENERIC_TOKENS = {
    "about",
    "actually",
    "after",
    "again",
    "back",
    "been",
    "before",
    "being",
    "definitely",
    "did",
    "doing",
    "finally",
    "forward",
    "from",
    "get",
    "getting",
    "going",
    "got",
    "have",
    "having",
    "just",
    "know",
    "like",
    "looking",
    "make",
    "really",
    "recently",
    "remember",
    "should",
    "since",
    "some",
    "something",
    "thanks",
    "that",
    "them",
    "then",
    "there",
    "they",
    "thing",
    "things",
    "think",
    "thinking",
    "this",
    "time",
    "told",
    "want",
    "wanted",
    "was",
    "way",
    "week",
    "well",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "will",
    "with",
    "would",
    "your",
}


def _anchor_tokens(text: str) -> set[str]:
    return {
        tok
        for tok in re.findall(r"[a-z]+", text.casefold())
        if len(tok) > 2 and tok not in _GENERIC_TOKENS
    }


def _numeric_values_set(text: str) -> set[str]:
    return {m.group(0).lstrip("$").replace(",", "") for m in _NUMERIC_VALUE_RE.finditer(text)}


def _same_slot_numeric_conflict(text_a: str, text_b: str) -> bool:
    """Two statements describe the same fact slot but disagree on a number.

    Gate: ≥4 shared non-generic content tokens (the slot anchor, e.g.
    'pre-approved … Wells Fargo mortgage') and disjoint-in-part numeric values.
    """
    nums_a = _numeric_values_set(text_a)
    nums_b = _numeric_values_set(text_b)
    if not nums_a or not nums_b:
        return False
    if not (nums_a - nums_b) and not (nums_b - nums_a):
        return False
    shared = _anchor_tokens(text_a) & _anchor_tokens(text_b)
    return len(shared) >= 4


def _conflict_block(retrieved: list[RetrievedItem], question: str | None = None) -> str:
    """Surface same-slot numeric conflicts with their dates, newest first.

    v4-run fix (session 41698283): the previous version greedily paired the
    first two same-slot items and then ASSERTED "the value from the MOST
    RECENT date is the correct, current one". When the truly newest relevant
    memory (70-200mm lens, 2023-08-30) fell outside the pair, the block
    declared an older value (Sony 24-70mm, 2023-06-09) authoritative and the
    answerer obediently returned it. Three changes:

    1. Question gate: when the question has anchor tokens, a group member must
       share at least one of them, so off-topic numeric pairs never surface.
    2. Cluster completion: once a pair matches, every other dated numeric item
       sharing the slot with either member joins the group, so the group's
       newest is far more likely to BE the newest.
    3. Neutral wording: the block presents dated values as a hint and defers
       to the full retrieved memory, instead of overriding the model's own
       date comparison with a possibly-incomplete "correct" verdict.
    """
    numeric_items: list[tuple[date, RetrievedItem]] = []
    for hit in retrieved:
        if not _numeric_values_set(hit.item.text):
            continue
        parsed = parse_any_date(hit.item.timestamp)
        if parsed is not None:
            numeric_items.append((parsed, hit))
    q_anchors = _anchor_tokens(question or "")
    if q_anchors:
        numeric_items = [
            (d, hit) for d, hit in numeric_items if _anchor_tokens(hit.item.text) & q_anchors
        ]
    groups: list[list[tuple[date, RetrievedItem]]] = []
    used: set[int] = set()
    for i in range(len(numeric_items)):
        if i in used:
            continue
        for j in range(i + 1, len(numeric_items)):
            if j in used:
                continue
            if _same_slot_numeric_conflict(
                numeric_items[i][1].item.text, numeric_items[j][1].item.text
            ):
                group = [numeric_items[i], numeric_items[j]]
                used.update((i, j))
                # Cluster completion: pull in every remaining item that shares
                # the slot with any current member.
                for k in range(len(numeric_items)):
                    if k in used:
                        continue
                    if any(
                        _same_slot_numeric_conflict(
                            numeric_items[k][1].item.text, member[1].item.text
                        )
                        for member in group
                    ):
                        group.append(numeric_items[k])
                        used.add(k)
                groups.append(group)
                break
        if len(groups) >= 2:
            break
    blocks: list[str] = []
    if groups:
        lines = [
            "----- DIFFERING DATED VALUES (heuristic hint; may be incomplete) -----",
            "Some retrieved memories give different values for what may be the "
            "same fact. Compare their dates together with ALL other retrieved "
            "memories before answering; the most recent relevant evidence wins.",
        ]
        for group in groups:
            ordered = sorted(group, key=lambda entry: entry[0], reverse=True)
            for d, hit in ordered:
                lines.append(f"- {d.isoformat()}: {hit.item.text[:160]}")
        blocks.append("\n".join(lines))

    current_location = _current_location_block(question or "", retrieved)
    if current_location:
        blocks.append(current_location)
    return "\n".join(blocks)


def _current_location_block(question: str, retrieved: list[RetrievedItem]) -> str:
    q = question.casefold()
    if _requests_historical_memory(question):
        return ""
    if "where" not in q or not any(
        marker in q for marker in ("current", "currently", "now", "keep", "kept", "stored")
    ):
        return ""
    anchors = _anchor_tokens(question) - {
        "current",
        "currently",
        "keep",
        "kept",
        "store",
        "stored",
        "location",
        "place",
    }
    if not anchors:
        return ""
    location_re = re.compile(
        r"\b(?:in|inside|under|on|at)\s+(?:my|their|the|a|an)?\s+[a-z]",
        re.IGNORECASE,
    )
    candidates: list[tuple[datetime, float, RetrievedItem]] = []
    seen: set[tuple[str, int, str]] = set()
    for hit in retrieved:
        # Current-state claims must come from user-authored/extracted evidence;
        # assistant advice such as "you could store it under the bed" is not a
        # state update and must never win merely because it is newer.
        if hit.item.role != "user":
            continue
        key = (hit.item.session_id, hit.item.turn_idx, hit.item.text)
        if key in seen:
            continue
        seen.add(key)
        d = parse_any_date(hit.item.timestamp)
        if d is None:
            continue
        shared = anchors & _anchor_tokens(hit.item.text)
        if not shared:
            continue
        text_l = hit.item.text.casefold()
        if (
            not location_re.search(hit.item.text)
            and "stored" not in text_l
            and "storing" not in text_l
        ):
            continue
        score = len(shared) + float(hit.score)
        candidates.append((datetime.combine(d, datetime.min.time()), score, hit))
    if not candidates:
        return ""
    candidates.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    lines = [
        "----- CURRENT LOCATION CANDIDATES -----",
        "The question asks for a current location. Use the most recent dated matching memory.",
    ]
    for d, _, hit in candidates[:4]:
        lines.append(f"- {d.date().isoformat()}: {hit.item.text[:160]}")
    newest_date, _, newest_hit = candidates[0]
    lines.append(f"Most recent ({newest_date.date().isoformat()}): {newest_hit.item.text[:160]}")
    return "\n".join(lines)


def _normalize_for_dedup(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _is_duplicate_text(candidate_text: str, prior_text: str) -> bool:
    """True when the candidate is a near-verbatim restatement of the prior.

    Used only to suppress a redundant KEEP insertion. Intentionally strict
    (normalized exact match) so distinct facts are never discarded — the prior
    is the newest same-type memory, which is frequently unrelated to the
    candidate, so anything looser would resurrect the silent-drop bug.
    """
    return _normalize_for_dedup(candidate_text) == _normalize_for_dedup(prior_text)


def _is_exact_unknown(text: str) -> bool:
    return text.strip() == "Unknown"


_CURRENCY_WS_RE = re.compile(r"[,$€£¥\s]")
_NONWORD_RE = re.compile(r"[^\w]")
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)
_NUMBER_IN_TEXT_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _parse_json_array(text: str) -> list[Any]:
    """Extract the first JSON array from a (possibly fenced) completion.

    The aggregation scaffold (docx §4 fix 4) asks for a bare JSON array, but
    small models sometimes wrap it in prose or a code fence. Grab the outermost
    [...] span and parse it; return [] on any failure so the scaffold degrades
    gracefully to the plain answerer.
    """
    if not text:
        return []
    match = _JSON_ARRAY_RE.search(text)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _coerce_number(value: Any) -> float | None:
    """Best-effort numeric coercion for scaffold values ('$1,300' -> 1300.0)."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = _NUMBER_IN_TEXT_RE.search(value)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _format_scaffold_number(value: float) -> str:
    """Render a scaffold total without a trailing '.0' for whole numbers."""
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}"


def _answers_equivalent(a: str, b: str) -> bool:
    """Loose agreement test for computation-bypass verification (docx §4 fix 5).

    Agreement means the LLM independently reached the deterministic value. Tries
    a numeric compare first (stripping currency symbols / thousands separators),
    then a punctuation-insensitive string compare with substring tolerance so
    "$50" == "50 dollars" and "Target" == "target." count as agreement while a
    real mismatch ("$120" vs "$50") does not.
    """
    ta = (a or "").strip().lower()
    tb = (b or "").strip().lower()
    if not ta or not tb:
        return False
    na = _CURRENCY_WS_RE.sub("", ta)
    nb = _CURRENCY_WS_RE.sub("", tb)
    try:
        if float(na) == float(nb):
            return True
    except ValueError:
        pass
    sa = _NONWORD_RE.sub("", ta)
    sb = _NONWORD_RE.sub("", tb)
    if not sa or not sb:
        return False
    return sa == sb or sa in sb or sb in sa


_ANSWER_ALNUM_RE = re.compile(r"\w", re.UNICODE)


def _looks_degenerate_answer(text: str) -> bool:
    """Non-empty answer carrying no alphanumeric content (e.g. a bare ``$``).

    Mirrors ``ksa.eval.longmemeval.looks_degenerate_answer`` but is kept local so
    the hot answer path takes on no eval-module import. This is the
    silent-truncation signature behind session 852ce960 ("$" instead of
    "$400,000"): a saturated context window left no room to generate. A genuine
    one-character answer such as "3" or "A" has an alphanumeric character and is
    NOT degenerate, so counting answers are never misclassified.
    """
    t = text.strip()
    return bool(t) and _ANSWER_ALNUM_RE.search(t) is None


def _answer_needs_retry(text: str) -> bool:
    """True when an answer should trigger the (opt-in) answer-retry pass.

    Fires for an exact 'Unknown', an empty answer, or a degenerate bare-symbol
    answer ('$'). Extracted as a named predicate so the trigger is unit-testable
    independently of the full pipeline.
    """
    return _is_exact_unknown(text) or not text.strip() or _looks_degenerate_answer(text)


def _expand_retrieval_neighbors(
    retrieved: list[RetrievedItem],
    items: list[RetrievalMemoryItem],
    *,
    window: int,
    corpus: Mapping[str, LongMemEvalSession] | None = None,
) -> list[RetrievedItem]:
    out = list(retrieved)
    seen = {(hit.item.session_id, hit.item.turn_idx, hit.item.text) for hit in retrieved}
    for hit in retrieved:
        neighbors = [
            item
            for item in items
            if item.session_id == hit.item.session_id
            and abs(item.turn_idx - hit.item.turn_idx) <= window
            and (item.session_id, item.turn_idx, item.text) not in seen
        ]
        neighbors.sort(key=lambda item: (abs(item.turn_idx - hit.item.turn_idx), item.turn_idx))
        for item in neighbors:
            seen.add((item.session_id, item.turn_idx, item.text))
            out.append(
                RetrievedItem(
                    item=item,
                    score=hit.score,
                    rank=len(out),
                )
            )
        if corpus is None:
            continue
        support = corpus.get(hit.item.session_id)
        if support is None:
            continue
        raw_neighbors = [
            RetrievalMemoryItem(
                text=turn.content,
                role=turn.role,
                session_id=support.session_id,
                turn_idx=idx,
                timestamp=turn.timestamp,
            )
            for idx, turn in enumerate(support.turns)
            if turn.role == "user"
            and abs(idx - hit.item.turn_idx) <= window
            and (support.session_id, idx, turn.content) not in seen
        ]
        raw_neighbors.sort(key=lambda item: (abs(item.turn_idx - hit.item.turn_idx), item.turn_idx))
        for item in raw_neighbors:
            seen.add((item.session_id, item.turn_idx, item.text))
            out.append(
                RetrievedItem(
                    item=item,
                    score=hit.score,
                    rank=len(out),
                )
            )
    return out


def _fingerprint(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_key(payload: Mapping[str, Any]) -> str:
    return _fingerprint(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        fh.write("\n")


def _component_model_id(component: Any) -> str:
    for obj in (
        component,
        getattr(component, "llm", None),
        getattr(getattr(component, "llm", None), "inner", None),
        getattr(component, "inner", None),
    ):
        model_id = getattr(obj, "model_id", None)
        if model_id:
            return str(model_id)
    return type(component).__qualname__


def _trace_model_id(responses: Any) -> str | None:
    if not isinstance(responses, list):
        return None
    for response in responses:
        if isinstance(response, Mapping):
            model_id = response.get("model_id")
            if model_id:
                return str(model_id)
    return None


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def _next_jsonl_id(path: Path | None) -> int:
    if path is None or not path.exists():
        return 1
    max_id = 0
    for row in _iter_jsonl(path):
        value = row.get("id")
        if isinstance(value, int):
            max_id = max(max_id, value)
    return max_id + 1


def _current_turn_from_extraction_prompt(prompt: str) -> dict[str, Any] | None:
    marker = "Current turn:\n"
    start = prompt.find(marker)
    if start < 0:
        return None
    start += len(marker)
    end = prompt.find("\n\nNext turn:", start)
    if end < 0:
        return None
    try:
        turn = json.loads(prompt[start:end].strip())
    except json.JSONDecodeError:
        return None
    return turn if isinstance(turn, dict) else None
