"""Pydantic schema for precision-biased memory extraction."""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MemoryTypeGuess = Literal["stable_pref", "transient_pref", "episodic_fact"]


class EvidenceSpan(BaseModel):
    """Location of the source text supporting one extracted item."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    turn_idx: int = Field(ge=0)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)

    @field_validator("char_start", mode="before")
    @classmethod
    def _coerce_char_start(cls, value: Any) -> Any:
        return _coerce_span_boundary(value, mode="floor")

    @field_validator("char_end", mode="before")
    @classmethod
    def _coerce_char_end(cls, value: Any) -> Any:
        return _coerce_span_boundary(value, mode="ceil")

    @model_validator(mode="after")
    def _span_is_ordered(self) -> EvidenceSpan:
        if self.char_end < self.char_start:
            raise ValueError("char_end must be greater than or equal to char_start")
        return self


class ExtractedItem(BaseModel):
    """One candidate MemoryItem row emitted by the extractor."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    type_guess: MemoryTypeGuess
    evidence_span: EvidenceSpan
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    negation_marker: bool
    hedge_marker: bool
    polarity_subject: str | None = None


class ExtractionOutput(BaseModel):
    """Structured output for one turn-level extraction call."""

    model_config = ConfigDict(extra="forbid")

    items: list[ExtractedItem]
    no_extractable_content: bool
    coverage_note: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _default_no_extractable_content(cls, data: Any) -> Any:
        """Infer ``no_extractable_content`` when the model omits it.

        Small instruction-tuned extractors frequently emit a valid
        ``{"items": [...]}`` object without the required
        ``no_extractable_content`` flag. Strict validation would then reject a
        genuinely good extraction, the repair retry collapses to an empty
        ``no_extractable_content: true`` answer, and the real items are lost
        (confirmed on 46/60 MGP-6 scenarios in runs/m4w14). Filling the flag
        from the items list here keeps the extraction instead of discarding it.

        This only fills a *missing* field; an explicit but inconsistent flag is
        still rejected by ``_no_content_matches_items`` so genuinely malformed
        outputs stay strict.
        """
        if (
            isinstance(data, dict)
            and "no_extractable_content" not in data
            and isinstance(data.get("items"), list)
        ):
            data = dict(data)
            data["no_extractable_content"] = len(data["items"]) == 0
        return data

    @model_validator(mode="after")
    def _no_content_matches_items(self) -> ExtractionOutput:
        if self.items and self.no_extractable_content:
            raise ValueError("no_extractable_content must be false when items are present")
        if not self.items and not self.no_extractable_content:
            raise ValueError("no_extractable_content must be true when items is empty")
        return self


def _coerce_span_boundary(value: Any, *, mode: Literal["floor", "ceil"]) -> Any:
    """Accept model-emitted numeric span approximations while preserving coverage."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return value
        return math.floor(value) if mode == "floor" else math.ceil(value)
    return value
