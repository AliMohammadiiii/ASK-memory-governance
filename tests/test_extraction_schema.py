"""Extraction schema contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ask.extraction.schema import EvidenceSpan, ExtractedItem, ExtractionOutput


def test_extraction_output_round_trips() -> None:
    output = ExtractionOutput(
        items=[
            ExtractedItem(
                text="User prefers coffee in the morning.",
                type_guess="stable_pref",
                evidence_span=EvidenceSpan(
                    session_id="lme-s-00001",
                    turn_idx=0,
                    char_start=0,
                    char_end=31,
                ),
                extraction_confidence=0.92,
                negation_marker=False,
                hedge_marker=False,
                polarity_subject="user",
            )
        ],
        no_extractable_content=False,
        coverage_note=None,
    )

    recovered = ExtractionOutput.model_validate_json(output.model_dump_json())

    assert recovered == output
    assert recovered.items[0].type_guess == "stable_pref"


def test_rejects_malformed_type_guess() -> None:
    with pytest.raises(ValidationError):
        ExtractionOutput.model_validate(
            {
                "items": [
                    {
                        "text": "User prefers coffee.",
                        "type_guess": "preference",
                        "evidence_span": {
                            "session_id": "lme-s-00001",
                            "turn_idx": 0,
                            "char_start": 0,
                            "char_end": 20,
                        },
                        "extraction_confidence": 0.7,
                        "negation_marker": False,
                        "hedge_marker": False,
                        "polarity_subject": "user",
                    }
                ],
                "no_extractable_content": False,
                "coverage_note": None,
            }
        )


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_rejects_confidence_outside_unit_interval(confidence: float) -> None:
    with pytest.raises(ValidationError):
        ExtractedItem(
            text="User prefers coffee.",
            type_guess="stable_pref",
            evidence_span=EvidenceSpan(
                session_id="lme-s-00001",
                turn_idx=0,
                char_start=0,
                char_end=20,
            ),
            extraction_confidence=confidence,
            negation_marker=False,
            hedge_marker=False,
            polarity_subject="user",
        )


def test_rejects_empty_items_without_no_extractable_content() -> None:
    with pytest.raises(ValidationError):
        ExtractionOutput(items=[], no_extractable_content=False)


def test_rejects_inverted_evidence_span() -> None:
    with pytest.raises(ValidationError):
        EvidenceSpan(
            session_id="lme-s-00001",
            turn_idx=0,
            char_start=12,
            char_end=4,
        )


def test_coerces_fractional_evidence_span_boundaries_conservatively() -> None:
    span = EvidenceSpan(
        session_id="lme-s-00001",
        turn_idx=0,
        char_start=1200.05,
        char_end=1219.99,
    )

    assert span.char_start == 1200
    assert span.char_end == 1220
