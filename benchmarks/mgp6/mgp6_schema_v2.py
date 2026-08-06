"""Pydantic schema for the MGP-6 v2 diagnostic dataset."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Action = Literal["KEEP", "SUPERSEDE", "ABSTAIN"]
MemoryType = Literal["stable_pref", "transient_pref", "episodic_fact"]
MemoryStatus = Literal["active", "superseded"]
Role = Literal["user", "assistant", "system", "tool"]
EvidenceSource = Literal[
    "direct_user_assertion",
    "assistant_claim",
    "quoted_third_party",
    "tool_output",
    "extractor_candidate",
    "mixed",
    "ambiguous",
]
SourceReliability = Literal["high", "medium", "low", "garbled", "unknown"]
TemporalScope = Literal["durable", "temporary", "vague", "unknown"]
Difficulty = Literal["easy", "medium", "hard", "adversarial"]
QueryMode = Literal["direct_recall", "premise_resistance", "implicit_application"]
Split = Literal["train", "dev", "test"]

# Reserved for a future schema version; v2 examples cannot use these labels.
RESERVED_ACTIONS = frozenset({"FORGET"})
RESERVED_STATUSES = frozenset({"forgotten"})
RULE_IDS = frozenset(f"R{i}" for i in range(1, 11))


def memory_value(text: str) -> str:
    """Return the value from the dataset's auditable ``slot = value`` text."""
    return text.split(" = ", 1)[1].strip() if " = " in text else text.strip()


class DialogueTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role
    content: str = Field(min_length=1)


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: MemoryType
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    status: MemoryStatus
    supersedes_id: str | None = None
    valid_from: str | None = None
    semantic_slot: str = Field(min_length=1)
    source: EvidenceSource | None = None

    @model_validator(mode="after")
    def validate_record(self) -> MemoryRecord:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.semantic_slot):
            raise ValueError("semantic_slot must be lower snake_case")
        if " = " not in self.text:
            raise ValueError("memory text must use the auditable 'slot = value' form")
        text_slot, value = self.text.split(" = ", 1)
        if text_slot != self.semantic_slot or not value.strip():
            raise ValueError("memory text slot must match semantic_slot and have a value")
        if self.status == "superseded" and self.supersedes_id is not None:
            raise ValueError("a superseded record cannot supersede another record in v2")
        return self


class JudgeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include: list[str] = Field(min_length=1)
    not_include: list[str] = Field(default_factory=list)
    notes: str = Field(min_length=1)

    @field_validator("include", "not_include")
    @classmethod
    def validate_regexes(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            if not pattern:
                raise ValueError("judge regexes cannot be empty")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid judge regex {pattern!r}: {exc}") from exc
        return patterns


def _validate_memory_state(
    state_name: str,
    state: list[MemoryRecord],
    semantic_slot: str,
) -> None:
    ids = [record.id for record in state]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate memory id in {state_name}")
    if any(record.semantic_slot != semantic_slot for record in state):
        raise ValueError(f"all {state_name} records must use the example slot")
    if not any(record.status == "active" for record in state):
        raise ValueError(f"{state_name} needs at least one active memory")
    state_by_id = {record.id: record for record in state}
    for record in state:
        if record.supersedes_id is None:
            continue
        target = state_by_id.get(record.supersedes_id)
        if target is None:
            raise ValueError(f"dangling supersedes_id in {state_name}: {record.supersedes_id}")
        if target.status != "superseded" or target.id == record.id:
            raise ValueError(
                f"{state_name} supersedes_id must target a different superseded record"
            )
    stable_active = [
        record for record in state if record.type == "stable_pref" and record.status == "active"
    ]
    if any(record.type == "stable_pref" for record in state) and len(stable_active) != 1:
        raise ValueError(f"{state_name} must have exactly one active stable memory for the slot")


def _validate_supersede_transition(
    initial_memory_state: list[MemoryRecord],
    gold_memory_state: list[MemoryRecord],
    active: list[MemoryRecord],
) -> None:
    initial_active = {
        record.id: record for record in initial_memory_state if record.status == "active"
    }
    replaced = [
        record
        for record in gold_memory_state
        if record.id in initial_active and record.status == "superseded"
    ]
    successors = [record for record in active if record.supersedes_id in initial_active]
    if len(replaced) != 1 or len(successors) != 1:
        raise ValueError("SUPERSEDE requires exactly one retained predecessor and one successor")
    predecessor = replaced[0]
    initial_predecessor = initial_active[predecessor.id]
    if predecessor.model_copy(update={"status": "active"}) != initial_predecessor:
        raise ValueError("SUPERSEDE may change only the predecessor status")
    successor = successors[0]
    if successor.supersedes_id != predecessor.id or successor.type != predecessor.type:
        raise ValueError("SUPERSEDE successor must replace the retained same-type predecessor")
    if memory_value(successor.text).casefold() == memory_value(predecessor.text).casefold():
        raise ValueError("SUPERSEDE successor must contain a different value")


def _validate_keep_transition(
    initial_memory_state: list[MemoryRecord],
    active: list[MemoryRecord],
) -> None:
    initial_active = {
        record.id: record for record in initial_memory_state if record.status == "active"
    }
    gold_active = {record.id: record for record in active}
    if any(record_id not in gold_active for record_id in initial_active):
        raise ValueError("KEEP must preserve every initially active memory")
    if any(gold_active[record_id] != record for record_id, record in initial_active.items()):
        raise ValueError("KEEP may not mutate a preserved active memory")
    added = [record for record in active if record.id not in initial_active]
    if any(record.type != "transient_pref" for record in added):
        raise ValueError("KEEP may add only a separate transient_pref")
    if any(record.supersedes_id is not None for record in added):
        raise ValueError("a transient KEEP record cannot supersede durable memory")


def _validate_answer_contract(
    expected: str,
    forbidden_patterns: list[str],
    judge_spec: JudgeSpec,
    active: list[MemoryRecord],
    gold_memory_state: list[MemoryRecord],
) -> None:
    if any(re.search(pattern, expected) for pattern in forbidden_patterns):
        raise ValueError("expected_answer matches a forbidden pattern")
    if not set(forbidden_patterns).issubset(judge_spec.not_include):
        raise ValueError("judge_spec.not_include must contain all forbidden patterns")
    if not all(re.search(pattern, expected) for pattern in judge_spec.include):
        raise ValueError("expected_answer must match every judge_spec.include regex")
    if any(re.search(pattern, expected) for pattern in judge_spec.not_include):
        raise ValueError("expected_answer matches judge_spec.not_include")
    active_values = [memory_value(record.text) for record in active]
    if not any(value.casefold() in expected.casefold() for value in active_values):
        raise ValueError("expected_answer must use at least one active memory value")
    stale_values = [
        memory_value(record.text) for record in gold_memory_state if record.status == "superseded"
    ]
    for value in stale_values:
        if value.casefold() in expected.casefold():
            raise ValueError("expected_answer uses a superseded value")
        if not any(re.search(pattern, value) for pattern in judge_spec.not_include):
            raise ValueError("judge_spec.not_include must cover every superseded value")


class MGP6Example(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1)
    version: Literal["mgp6_v2"] = "mgp6_v2"
    type: Literal["T1", "T2", "T3", "T4", "T5", "T6"]
    subtype: str = Field(min_length=1)
    difficulty: Difficulty = "medium"

    base_dialogue_prefix: list[DialogueTurn] = Field(min_length=1)
    initial_memory_state: list[MemoryRecord] = Field(min_length=1)
    perturbation_event: str = Field(min_length=1)

    evidence_source: EvidenceSource
    source_reliability: SourceReliability
    temporal_scope: TemporalScope
    semantic_slot: str = Field(min_length=1)
    conflict_type: str = Field(min_length=1)
    memory_age: str = Field(min_length=1)

    gold_action: Action
    gold_memory_state: list[MemoryRecord] = Field(min_length=1)

    query_mode: QueryMode = "direct_recall"
    evaluation_query: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    forbidden_answer_patterns: list[str] = Field(default_factory=list)
    judge_spec: JudgeSpec

    rationale_notes: str = Field(min_length=1)
    annotation_rule_ids: list[str] = Field(min_length=1)
    template_family_id: str = Field(min_length=1)
    minimal_pair_group_id: str | None = None
    split: Split
    quality_flags: list[str] = Field(default_factory=list)

    @field_validator("annotation_rule_ids")
    @classmethod
    def validate_rules(cls, rules: list[str]) -> list[str]:
        unknown = sorted(set(rules) - RULE_IDS)
        if unknown:
            raise ValueError(f"unknown annotation rule ids: {unknown}")
        if len(rules) != len(set(rules)):
            raise ValueError("annotation_rule_ids contains duplicates")
        return rules

    @field_validator("forbidden_answer_patterns")
    @classmethod
    def validate_forbidden_regexes(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            if not pattern:
                raise ValueError("forbidden patterns cannot be empty")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid forbidden regex {pattern!r}: {exc}") from exc
        return patterns

    @model_validator(mode="after")
    def validate_example(self) -> MGP6Example:
        expected = self.expected_answer.strip()
        if not expected:
            raise ValueError("expected_answer cannot be blank")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.semantic_slot):
            raise ValueError("example semantic_slot must be lower snake_case")
        for state_name, state in (
            ("initial_memory_state", self.initial_memory_state),
            ("gold_memory_state", self.gold_memory_state),
        ):
            _validate_memory_state(state_name, state, self.semantic_slot)
        active = [record for record in self.gold_memory_state if record.status == "active"]
        if self.gold_action == "SUPERSEDE":
            _validate_supersede_transition(
                self.initial_memory_state,
                self.gold_memory_state,
                active,
            )
        elif self.gold_action == "KEEP":
            _validate_keep_transition(self.initial_memory_state, active)
        elif self.gold_memory_state != self.initial_memory_state:
            raise ValueError("ABSTAIN must leave the memory state unchanged")
        _validate_answer_contract(
            expected,
            self.forbidden_answer_patterns,
            self.judge_spec,
            active,
            self.gold_memory_state,
        )
        return self


__all__ = [
    "RESERVED_ACTIONS",
    "RESERVED_STATUSES",
    "DialogueTurn",
    "JudgeSpec",
    "MGP6Example",
    "MemoryRecord",
    "memory_value",
]
