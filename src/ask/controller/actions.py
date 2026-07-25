"""Three-action rule (§I.5.5). Precision-biased: Abstain wins ties."""

from __future__ import annotations

from dataclasses import dataclass

from ..memory.models import ControllerAction, MemoryType
from .features import FeatureVector
from .scoring import ControllerConfig, s_abs, s_rev


@dataclass(frozen=True)
class Decision:
    action: ControllerAction
    s_rev: float
    s_abs: float
    theta_sup: float
    theta_abs: float
    rationale: str


def decide(
    fv: FeatureVector,
    memory_type: MemoryType,
    relation_class: str,
    config: ControllerConfig,
) -> Decision:
    """Apply the action rule:

        if S_abs ≥ θ_abs OR relation_class == "unclear":
            action = Abstain
        elif S_rev ≥ θ_sup(type):
            action = Supersede
        else:
            action = Keep
    """
    tc = config.for_type(memory_type.value)
    ac = config.abstain

    score_rev = s_rev(fv, tc)
    score_abs = s_abs(fv, ac)

    if score_abs >= ac.theta_abs or relation_class == "unclear":
        action = ControllerAction.ABSTAIN
        why = (
            f"Abstain: S_abs={score_abs:.3f} ≥ θ_abs={ac.theta_abs:.2f}"
            if score_abs >= ac.theta_abs
            else "Abstain: relation_class == 'unclear'"
        )
    elif score_rev >= tc.theta_sup:
        action = ControllerAction.SUPERSEDE
        why = (
            f"Supersede: S_rev={score_rev:.3f} ≥ θ_sup({memory_type.value})={tc.theta_sup:.2f}"
        )
    else:
        action = ControllerAction.KEEP
        why = (
            f"Keep: S_rev={score_rev:.3f} < θ_sup({memory_type.value})={tc.theta_sup:.2f} "
            f"and S_abs={score_abs:.3f} < θ_abs={ac.theta_abs:.2f}"
        )

    return Decision(
        action=action,
        s_rev=score_rev,
        s_abs=score_abs,
        theta_sup=tc.theta_sup,
        theta_abs=ac.theta_abs,
        rationale=why,
    )
