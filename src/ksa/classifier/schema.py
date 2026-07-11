"""Pydantic contracts for the two-stage relation classifier."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MemoryType = Literal["stable_pref", "transient_pref", "episodic_fact"]
LogicalRelation = Literal["support", "contradict", "independent"]
TemporalRelation = Literal["newer", "older", "same", "unknown"]
FinalRelation = Literal["support", "contradict", "supersede", "unclear"]


class CandidateMemory(BaseModel):
    """Candidate memory emitted by the extractor."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    type_guess: MemoryType
    source_turn: str | None = None
    session_id: str | None = None
    turn_id: str | None = None
    timestamp: str | None = None


class PriorMemory(BaseModel):
    """Retrieved active memory item to compare against a candidate."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    type: MemoryType
    memory_id: str | None = None
    timestamp: str | None = None


_RATIONALE_OMITTED = "(rationale omitted by model)"


def _default_missing_rationale(data: Any, *fields: str) -> Any:
    """Fill rationale fields the model omitted while keeping the decision label.

    The substantive classifier signal is the relation/temporal label, not the
    free-text rationale. Small local models routinely emit the label without a
    rationale; strict validation would then reject the whole stage, fall back to
    ``independent``/``unclear``, and silently turn a real contradiction into a
    Keep. Defaulting only the explanatory text preserves the label while still
    rejecting outputs that are missing the actual decision fields.
    """
    if not isinstance(data, dict):
        return data
    patched = None
    for field in fields:
        if not data.get(field):
            patched = dict(data) if patched is None else patched
            patched[field] = _RATIONALE_OMITTED
    return patched if patched is not None else data


class Stage1Output(BaseModel):
    """Logical relation before temporal/update interpretation."""

    model_config = ConfigDict(extra="forbid")

    logical_relation: LogicalRelation
    rationale: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _fill_rationale(cls, data: Any) -> Any:
        return _default_missing_rationale(data, "rationale")


class Stage2Output(BaseModel):
    """Temporal and subject qualifier for the logical relation."""

    model_config = ConfigDict(extra="forbid")

    temporal: TemporalRelation
    same_subject: bool
    rationale: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _fill_rationale(cls, data: Any) -> Any:
        return _default_missing_rationale(data, "rationale")


class RelationOutput(BaseModel):
    """Combined two-stage classifier result."""

    model_config = ConfigDict(extra="forbid")

    logical_relation: LogicalRelation
    temporal: TemporalRelation
    same_subject: bool
    relation_to_prior_state: FinalRelation
    stage1_rationale: str
    stage2_rationale: str

    @model_validator(mode="before")
    @classmethod
    def _fill_rationale(cls, data: Any) -> Any:
        return _default_missing_rationale(data, "stage1_rationale", "stage2_rationale")
