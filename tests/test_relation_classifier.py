"""Two-stage relation classifier tests."""

from __future__ import annotations

import json
from collections import deque

import pytest
from pydantic import ValidationError

from ask.classifier import CandidateMemory, PriorMemory, RelationClassifier, Stage1Output
from ask.inference.fake import FakeLLM
from ask.inference.llm import StructuredLLM

STAGE1 = """
Candidate: {{ candidate | tojson }}
Prior: {{ prior | tojson }}
Return {"logical_relation":"support","rationale":"..."}
"""

STAGE2 = """
Stage1: {{ stage1 | tojson }}
Return {"temporal":"same","same_subject":true,"rationale":"..."}
"""


def _classifier(*responses: str) -> RelationClassifier:
    return RelationClassifier(
        StructuredLLM(FakeLLM(scripted=deque(responses))),
        STAGE1,
        STAGE2,
    )


def _candidate(text: str = "User prefers coffee.") -> CandidateMemory:
    return CandidateMemory(text=text, type_guess="stable_pref")


def _prior(text: str = "User prefers coffee.") -> PriorMemory:
    return PriorMemory(text=text, type="stable_pref")


class _UnavailableLLM:
    model_id = "unavailable"

    def generate(self, prompt, *, max_new_tokens, temperature, seed):
        raise RuntimeError("HTTP 402 insufficient credit")


def test_relation_classifier_propagates_no_response_provider_failure() -> None:
    classifier = RelationClassifier(
        StructuredLLM(_UnavailableLLM()), STAGE1, STAGE2
    )

    with pytest.raises(RuntimeError, match="HTTP 402"):
        classifier.classify(_candidate(), _prior())


def test_support_relation_maps_to_support() -> None:
    clf = _classifier(
        '{"logical_relation":"support","rationale":"same preference"}',
        '{"temporal":"same","same_subject":true,"rationale":"same subject"}',
    )

    out = clf.classify(_candidate(), _prior())

    assert out.logical_relation == "support"
    assert out.relation_to_prior_state == "support"


def test_newer_same_subject_contradiction_maps_to_supersede() -> None:
    clf = _classifier(
        '{"logical_relation":"contradict","rationale":"coffee vs tea"}',
        '{"temporal":"newer","same_subject":true,"rationale":"candidate is newer"}',
    )

    out = clf.classify(_candidate("User prefers tea."), _prior("User prefers coffee."))

    assert out.relation_to_prior_state == "supersede"


def test_now_instead_update_maps_to_supersede() -> None:
    clf = _classifier(
        '{"logical_relation":"contradict","rationale":"same preference slot changed"}',
        '{"temporal":"newer","same_subject":true,"rationale":"candidate says now/instead"}',
    )

    out = clf.classify(
        _candidate("I now prefer tea instead of coffee."),
        _prior("I prefer coffee."),
    )

    assert out.logical_relation == "contradict"
    assert out.relation_to_prior_state == "supersede"


def test_timestamp_override_maps_newer_contradiction_to_supersede(tmp_path) -> None:
    inner = FakeLLM(scripted=deque([
        '{"logical_relation":"contradict","rationale":"coffee vs tea"}',
        '{"temporal":"unknown","same_subject":true,"rationale":"ignored timestamps"}',
    ]))
    log_path = tmp_path / "relation_trace.jsonl"
    clf = RelationClassifier(
        StructuredLLM(inner),
        STAGE1,
        STAGE2,
        log_path=log_path,
    )

    out = clf.classify(
        CandidateMemory(
            text="User prefers tea.",
            type_guess="stable_pref",
            timestamp="2026-02-03T00:00:00Z",
        ),
        PriorMemory(
            text="User prefers coffee.",
            type="stable_pref",
            timestamp="2024-01-01T00:00:00+00:00",
        ),
    )

    trace = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])

    assert out.temporal == "newer"
    assert out.relation_to_prior_state == "supersede"
    assert "Timestamp override" in out.stage2_rationale
    assert trace["raw_stage1_label"] == "contradict"
    assert trace["raw_stage2_temporal"] == "unknown"
    assert trace["routed_stage2_temporal"] == "newer"
    assert trace["final_routed_relation"] == "supersede"
    assert "timestamp_override" in trace["deterministic_routing_reason"]


