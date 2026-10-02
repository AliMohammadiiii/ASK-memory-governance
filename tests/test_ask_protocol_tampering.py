"""Regression tests for the ASK transition validator against tampered transitions.

Each tampering probe builds a conforming transition with ``apply_transition``, alters the
after state or the event, recomputes the state digests and the event identifier so that the
tampered transition is self-consistent, and checks that ``ASKInvariantValidator.validate``
rejects it with a named reason code. Probe identifiers S01-S12, K01-K05 and I01-I02 follow the
audit record of the baseline validator, which accepted all 19. Positive controls check that
conforming transitions are still accepted.

A self-consistent probe set is a regression suite for this implementation. It is not evidence
that the validator is complete or that any external store conforms to the protocol.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, NamedTuple

import pytest

from ask.controller.features import FeatureSnapshot
from ask.controller.score import DEFAULT_SCORECARD_CONFIG, ScorecardConfig
from ask.protocol import (
    UNVERIFIED,
    Action,
    ASKInvariantValidator,
    ASKLMEAdapter,
    ASKMGPAdapter,
    ASKValidationError,
    CandidateRecord,
    ConfigurationIdentity,
    DecisionTrace,
    EvidenceReference,
    InMemoryASKStore,
    MemoryRecord,
    PredecessorReference,
    ReplayScope,
    StoreMode,
    TransitionEvent,
    apply_transition,
    canonical_json_bytes,
    compute_event_id,
    configuration_digest,
    replay_transition,
    validate_event_chain,
)
from ask.protocol.core import evidence_set_digest, state_digest

# ---------------------------------------------------------------------------------------------
# fixtures


def _h(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


CFG_MAPPING = {"adapter_version": "ask-mgp/v1", "parameters": {"example": 1}}
CFG = ConfigurationIdentity.from_configuration("cfg-A", "ask-mgp/v1", CFG_MAPPING)
REFS = (EvidenceReference("turn-1", _h("evidence turn 1")),)
CANDIDATE = CandidateRecord("c1", "stable_pref", "new value", 0.9, _h("cand evidence"))

BASE_MULTI = (
    MemoryRecord("p1", "stable_pref", "old value", True, None, _h("p1 ev")),
    MemoryRecord("u1", "episodic_fact", "unrelated fact", True, None, _h("u1 ev")),
)
BASE_SLOT_HISTORY = (
    MemoryRecord("p0", "stable_pref", "oldest", False, None, _h("p0 ev")),
    MemoryRecord("p1", "stable_pref", "old value", True, PredecessorReference("p0"), _h("p1 ev")),
)


def _trace(action: Action, *, evidence_digest: str | None = None) -> DecisionTrace:
    return DecisionTrace(
        adapter_id="ASK-MGP",
        adapter_version=CFG.adapter_version,
        replay_scope=ReplayScope.COMPOSITION_AND_TRANSITION,
        configuration=CFG,
        evidence_references=REFS,
        evidence_digest=evidence_digest or evidence_set_digest(REFS),
        inputs={"model_proposal": action.value, "rule_proposal": action.value},
        intermediates={},
        final_action=action,
        sufficient_fields=("model_proposal",),
    )


class Transition(NamedTuple):
    before: tuple[MemoryRecord, ...]
    after: tuple[MemoryRecord, ...]
    event: TransitionEvent
    trace: DecisionTrace
    candidate: CandidateRecord | None = CANDIDATE


def _build(
    action: Action,
    *,
    before: tuple[MemoryRecord, ...] = BASE_MULTI,
    mode: StoreMode = StoreMode.MULTI_RECORD,
    prior: str | None = "p1",
    admit: bool = False,
) -> Transition:
    trace = _trace(action)
    after, event = apply_transition(
        before,
        action=action,
        store_mode=mode,
        prior_record_id=prior,
        candidate=CANDIDATE,
        trace=trace,
        admit_candidate_on_keep=admit,
    )
    return Transition(before, after, event, trace)


def _reidentify(
    event: TransitionEvent,
    before: tuple[MemoryRecord, ...],
    after: tuple[MemoryRecord, ...],
    **changes: Any,
) -> TransitionEvent:
    """Self-consistent tampering: recompute state digests and the event identifier."""
    altered = replace(
        event, before_digest=state_digest(before), after_digest=state_digest(after), **changes
    )
    return replace(altered, event_id=compute_event_id(altered))


def _tamper(
    base: Transition,
    mutate: Callable[[list[MemoryRecord]], list[MemoryRecord]],
    *,
    before: tuple[MemoryRecord, ...] | None = None,
    **event_changes: Any,
) -> Transition:
    new_before = base.before if before is None else before
    new_after = tuple(mutate(list(base.after)))
    event = _reidentify(base.event, new_before, new_after, **event_changes)
    return base._replace(before=new_before, after=new_after, event=event)


def _validate(transition: Transition, **overrides: Any):
    arguments: dict[str, Any] = {
        "before": transition.before,
        "after": transition.after,
        "event": transition.event,
        "trace": transition.trace,
        "candidate": transition.candidate,
        "configuration": CFG_MAPPING,
    }
    arguments.update(overrides)
    return ASKInvariantValidator().validate(**arguments)


def _set(records: list[MemoryRecord], record_id: str, **fields: Any) -> list[MemoryRecord]:
    return [replace(r, **fields) if r.record_id == record_id else r for r in records]


# ---------------------------------------------------------------------------------------------
# the 19 probes


@dataclass(frozen=True)
class Probe:
    description: str
    code: str
    build: Callable[[], Transition]


def _supersede() -> Transition:
    return _build(Action.SUPERSEDE)


def _keep() -> Transition:
    return _build(Action.KEEP)


def _s11() -> Transition:
    base = _supersede()
    before = tuple(replace(r, active=False) if r.record_id == "p1" else r for r in BASE_MULTI)
    after = (*before, base.after[-1])
    return base._replace(before=before, after=after, event=_reidentify(base.event, before, after))


def _s12() -> Transition:
    base = _build(Action.SUPERSEDE, before=BASE_SLOT_HISTORY, mode=StoreMode.SINGLE_SLOT_VERSIONED)
    return _tamper(
        base,
        lambda a: [
            replace(r, predecessor=None) if r.record_id == "p1" else r
            for r in a
            if r.record_id != "p0"
        ],
    )


def _i01() -> Transition:
    base = _supersede()
    return base._replace(event=replace(base.event, event_id=_h("arbitrary")))


def _i02() -> Transition:
    base = _supersede()
    trace = _trace(Action.SUPERSEDE, evidence_digest=_h("not the reference-set digest"))
    event = replace(base.event, evidence_digest=trace.evidence_digest)
    return base._replace(event=_reidentify(event, base.before, base.after), trace=trace)


PROBES: dict[str, Probe] = {
    "S01": Probe(
        "SUPERSEDE: retained predecessor value altered",
        "retained_predecessor_mutated",
        lambda: _tamper(_supersede(), lambda a: _set(a, "p1", value="REWRITTEN HISTORY")),
    ),
    "S02": Probe(
        "SUPERSEDE: retained predecessor memory_type altered",
        "retained_predecessor_mutated",
        lambda: _tamper(_supersede(), lambda a: _set(a, "p1", memory_type="episodic_fact")),
    ),
    "S03": Probe(
        "SUPERSEDE: retained predecessor evidence_digest altered",
        "retained_predecessor_mutated",
        lambda: _tamper(_supersede(), lambda a: _set(a, "p1", evidence_digest=_h("forged"))),
    ),
    "S04": Probe(
        "SUPERSEDE: unrelated active record deleted",
        "unaccounted_record_removed",
        lambda: _tamper(_supersede(), lambda a: [r for r in a if r.record_id != "u1"]),
    ),
    "S05": Probe(
        "SUPERSEDE: unrelated record value mutated",
        "unaccounted_record_changed",
        lambda: _tamper(_supersede(), lambda a: _set(a, "u1", value="silently changed")),
    ),
    "S06": Probe(
        "SUPERSEDE: successor value differs from candidate value",
        "successor_differs_from_candidate",
        lambda: _tamper(_supersede(), lambda a: _set(a, "c1", value="not what the candidate said")),
    ),
    "S07": Probe(
        "SUPERSEDE: unrelated record deactivated",
        "unaccounted_record_changed",
        lambda: _tamper(_supersede(), lambda a: _set(a, "u1", active=False)),
    ),
    "S08": Probe(
        "SUPERSEDE: extra unannounced active record inserted",
        "unaccounted_record_added",
        lambda: _tamper(
            _supersede(), lambda a: [*a, MemoryRecord("x9", "episodic_fact", "injected", True)]
        ),
    ),
    "S09": Probe(
        "SUPERSEDE: event predecessor_record_id points to an unrelated record",
        "event_predecessor_id_mismatch",
        lambda: _tamper(_supersede(), lambda a: a, predecessor_record_id="u1"),
    ),
    "S10": Probe(
        "SUPERSEDE: event candidate_record_id wrong",
        "event_candidate_id_mismatch",
        lambda: _tamper(_supersede(), lambda a: a, candidate_record_id="zzz"),
    ),
    "S11": Probe(
        "SUPERSEDE of a prior that was already inactive before the transition",
        "prior_not_active_before",
        _s11,
    ),
    "S12": Probe(
        "SINGLE_SLOT SUPERSEDE: ancestor deleted and lineage pointer rewritten",
        "unaccounted_record_removed",
        _s12,
    ),
    "K01": Probe(
        "MULTI KEEP without admission: candidate silently inserted",
        "unaccounted_record_added",
        lambda: _tamper(
            _keep(),
            lambda a: [
                *a,
                MemoryRecord("c1", "stable_pref", "new value", True, None, _h("cand evidence")),
            ],
        ),
    ),
    "K02": Probe(
        "MULTI KEEP: unrelated record deleted",
        "unaccounted_record_removed",
        lambda: _tamper(_keep(), lambda a: [r for r in a if r.record_id != "u1"]),
    ),
    "K03": Probe(
        "MULTI KEEP: unrelated record value mutated",
        "unaccounted_record_changed",
        lambda: _tamper(_keep(), lambda a: _set(a, "u1", value="changed")),
    ),
    "K04": Probe(
        "MULTI KEEP with prior_record_id=None: record rewritten",
        "unaccounted_record_changed",
        lambda: _tamper(_keep(), lambda a: _set(a, "p1", value="changed"), prior_record_id=None),
    ),
    "K05": Probe(
        "TEMPORAL_EVENT KEEP: arbitrary mutation of an unrelated record",
        "unaccounted_record_changed",
        lambda: _tamper(
            _keep(),
            lambda a: _set(a, "u1", value="changed"),
            store_mode=StoreMode.TEMPORAL_EVENT,
        ),
    ),
    "I01": Probe(
        "Event identifier is not the digest of the event body",
        "event_id_mismatch",
        _i01,
    ),
    "I02": Probe(
        "Trace evidence_digest is not the digest of its evidence references",
        "trace_evidence_digest_mismatch",
        _i02,
    ),
}


def test_probe_set_covers_the_19_audited_probes() -> None:
    expected = {f"S{n:02d}" for n in range(1, 13)} | {f"K{n:02d}" for n in range(1, 6)}
    assert set(PROBES) == expected | {"I01", "I02"}
    assert len(PROBES) == 19


@pytest.mark.parametrize("probe_id", sorted(PROBES))
def test_tampering_probe_is_rejected_with_named_reason(probe_id: str) -> None:
    probe = PROBES[probe_id]
    transition = probe.build()
    with pytest.raises(ASKValidationError) as info:
        _validate(transition)
    assert probe.code in info.value.codes, (probe_id, info.value.codes)


@pytest.mark.parametrize("probe_id", sorted(PROBES))
def test_tampering_probe_is_self_consistent_before_validation(probe_id: str) -> None:
    """The digests the probe carries match its states, so rejection is not a digest check."""
    transition = PROBES[probe_id].build()
    assert transition.event.before_digest == state_digest(transition.before)
    assert transition.event.after_digest == state_digest(transition.after)
    if probe_id != "I01":
        assert transition.event.event_id == compute_event_id(transition.event)


# ---------------------------------------------------------------------------------------------
# positive controls

CONTROLS: dict[str, Callable[[], Transition]] = {
    "abstain_multi": lambda: _build(Action.ABSTAIN),
    "abstain_single_slot": lambda: _build(
        Action.ABSTAIN, before=BASE_SLOT_HISTORY, mode=StoreMode.SINGLE_SLOT_VERSIONED
    ),
    "keep_multi": lambda: _build(Action.KEEP),
    "keep_multi_admit": lambda: _build(Action.KEEP, admit=True),
    "keep_multi_admit_no_prior": lambda: _build(Action.KEEP, admit=True, prior=None),
    "keep_single_slot": lambda: _build(
        Action.KEEP, before=BASE_SLOT_HISTORY, mode=StoreMode.SINGLE_SLOT_VERSIONED
    ),
    "supersede_multi": lambda: _build(Action.SUPERSEDE),
    "supersede_single_slot_history": lambda: _build(
        Action.SUPERSEDE, before=BASE_SLOT_HISTORY, mode=StoreMode.SINGLE_SLOT_VERSIONED
    ),
    "supersede_temporal_event_mode": lambda: _build(
        Action.SUPERSEDE, mode=StoreMode.TEMPORAL_EVENT
    ),
}


@pytest.mark.parametrize("name", sorted(CONTROLS))
def test_conforming_transition_is_accepted(name: str) -> None:
    transition = CONTROLS[name]()
    report = _validate(transition)
    assert report.unverified == ()
    assert "record_accounting" in report.checks
    assert transition.event.event_id == compute_event_id(transition.event)


def test_replay_of_preserved_event_is_accepted() -> None:
    base = _build(Action.SUPERSEDE)
    replayed_state, replayed_event = replay_transition(
        base.before,
        event=base.event,
        candidate=CANDIDATE,
        trace=base.trace,
        configuration=CFG_MAPPING,
    )
    assert replayed_state == base.after
    assert replayed_event == base.event


def test_in_memory_store_applies_with_configuration_binding() -> None:
    store = InMemoryASKStore(store_mode=StoreMode.MULTI_RECORD, records=BASE_MULTI)
    event = store.apply(
        action=Action.SUPERSEDE,
        prior_record_id="p1",
        candidate=CANDIDATE,
        trace=_trace(Action.SUPERSEDE),
        configuration=CFG_MAPPING,
    )
    assert store.records()[-1].record_id == "c1"
    assert event.event_id == compute_event_id(event)


def test_builder_event_ids_match_the_baseline_commit() -> None:
    """Event identifiers and after digests were computed with the unmodified baseline builder."""
    pinned = {
        "abstain": (Action.ABSTAIN, False),
        "keep": (Action.KEEP, False),
        "keep_admit": (Action.KEEP, True),
        "supersede": (Action.SUPERSEDE, False),
    }
    expected = {
        "abstain": "85b0432ec50a77d888ce28a976655535065fb33150934b8380a2c75b88154ede",
        "keep": "203ab28a0fb71e1e5a00c3abf17eaa283e14ef28c58dfde6ab069dbef67587c7",
        "keep_admit": "2218edcc84ff86fc19501ff2383869962980137e7ddfcb1837e76ca33fd7f096",
        "supersede": "ffdec22c74ddfb405aefe3f6a9d92ddf1f0664c1db6b4269c4120467bf26eaa1",
    }
    for name, (action, admit) in pinned.items():
        assert _build(action, admit=admit).event.event_id == expected[name], name


# ---------------------------------------------------------------------------------------------
# further negative cases


def _reject(transition: Transition, code: str, **overrides: Any) -> ASKValidationError:
    with pytest.raises(ASKValidationError) as info:
        _validate(transition, **overrides)
    assert code in info.value.codes, info.value.codes
    return info.value


def test_stale_event_digests_are_rejected() -> None:
    base = _supersede()
    tampered_after = tuple(_set(list(base.after), "u1", value="changed"))
    _reject(base._replace(after=tampered_after), "state_digest_mismatch")


def test_superseded_prior_deleted_is_rejected() -> None:
    base = _supersede()
    dangling = _tamper(base, lambda a: [r for r in a if r.record_id != "p1"])
    _reject(dangling, "dangling_lineage")
    unlinked = _tamper(
        base, lambda a: [replace(r, predecessor=None) for r in a if r.record_id != "p1"]
    )
    _reject(unlinked, "supersede_prior_not_invalidated")


def test_retained_predecessor_lineage_pointer_rewritten_is_rejected() -> None:
    base = _build(Action.SUPERSEDE, before=BASE_SLOT_HISTORY, mode=StoreMode.SINGLE_SLOT_VERSIONED)
    error = _reject(
        _tamper(base, lambda a: _set(a, "p1", predecessor=None)), "retained_predecessor_mutated"
    )
    assert "predecessor" in str(error)


@pytest.mark.parametrize(
    ("field", "value"),
    [("memory_type", "episodic_fact"), ("evidence_digest", _h("other"))],
)
def test_successor_fields_must_equal_candidate(field: str, value: str) -> None:
    base = _supersede()
    _reject(
        _tamper(base, lambda a: _set(a, "c1", **{field: value})), "successor_differs_from_candidate"
    )


def test_successor_must_be_active_and_point_to_prior() -> None:
    base = _supersede()
    _reject(
        _tamper(base, lambda a: _set(a, "c1", predecessor=PredecessorReference("u1"))),
        "supersede_successor_lineage",
    )


def test_admitted_record_must_equal_candidate() -> None:
    base = _build(Action.KEEP, admit=True)
    tampered = _tamper(base, lambda a: _set(a, "c1", value="other"))
    _reject(tampered, "admitted_record_differs_from_candidate")


def test_admission_with_an_extra_record_is_rejected() -> None:
    base = _build(Action.KEEP, admit=True)
    _reject(
        _tamper(base, lambda a: [*a, MemoryRecord("x9", "episodic_fact", "injected", True)]),
        "unaccounted_record_added",
    )


def test_abstain_with_inserted_candidate_is_rejected() -> None:
    base = _build(Action.ABSTAIN)
    _reject(
        _tamper(base, lambda a: [*a, MemoryRecord("c1", "stable_pref", "new value", True)]),
        "abstain_state_changed",
    )


def test_keep_event_must_not_report_a_resulting_record() -> None:
    base = _keep()
    _reject(_tamper(base, lambda a: a, resulting_record_id="c1"), "event_resulting_id_mismatch")


def test_admission_flag_on_supersede_event_is_rejected() -> None:
    base = _supersede()
    _reject(
        _tamper(base, lambda a: a, keep_admitted_candidate=True), "event_admission_flag_mismatch"
    )


def test_keep_with_inactive_prior_is_rejected() -> None:
    base = _keep()
    before = tuple(replace(r, active=False) if r.record_id == "p1" else r for r in BASE_MULTI)
    tampered = base._replace(before=before, after=before)
    tampered = tampered._replace(event=_reidentify(base.event, before, before))
    _reject(tampered, "prior_not_active_before")


def test_prior_missing_from_before_state_is_rejected() -> None:
    base = _keep()
    _reject(_tamper(base, lambda a: a, prior_record_id="missing"), "prior_not_in_before")


def test_duplicate_record_ids_in_before_state_are_rejected() -> None:
    base = _keep()
    before = (*BASE_MULTI, BASE_MULTI[1])
    tampered = base._replace(before=before, event=_reidentify(base.event, before, base.after))
    _reject(tampered, "duplicate_record_id")


def test_candidate_identifier_colliding_with_existing_record_is_rejected() -> None:
    base = _supersede()
    clash = CandidateRecord("u1", "stable_pref", "new value", 0.9, _h("cand evidence"))
    _reject(base, "event_candidate_id_mismatch", candidate=clash)


def test_second_active_record_in_single_slot_state_is_rejected() -> None:
    base = _build(Action.SUPERSEDE, before=BASE_SLOT_HISTORY, mode=StoreMode.SINGLE_SLOT_VERSIONED)
    _reject(_tamper(base, lambda a: _set(a, "p0", active=True)), "single_slot_multiple_active")


# ---------------------------------------------------------------------------------------------
# explicit unverified inputs


def test_candidate_is_required_for_a_committing_action() -> None:
    base = _supersede()
    _reject(base, "event_candidate_id_mismatch", candidate=None)
    admitting_without_candidate = _tamper(
        _keep(), lambda a: a, keep_admitted_candidate=True, candidate_record_id=None
    )
    _reject(admitting_without_candidate, "candidate_required", candidate=None)


def test_unverified_candidate_skips_content_binding_and_is_reported() -> None:
    base = _supersede()
    report = _validate(base, candidate=UNVERIFIED)
    assert report.unverified == ("candidate_content",)
    assert "candidate_binding" not in report.checks


def test_unverified_candidate_still_enforces_record_accounting() -> None:
    base = _supersede()
    injected = _tamper(base, lambda a: [*a, MemoryRecord("x9", "episodic_fact", "injected", True)])
    _reject(injected, "unaccounted_record_added", candidate=UNVERIFIED)
    unlinked = _tamper(base, lambda a: _set(a, "c1", active=False))
    with pytest.raises(ASKValidationError):
        _validate(unlinked, candidate=UNVERIFIED)


def test_configuration_is_required_unless_declared_unverified() -> None:
    base = _supersede()
    _reject(base, "configuration_binding_required", configuration=None)
    report = _validate(base, configuration=UNVERIFIED)
    assert report.unverified == ("configuration_digest",)


def test_validator_rejects_a_configuration_that_does_not_hash_to_the_identity() -> None:
    base = _supersede()
    changed = {**CFG_MAPPING, "parameters": {"example": 2}}
    _reject(base, "configuration_digest_mismatch", configuration=changed)


def test_apply_transition_verifies_configuration_when_supplied() -> None:
    trace = _trace(Action.SUPERSEDE)
    kwargs: dict[str, Any] = {
        "action": Action.SUPERSEDE,
        "store_mode": StoreMode.MULTI_RECORD,
        "prior_record_id": "p1",
        "candidate": CANDIDATE,
        "trace": trace,
    }
    apply_transition(BASE_MULTI, configuration=CFG_MAPPING, **kwargs)
    with pytest.raises(ASKValidationError) as info:
        apply_transition(BASE_MULTI, configuration={"other": 1}, **kwargs)
    assert info.value.code == "configuration_digest_mismatch"


def test_trace_logged_record_identifiers_must_match_the_event() -> None:
    base = _supersede()
    logged = {**base.trace.inputs, "prior_record_id": "p1", "candidate_record_id": "c1"}
    matching = replace(base.trace, inputs=logged)
    assert _validate(base._replace(trace=matching)).checks
    mismatched = replace(base.trace, inputs={**base.trace.inputs, "prior_record_id": "u1"})
    _reject(base._replace(trace=mismatched), "trace_event_record_mismatch")


def test_expected_store_mode_binds_the_mode_stated_by_the_event() -> None:
    base = _keep()
    report = _validate(base, expected_store_mode=StoreMode.MULTI_RECORD)
    assert "store_mode_binding" in report.checks
    _reject(base, "event_store_mode_mismatch", expected_store_mode=StoreMode.SINGLE_SLOT_VERSIONED)


def test_unsupported_argument_types_do_not_silently_skip_binding() -> None:
    base = _supersede()
    with pytest.raises(TypeError):
        _validate(base, candidate={"record_id": "c1"})
    with pytest.raises(TypeError):
        _validate(base, configuration="not a mapping")


def _three_event_log() -> list[TransitionEvent]:
    store = InMemoryASKStore(store_mode=StoreMode.MULTI_RECORD, records=BASE_MULTI)
    second = CandidateRecord("c2", "episodic_fact", "later value", 0.8, _h("c2 evidence"))
    steps = [
        (Action.ABSTAIN, "p1", CANDIDATE),
        (Action.SUPERSEDE, "p1", CANDIDATE),
        (Action.KEEP, "c1", second),
    ]
    return [
        store.apply(action=action, prior_record_id=prior, candidate=cand, trace=_trace(action))
        for action, prior, cand in steps
    ]


def test_event_chain_continuity_is_checked() -> None:
    events = _three_event_log()
    validate_event_chain(events, initial_state=BASE_MULTI)
    with pytest.raises(ASKValidationError) as info:
        validate_event_chain([events[0], events[2]])
    assert info.value.code == "event_chain_break"
    with pytest.raises(ASKValidationError) as info:
        validate_event_chain(events, initial_state=BASE_SLOT_HISTORY)
    assert info.value.code == "initial_state_digest_mismatch"
    forged = [events[0], replace(events[1], event_id=_h("forged")), events[2]]
    with pytest.raises(ASKValidationError) as info:
        validate_event_chain(forged)
    assert info.value.code == "event_id_mismatch"


# ---------------------------------------------------------------------------------------------
# configuration identity


def test_canonical_serialization_is_sorted_compact_utf8() -> None:
    value = {"b": [1, 2.5, None, True], "a": {"z": "é", "y": "x y"}}
    expected = '{"a":{"y":"x y","z":"é"},"b":[1,2.5,null,true]}'.encode()
    assert canonical_json_bytes(value) == expected
    reordered = {"a": {"y": "x y", "z": "é"}, "b": [1, 2.5, None, True]}
    assert canonical_json_bytes(reordered) == expected
    assert configuration_digest(value) == hashlib.sha256(expected).hexdigest()


def test_canonical_serialization_distinguishes_int_and_float() -> None:
    assert configuration_digest({"v": 1}) != configuration_digest({"v": 1.0})


@pytest.mark.parametrize(
    ("bad", "error"),
    [
        ({"v": math.nan}, ValueError),
        ({"v": math.inf}, ValueError),
        ({1: "x"}, TypeError),
        ({"v": {1, 2}}, TypeError),
        ({"v": b"bytes"}, TypeError),
    ],
)
def test_canonical_serialization_rejects_non_canonical_values(bad: dict, error: type) -> None:
    with pytest.raises(error):
        canonical_json_bytes(bad)


def test_identity_computed_from_configuration_verifies() -> None:
    identity = ConfigurationIdentity.from_configuration("id", "ask-mgp/v1", CFG_MAPPING)
    identity.verify(CFG_MAPPING)
    identity.verify(dict(reversed(list(CFG_MAPPING.items()))))
    with pytest.raises(ASKValidationError) as info:
        identity.verify({**CFG_MAPPING, "parameters": {"example": 2}})
    assert info.value.code == "configuration_digest_mismatch"


def test_all_zero_identity_is_not_bound_to_any_configuration() -> None:
    zero = ConfigurationIdentity.unverified("lme", "ask-lme-scorecard/v1", "0" * 64)
    with pytest.raises(ASKValidationError) as info:
        zero.verify(ASKLMEAdapter.bound("lme").frozen_configuration())
    assert info.value.code == "configuration_digest_mismatch"
    assert ConfigurationIdentity("lme", "ask-lme-scorecard/v1", "0" * 64) == zero


def test_format_check_on_construction_is_unchanged() -> None:
    for bad in ("", "g" * 64, "a" * 63):
        with pytest.raises(ValueError, match="64-character"):
            ConfigurationIdentity("id", "v1", bad)


def test_zero_identity_adapter_fails_identity_verification() -> None:
    adapter = ASKLMEAdapter(ConfigurationIdentity("lme", "ask-lme-scorecard/v1", "0" * 64))
    with pytest.raises(ASKValidationError) as info:
        adapter.verify_configuration_identity()
    assert info.value.code == "configuration_digest_mismatch"


def test_zero_identity_transition_fails_validation_against_frozen_configuration() -> None:
    adapter = ASKLMEAdapter(ConfigurationIdentity("lme", "ask-lme-scorecard/v1", "0" * 64))
    trace = replace(
        _trace(Action.SUPERSEDE),
        configuration=adapter.configuration,
        adapter_version=adapter.adapter_version,
    )
    after, event = apply_transition(
        BASE_MULTI,
        action=Action.SUPERSEDE,
        store_mode=StoreMode.MULTI_RECORD,
        prior_record_id="p1",
        candidate=CANDIDATE,
        trace=trace,
    )
    with pytest.raises(ASKValidationError) as info:
        ASKInvariantValidator().validate(
            before=BASE_MULTI,
            after=after,
            event=event,
            trace=trace,
            candidate=CANDIDATE,
            configuration=adapter.frozen_configuration(),
        )
    assert info.value.code == "configuration_digest_mismatch"


# ---------------------------------------------------------------------------------------------
# adapters


def _features() -> FeatureSnapshot:
    return FeatureSnapshot(c=0.95, e=0.85, f=0.0, r=-1.0, rho=0.6)


def _shifted(delta: float) -> ScorecardConfig:
    return ScorecardConfig(
        weights=DEFAULT_SCORECARD_CONFIG.weights,
        theta_sup={k: v + delta for k, v in DEFAULT_SCORECARD_CONFIG.theta_sup.items()},
        theta_abs={k: v + delta for k, v in DEFAULT_SCORECARD_CONFIG.theta_abs.items()},
    )


def test_bound_lme_adapter_identity_verifies_and_replays_strictly() -> None:
    adapter = ASKLMEAdapter.bound("lme-test")
    adapter.verify_configuration_identity()
    action, trace = adapter.decide(
        features=_features(),
        memory_type="episodic_fact",
        evidence_references=REFS,
        prior_record_id="p1",
        candidate_record_id="c1",
    )
    assert adapter.replay(trace, strict=True) is action
    frozen = adapter.frozen_configuration()
    assert frozen["feature_schema_version"] == trace.inputs["feature_schema_version"]
    assert tuple(frozen["ordered_rules"]) == tuple(trace.intermediates["ordered_rules"])
    assert frozen["relation_guard"] == trace.intermediates["relation_guard"]


def test_shifted_thresholds_under_the_same_identity_fail_strict_replay() -> None:
    adapter = ASKLMEAdapter.bound("lme-test")
    _, trace = adapter.decide(
        features=_features(),
        memory_type="episodic_fact",
        evidence_references=REFS,
        prior_record_id="p1",
        candidate_record_id="c1",
    )
    shifted_same_identity = ASKLMEAdapter(adapter.configuration, config=_shifted(0.01))
    assert shifted_same_identity.replay(trace) is trace.final_action  # default replay is unchanged
    with pytest.raises(ASKValidationError) as info:
        shifted_same_identity.replay(trace, strict=True)
    assert info.value.code == "configuration_digest_mismatch"


def test_shifted_thresholds_under_their_own_identity_fail_strict_replay_of_foreign_trace() -> None:
    adapter = ASKLMEAdapter.bound("lme-test")
    _, trace = adapter.decide(
        features=_features(),
        memory_type="episodic_fact",
        evidence_references=REFS,
        prior_record_id="p1",
        candidate_record_id="c1",
    )
    other = ASKLMEAdapter.bound("lme-test", config=_shifted(0.01))
    other.verify_configuration_identity()
    with pytest.raises(ASKValidationError) as info:
        other.replay(trace, strict=True)
    assert info.value.code == "trace_configuration_mismatch"


def test_strict_replay_rejects_logged_threshold_that_differs_from_replay_configuration() -> None:
    adapter = ASKLMEAdapter.bound("lme-test")
    _, trace = adapter.decide(
        features=_features(),
        memory_type="episodic_fact",
        evidence_references=REFS,
        prior_record_id="p1",
        candidate_record_id="c1",
    )
    forged = replace(trace, intermediates={**trace.intermediates, "theta_sup": 0.5})
    assert adapter.replay(forged) is trace.final_action  # default replay is unchanged
    with pytest.raises(ASKValidationError) as info:
        adapter.replay(forged, strict=True)
    assert info.value.code == "logged_threshold_mismatch"


def test_bound_mgp_adapter_verifies_and_strict_replay_checks_trace_identity() -> None:
    adapter = ASKMGPAdapter.bound("mgp-test")
    adapter.verify_configuration_identity()
    action, trace = adapter.decide(
        model_proposal=Action.ABSTAIN,
        rule_proposal=Action.SUPERSEDE,
        rule_verdict="direct_documented_slot_change",
        evidence_references=REFS,
        guard_rule_id="indexed-evidence/v1",
    )
    assert adapter.replay(trace, strict=True) is action
    other = ASKMGPAdapter.bound("mgp-other")
    with pytest.raises(ASKValidationError) as info:
        other.replay(trace, strict=True)
    assert info.value.code == "trace_configuration_mismatch"


def test_adapter_with_arbitrary_digest_keeps_working_in_default_mode() -> None:
    adapter = ASKMGPAdapter(ConfigurationIdentity("frozen-test", "ask-mgp/v1", "2" * 64))
    action, trace = adapter.decide(
        model_proposal=Action.KEEP,
        rule_proposal=Action.KEEP,
        rule_verdict="unresolved",
        evidence_references=REFS,
        guard_rule_id="indexed-evidence/v1",
    )
    assert adapter.replay(trace) is action
    with pytest.raises(ASKValidationError):
        adapter.replay(trace, strict=True)


# ---------------------------------------------------------------------------------------------
# characterization of known limits (these tests document behavior that is NOT enforced)


def test_known_limit_event_metadata_is_not_part_of_the_event_identifier() -> None:
    base = _supersede()
    annotated = base._replace(event=replace(base.event, metadata={"note": "unbound"}))
    assert _validate(annotated).unverified == ()


def test_known_limit_temporal_event_mode_has_no_temporal_semantics() -> None:
    """temporal_event is checked with the same accounting as multi_record. No time semantics."""
    transition = _build(Action.SUPERSEDE, mode=StoreMode.TEMPORAL_EVENT)
    assert _validate(transition).unverified == ()


def test_known_limit_self_consistent_forgery_of_all_bound_fields_is_accepted() -> None:
    """An event whose id is recomputed over a conforming transition is accepted. No signature."""
    base = _supersede()
    rebuilt = replace(base.event, event_id="0" * 64)
    forged = base._replace(event=replace(rebuilt, event_id=compute_event_id(rebuilt)))
    assert _validate(forged).checks
