"""Pydantic schema and loader for the MGP-6 scenario slice."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MGP6Type = Literal["T1", "T2", "T3", "T4", "T5", "T6"]
MGP6GoldAction = Literal["KEEP", "SUPERSEDE", "ABSTAIN"]
MGP6MemoryType = Literal["stable_pref", "transient_pref", "episodic_fact"]
MGP6MemoryStatus = Literal["active", "superseded"]


class MGP6MemoryItem(BaseModel):
    """Memory-state row embedded in a scenario."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: MGP6MemoryType
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    status: MGP6MemoryStatus = "active"
    supersedes_id: str | None = None
    valid_from: str | None = None


class MGP6Scenario(BaseModel):
    """One MGP-6 perturbation scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(pattern=r"^MGP6-T[1-6]-\d{2}$")
    type: MGP6Type
    base_dialogue_prefix: list[dict[str, str]] = Field(min_length=1)
    initial_memory_state: list[MGP6MemoryItem]
    perturbation_event: str = Field(min_length=1)
    gold_memory_state: list[MGP6MemoryItem]
    gold_action: MGP6GoldAction
    evaluation_query: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    rationale_notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def _scenario_id_matches_type(self) -> MGP6Scenario:
        prefix = f"MGP6-{self.type}-"
        if not self.scenario_id.startswith(prefix):
            raise ValueError(f"scenario_id must start with {prefix!r}")
        for i, turn in enumerate(self.base_dialogue_prefix):
            if turn.get("role") not in {"user", "assistant"}:
                raise ValueError(f"base_dialogue_prefix[{i}] role must be user/assistant")
            if not turn.get("content"):
                raise ValueError(f"base_dialogue_prefix[{i}] content is required")
        return self


class MGP6AdvisorScenario(BaseModel):
    """Cold advisor-facing scenario without student gold labels."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(pattern=r"^MGP6-T[1-6]-\d{2}$")
    type: MGP6Type
    base_dialogue_prefix: list[dict[str, str]] = Field(min_length=1)
    initial_memory_state: list[MGP6MemoryItem]
    perturbation_event: str = Field(min_length=1)
    evaluation_query: str = Field(min_length=1)


class MGP6AdvisorAnnotation(BaseModel):
    """Advisor-produced gold fields for one cold scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(pattern=r"^MGP6-T[1-6]-\d{2}$")
    gold_memory_state: list[MGP6MemoryItem]
    gold_action: MGP6GoldAction
    expected_answer: str = Field(min_length=1)


def load_mgp6_jsonl(path: str | Path) -> list[MGP6Scenario]:
    """Load and validate an MGP-6 JSONL file."""
    scenarios: list[MGP6Scenario] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_no}: invalid JSON") from exc
            try:
                scenarios.append(MGP6Scenario.model_validate(raw))
            except Exception as exc:
                raise ValueError(f"line {line_no}: invalid MGP-6 scenario") from exc
    return scenarios


def validate_mgp6_coverage(scenarios: list[MGP6Scenario]) -> None:
    """Assert the MGP-6 v1 coverage contract: 60 rows, 10 per type, unique ids."""
    ids = [scenario.scenario_id for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate scenario_id found")
    if len(scenarios) != 60:
        raise ValueError(f"expected 60 scenarios; got {len(scenarios)}")
    counts = Counter(scenario.type for scenario in scenarios)
    expected = {f"T{i}": 10 for i in range(1, 7)}
    if dict(counts) != expected:
        raise ValueError(f"expected 10 scenarios per type; got {dict(counts)}")


def strip_for_advisor(scenario: MGP6Scenario) -> MGP6AdvisorScenario:
    """Return the cold advisor-facing view of a student-authored scenario."""
    return MGP6AdvisorScenario(
        scenario_id=scenario.scenario_id,
        type=scenario.type,
        base_dialogue_prefix=scenario.base_dialogue_prefix,
        initial_memory_state=scenario.initial_memory_state,
        perturbation_event=scenario.perturbation_event,
        evaluation_query=scenario.evaluation_query,
    )
