"""Controller feature functions.

The M3-W9 scorecard uses a transparent five-feature snapshot:

    c   extraction confidence
    e   evidence quality (span specificity + recency)
    f   extraction marker burden
    r   signed relation signal from the M2-W7 classifier
    rho type-conditional stability prior

The older proposal-era helpers (`explicitness`, `repetition`,
`recency_protection`) are kept below because the M1 tests and notes still
exercise that scaffold.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from ..classifier.schema import CandidateMemory, PriorMemory

_SPAN_LENGTH_CAP = 80.0

_NEGATION_RE = re.compile(
    r"\b(?:no longer|not|never|none|cannot|can't|dont|don't|doesnt|doesn't|do not|does not)\b",
    re.IGNORECASE,
)
_HEDGE_RE = re.compile(
    r"\b(?:maybe|perhaps|possibly|probably|sort of|kind of|i think|i guess)\b",
    re.IGNORECASE,
)

STABILITY_PRIORS: dict[str, float] = {
    "stable_pref": 0.9,
    "episodic_fact": 0.6,
    "transient_pref": 0.3,
}


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _type_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _timestamp(obj: Any) -> datetime | None:
    for name in ("timestamp", "valid_from", "created_at"):
        parsed = _parse_datetime(_get(obj, name))
        if parsed is not None:
            return parsed
    span = _get(obj, "evidence_span")
    return _parse_datetime(_get(span, "created_at"))


def _turn_index(obj: Any) -> int | None:
    for name in ("turn_idx", "turn_index"):
        value = _get(obj, name)
        if isinstance(value, int):
            return value
    span = _get(obj, "evidence_span")
    for name in ("turn_idx", "turn_index"):
        value = _get(span, name)
        if isinstance(value, int):
            return value
    return None


def _span_length(candidate: Any) -> int:
    span = _get(candidate, "evidence_span")
    start = _get(span, "char_start", _get(span, "start_char"))
    end = _get(span, "char_end", _get(span, "end_char"))
    text = str(_get(candidate, "text") or "")
    source_turn = str(_get(candidate, "source_turn") or "")
    if isinstance(start, int) and isinstance(end, int) and end >= start:
        span_len = end - start
        if source_turn and span_len < len(text):
            return len(source_turn)
        return span_len
    return len(source_turn or text)


def c(candidate: Any) -> float:
    """Extraction confidence from the extractor's Pydantic `extraction_confidence`."""
    value = _get(candidate, "extraction_confidence", _get(candidate, "confidence", 0.0))
    return _clamp(float(value))


def e(candidate: Any, prior: Any) -> float:
    """Evidence quality in [0, 1].

    Span specificity is the normalized evidence span length. Recency is a
    deterministic timestamp/turn comparison when both sides expose comparable
    metadata, otherwise neutral. The span term is weighted more heavily because
    the M2 extractor notes identify over-broad or synthetic spans as the main
    local evidence risk.
    """
    span_specificity = _clamp(_span_length(candidate) / _SPAN_LENGTH_CAP)
    recency = _recency_score(candidate, prior)
    return _clamp(0.7 * span_specificity + 0.3 * recency)


def _recency_score(candidate: Any, prior: Any) -> float:
    candidate_time = _timestamp(candidate)
    prior_time = _timestamp(prior)
    if candidate_time is not None and prior_time is not None:
        if candidate_time > prior_time:
            return 1.0
        if candidate_time == prior_time:
            return 0.7
        return 0.35

    candidate_turn = _turn_index(candidate)
    prior_turn = _turn_index(prior)
    if candidate_turn is not None and prior_turn is not None:
        if candidate_turn > prior_turn:
            return 1.0
        if candidate_turn == prior_turn:
            return 0.7
        return 0.35

    return 0.5


def f(candidate: Any) -> float:
    """Extraction marker burden: +0.5 per negation or hedge marker."""
    burden = 0.0
    negation = _get(candidate, "negation_marker")
    hedge = _get(candidate, "hedge_marker")

    text = str(_get(candidate, "source_turn") or _get(candidate, "text") or "")
    negation = bool(negation) or bool(_NEGATION_RE.search(text))
    hedge = bool(hedge) or bool(_HEDGE_RE.search(text))

    if negation:
        burden += 0.5
    if hedge:
        burden += 0.5
    return _clamp(burden)


def r(candidate: Any, prior: Any, classifier: Any | None = None) -> float:
    """Signed relation signal from the M2-W7 relation classifier.

    `classifier` must expose `classify(candidate, prior)` and should be the
    live `RelationClassifier` in production. Tests can pass a fake classifier
    that returns a `RelationOutput`-shaped object. If no classifier or embedded
    relation output is available, the function fails loudly rather than
    fabricating a relation.
    """
    relation = _embedded_relation(candidate)
    if relation is None:
        if classifier is None:
            raise ValueError("r() requires a RelationClassifier or embedded relation output")
        relation = classifier.classify(_as_candidate_memory(candidate), _as_prior_memory(prior))
    return _relation_value(relation)


def _embedded_relation(candidate: Any) -> Any | None:
    for name in ("relation_output", "prediction", "relation"):
        relation = _get(candidate, name)
        if relation is not None:
            return relation
    if _get(candidate, "relation_to_prior_state") is not None:
        return candidate
    return None


