from __future__ import annotations

from ask.memory.models import ControllerAction
from ask.protocol import (
    ASKMGPAdapter,
    CandidateRecord,
    ConfigurationIdentity,
    EvidenceReference,
    MemoryRecord,
    StoreMode,
    apply_transition,
)

DIGEST = "a" * 64


def _adapter() -> ASKMGPAdapter:
    return ASKMGPAdapter(ConfigurationIdentity("formal-fixture", "ask-mgp/v1", DIGEST))


def test_endpoint_answer_does_not_identify_write_transition() -> None:
    prior = MemoryRecord("m1", "stable_pref", "tea", evidence_digest=DIGEST)
    candidate = CandidateRecord("m2", "stable_pref", "coffee", 0.9, DIGEST)
    evidence = (EvidenceReference("turn-2", DIGEST),)
    abstain_action, abstain_trace = _adapter().decide(
        model_proposal=ControllerAction.ABSTAIN,
        rule_proposal=ControllerAction.ABSTAIN,
        rule_verdict="ambiguous",
        evidence_references=evidence,
        guard_rule_id="formal/v1",
    )
    supersede_action, supersede_trace = _adapter().decide(
        model_proposal=ControllerAction.SUPERSEDE,
        rule_proposal=ControllerAction.ABSTAIN,
        rule_verdict="ambiguous",
        evidence_references=evidence,
        guard_rule_id="formal/v1",
    )
    abstain_state, abstain_event = apply_transition(
        (prior,),
        action=abstain_action,
        store_mode=StoreMode.SINGLE_SLOT_VERSIONED,
        prior_record_id="m1",
        candidate=candidate,
        trace=abstain_trace,
    )
    supersede_state, supersede_event = apply_transition(
        (prior,),
        action=supersede_action,
        store_mode=StoreMode.SINGLE_SLOT_VERSIONED,
        prior_record_id="m1",
        candidate=candidate,
        trace=supersede_trace,
    )
    endpoint_answer_a = endpoint_answer_b = "Your recorded preference is coffee."
    assert endpoint_answer_a == endpoint_answer_b
    assert abstain_event.action != supersede_event.action
    assert abstain_state != supersede_state
    assert abstain_event.after_digest != supersede_event.after_digest


def test_transition_identity_is_stable_under_repeated_fixed_inputs() -> None:
    prior = MemoryRecord("m1", "stable_pref", "tea", evidence_digest=DIGEST)
    candidate = CandidateRecord("m2", "stable_pref", "coffee", 0.9, DIGEST)
    action, trace = _adapter().decide(
        model_proposal=ControllerAction.SUPERSEDE,
        rule_proposal=ControllerAction.SUPERSEDE,
        rule_verdict="explicit_update",
        evidence_references=(EvidenceReference("turn-2", DIGEST),),
        guard_rule_id="formal/v1",
    )
    events = {
        apply_transition(
            (prior,),
            action=action,
            store_mode=StoreMode.SINGLE_SLOT_VERSIONED,
            prior_record_id="m1",
            candidate=candidate,
            trace=trace,
        )[1].event_id
        for _ in range(100)
    }
    assert len(events) == 1
