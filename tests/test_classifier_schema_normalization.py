"""Classifier schema normalization: omitted rationale must not collapse the label.

A small local model often emits the relation label without a rationale. Before
the fix, strict validation rejected the stage, the classifier fell back to
``independent``/``unclear``, and a genuine contradiction silently became a Keep.
The before-validators default only the explanatory rationale while keeping the
decision label, and still reject outputs missing the actual decision fields.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ksa.classifier.schema import RelationOutput, Stage1Output, Stage2Output


def test_stage1_missing_rationale_keeps_label() -> None:
    out = Stage1Output.model_validate({"logical_relation": "contradict"})
    assert out.logical_relation == "contradict"
    assert out.rationale  # filled, non-empty


def test_stage1_empty_rationale_filled() -> None:
    out = Stage1Output.model_validate({"logical_relation": "support", "rationale": ""})
    assert out.logical_relation == "support"
    assert out.rationale


def test_stage1_missing_label_still_rejected() -> None:
    with pytest.raises(ValidationError):
        Stage1Output.model_validate({"rationale": "some text"})


def test_stage2_missing_rationale_keeps_label() -> None:
    out = Stage2Output.model_validate({"temporal": "newer", "same_subject": True})
    assert out.temporal == "newer"
    assert out.same_subject is True
    assert out.rationale


def test_stage2_missing_decision_field_still_rejected() -> None:
    with pytest.raises(ValidationError):
        Stage2Output.model_validate({"temporal": "newer"})  # same_subject missing


def test_relation_output_fills_missing_rationales() -> None:
    out = RelationOutput.model_validate(
        {
            "logical_relation": "contradict",
            "temporal": "newer",
            "same_subject": True,
            "relation_to_prior_state": "supersede",
        }
    )
    assert out.relation_to_prior_state == "supersede"
    assert out.stage1_rationale
    assert out.stage2_rationale
