"""Regression tests for the P0 extraction discard bug (runs/m4w14).

Root cause: small extractors emitted a valid ``{"items": [...]}`` object that
omitted the required ``no_extractable_content`` flag. Strict validation rejected
it, the single repair retry collapsed to an empty
``{"items": [], "no_extractable_content": true}``, and ``generate_json``
returned that empty object as a *success* — silently discarding the real items.

The fixture ``fixtures/m4w14_extraction_first_pass.jsonl`` holds the actual
first-pass model responses from runs/m4w14/controller, so this test proves the
fix against the exact outputs that were lost, without needing a live model.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import pytest

from ask.extraction import Extractor
from ask.extraction.schema import ExtractionOutput
from ask.inference.fake import FakeLLM
from ask.inference.llm import StructuredLLM, _validate_any_json_object

_FIXTURE = Path(__file__).parent / "fixtures" / "m4w14_extraction_first_pass.jsonl"


def _load_fixture() -> list[dict]:
    return [json.loads(line) for line in _FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_missing_flag_with_items_is_recovered_not_rejected() -> None:
    """The exact shape that broke m4w14: items present, flag omitted."""
    raw = '{"items": [{"text": "I now prefer green tea in the morning instead of coffee.", "type_guess": "stable_pref", "evidence_span": {"session_id": "MGP6-T1-01", "turn_idx": 2, "char_start": 0, "char_end": 37}, "extraction_confidence": 1.0, "negation_marker": false, "hedge_marker": false, "polarity_subject": "user"}]}'
    output = _validate_any_json_object(raw, ExtractionOutput)
    assert len(output.items) == 1
    assert output.no_extractable_content is False


def test_missing_flag_with_empty_items_infers_true() -> None:
    output = ExtractionOutput.model_validate({"items": []})
    assert output.no_extractable_content is True


def test_explicit_inconsistent_flag_still_rejected() -> None:
    """Tolerance is only for the *missing* field; explicit contradiction stays strict."""
    with pytest.raises(Exception):
        ExtractionOutput.model_validate({"items": [], "no_extractable_content": False})


def test_first_pass_no_longer_triggers_repair_for_valid_items() -> None:
    """With the before-validator, a valid first pass must not fall through to repair.

    The FakeLLM only has the first-pass scripted; if repair were triggered it
    would fall back to a deterministic non-JSON answer and raise.
    """
    first = '{"items": [{"text": "User prefers green tea.", "type_guess": "stable_pref", "evidence_span": {"session_id": "s1", "turn_idx": 2, "char_start": 0, "char_end": 10}, "extraction_confidence": 0.9, "negation_marker": false, "hedge_marker": false, "polarity_subject": "user"}]}'
    inner = FakeLLM(scripted=deque([first]))
    extractor = Extractor(StructuredLLM(inner), "Current turn: {{ turn | tojson }}")
    output = extractor.extract(
        {"session_id": "s1", "turn_idx": 2, "role": "user", "content": "I like green tea.", "timestamp": None},
        (None, None),
    )
    assert [item.text for item in output.items] == ["User prefers green tea."]
    # Exactly one model call: no repair retry was needed.
    assert len(inner.scripted) == 0


def test_m4w14_real_traces_recover_majority_of_discarded_items() -> None:
    """Replay every real m4w14 first-pass response through the fixed parser."""
    rows = _load_fixture()
    assert len(rows) == 60

    old_with_items = sum(1 for r in rows if r["old_validated_item_count"] > 0)
    new_with_items = 0
    for row in rows:
        try:
            output = _validate_any_json_object(row["first_pass_text"], ExtractionOutput)
        except Exception:
            continue
        if output.items:
            new_with_items += 1

    # m4w14 as shipped extracted items on only 14/60 scenarios. The fix must
    # recover the large majority of the rest from the identical model outputs.
    assert old_with_items <= 14
    assert new_with_items >= 45
    assert new_with_items - old_with_items >= 30


def test_trace_records_parse_path_and_repair_flag(tmp_path) -> None:
    first = '{"items": [{"text": "User prefers tea.", "type_guess": "stable_pref", "evidence_span": {"session_id": "s1", "turn_idx": 0, "char_start": 0, "char_end": 5}, "extraction_confidence": 0.8, "negation_marker": false, "hedge_marker": false, "polarity_subject": "user"}]}'
    inner = FakeLLM(scripted=deque([first]))
    extractor = Extractor(
        StructuredLLM(inner),
        "Current turn: {{ turn | tojson }}",
        log_path=tmp_path / "trace.jsonl",
    )
    extractor.extract(
        {"session_id": "s1", "turn_idx": 0, "role": "user", "content": "I like tea.", "timestamp": None},
        (None, None),
    )
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert trace["parse_path"] == "first"
    assert trace["repair_used"] is False
    assert trace["first_parse_error"] is None
