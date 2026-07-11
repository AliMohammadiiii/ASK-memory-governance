"""Two-stage relation classifier built on `StructuredLLM.generate_json`."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Template

from ..inference.llm import LLM, LLMResponse, StructuredLLM
from .schema import (
    CandidateMemory,
    PriorMemory,
    RelationOutput,
    Stage1Output,
    Stage2Output,
)


class _ResponseTraceLLM:
    """Record successful responses so transport failures are distinguishable."""

    def __init__(self, inner: LLM) -> None:
        self.inner = inner
        self.model_id = inner.model_id
        self.responses: list[LLMResponse] = []

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        response = self.inner.generate(prompt, **kwargs)
        self.responses.append(response)
        return response


class RelationClassifier:
    """Classify candidate-vs-prior memory relation through two JSON prompts."""

    def __init__(
        self,
        llm: StructuredLLM,
        stage1_template: str,
        stage2_template: str,
        *,
        log_path: str | Path | None = None,
    ) -> None:
        self.llm = llm
        self.stage1_template = stage1_template
        self.stage2_template = stage2_template
        self.log_path = Path(log_path) if log_path is not None else None

    @classmethod
    def from_template_files(
        cls,
        llm: StructuredLLM,
        stage1_prompt_path: str | Path,
        stage2_prompt_path: str | Path,
        *,
        log_path: str | Path | None = None,
    ) -> RelationClassifier:
        return cls(
            llm=llm,
            stage1_template=Path(stage1_prompt_path).read_text(encoding="utf-8"),
            stage2_template=Path(stage2_prompt_path).read_text(encoding="utf-8"),
            log_path=log_path,
        )

    def classify(
        self,
        candidate: CandidateMemory | Mapping[str, Any],
        prior: PriorMemory | Mapping[str, Any],
        *,
        max_new_tokens: int = 128,
        temperature: float = 0.0,
        seed: int = 0,
    ) -> RelationOutput:
        candidate_model = (
            candidate
            if isinstance(candidate, CandidateMemory)
            else CandidateMemory.model_validate(candidate)
        )
        prior_model = prior if isinstance(prior, PriorMemory) else PriorMemory.model_validate(prior)
        tracer = _ResponseTraceLLM(self.llm.inner)
        traced_llm = StructuredLLM(
            tracer, max_repair_tokens=self.llm.max_repair_tokens
        )

        prompt1 = self._render_stage1(candidate_model, prior_model)
        response_count_before = _response_count(traced_llm)
        try:
            stage1 = traced_llm.generate_json(
                prompt1,
                Stage1Output,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                seed=seed,
            )
        except Exception as exc:
            stage1_responses = _responses_since(traced_llm, response_count_before)
            output = RelationOutput(
                logical_relation="independent",
                temporal="unknown",
                same_subject=False,
                relation_to_prior_state="unclear",
                stage1_rationale=f"fallback: stage-1 parse failed: {exc}",
                stage2_rationale="fallback: stage 2 skipped after stage-1 parse failure",
            )
            self._write_trace(
                candidate_model,
                prior_model,
                prompt1,
                "",
                stage1_responses,
                [],
                output,
                seed,
                temperature,
                stage1=None,
                raw_stage2=None,
                routed_stage2=None,
                deterministic_routing_reason="stage1_parse_fallback",
            )
            if not stage1_responses:
                # A provider/transport outage is not semantic evidence for an
                # independent relation. Abort this session so shard retry/resume
                # can obtain a real classification instead of caching a Keep.
                raise
            return output
        stage1_responses = _responses_since(traced_llm, response_count_before)

        prompt2 = self._render_stage2(candidate_model, prior_model, stage1)
        response_count_before = _response_count(traced_llm)
        try:
            stage2 = traced_llm.generate_json(
                prompt2,
                Stage2Output,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                seed=seed,
            )
        except Exception as exc:
            stage2_responses = _responses_since(traced_llm, response_count_before)
            stage2 = Stage2Output(
                temporal="unknown",
                same_subject=False,
                rationale=f"fallback: stage-2 parse failed: {exc}",
            )
            if not stage2_responses:
                output = RelationOutput(
                    logical_relation=stage1.logical_relation,
                    temporal=stage2.temporal,
                    same_subject=stage2.same_subject,
                    relation_to_prior_state="unclear",
                    stage1_rationale=stage1.rationale,
                    stage2_rationale=stage2.rationale,
                )
                self._write_trace(
                    candidate_model,
                    prior_model,
                    prompt1,
                    prompt2,
                    stage1_responses,
                    stage2_responses,
                    output,
                    seed,
                    temperature,
                    stage1=stage1,
                    raw_stage2=stage2,
                    routed_stage2=stage2,
                    deterministic_routing_reason="stage2_unavailable",
                )
                raise
        raw_stage2 = stage2
        stage2 = _override_temporal_from_timestamps(candidate_model, prior_model, stage2)
        stage2 = _override_same_subject_for_timestamped_relation(
            candidate_model,
            prior_model,
            stage1,
            stage2,
        )
        stage2_responses = _responses_since(traced_llm, response_count_before)

        output = RelationOutput(
            logical_relation=stage1.logical_relation,
            temporal=stage2.temporal,
            same_subject=stage2.same_subject,
            relation_to_prior_state=_final_relation(stage1, stage2, candidate_model, prior_model),
            stage1_rationale=stage1.rationale,
            stage2_rationale=stage2.rationale,
        )
        routing_reason = _routing_reason(stage1, raw_stage2, stage2, output)
        self._write_trace(
            candidate_model,
            prior_model,
            prompt1,
            prompt2,
            stage1_responses,
            stage2_responses,
            output,
            seed,
            temperature,
            stage1=stage1,
            raw_stage2=raw_stage2,
            routed_stage2=stage2,
            deterministic_routing_reason=routing_reason,
        )
        return output

    def _render_stage1(self, candidate: CandidateMemory, prior: PriorMemory) -> str:
        return Template(self.stage1_template).render(
            candidate=candidate.model_dump(),
            prior=prior.model_dump(),
        )

    def _render_stage2(
        self,
        candidate: CandidateMemory,
        prior: PriorMemory,
        stage1: Stage1Output,
    ) -> str:
        return Template(self.stage2_template).render(
            candidate=candidate.model_dump(),
            prior=prior.model_dump(),
            stage1=stage1.model_dump(),
        )

    def _write_trace(
        self,
        candidate: CandidateMemory,
        prior: PriorMemory,
        prompt1: str,
        prompt2: str,
        stage1_responses: list[LLMResponse],
        stage2_responses: list[LLMResponse],
        output: RelationOutput,
        seed: int,
        temperature: float,
        *,
        stage1: Stage1Output | None = None,
        raw_stage2: Stage2Output | None = None,
        routed_stage2: Stage2Output | None = None,
        deterministic_routing_reason: str | None = None,
    ) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "candidate": candidate.model_dump(),
            "prior": prior.model_dump(),
            "stage1_prompt": prompt1,
            "stage2_prompt": prompt2,
            "stage1_responses": [r.to_dict() for r in stage1_responses],
            "stage2_responses": [r.to_dict() for r in stage2_responses],
            "raw_stage1_label": stage1.logical_relation if stage1 is not None else None,
            "raw_stage2_temporal": raw_stage2.temporal if raw_stage2 is not None else None,
            "raw_stage2_same_subject": raw_stage2.same_subject if raw_stage2 is not None else None,
            "routed_stage2_temporal": routed_stage2.temporal if routed_stage2 is not None else None,
            "routed_stage2_same_subject": (
                routed_stage2.same_subject if routed_stage2 is not None else None
            ),
            "final_routed_relation": output.relation_to_prior_state,
            "deterministic_routing_reason": deterministic_routing_reason,
            "output": output.model_dump(),
            "seed": seed,
            "temperature": temperature,
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


def _final_relation(
    stage1: Stage1Output,
    stage2: Stage2Output,
    candidate: CandidateMemory | None = None,
    prior: PriorMemory | None = None,
) -> str:
    if stage1.logical_relation == "independent":
        return "unclear"

    if stage2.same_subject and stage2.temporal == "newer":
        if stage1.logical_relation == "contradict":
            return "supersede"
        if _is_material_timestamped_update(candidate, prior):
            return "supersede"
    if stage1.logical_relation == "support":
        return "support"
    return "contradict"


def _routing_reason(
    stage1: Stage1Output,
    raw_stage2: Stage2Output,
    routed_stage2: Stage2Output,
    output: RelationOutput,
) -> str:
    reasons: list[str] = []
    if raw_stage2.temporal != routed_stage2.temporal:
        reasons.append("timestamp_override")
    if raw_stage2.same_subject != routed_stage2.same_subject:
        reasons.append("same_subject_override")
    if stage1.logical_relation == "independent" and output.relation_to_prior_state == "unclear":
        reasons.append("independent_routes_to_unclear")
    if stage1.logical_relation == "support" and output.relation_to_prior_state == "supersede":
        reasons.append("material_timestamped_update_routes_to_supersede")
    if not reasons:
        reasons.append("prompt_labels_used")
    return "+".join(reasons)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _override_temporal_from_timestamps(
    candidate: CandidateMemory,
    prior: PriorMemory,
    stage2: Stage2Output,
) -> Stage2Output:
    candidate_time = _parse_timestamp(candidate.timestamp)
    prior_time = _parse_timestamp(prior.timestamp)
    if candidate_time is None or prior_time is None:
        return stage2

    if candidate_time > prior_time:
        temporal = "newer"
    elif candidate_time < prior_time:
        temporal = "older"
    else:
        temporal = "same"

    if temporal == stage2.temporal:
        return stage2

    return Stage2Output(
        temporal=temporal,
        same_subject=stage2.same_subject,
        rationale=(
            f"{stage2.rationale} Timestamp override: candidate timestamp "
            f"{candidate.timestamp!r} is {temporal} than prior timestamp {prior.timestamp!r}."
        ),
    )


def _override_same_subject_for_timestamped_relation(
    candidate: CandidateMemory,
    prior: PriorMemory,
    stage1: Stage1Output,
    stage2: Stage2Output,
) -> Stage2Output:
    if stage2.same_subject or stage1.logical_relation == "independent":
        return stage2
    if candidate.type_guess != prior.type:
        return stage2
    if _parse_timestamp(candidate.timestamp) is None or _parse_timestamp(prior.timestamp) is None:
        return stage2

    return Stage2Output(
        temporal=stage2.temporal,
        same_subject=True,
        rationale=(
            f"{stage2.rationale} Same-subject override: the pair has the same "
            "memory type, explicit timestamps, and a non-independent logical relation."
        ),
    )


def _is_material_timestamped_update(
    candidate: CandidateMemory | None,
    prior: PriorMemory | None,
) -> bool:
    if candidate is None or prior is None:
        return False
    candidate_time = _parse_timestamp(candidate.timestamp)
    prior_time = _parse_timestamp(prior.timestamp)
    if candidate_time is None or prior_time is None or candidate_time <= prior_time:
        return False
    if candidate.type_guess != prior.type:
        return False
    return _normalize_memory_text(candidate.text) != _normalize_memory_text(prior.text)


def _normalize_memory_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _response_count(llm: StructuredLLM) -> int:
    responses = getattr(llm.inner, "responses", None)
    return len(responses) if isinstance(responses, list) else 0


def _responses_since(llm: StructuredLLM, start: int) -> list[LLMResponse]:
    responses = getattr(llm.inner, "responses", None)
    if not isinstance(responses, list):
        return []
    return responses[start:]
