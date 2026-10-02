"""Pure reference state machine for the ASK audit contract.

The implementation fixes observable transition semantics. It intentionally does
not prescribe a predictor, feature representation, or storage cardinality.
"""

from __future__ import annotations

import hashlib
import json
import math
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


class ASKValidationError(ValueError):
    """Rejection of a transition, event, state or configuration binding.

    The class subclasses ``ValueError`` so callers written against the earlier validator keep
    working. ``code`` is the stable reason code of the first violation and ``codes`` lists every
    reason code found by the stage that rejected the input.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        violations: Sequence[tuple[str, str]] | None = None,
    ) -> None:
        pairs = tuple(violations) if violations else ((code, message),)
        self.code = pairs[0][0]
        self.codes = tuple(item[0] for item in pairs)
        self.violations = pairs
        super().__init__("; ".join(f"[{item[0]}] {item[1]}" for item in pairs))

    @classmethod
    def from_violations(cls, violations: Sequence[tuple[str, str]]) -> ASKValidationError:
        first = violations[0]
        return cls(first[0], first[1], violations=violations)


class _Unverified:
    """Marker for an input the caller explicitly declines to bind or verify."""

    _instance: _Unverified | None = None

    def __new__(cls) -> _Unverified:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNVERIFIED"


UNVERIFIED = _Unverified()


@dataclass(frozen=True)
class ValidationReport:
    """Names of the checks that ran and of the bindings that were explicitly not verified."""

    checks: tuple[str, ...]
    unverified: tuple[str, ...] = ()


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

    @classmethod
    def from_configuration(
        cls, configuration_id: str, adapter_version: str, configuration: Mapping[str, Any]
    ) -> ConfigurationIdentity:
        """Build an identity whose digest is computed from a frozen configuration mapping."""
        return cls(configuration_id, adapter_version, configuration_digest(configuration))

    @classmethod
    def unverified(
        cls, configuration_id: str, adapter_version: str, sha256: str
    ) -> ConfigurationIdentity:
        """Format-only construction. The digest is not tied to any configuration mapping.

        The plain constructor behaves the same way and is kept for compatibility. Neither form
        establishes that ``sha256`` identifies a configuration; call ``verify`` for that.
        """
        return cls(configuration_id, adapter_version, sha256)

    def verify(self, configuration: Mapping[str, Any]) -> None:
        """Recompute the digest of ``configuration`` and reject a mismatch."""
        expected = configuration_digest(configuration)
        if self.sha256.lower() != expected:
            raise ASKValidationError(
                "configuration_digest_mismatch",
                f"configuration identity {self.configuration_id!r} carries digest "
                f"{self.sha256[:12]}... but the supplied configuration hashes to "
                f"{expected[:12]}...",
            )


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


def _canonical_value(value: Any, path: str) -> Any:
    if isinstance(value, Enum):
        value = value.value
    if value is None or isinstance(value, bool | str | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"configuration value at {path} is not finite")
        return value
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"configuration key at {path} is not a string: {key!r}")
            out[key] = _canonical_value(item, f"{path}.{key}")
        return out
    if isinstance(value, list | tuple):
        return [_canonical_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    raise TypeError(f"configuration value at {path} has non-canonical type {type(value).__name__}")


def canonical_json_bytes(configuration: Mapping[str, Any]) -> bytes:
    """Canonical serialization of a frozen configuration mapping.

    Sorted keys, no insignificant whitespace, non-ASCII characters not escaped, UTF-8 bytes.
    Only str-keyed mappings, lists, tuples, str, int, finite float, bool and None are accepted.
    The integer 1 and the float 1.0 serialize differently. This is not RFC 8785 (JCS).
    """
    payload = json.dumps(
        _canonical_value(configuration, "$"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return payload.encode("utf-8")


def configuration_digest(configuration: Mapping[str, Any]) -> str:
    """SHA-256 hex digest of ``canonical_json_bytes(configuration)``."""
    return hashlib.sha256(canonical_json_bytes(configuration)).hexdigest()


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


def _event_body(
    *,
    action: Action,
    store_mode: StoreMode,
    prior_record_id: str | None,
    candidate_record_id: str | None,
    resulting_record_id: str | None,
    predecessor_record_id: str | None,
    configuration: ConfigurationIdentity,
    evidence_digest: str,
    before_digest: str,
    after_digest: str,
    keep_admitted_candidate: bool,
) -> dict[str, Any]:
    return {
        "action": action.value,
        "store_mode": store_mode.value,
        "prior_record_id": prior_record_id,
        "candidate_record_id": candidate_record_id,
        "resulting_record_id": resulting_record_id,
        "predecessor_record_id": predecessor_record_id,
        "configuration_id": configuration.configuration_id,
        "configuration_sha256": configuration.sha256,
        "evidence_digest": evidence_digest,
        "before_digest": before_digest,
        "after_digest": after_digest,
        "keep_admitted_candidate": keep_admitted_candidate,
    }


def compute_event_id(event: TransitionEvent) -> str:
    """Digest of the event body. ``metadata`` and ``adapter_version`` are not part of the body."""
    return stable_digest(
        _event_body(
            action=event.action,
            store_mode=event.store_mode,
            prior_record_id=event.prior_record_id,
            candidate_record_id=event.candidate_record_id,
            resulting_record_id=event.resulting_record_id,
            predecessor_record_id=event.predecessor_record_id,
            configuration=event.configuration,
            evidence_digest=event.evidence_digest,
            before_digest=event.before_digest,
            after_digest=event.after_digest,
            keep_admitted_candidate=event.keep_admitted_candidate,
        )
    )


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
    configuration: Mapping[str, Any] | _Unverified = UNVERIFIED,
) -> tuple[tuple[MemoryRecord, ...], TransitionEvent]:
    """Apply one deterministic ASK transition to an immutable state snapshot.

    ``configuration`` is the frozen configuration mapping whose digest must equal the identity
    in ``trace``. The default ``UNVERIFIED`` keeps the earlier behavior, in which the identity is
    checked for format only.
    """
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
    event_body = _event_body(
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
    ASKInvariantValidator().validate(
        before=before,
        after=after,
        event=event,
        trace=trace,
        candidate=candidate,
        configuration=configuration,
    )
    return after, event


def replay_transition(
    records: Sequence[MemoryRecord],
    *,
    event: TransitionEvent,
    candidate: CandidateRecord | None,
    trace: DecisionTrace,
    configuration: Mapping[str, Any] | _Unverified = UNVERIFIED,
) -> tuple[tuple[MemoryRecord, ...], TransitionEvent]:
    replayed = apply_transition(
        records,
        action=event.action,
        store_mode=event.store_mode,
        prior_record_id=event.prior_record_id,
        candidate=candidate,
        trace=trace,
        admit_candidate_on_keep=event.keep_admitted_candidate,
        configuration=configuration,
    )
    if replayed[1] != event:
        raise ValueError("transition replay differs from preserved event")
    return replayed


_RECORD_FIELDS = ("memory_type", "value", "active", "predecessor", "evidence_digest")


def _changed_fields(left: MemoryRecord, right: MemoryRecord) -> tuple[str, ...]:
    return tuple(name for name in _RECORD_FIELDS if getattr(left, name) != getattr(right, name))


class ASKInvariantValidator:
    """Validate state, lineage, event completeness, and action semantics.

    Beyond the original structural checks, ``validate`` accounts for every record: the only
    differences between ``before`` and ``after`` that an action may produce are the ones listed
    in ``_validate_transition_accounting``. A conforming transition cannot delete, mutate,
    deactivate or add any other record, and the retained predecessor of a Supersede keeps every
    field except ``active``. The validator is fail-closed: the candidate and the frozen
    configuration must be supplied, or the caller must pass ``UNVERIFIED`` for that input, and
    ``ValidationReport.unverified`` records the choice.
    """

    @staticmethod
    def _validate_event_identity(
        *,
        before: Sequence[MemoryRecord],
        after: Sequence[MemoryRecord],
        event: TransitionEvent,
        trace: DecisionTrace,
    ) -> None:
        if event.configuration != trace.configuration:
            raise ASKValidationError(
                "event_configuration_mismatch", "event and trace configuration identities differ"
            )
        if event.evidence_digest != trace.evidence_digest:
            raise ASKValidationError(
                "event_evidence_digest_mismatch", "event and trace evidence digests differ"
            )
        if event.action != trace.final_action:
            raise ASKValidationError("event_action_mismatch", "event and trace actions differ")
        if event.before_digest != state_digest(before) or event.after_digest != state_digest(after):
            raise ASKValidationError(
                "state_digest_mismatch", "event state digest does not match transition state"
            )
        try:
            _require_sha256(event.event_id, "event identifier")
        except ValueError as exc:
            raise ASKValidationError("event_id_format", str(exc)) from exc
        if trace.evidence_digest != evidence_set_digest(trace.evidence_references):
            raise ASKValidationError(
                "trace_evidence_digest_mismatch",
                "trace evidence digest is not the digest of its evidence references",
            )
        if event.event_id != compute_event_id(event):
            raise ASKValidationError(
                "event_id_mismatch", "event identifier is not the digest of the event body"
            )

    @staticmethod
    def _validate_trace_event_binding(*, event: TransitionEvent, trace: DecisionTrace) -> None:
        """Record identifiers that a trace logs among its inputs must match the event."""
        logged = (
            ("prior_record_id", event.prior_record_id),
            ("candidate_record_id", event.candidate_record_id),
        )
        for key, value in logged:
            if key in trace.inputs and trace.inputs[key] != value:
                raise ASKValidationError(
                    "trace_event_record_mismatch",
                    f"trace input {key!r} is {trace.inputs[key]!r} but the event has {value!r}",
                )

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
        else:
            raise ASKValidationError("unsupported_action", f"unsupported action {event.action!r}")

    @staticmethod
    def _validate_abstain(
        before: Sequence[MemoryRecord],
        after: Sequence[MemoryRecord],
        event: TransitionEvent,
    ) -> None:
        if tuple(before) != tuple(after) or event.resulting_record_id is not None:
            raise ASKValidationError(
                "abstain_state_changed", "Abstain must commit no candidate and preserve state"
            )

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
            raise ASKValidationError("keep_prior_changed", "Keep must preserve the compared prior")
        if event.store_mode is StoreMode.SINGLE_SLOT_VERSIONED and tuple(before) != tuple(after):
            raise ASKValidationError(
                "keep_single_slot_state_changed", "single-slot Keep must preserve the full state"
            )
        if event.keep_admitted_candidate and event.store_mode is not StoreMode.MULTI_RECORD:
            raise ASKValidationError(
                "keep_admission_mode", "Keep admission requires multi-record mode"
            )

    @staticmethod
    def _validate_supersede(
        event: TransitionEvent,
        *,
        prior_before: MemoryRecord | None,
        prior_after: MemoryRecord | None,
        after_by_id: Mapping[str, MemoryRecord],
    ) -> None:
        if prior_before is None or prior_after is None or prior_after.active:
            raise ASKValidationError(
                "supersede_prior_not_invalidated",
                "Supersede must retain and invalidate the compared prior",
            )
        successor = after_by_id.get(event.resulting_record_id or "")
        if successor is None or not successor.active:
            raise ASKValidationError(
                "supersede_successor_missing", "Supersede must create an active successor"
            )
        if (
            successor.predecessor is None
            or successor.predecessor.record_id != prior_before.record_id
        ):
            raise ASKValidationError(
                "supersede_successor_lineage",
                "Supersede successor must resolve to the retained predecessor",
            )

    @staticmethod
    def _validate_event_fields(
        *,
        event: TransitionEvent,
        candidate: CandidateRecord | None | _Unverified,
    ) -> None:
        """Check that the identifiers and flags in the event follow from the action."""
        violations: list[tuple[str, str]] = []
        action = event.action
        admits = action is Action.KEEP and event.keep_admitted_candidate
        commits = action is Action.SUPERSEDE or admits
        if event.keep_admitted_candidate and action is not Action.KEEP:
            violations.append(
                ("event_admission_flag_mismatch", "keep_admitted_candidate is set on a non-Keep")
            )
        if isinstance(candidate, CandidateRecord):
            expected_candidate: str | None = candidate.record_id
        elif candidate is None:
            expected_candidate = None
        else:
            expected_candidate = event.candidate_record_id
        if event.candidate_record_id != expected_candidate:
            violations.append(
                (
                    "event_candidate_id_mismatch",
                    f"event candidate {event.candidate_record_id!r} differs from the supplied "
                    f"candidate {expected_candidate!r}",
                )
            )
        expected_resulting = expected_candidate if commits else None
        if event.resulting_record_id != expected_resulting:
            violations.append(
                (
                    "event_resulting_id_mismatch",
                    f"event resulting record {event.resulting_record_id!r}, "
                    f"expected {expected_resulting!r}",
                )
            )
        expected_predecessor = event.prior_record_id if action is Action.SUPERSEDE else None
        if event.predecessor_record_id != expected_predecessor:
            violations.append(
                (
                    "event_predecessor_id_mismatch",
                    f"event predecessor {event.predecessor_record_id!r}, "
                    f"expected {expected_predecessor!r}",
                )
            )
        if violations:
            raise ASKValidationError.from_violations(violations)

    @staticmethod
    def _validate_transition_accounting(
        *,
        before_by_id: Mapping[str, MemoryRecord],
        after_by_id: Mapping[str, MemoryRecord],
        event: TransitionEvent,
        candidate: CandidateRecord | None | _Unverified,
    ) -> None:
        """Exact accounting of the records a transition may add or change.

        Allowed differences between ``before`` and ``after``:

        * Abstain, and Keep without admission: none.
        * Keep with admission (multi_record only): add one record equal to the candidate,
          active, without predecessor.
        * Supersede: set ``active`` to False on the compared prior and change no other field
          of it, and add one record equal to the candidate, active, whose predecessor is the
          compared prior.

        Any other removed, changed or added record is a violation. The checks are the same for
        every store mode. ``temporal_event`` has no additional semantics here.
        """
        violations: list[tuple[str, str]] = []
        action = event.action
        prior_id = event.prior_record_id
        prior_before = before_by_id.get(prior_id) if prior_id is not None else None
        if prior_id is not None and prior_before is None:
            violations.append(
                (
                    "prior_not_in_before",
                    f"compared prior {prior_id!r} is absent from the before state",
                )
            )
        if (
            prior_before is not None
            and action in (Action.KEEP, Action.SUPERSEDE)
            and not prior_before.active
        ):
            violations.append(
                (
                    "prior_not_active_before",
                    f"{action.value} requires the compared prior {prior_id!r} to be active "
                    "in the before state",
                )
            )
        commits = action is Action.SUPERSEDE or (
            action is Action.KEEP and event.keep_admitted_candidate
        )
        deactivates = action is Action.SUPERSEDE
        if commits and candidate is None:
            violations.append(
                (
                    "candidate_required",
                    f"{action.value} commits a candidate; supply it, or pass UNVERIFIED to skip "
                    "content binding",
                )
            )
        committed_id: str | None = None
        if commits:
            if isinstance(candidate, CandidateRecord):
                committed_id = candidate.record_id
            else:
                committed_id = event.candidate_record_id
        if committed_id is not None and committed_id in before_by_id:
            violations.append(
                (
                    "candidate_id_exists_in_before",
                    f"candidate identifier {committed_id!r} already exists",
                )
            )

        expected_new: MemoryRecord | None = None
        if commits and isinstance(candidate, CandidateRecord):
            expected_new = MemoryRecord(
                record_id=candidate.record_id,
                memory_type=candidate.memory_type,
                value=candidate.value,
                active=True,
                predecessor=PredecessorReference(prior_id) if deactivates and prior_id else None,
                evidence_digest=candidate.evidence_digest,
            )

        for record_id in sorted(set(before_by_id) - set(after_by_id)):
            if deactivates and record_id == prior_id:
                violations.append(
                    ("retained_predecessor_removed", f"compared prior {record_id!r} was deleted")
                )
            else:
                violations.append(
                    ("unaccounted_record_removed", f"record {record_id!r} was deleted")
                )
        for record_id in sorted(set(before_by_id) & set(after_by_id)):
            changed = _changed_fields(before_by_id[record_id], after_by_id[record_id])
            if not changed:
                continue
            if deactivates and record_id == prior_id:
                illegal = [name for name in changed if name != "active"]
                if illegal:
                    violations.append(
                        (
                            "retained_predecessor_mutated",
                            f"retained predecessor {record_id!r} changed fields {illegal}",
                        )
                    )
            else:
                violations.append(
                    (
                        "unaccounted_record_changed",
                        f"record {record_id!r} changed fields {list(changed)}",
                    )
                )
        added = sorted(set(after_by_id) - set(before_by_id))
        for record_id in added:
            if record_id != committed_id:
                violations.append(
                    (
                        "unaccounted_record_added",
                        f"record {record_id!r} was added without being announced",
                    )
                )
                continue
            record = after_by_id[record_id]
            if expected_new is not None:
                differing = _changed_fields(expected_new, record)
                if differing:
                    code = (
                        "successor_differs_from_candidate"
                        if deactivates
                        else "admitted_record_differs_from_candidate"
                    )
                    violations.append(
                        (
                            code,
                            f"record {record_id!r} differs from the candidate in {list(differing)}",
                        )
                    )
            else:
                expected_predecessor = prior_id if deactivates else None
                actual = record.predecessor.record_id if record.predecessor else None
                if not record.active or actual != expected_predecessor:
                    violations.append(
                        (
                            "committed_record_structure_mismatch",
                            f"record {record_id!r} must be active with predecessor "
                            f"{expected_predecessor!r}",
                        )
                    )
        missing = committed_id not in added and committed_id not in before_by_id
        if commits and candidate is not None and missing:
            violations.append(
                (
                    "committed_record_missing",
                    f"announced record {committed_id!r} is absent from the after state",
                )
            )
        if violations:
            raise ASKValidationError.from_violations(violations)

    def validate(
        self,
        *,
        before: Sequence[MemoryRecord],
        after: Sequence[MemoryRecord],
        event: TransitionEvent,
        trace: DecisionTrace,
        candidate: CandidateRecord | None | _Unverified = None,
        configuration: Mapping[str, Any] | None | _Unverified = None,
        expected_store_mode: StoreMode | None = None,
    ) -> ValidationReport:
        """Validate one transition or raise ``ASKValidationError``.

        ``candidate`` is the proposed record (``None`` when none was proposed); it binds the
        committed record to its content. ``configuration`` is the frozen configuration mapping
        whose canonical digest must equal the identity carried by the trace and event. Passing
        ``UNVERIFIED`` for either skips that binding and records it in the report. Omitting
        ``configuration`` is rejected. ``expected_store_mode`` is the mode of the store that
        produced the states; the event states its own mode, which the validator cannot
        otherwise confirm.
        """
        if not isinstance(candidate, CandidateRecord | _Unverified) and candidate is not None:
            raise TypeError("candidate must be a CandidateRecord, None or UNVERIFIED")
        if not isinstance(configuration, Mapping | _Unverified) and configuration is not None:
            raise TypeError("configuration must be a Mapping, None or UNVERIFIED")
        checks = ["event_identity", "event_id_recomputed", "trace_evidence_digest"]
        unverified: list[str] = []
        self._validate_event_identity(before=before, after=after, event=event, trace=trace)
        self._validate_trace_event_binding(event=event, trace=trace)
        if expected_store_mode is not None:
            if event.store_mode is not expected_store_mode:
                raise ASKValidationError(
                    "event_store_mode_mismatch",
                    f"event store mode {event.store_mode.value!r}, "
                    f"expected {expected_store_mode.value!r}",
                )
            checks.append("store_mode_binding")
        self._validate_unique_ids(before)
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
                raise ASKValidationError(
                    "single_slot_multiple_active", "single-slot state has multiple active records"
                )
        self._validate_event_fields(event=event, candidate=candidate)
        self._validate_transition_accounting(
            before_by_id=before_by_id,
            after_by_id=after_by_id,
            event=event,
            candidate=candidate,
        )
        checks += ["structural_rules", "event_field_accounting", "record_accounting"]
        if isinstance(candidate, _Unverified):
            unverified.append("candidate_content")
        else:
            checks.append("candidate_binding")

        if isinstance(configuration, _Unverified):
            unverified.append("configuration_digest")
        elif configuration is None:
            raise ASKValidationError(
                "configuration_binding_required",
                "no frozen configuration supplied; pass the mapping, or UNVERIFIED to skip",
            )
        else:
            event.configuration.verify(configuration)
            checks.append("configuration_digest")
        return ValidationReport(checks=tuple(checks), unverified=tuple(unverified))

    @staticmethod
    def _validate_unique_ids(records: Sequence[MemoryRecord]) -> None:
        identifiers = [record.record_id for record in records]
        if len(identifiers) != len(set(identifiers)):
            raise ASKValidationError(
                "duplicate_record_id", "state contains duplicate record identifiers"
            )

    @staticmethod
    def _validate_lineage(records: Sequence[MemoryRecord]) -> None:
        by_id = {record.record_id: record for record in records}
        for record in records:
            if record.predecessor and record.predecessor.record_id not in by_id:
                raise ASKValidationError(
                    "dangling_lineage", f"dangling predecessor for {record.record_id}"
                )
            seen: set[str] = set()
            current = record
            while current.predecessor is not None:
                predecessor_id = current.predecessor.record_id
                if predecessor_id in seen or predecessor_id == record.record_id:
                    raise ASKValidationError(
                        "lineage_cycle", f"lineage cycle at {record.record_id}"
                    )
                seen.add(predecessor_id)
                current = by_id[predecessor_id]


def validate_event_chain(
    events: Sequence[TransitionEvent],
    *,
    initial_state: Sequence[MemoryRecord] | None = None,
) -> None:
    """Check digest continuity of an ordered event log without re-executing transitions.

    Every event identifier must equal the digest of its body, each ``before_digest`` must equal
    the preceding ``after_digest``, and, when ``initial_state`` is given, the first
    ``before_digest`` must equal the digest of that state.
    """
    for index, event in enumerate(events):
        if event.event_id != compute_event_id(event):
            raise ASKValidationError(
                "event_id_mismatch", f"event {index} identifier is not the digest of its body"
            )
        if index and events[index - 1].after_digest != event.before_digest:
            raise ASKValidationError(
                "event_chain_break",
                f"event {index} does not start from the state event {index - 1} left",
            )
    start = events[0].before_digest if events else None
    if initial_state is not None and start is not None and start != state_digest(initial_state):
        raise ASKValidationError(
            "initial_state_digest_mismatch", "first event does not start from the supplied state"
        )


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
        configuration: Mapping[str, Any] | _Unverified = UNVERIFIED,
    ) -> TransitionEvent:
        self._records, event = apply_transition(
            self._records,
            action=action,
            store_mode=self.store_mode,
            prior_record_id=prior_record_id,
            candidate=candidate,
            trace=trace,
            admit_candidate_on_keep=admit_candidate_on_keep,
            configuration=configuration,
        )
        return event
