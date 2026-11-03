from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from ask.controller.features import FeatureSnapshot
from ask.memory.models import ControllerAction
from ask.protocol import (
    ASKInvariantValidator,
    ASKLMEAdapter,
    ASKMGPAdapter,
    CandidateRecord,
    ConfigurationIdentity,
    EvidenceReference,
    MemoryRecord,
    ReplayScope,
    StoreMode,
    apply_transition,
    replay_transition,
)
from ask.protocol.core import PredecessorReference

ROOT = Path(__file__).resolve().parents[1]
DIGEST = "1" * 64


def _config(adapter_version: str) -> ConfigurationIdentity:
    return ConfigurationIdentity("frozen-test", adapter_version, "2" * 64)


def _evidence() -> tuple[EvidenceReference, ...]:
    return (EvidenceReference("turn-7", DIGEST),)


def _prior() -> MemoryRecord:
    return MemoryRecord("m1", "stable_pref", "vegetarian", evidence_digest=DIGEST)


def _candidate() -> CandidateRecord:
    return CandidateRecord("m2", "stable_pref", "omnivore", 0.9, DIGEST)


def test_mgp_adapter_replays_composition_without_claiming_model_replay() -> None:
    adapter = ASKMGPAdapter(_config("ask-mgp/v1"))
    action, trace = adapter.decide(
        model_proposal=ControllerAction.ABSTAIN,
        rule_proposal=ControllerAction.SUPERSEDE,
        rule_verdict="direct_documented_slot_change",
        evidence_references=_evidence(),
        guard_rule_id="indexed-evidence/v1",
    )
    assert action is ControllerAction.SUPERSEDE
    assert trace.replay_scope is ReplayScope.COMPOSITION_AND_TRANSITION
    assert adapter.replay(trace) is action
    assert trace.intermediates["overrode_model_abstention"] is True


def test_mgp_guard_does_not_override_keep_or_supersede() -> None:
    adapter = ASKMGPAdapter(_config("ask-mgp/v1"))
    for model_action in (ControllerAction.KEEP, ControllerAction.SUPERSEDE):
        action, _ = adapter.decide(
            model_proposal=model_action,
            rule_proposal=ControllerAction.ABSTAIN,
            rule_verdict="unresolved",
            evidence_references=_evidence(),
            guard_rule_id="indexed-evidence/v1",
        )
        assert action is model_action


def test_lme_adapter_has_distinct_predictor_storage_and_replay_scope() -> None:
    mgp = ASKMGPAdapter(_config("ask-mgp/v1"))
    lme = ASKLMEAdapter(_config("ask-lme-scorecard/v1"))
    action, trace = lme.decide(
        features=FeatureSnapshot(c=0.95, e=0.85, f=0.0, r=-1.0, rho=0.9),
        memory_type="stable_pref",
        evidence_references=_evidence(),
        prior_record_id="m1",
        candidate_record_id="m2",
    )
    assert lme.replay(trace) is action
    assert lme.store_mode is StoreMode.MULTI_RECORD
    assert mgp.store_mode is StoreMode.SINGLE_SLOT_VERSIONED
    assert lme.replay_scope is ReplayScope.FINAL_POLICY_AND_TRANSITION
    assert mgp.replay_scope is ReplayScope.COMPOSITION_AND_TRANSITION


def test_abstain_preserves_state_and_emits_durable_event() -> None:
    adapter = ASKMGPAdapter(_config("ask-mgp/v1"))
    action, trace = adapter.decide(
        model_proposal=ControllerAction.ABSTAIN,
        rule_proposal=ControllerAction.ABSTAIN,
        rule_verdict="unresolved",
        evidence_references=_evidence(),
        guard_rule_id="indexed-evidence/v1",
    )
    after, event = apply_transition(
        (_prior(),),
        action=action,
        store_mode=StoreMode.SINGLE_SLOT_VERSIONED,
        prior_record_id="m1",
        candidate=_candidate(),
        trace=trace,
    )
    assert after == (_prior(),)
    assert event.resulting_record_id is None
    assert event.before_digest == event.after_digest
    assert (
        replay_transition((_prior(),), event=event, candidate=_candidate(), trace=trace)[0] == after
    )


