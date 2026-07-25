"""M3-W9.1 active scorecard functions and parameterization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .features import FeatureSnapshot

MEMORY_TYPES = ("stable_pref", "episodic_fact", "transient_pref")


@dataclass(frozen=True)
class ScoreWeights:
    """Named M3-W9.1 scorecard weights.

    The serialized names remain ``w1``-``w5`` so older run manifests and YAML
    files stay readable. In the active controller they mean:

    - ``w1``: extraction confidence
    - ``w2``: evidence quality
    - ``w3``: marker burden penalty
    - ``w4``: supersession/update relation pressure
    - ``w5``: stability-prior penalty
    """

    w1: float = 1.0
    w2: float = 0.8
    w3: float = 0.7
    w4: float = 1.2
    w5: float = 0.5


@dataclass(frozen=True)
class ScorecardConfig:
    """Controller thresholds are supplied as data, not embedded in policy."""

    weights: ScoreWeights = field(default_factory=ScoreWeights)
    theta_sup: Mapping[str, float] = field(
        default_factory=lambda: {
            "stable_pref": 0.90,
            "episodic_fact": 0.75,
            "transient_pref": 0.55,
        }
    )
    theta_abs: Mapping[str, float] = field(
        default_factory=lambda: {
            "stable_pref": 0.60,
            "episodic_fact": 0.70,
            "transient_pref": 0.80,
        }
    )

    def __post_init__(self) -> None:
        missing_sup = set(MEMORY_TYPES) - set(self.theta_sup)
        missing_abs = set(MEMORY_TYPES) - set(self.theta_abs)
        if missing_sup:
            raise ValueError(f"theta_sup missing memory types: {sorted(missing_sup)}")
        if missing_abs:
            raise ValueError(f"theta_abs missing memory types: {sorted(missing_abs)}")
        if not (
            self.theta_sup["stable_pref"]
            > self.theta_sup["episodic_fact"]
            > self.theta_sup["transient_pref"]
        ):
            raise ValueError("theta_sup must satisfy stable_pref > episodic_fact > transient_pref")

    def theta_sup_for(self, memory_type: Any) -> float:
        return float(self.theta_sup[_memory_type_value(memory_type)])

    def theta_abs_for(self, memory_type: Any) -> float:
        return float(self.theta_abs[_memory_type_value(memory_type)])


@dataclass(frozen=True)
class ScorecardScores:
    """Computed active scorecard values.

    ``s_rev`` is retained as the action-log/config compatibility name for the
    active Supersede score. Documentation and rationales call it ``S_sup``.
    """

    s_rev: float
    s_abs: float


DEFAULT_SCORECARD_CONFIG = ScorecardConfig()


def _memory_type_value(memory_type: Any) -> str:
    if isinstance(memory_type, Enum):
        memory_type = memory_type.value
    value = str(memory_type)
    if value not in MEMORY_TYPES:
        raise KeyError(f"unknown memory type: {value}")
    return value


def load_scorecard_config(path: str | Path) -> ScorecardConfig:
    """Load M3-W9 scorecard parameters from YAML."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    weights_raw = raw.get("weights", {})
    return ScorecardConfig(
        weights=ScoreWeights(**weights_raw),
        theta_sup={k: float(v) for k, v in raw["theta_sup"].items()},
        theta_abs={k: float(v) for k, v in raw["theta_abs"].items()},
    )


def relation_update_pressure(features: FeatureSnapshot) -> float:
    """Positive supersession pressure from the signed relation signal."""
    return max(0.0, -features.r)


def relation_support_pressure(features: FeatureSnapshot) -> float:
    """Positive support pressure from the signed relation signal."""
    return max(0.0, features.r)


def s_rev(features: FeatureSnapshot, weights: ScoreWeights | None = None) -> float:
    """Supersede score.

    M3-W9.1 repairs the M3-W9 sign issue: negative signed relation values mean
    contradiction/supersession pressure, so ``max(0, -r)`` must increase the
    Supersede score. The type stability prior protects stable memories and is
    therefore subtracted.
    """
    w = weights or DEFAULT_SCORECARD_CONFIG.weights
    update_pressure = relation_update_pressure(features)
    return (
        w.w1 * features.c
        + w.w2 * features.e
        - w.w3 * features.f
        + w.w4 * update_pressure
        - w.w5 * features.rho
    )


def s_abs(features: FeatureSnapshot) -> float:
    """Abstain score: high for low confidence, marker burden, and weak relation."""
    return (1.0 - features.c) + features.f + (1.0 - abs(features.r))


def score(features: FeatureSnapshot, config: ScorecardConfig | None = None) -> ScorecardScores:
    """Compute both scorecard scores under a named configuration."""
    cfg = config or DEFAULT_SCORECARD_CONFIG
    return ScorecardScores(
        s_rev=s_rev(features, cfg.weights),
        s_abs=s_abs(features),
    )
