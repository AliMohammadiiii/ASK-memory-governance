"""Pure reference state machine for the ASK audit contract.

The implementation fixes observable transition semantics. It intentionally does
not prescribe a predictor, feature representation, or storage cardinality.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, Protocol, TypeAlias, runtime_checkable

from ask.memory.models import ControllerAction

Action: TypeAlias = ControllerAction


class StoreMode(str, Enum):
    SINGLE_SLOT_VERSIONED = "single_slot_versioned"
    MULTI_RECORD = "multi_record"
    TEMPORAL_EVENT = "temporal_event"


class ReplayScope(str, Enum):
    COMPOSITION_AND_TRANSITION = "composition_and_transition"
    FINAL_POLICY_AND_TRANSITION = "final_policy_and_transition"


@dataclass(frozen=True)
class EvidenceReference:
    reference_id: str
    sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.sha256, "evidence reference")


@dataclass(frozen=True)
class ConfigurationIdentity:
    configuration_id: str
    adapter_version: str
    sha256: str

    def __post_init__(self) -> None:
        if not self.configuration_id or not self.adapter_version:
            raise ValueError("configuration identity and adapter version are required")
        _require_sha256(self.sha256, "configuration")


@dataclass(frozen=True)
class PredecessorReference:
    record_id: str


@dataclass(frozen=True)
class CandidateRecord:
    record_id: str
    memory_type: str
    value: str
    confidence: float
    evidence_digest: str

    def __post_init__(self) -> None:
        if not self.record_id or not self.memory_type:
            raise ValueError("candidate record_id and memory_type are required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("candidate confidence must be in [0, 1]")
        _require_sha256(self.evidence_digest, "candidate evidence")


@dataclass(frozen=True)
class MemoryRecord:
    record_id: str
    memory_type: str
    value: str
    active: bool = True
    predecessor: PredecessorReference | None = None
    evidence_digest: str | None = None


@dataclass(frozen=True)
class DecisionTrace:
    adapter_id: str
    adapter_version: str
    replay_scope: ReplayScope
    configuration: ConfigurationIdentity
    evidence_references: tuple[EvidenceReference, ...]
    evidence_digest: str
    inputs: Mapping[str, Any]
    intermediates: Mapping[str, Any]
    final_action: Action
    sufficient_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.adapter_id or not self.adapter_version:
            raise ValueError("adapter identity is required")
        if self.adapter_version != self.configuration.adapter_version:
            raise ValueError("trace and configuration adapter versions differ")
        _require_sha256(self.evidence_digest, "trace evidence")
        if not self.sufficient_fields:
            raise ValueError("trace must declare fields sufficient for its replay scope")


@dataclass(frozen=True)
class TransitionEvent:
    event_id: str
    action: Action
    store_mode: StoreMode
    prior_record_id: str | None
    candidate_record_id: str | None
    resulting_record_id: str | None
    predecessor_record_id: str | None
    configuration: ConfigurationIdentity
    evidence_digest: str
    before_digest: str
    after_digest: str
    keep_admitted_candidate: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["action"] = self.action.value
        value["store_mode"] = self.store_mode.value
        return value


@runtime_checkable
class ASKAdapter(Protocol):
    adapter_id: str
    adapter_version: str
    store_mode: StoreMode
    replay_scope: ReplayScope

    def replay(self, trace: DecisionTrace) -> Action: ...


@runtime_checkable
class ASKStore(Protocol):
    store_mode: StoreMode

    def records(self) -> tuple[MemoryRecord, ...]: ...

    def apply(
        self,
        *,
        action: Action,
        prior_record_id: str | None,
        candidate: CandidateRecord | None,
        trace: DecisionTrace,
        admit_candidate_on_keep: bool = False,
    ) -> TransitionEvent: ...


def _require_sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower()):
        raise ValueError(f"{label} digest must be a 64-character SHA-256 hex string")


def stable_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evidence_set_digest(references: Sequence[EvidenceReference]) -> str:
    return stable_digest(
        [{"reference_id": item.reference_id, "sha256": item.sha256} for item in references]
    )


def state_digest(records: Sequence[MemoryRecord]) -> str:
    normalized = []
    for record in sorted(records, key=lambda item: item.record_id):
        normalized.append(
            {
                "record_id": record.record_id,
                "memory_type": record.memory_type,
                "value": record.value,
                "active": record.active,
                "predecessor": record.predecessor.record_id if record.predecessor else None,
                "evidence_digest": record.evidence_digest,
            }
        )
    return stable_digest(normalized)


@dataclass(frozen=True)
class _TransitionResult:
    records: tuple[MemoryRecord, ...]
    candidate_id: str | None = None
    resulting_id: str | None = None
    predecessor_id: str | None = None
    keep_admitted: bool = False


def _apply_keep(
    before: tuple[MemoryRecord, ...],
    *,
    by_id: Mapping[str, MemoryRecord],
    prior: MemoryRecord | None,
    candidate: CandidateRecord | None,
    store_mode: StoreMode,
    admit_candidate: bool,
) -> _TransitionResult:
    if prior is not None and not prior.active:
        raise ValueError("Keep requires the compared prior to remain active")
    candidate_id = candidate.record_id if candidate else None
    if not admit_candidate:
        return _TransitionResult(before, candidate_id=candidate_id)
    if store_mode is not StoreMode.MULTI_RECORD:
        raise ValueError("candidate admission on Keep is only valid in multi_record mode")
    if candidate is None:
        raise ValueError("candidate admission on Keep requires a candidate")
    if candidate.record_id in by_id:
        raise ValueError("candidate identifier already exists")
    admitted = MemoryRecord(
        record_id=candidate.record_id,
        memory_type=candidate.memory_type,
        value=candidate.value,
        active=True,
        evidence_digest=candidate.evidence_digest,
    )
    return _TransitionResult(
        (*before, admitted),
        candidate_id=candidate.record_id,
        resulting_id=admitted.record_id,
        keep_admitted=True,
    )


def _apply_supersede(
    before: tuple[MemoryRecord, ...],
    *,
    by_id: Mapping[str, MemoryRecord],
    prior: MemoryRecord | None,
    candidate: CandidateRecord | None,
) -> _TransitionResult:
    if prior is None or not prior.active:
        raise ValueError("Supersede requires an active compared prior")
    if candidate is None:
        raise ValueError("Supersede requires a candidate")
    if candidate.record_id in by_id:
        raise ValueError("candidate identifier already exists")
    retained = tuple(
        replace(record, active=False) if record.record_id == prior.record_id else record
        for record in before
    )
    successor = MemoryRecord(
        record_id=candidate.record_id,
        memory_type=candidate.memory_type,
        value=candidate.value,
        active=True,
        predecessor=PredecessorReference(prior.record_id),
        evidence_digest=candidate.evidence_digest,
    )
    return _TransitionResult(
        (*retained, successor),
        candidate_id=candidate.record_id,
        resulting_id=successor.record_id,
        predecessor_id=prior.record_id,
    )


def _transition_result(
    before: tuple[MemoryRecord, ...],
    *,
    by_id: Mapping[str, MemoryRecord],
    prior: MemoryRecord | None,
    action: Action,
    store_mode: StoreMode,
    candidate: CandidateRecord | None,
    admit_candidate_on_keep: bool,
) -> _TransitionResult:
    if action is Action.ABSTAIN:
        return _TransitionResult(before, candidate_id=candidate.record_id if candidate else None)
    if action is Action.KEEP:
        return _apply_keep(
            before,
            by_id=by_id,
            prior=prior,
            candidate=candidate,
            store_mode=store_mode,
            admit_candidate=admit_candidate_on_keep,
        )
    if action is Action.SUPERSEDE:
        return _apply_supersede(
            before,
            by_id=by_id,
            prior=prior,
            candidate=candidate,
        )
    raise ValueError(f"unsupported action {action!r}")


def apply_transition(
    records: Sequence[MemoryRecord],
    *,
    action: Action,
    store_mode: StoreMode,
    prior_record_id: str | None,
    candidate: CandidateRecord | None,
    trace: DecisionTrace,
    admit_candidate_on_keep: bool = False,
) -> tuple[tuple[MemoryRecord, ...], TransitionEvent]:
    """Apply one deterministic ASK transition to an immutable state snapshot."""
    before = tuple(records)
    by_id = {record.record_id: record for record in before}
    if len(by_id) != len(before):
        raise ValueError("state contains duplicate record identifiers")
    prior = by_id.get(prior_record_id) if prior_record_id is not None else None
    if prior_record_id is not None and prior is None:
        raise ValueError(f"prior record {prior_record_id!r} does not exist")
    if trace.final_action != action:
        raise ValueError("trace final action differs from requested transition")

    result = _transition_result(
        before,
        by_id=by_id,
        prior=prior,
        action=action,
        store_mode=store_mode,
        candidate=candidate,
        admit_candidate_on_keep=admit_candidate_on_keep,
    )
    after = result.records

    before_hash = state_digest(before)
    after_hash = state_digest(after)
    event_body = {
        "action": action.value,
        "store_mode": store_mode.value,
        "prior_record_id": prior_record_id,
        "candidate_record_id": result.candidate_id,
        "resulting_record_id": result.resulting_id,
        "predecessor_record_id": result.predecessor_id,
        "configuration_id": trace.configuration.configuration_id,
        "configuration_sha256": trace.configuration.sha256,
        "evidence_digest": trace.evidence_digest,
        "before_digest": before_hash,
        "after_digest": after_hash,
        "keep_admitted_candidate": result.keep_admitted,
    }
    event = TransitionEvent(
        event_id=stable_digest(event_body),
        action=action,
        store_mode=store_mode,
        prior_record_id=prior_record_id,
        candidate_record_id=result.candidate_id,
        resulting_record_id=result.resulting_id,
        predecessor_record_id=result.predecessor_id,
        configuration=trace.configuration,
        evidence_digest=trace.evidence_digest,
        before_digest=before_hash,
        after_digest=after_hash,
        keep_admitted_candidate=result.keep_admitted,
    )
    ASKInvariantValidator().validate(before=before, after=after, event=event, trace=trace)
    return after, event


def replay_transition(
    records: Sequence[MemoryRecord],
    *,
    event: TransitionEvent,
    candidate: CandidateRecord | None,
    trace: DecisionTrace,
) -> tuple[tuple[MemoryRecord, ...], TransitionEvent]:
    replayed = apply_transition(
        records,
        action=event.action,
        store_mode=event.store_mode,
        prior_record_id=event.prior_record_id,
        candidate=candidate,
        trace=trace,
        admit_candidate_on_keep=event.keep_admitted_candidate,
    )
    if replayed[1] != event:
        raise ValueError("transition replay differs from preserved event")
    return replayed


class ASKInvariantValidator:
    """Validate state, lineage, event completeness, and action semantics."""

    @staticmethod
    def _validate_event_identity(
        *,
        before: Sequence[MemoryRecord],
        after: Sequence[MemoryRecord],
        event: TransitionEvent,
        trace: DecisionTrace,
    ) -> None:
        if event.configuration != trace.configuration:
            raise ValueError("event and trace configuration identities differ")
        if event.evidence_digest != trace.evidence_digest:
            raise ValueError("event and trace evidence digests differ")
        if event.action != trace.final_action:
            raise ValueError("event and trace actions differ")
        if event.before_digest != state_digest(before) or event.after_digest != state_digest(after):
            raise ValueError("event state digest does not match transition state")
        _require_sha256(event.event_id, "event identifier")

    @staticmethod
    def _validate_action(
        *,
        before: Sequence[MemoryRecord],
        after: Sequence[MemoryRecord],
        event: TransitionEvent,
        before_by_id: Mapping[str, MemoryRecord],
        after_by_id: Mapping[str, MemoryRecord],
    ) -> None:
        prior_before = before_by_id.get(event.prior_record_id or "")
        prior_after = after_by_id.get(event.prior_record_id or "")
        if event.action is Action.ABSTAIN:
            ASKInvariantValidator._validate_abstain(before, after, event)
        elif event.action is Action.KEEP:
            ASKInvariantValidator._validate_keep(
                before,
                after,
                event,
                prior_before=prior_before,
                prior_after=prior_after,
            )
        elif event.action is Action.SUPERSEDE:
            ASKInvariantValidator._validate_supersede(
                event,
                prior_before=prior_before,
                prior_after=prior_after,
                after_by_id=after_by_id,
            )

    @staticmethod
    def _validate_abstain(
        before: Sequence[MemoryRecord],
        after: Sequence[MemoryRecord],
        event: TransitionEvent,
    ) -> None:
        if tuple(before) != tuple(after) or event.resulting_record_id is not None:
            raise ValueError("Abstain must commit no candidate and preserve state")

    @staticmethod
    def _validate_keep(
        before: Sequence[MemoryRecord],
        after: Sequence[MemoryRecord],
        event: TransitionEvent,
        *,
        prior_before: MemoryRecord | None,
        prior_after: MemoryRecord | None,
    ) -> None:
        if prior_before is not None and prior_after != prior_before:
            raise ValueError("Keep must preserve the compared prior")
        if event.store_mode is StoreMode.SINGLE_SLOT_VERSIONED and tuple(before) != tuple(after):
            raise ValueError("single-slot Keep must preserve the full state")
        if event.keep_admitted_candidate and event.store_mode is not StoreMode.MULTI_RECORD:
            raise ValueError("Keep admission requires multi-record mode")

    @staticmethod
    def _validate_supersede(
        event: TransitionEvent,
        *,
        prior_before: MemoryRecord | None,
        prior_after: MemoryRecord | None,
        after_by_id: Mapping[str, MemoryRecord],
    ) -> None:
        if prior_before is None or prior_after is None or prior_after.active:
            raise ValueError("Supersede must retain and invalidate the compared prior")
        successor = after_by_id.get(event.resulting_record_id or "")
        if successor is None or not successor.active:
            raise ValueError("Supersede must create an active successor")
        if (
            successor.predecessor is None
            or successor.predecessor.record_id != prior_before.record_id
        ):
            raise ValueError("Supersede successor must resolve to the retained predecessor")

    def validate(
        self,
        *,
        before: Sequence[MemoryRecord],
        after: Sequence[MemoryRecord],
        event: TransitionEvent,
        trace: DecisionTrace,
    ) -> None:
        self._validate_event_identity(before=before, after=after, event=event, trace=trace)
        self._validate_unique_ids(after)
        self._validate_lineage(after)

        before_by_id = {record.record_id: record for record in before}
        after_by_id = {record.record_id: record for record in after}
        self._validate_action(
            before=before,
            after=after,
            event=event,
            before_by_id=before_by_id,
            after_by_id=after_by_id,
        )

        if event.store_mode is StoreMode.SINGLE_SLOT_VERSIONED:
            active = [record for record in after if record.active]
            if len(active) > 1:
                raise ValueError("single-slot state has multiple active records")

    @staticmethod
    def _validate_unique_ids(records: Sequence[MemoryRecord]) -> None:
        identifiers = [record.record_id for record in records]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("state contains duplicate record identifiers")

    @staticmethod
    def _validate_lineage(records: Sequence[MemoryRecord]) -> None:
        by_id = {record.record_id: record for record in records}
        for record in records:
            if record.predecessor and record.predecessor.record_id not in by_id:
                raise ValueError(f"dangling predecessor for {record.record_id}")
            seen: set[str] = set()
            current = record
            while current.predecessor is not None:
                predecessor_id = current.predecessor.record_id
                if predecessor_id in seen or predecessor_id == record.record_id:
                    raise ValueError(f"lineage cycle at {record.record_id}")
                seen.add(predecessor_id)
                current = by_id[predecessor_id]


class InMemoryASKStore:
    """Small deterministic conformance store used by tests and examples."""

    def __init__(self, *, store_mode: StoreMode, records: Sequence[MemoryRecord] = ()) -> None:
        self.store_mode = store_mode
        self._records = tuple(records)

    def records(self) -> tuple[MemoryRecord, ...]:
        return self._records

    def apply(
        self,
        *,
        action: Action,
        prior_record_id: str | None,
        candidate: CandidateRecord | None,
        trace: DecisionTrace,
        admit_candidate_on_keep: bool = False,
    ) -> TransitionEvent:
        self._records, event = apply_transition(
            self._records,
            action=action,
            store_mode=self.store_mode,
            prior_record_id=prior_record_id,
            candidate=candidate,
            trace=trace,
            admit_candidate_on_keep=admit_candidate_on_keep,
        )
        return event
