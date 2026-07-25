"""Official active controller API.

This module is the public import surface for final experiments. Proposal-era
helpers remain importable from their historical modules for legacy tests and
notes, but runtime code should import from here.
"""

from __future__ import annotations

from .features import (
    FeatureSnapshot,
    build_snapshot,
    c,
    e,
    f,
    r,
    rho,
    type_stability_prior,
)
from .policy import ScorecardDecision, decide
from .score import (
    DEFAULT_SCORECARD_CONFIG,
    ScorecardConfig,
    ScorecardScores,
    ScoreWeights,
    load_scorecard_config,
    relation_support_pressure,
    relation_update_pressure,
    s_abs,
    s_rev,
    score,
)

__all__ = [
    "DEFAULT_SCORECARD_CONFIG",
    "FeatureSnapshot",
    "ScoreWeights",
    "ScorecardConfig",
    "ScorecardDecision",
    "ScorecardScores",
    "build_snapshot",
    "c",
    "decide",
    "e",
    "f",
    "load_scorecard_config",
    "r",
    "relation_support_pressure",
    "relation_update_pressure",
    "rho",
    "s_abs",
    "s_rev",
    "score",
    "type_stability_prior",
]