def test_keep_modes_are_explicit_and_preserve_compared_prior() -> None:
    adapter = ASKLMEAdapter(_config("ask-lme-scorecard/v1"))
    action, trace = adapter.decide(
        features=FeatureSnapshot(c=0.95, e=0.85, f=0.0, r=1.0, rho=0.6),
        memory_type="episodic_fact",
        evidence_references=_evidence(),
        prior_record_id="m1",
        candidate_record_id="m2",
    )
    assert action is ControllerAction.KEEP
    after, event = apply_transition(
        (_prior(),),
        action=action,
        store_mode=StoreMode.MULTI_RECORD,
        prior_record_id="m1",
        candidate=_candidate(),
        trace=trace,
        admit_candidate_on_keep=True,
    )
    assert after[0] == _prior()
    assert after[1].record_id == "m2"
    assert event.keep_admitted_candidate is True
    with pytest.raises(ValueError, match="only valid in multi_record"):
        apply_transition(
            (_prior(),),
            action=action,
            store_mode=StoreMode.SINGLE_SLOT_VERSIONED,
            prior_record_id="m1",
            candidate=_candidate(),
            trace=trace,
            admit_candidate_on_keep=True,
        )


def test_supersede_retains_predecessor_and_is_deterministic() -> None:
    adapter = ASKMGPAdapter(_config("ask-mgp/v1"))
    action, trace = adapter.decide(
        model_proposal=ControllerAction.SUPERSEDE,
        rule_proposal=ControllerAction.KEEP,
        rule_verdict="temporary_exception",
        evidence_references=_evidence(),
        guard_rule_id="indexed-evidence/v1",
    )
    first = apply_transition(
        (_prior(),),
        action=action,
        store_mode=StoreMode.SINGLE_SLOT_VERSIONED,
        prior_record_id="m1",
        candidate=_candidate(),
        trace=trace,
    )
    second = apply_transition(
        (_prior(),),
        action=action,
        store_mode=StoreMode.SINGLE_SLOT_VERSIONED,
        prior_record_id="m1",
        candidate=_candidate(),
        trace=trace,
    )
    assert first == second
    assert first[0][0].active is False
    assert first[0][1].predecessor == PredecessorReference("m1")


def test_validator_rejects_dangling_lineage_and_cycles() -> None:
    validator = ASKInvariantValidator()
    dangling = (MemoryRecord("m2", "stable_pref", "x", predecessor=PredecessorReference("x")),)
    with pytest.raises(ValueError, match="dangling predecessor"):
        validator._validate_lineage(dangling)
    cycle = (
        MemoryRecord("a", "stable_pref", "a", predecessor=PredecessorReference("b")),
        MemoryRecord("b", "stable_pref", "b", predecessor=PredecessorReference("a")),
    )
    with pytest.raises(ValueError, match="lineage cycle"):
        validator._validate_lineage(cycle)


def test_transition_event_serialization_matches_schema() -> None:
    adapter = ASKMGPAdapter(_config("ask-mgp/v1"))
    action, trace = adapter.decide(
        model_proposal=ControllerAction.ABSTAIN,
        rule_proposal=ControllerAction.ABSTAIN,
        rule_verdict="unresolved",
        evidence_references=_evidence(),
        guard_rule_id="indexed-evidence/v1",
    )
    _, event = apply_transition(
        (_prior(),),
        action=action,
        store_mode=StoreMode.SINGLE_SLOT_VERSIONED,
        prior_record_id="m1",
        candidate=_candidate(),
        trace=trace,
    )
    schema = json.loads((ROOT / "schema/ask_transition_event.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(event.to_json_dict())
