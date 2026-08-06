"""Extractor recovery behavior for local model JSON drift."""

from __future__ import annotations

import json
from collections import deque

import pytest

from ask.extraction import ExtractionUnavailableError, Extractor
from ask.inference.fake import FakeLLM
from ask.inference.llm import StructuredLLM


class _UnavailableLLM:
    model_id = "unavailable"

    def generate(self, prompt, *, max_new_tokens, temperature, seed, stop=None):
        raise RuntimeError("HTTP 402 insufficient credit")


def test_extractor_propagates_failure_when_provider_returns_no_response(tmp_path) -> None:
    extractor = Extractor(
        StructuredLLM(_UnavailableLLM()),
        "Current turn: {{ turn | tojson }}",
        log_path=tmp_path / "trace.jsonl",
    )

    with pytest.raises(ExtractionUnavailableError, match="valid response") as exc_info:
        extractor.extract(
            {
                "session_id": "s-unavailable",
                "turn_idx": 0,
                "role": "user",
                "content": "I like coffee.",
                "timestamp": None,
            },
            (None, None),
        )

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "HTTP 402" in str(exc_info.value.__cause__)
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8"))
    assert trace["responses"] == []
    assert "extractor unavailable" in trace["error"]


def test_extractor_falls_back_to_empty_on_schema_echo() -> None:
    inner = FakeLLM(
        scripted=deque(
            [
                '{"title":"ExtractedItem","type":"object","properties":{}}',
                '{"title":"ExtractedItem","type":"object","properties":{}}',
            ]
        )
    )
    extractor = Extractor(
        StructuredLLM(inner),
        "Current turn: {{ turn | tojson }}",
    )

    output = extractor.extract(
        {
            "session_id": "s1",
            "turn_idx": 0,
            "role": "user",
            "content": "I like coffee.",
            "timestamp": None,
        },
        (None, None),
    )

    assert output.items == []
    assert output.no_extractable_content is True
    assert "could not be parsed" in (output.coverage_note or "")


def test_extractor_filters_placeholder_and_recovers_degree_fact(tmp_path) -> None:
    inner = FakeLLM(
        scripted=deque(
            [
                (
                    '{"items":[{"text":"one short canonical sentence",'
                    '"type_guess":"stable_pref",'
                    '"evidence_span":{"session_id":"answer_1","turn_idx":4,'
                    '"char_start":0,"char_end":0},'
                    '"extraction_confidence":0.0,'
                    '"negation_marker":false,"hedge_marker":false,'
                    '"polarity_subject":"user"}],'
                    '"no_extractable_content":false,"coverage_note":null}'
                )
            ]
        )
    )
    extractor = Extractor(
        StructuredLLM(inner),
        "Current turn: {{ turn | tojson }}",
        log_path=tmp_path / "trace.jsonl",
    )

    output = extractor.extract(
        {
            "session_id": "answer_1",
            "turn_idx": 4,
            "role": "user",
            "content": (
                "I graduated with a degree in Business Administration, "
                "which has definitely helped me in my new role."
            ),
            "timestamp": None,
        },
        (None, None),
    )

    assert output.no_extractable_content is False
    assert [item.text for item in output.items] == [
        "User graduated with a degree in Business Administration."
    ]
    assert output.items[0].type_guess == "episodic_fact"
    assert output.items[0].extraction_confidence == 1.0
    trace = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert trace["postprocessor_enabled"] is True
    assert trace["postprocessor_version"] == "extractor_postprocessor_v2"
    assert trace["raw_validated_output"]["items"][0]["text"] == "one short canonical sentence"
    assert trace["validated_output"]["items"][0]["text"] == (
        "User graduated with a degree in Business Administration."
    )


def test_extractor_salvages_complete_items_from_truncated_json() -> None:
    """A JSON output cut off mid-array keeps its complete leading items."""
    complete_two = (
        '{"text":"User prefers dark roast coffee.","type_guess":"stable_pref",'
        '"evidence_span":{"session_id":"s1","turn_idx":0,"char_start":0,"char_end":5},'
        '"extraction_confidence":0.9,"negation_marker":false,"hedge_marker":false,'
        '"polarity_subject":"user"},'
        '{"text":"User lives in Berlin.","type_guess":"episodic_fact",'
        '"evidence_span":{"session_id":"s1","turn_idx":0,"char_start":6,"char_end":10},'
        '"extraction_confidence":0.8,"negation_marker":false,"hedge_marker":false,'
        '"polarity_subject":"user"}'
    )
    # Two well-formed items, then a third object truncated mid-string (as an
    # output-token-budget cutoff would produce).
    truncated = '{"items":[' + complete_two + ',{"text":"User is planning a trip to'
    inner = FakeLLM(scripted=deque([truncated, truncated]))
    extractor = Extractor(
        StructuredLLM(inner),
        "Current turn: {{ turn | tojson }}",
    )

    output = extractor.extract(
        {
            "session_id": "s1",
            "turn_idx": 0,
            "role": "user",
            "content": "We chatted about a few unrelated things.",
            "timestamp": None,
        },
        (None, None),
    )

    assert output.no_extractable_content is False
    assert [item.text for item in output.items] == [
        "User prefers dark roast coffee.",
        "User lives in Berlin.",
    ]


def test_extractor_recovers_new_proper_possession_fact() -> None:
    inner = FakeLLM(
        scripted=deque(['{"items":[],"no_extractable_content":true,"coverage_note":"empty"}'])
    )
    extractor = Extractor(
        StructuredLLM(inner),
        "Current turn: {{ turn | tojson }}",
    )

    output = extractor.extract(
        {
            "session_id": "answer_3bf5b73b_1",
            "turn_idx": 2,
            "role": "user",
            "content": (
                "I'm actually thinking of using my new Instant Pot to make some "
                "of these soups and stews."
            ),
            "timestamp": None,
        },
        (None, None),
    )

    assert output.no_extractable_content is False
    assert [item.text for item in output.items] == ["User has a new Instant Pot."]