def test_timestamp_override_maps_newer_contradiction_to_supersede_legacy_helper() -> None:
    clf = _classifier(
        '{"logical_relation":"contradict","rationale":"coffee vs tea"}',
        '{"temporal":"unknown","same_subject":true,"rationale":"ignored timestamps"}',
    )

    out = clf.classify(
        CandidateMemory(
            text="User prefers tea.",
            type_guess="stable_pref",
            timestamp="2026-02-03T00:00:00Z",
        ),
        PriorMemory(
            text="User prefers coffee.",
            type="stable_pref",
            timestamp="2024-01-01T00:00:00+00:00",
        ),
    )

    assert out.temporal == "newer"
    assert out.relation_to_prior_state == "supersede"
    assert "Timestamp override" in out.stage2_rationale


def test_timestamped_material_support_update_maps_to_supersede() -> None:
    clf = _classifier(
        '{"logical_relation":"support","rationale":"candidate refines prior"}',
        '{"temporal":"unknown","same_subject":true,"rationale":"ignored timestamps"}',
    )

    out = clf.classify(
        CandidateMemory(
            text="User prefers a balanced learning style with structure.",
            type_guess="stable_pref",
            timestamp="2026-02-03T00:00:00Z",
        ),
        PriorMemory(
            text="User prefers non-traditional learning.",
            type="stable_pref",
            timestamp="2024-01-01T00:00:00Z",
        ),
    )

    assert out.logical_relation == "support"
    assert out.temporal == "newer"
    assert out.relation_to_prior_state == "supersede"


def test_timestamped_exact_support_restatement_stays_support() -> None:
    clf = _classifier(
        '{"logical_relation":"support","rationale":"same preference"}',
        '{"temporal":"unknown","same_subject":true,"rationale":"ignored timestamps"}',
    )

    out = clf.classify(
        CandidateMemory(
            text="User prefers coffee.",
            type_guess="stable_pref",
            timestamp="2026-02-03T00:00:00Z",
        ),
        PriorMemory(
            text="User prefers coffee.",
            type="stable_pref",
            timestamp="2024-01-01T00:00:00Z",
        ),
    )

    assert out.temporal == "newer"
    assert out.relation_to_prior_state == "support"


def test_timestamped_non_independent_same_type_overrides_same_subject() -> None:
    clf = _classifier(
        '{"logical_relation":"contradict","rationale":"user reversed preference"}',
        '{"temporal":"unknown","same_subject":false,"rationale":"changed stance"}',
    )

    out = clf.classify(
        CandidateMemory(
            text="User no longer wants role-play content.",
            type_guess="episodic_fact",
            timestamp="2026-02-03T00:00:00Z",
        ),
        PriorMemory(
            text="User was curious about role-play content.",
            type="episodic_fact",
            timestamp="2024-01-01T00:00:00Z",
        ),
    )

    assert out.same_subject is True
    assert out.relation_to_prior_state == "supersede"
    assert "Same-subject override" in out.stage2_rationale


def test_timestamp_override_keeps_older_contradiction_as_contradict() -> None:
    clf = _classifier(
        '{"logical_relation":"contradict","rationale":"coffee vs tea"}',
        '{"temporal":"unknown","same_subject":true,"rationale":"ignored timestamps"}',
    )

    out = clf.classify(
        CandidateMemory(
            text="User prefers tea.",
            type_guess="stable_pref",
            timestamp="2023-01-01T00:00:00Z",
        ),
        PriorMemory(
            text="User prefers coffee.",
            type="stable_pref",
            timestamp="2024-01-01T00:00:00+00:00",
        ),
    )

    assert out.temporal == "older"
    assert out.relation_to_prior_state == "contradict"


def test_independent_maps_to_unclear() -> None:
    clf = _classifier(
        '{"logical_relation":"independent","rationale":"different subject"}',
        '{"temporal":"unknown","same_subject":false,"rationale":"different subject"}',
    )

    out = clf.classify(_candidate("User owns a bike."), _prior())

    assert out.relation_to_prior_state == "unclear"


def test_schema_rejects_unknown_stage1_label() -> None:
    with pytest.raises(ValidationError):
        Stage1Output(logical_relation="supersede", rationale="not a stage-1 label")


def test_relation_classifier_falls_back_to_independent_on_schema_echo() -> None:
    clf = _classifier(
        '{"title":"Stage1Output","type":"object","properties":{}}',
        '{"title":"Stage1Output","type":"object","properties":{}}',
    )

    out = clf.classify(_candidate(), _prior())

    assert out.logical_relation == "independent"
    assert out.relation_to_prior_state == "unclear"
    assert "fallback" in out.stage1_rationale