def _as_candidate_memory(candidate: Any) -> CandidateMemory | Mapping[str, Any]:
    if isinstance(candidate, CandidateMemory):
        return candidate
    if isinstance(candidate, Mapping):
        data = dict(candidate)
    else:
        data = {
            "text": _get(candidate, "text"),
            "type_guess": _get(candidate, "type_guess"),
            "source_turn": _get(candidate, "source_turn"),
            "session_id": _get(candidate, "session_id"),
            "turn_id": _get(candidate, "turn_id"),
            "timestamp": _get(candidate, "timestamp"),
        }
    return {k: v for k, v in data.items() if k in CandidateMemory.model_fields and v is not None}


def _as_prior_memory(prior: Any) -> PriorMemory | Mapping[str, Any]:
    if isinstance(prior, PriorMemory):
        return prior
    if isinstance(prior, Mapping):
        data = dict(prior)
    else:
        data = {
            "text": _get(prior, "text"),
            "type": _get(prior, "type"),
            "memory_id": _get(prior, "memory_id", _get(prior, "id")),
            "timestamp": _get(prior, "timestamp"),
        }
    if data.get("type") is not None:
        data["type"] = _type_value(data["type"])
    return {k: v for k, v in data.items() if k in PriorMemory.model_fields and v is not None}


def _relation_value(output: Any) -> float:
    relation = (
        _get(output, "relation_to_prior_state")
        or _get(output, "logical_relation")
        or _get(output, "label")
    )
    if relation is None:
        raise ValueError("relation output lacks relation_to_prior_state/logical_relation")

    relation = str(relation).lower()
    if relation in {"support", "supports"}:
        sign = 1.0
    elif relation in {"contradict", "contradicts", "supersede", "supersedes"}:
        sign = -1.0
    elif relation in {"independent", "unclear"}:
        sign = 0.0
    else:
        raise ValueError(f"unknown relation label: {relation!r}")

    if sign == 0.0:
        return 0.0
    temporal = str(_get(output, "temporal", "unknown")).lower()
    return sign * _temporal_modulation(temporal)


def _temporal_modulation(temporal: str) -> float:
    if temporal == "newer":
        return 1.0
    if temporal == "same":
        return 0.9
    if temporal == "older":
        return 0.6
    return 0.8


def rho(type_guess: Any) -> float:
    """Type-conditional stability prior: stable > episodic > transient."""
    if not isinstance(type_guess, str) and not isinstance(type_guess, Enum):
        type_guess = _get(type_guess, "type_guess", _get(type_guess, "type", type_guess))
    key = _type_value(type_guess)
    try:
        return STABILITY_PRIORS[key]
    except KeyError as exc:
        raise ValueError(f"unknown memory type for stability prior: {key!r}") from exc


def type_stability_prior(type_guess: Any) -> float:
    """Readable alias for `rho()`."""
    return rho(type_guess)


@dataclass(frozen=True)
class FeatureSnapshot:
    """Full M3-W9 feature snapshot for one candidate/prior comparison."""

    c: float
    e: float
    f: float
    r: float
    rho: float

    def __post_init__(self) -> None:
        for name in ("c", "e", "f", "rho"):
            value = getattr(self, name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"feature {name} must be in [0,1]; got {value}")
        if not (-1.0 <= self.r <= 1.0):
            raise ValueError(f"feature r must be in [-1,1]; got {self.r}")


def build_snapshot(candidate: Any, prior: Any, classifier: Any | None = None) -> FeatureSnapshot:
    """Compute the complete M3-W9 feature snapshot."""
    return FeatureSnapshot(
        c=c(candidate),
        e=e(candidate, prior),
        f=f(candidate),
        r=r(candidate, prior, classifier=classifier),
        rho=rho(candidate),
    )

# --- explicitness: lexical cues from §I.5.5 worked example ------------------ #

# Cues from proposal §I.5.5. Max-match wins, so compound phrases (1.0) dominate
# single-token hedges (0.2–0.8) when both fire.
_EXPLICITNESS_CUES: list[tuple[str, float]] = [
    (r"\bi used to\b.*?\bbut now\b",          1.0),
    (r"\bi no longer\b",                      1.0),
    # "I actually don't like coffee anymore" — proposal's worked example.
    # Matches any don't/doesn't/do not .* anymore, with optional hedges in between.
    (r"\b(?:don'?t|doesn'?t|do not|does not)\b.*?\banymore\b",   1.0),
    (r"\bactually\b",                         0.8),
    (r"\bnever mind\b",                       0.3),
    (r"\bmaybe\b",                            0.2),
    (r"\bhmm\b",                              0.2),
]


def explicitness(text: str) -> float:
    """Score lexical cues for explicit reversal in [0, 1]. Max match wins."""
    if not text:
        return 0.0
    t = text.lower()
    best = 0.0
    for pat, score in _EXPLICITNESS_CUES:
        if re.search(pat, t):
            best = max(best, score)
    return best


def repetition(count_last_n_turns: int, cap: int = 3) -> float:
    """Normalized repetition: min(count / cap, 1.0) — §I.5.5 with cap=3."""
    if count_last_n_turns < 0:
        raise ValueError("count must be non-negative")
    return min(count_last_n_turns / cap, 1.0)


def recency_protection(turns_since_confirm: float, tau: float) -> float:
    """ρ = exp(−Δt / τ). Protects recently re-confirmed memories."""
    if tau <= 0:
        raise ValueError("tau must be positive")
    if turns_since_confirm < 0:
        raise ValueError("turns_since_confirm must be non-negative")
    return math.exp(-turns_since_confirm / tau)


# --- aggregated feature vector --------------------------------------------- #


class FeatureVector(FeatureSnapshot):
    """Backward-compatible name for the original controller tests."""

    pass
