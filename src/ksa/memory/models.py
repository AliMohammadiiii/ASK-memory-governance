"""Dataclasses mirroring schema/ksa_memory.yaml.

Kept hand-written for readability in the Master's. Swap in `gen-python`
output if the schema grows beyond ~10 classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MemoryType(str, Enum):
    STABLE_PREF = "stable_pref"
    TRANSIENT_PREF = "transient_pref"
    EPISODIC_FACT = "episodic_fact"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class RelationKind(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"


class ControllerAction(str, Enum):
    KEEP = "Keep"
    SUPERSEDE = "Supersede"
    ABSTAIN = "Abstain"


@dataclass
class EvidenceSpan:
    id: int | None
    session_id: str
    turn_index: int
    text: str
    start_char: int | None = None
    end_char: int | None = None
    created_at: datetime | None = None


@dataclass
class MemoryItem:
    id: int | None
    type: MemoryType
    text: str
    confidence: float
    status: MemoryStatus = MemoryStatus.ACTIVE
    normalized_value: str | None = None
    created_at: datetime | None = None
    valid_from: datetime | None = None
    supersedes_id: int | None = None
    evidence_span_ids: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0,1]; got {self.confidence}")


@dataclass
class MemoryRelation:
    id: int | None
    from_memory_id: int
    to_memory_id: int
    relation: RelationKind
    created_at: datetime | None = None


@dataclass
class ActionLogEntry:
    """Matches schema/generated/ksa_memory.schema.json (ActionLogEntry).

    M1-W4 §3.2 added session_id, baseline, candidate_type — these fields
    are nullable so that pre-W4 entries (which never carried them) remain
    valid. For W4 baselines, `feature_*`, `scores`, and `thresholds` are
    null; the controller in M3 fills them in. The `rationale` is a one-
    line human-readable string ('FIFO evicted oldest item id=42 ...').
    """

    id: int
    timestamp: datetime
    action: ControllerAction
    candidate_text: str
    rationale: str
    # M1-W4 additions: routing the action_log to the right run/baseline.
    session_id: str | None = None
    baseline: str | None = None
    candidate_type: MemoryType | None = None
    # Carried from M1-W2.
    candidate_id: int | None = None
    prior_memory_id: int | None = None
    resulting_memory_id: int | None = None
    feature_c: float | None = None
    feature_e: float | None = None
    feature_f: float | None = None
    feature_r: float | None = None
    feature_rho: float | None = None
    s_rev: float | None = None
    s_abs: float | None = None
    theta_sup: float | None = None
    theta_abs: float | None = None

    def to_json_dict(self) -> dict:
        """JSON-schema-compatible dict (datetime → ISO string, enum → value)."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
            "action": self.action.value,
            "candidate_text": self.candidate_text,
            "candidate_type": (
                self.candidate_type.value if self.candidate_type is not None else None
            ),
            "candidate_id": self.candidate_id,
            "session_id": self.session_id,
            "baseline": self.baseline,
            "prior_memory_id": self.prior_memory_id,
            "resulting_memory_id": self.resulting_memory_id,
            "feature_c": self.feature_c,
            "feature_e": self.feature_e,
            "feature_f": self.feature_f,
            "feature_r": self.feature_r,
            "feature_rho": self.feature_rho,
            "s_rev": self.s_rev,
            "s_abs": self.s_abs,
            "theta_sup": self.theta_sup,
            "theta_abs": self.theta_abs,
            "rationale": self.rationale,
        }
