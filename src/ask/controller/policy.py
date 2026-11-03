"""M3-W9.1 active three-action scorecard policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..memory.models import ControllerAction
from .features import FeatureSnapshot
from .score import (
    DEFAULT_SCORECARD_CONFIG,
    ScorecardConfig,
    ScorecardScores,
    relation_update_pressure,
    score,
)


@dataclass(frozen=True)
class ScorecardDecision:
    action: ControllerAction
    features: FeatureSnapshot
    scores: ScorecardScores
    theta_sup: float
    theta_abs: float
    memory_type: str
    rationale: str

    @property
    def s_rev(self) -> float:
        return self.scores.s_rev

    @property
    def s_abs(self) -> float:
        return self.scores.s_abs


def decide(
    features: FeatureSnapshot,
    memory_type: Any,
    config: ScorecardConfig | None = None,
) -> ScorecardDecision:
    """Apply the M3-W9.1 action rule.

    if S_abs > theta_abs[type]: ABSTAIN
    elif S_sup > theta_sup[type] and max(0, -r) > 0: SUPERSEDE
    else: KEEP
    """
    cfg = config or DEFAULT_SCORECARD_CONFIG
    memory_type_value = _memory_type_value(memory_type)
    scores = score(features, cfg)
    theta_sup = cfg.theta_sup_for(memory_type_value)
    theta_abs = cfg.theta_abs_for(memory_type_value)

    relation_update = relation_update_pressure(features)

    if scores.s_abs > theta_abs:
        action = ControllerAction.ABSTAIN
    elif scores.s_rev > theta_sup and relation_update > 0:
        action = ControllerAction.SUPERSEDE
    else:
        action = ControllerAction.KEEP

    return ScorecardDecision(
        action=action,
        features=features,
        scores=scores,
        theta_sup=theta_sup,
        theta_abs=theta_abs,
        memory_type=memory_type_value,
        rationale=_rationale(features, scores, theta_sup, theta_abs, memory_type_value, action),
    )


def _memory_type_value(memory_type: Any) -> str:
    if isinstance(memory_type, Enum):
        return str(memory_type.value)
    return str(memory_type)


def _relation_label(value: float) -> str:
    if value < 0:
        return "contradict"
    if value > 0:
        return "support"
    return "independent"


def _comparison(score_value: float, threshold: float) -> str:
    if score_value > threshold:
        return "above"
    if score_value < threshold:
        return "below"
    return "equal to"


def _rationale(
    features: FeatureSnapshot,
    scores: ScorecardScores,
    theta_sup: float,
    theta_abs: float,
    memory_type: str,
    action: ControllerAction,
) -> str:
    relation_update = relation_update_pressure(features)
    blocked = ""
    if action == ControllerAction.KEEP and scores.s_rev > theta_sup and relation_update == 0:
        blocked = " Supersede blocked because relation_update=0.000."
    return (
        f"c={features.c:.3f}, e={features.e:.3f}, f={features.f:.3f}, "
        f"r={features.r:.3f} ({_relation_label(features.r)}), "
        f"relation_update={relation_update:.3f}, rho={features.rho:.3f}; "
        f"S_sup={scores.s_rev:.3f} (S_rev={scores.s_rev:.3f} compatibility) "
        f"{_comparison(scores.s_rev, theta_sup)} "
        f"θ_sup={theta_sup:.3f} for {memory_type}; "
        f"S_abs={scores.s_abs:.3f} {_comparison(scores.s_abs, theta_abs)} "
        f"θ_abs={theta_abs:.3f}; {action.value.lower()}.{blocked}"
    )
