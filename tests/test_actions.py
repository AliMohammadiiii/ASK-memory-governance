"""Three-action rule decision paths (§I.5.5):

- Abstain wins when S_abs ≥ θ_abs  OR  relation_class == "unclear".
- Supersede when S_rev ≥ θ_sup(type) and Abstain did not fire.
- Keep otherwise.
- Tie-break: Abstain wins over Supersede when thresholds are simultaneously met.
"""

from __future__ import annotations

import math

from ask.controller.actions import decide
from ask.controller.features import FeatureVector
from ask.controller.scoring import load_config
from ask.memory.models import ControllerAction, MemoryType


def _fv(c: float, e: float, f: float, r: float, rho: float) -> FeatureVector:
    return FeatureVector(c=c, e=e, f=f, r=r, rho=rho)


def test_keep_when_below_thresholds() -> None:
    cfg = load_config()
    fv = _fv(c=0.88, e=1.0, f=0.83, r=0.0, rho=math.exp(-60 / 40))
    d = decide(fv, MemoryType.STABLE_PREF, relation_class="contradict", config=cfg)
    assert d.action == ControllerAction.KEEP


def test_supersede_on_corroborated_reversal() -> None:
    cfg = load_config()
    fv = _fv(c=0.88, e=1.0, f=0.83, r=0.67, rho=math.exp(-60 / 40))
    d = decide(fv, MemoryType.STABLE_PREF, relation_class="contradict", config=cfg)
    assert d.action == ControllerAction.SUPERSEDE


def test_abstain_on_unclear_relation_class() -> None:
    cfg = load_config()
    # Features alone would trigger Supersede in this setup, but relation="unclear" overrides.
    fv = _fv(c=0.90, e=1.0, f=0.9, r=1.0, rho=0.1)
    d = decide(fv, MemoryType.STABLE_PREF, relation_class="unclear", config=cfg)
    assert d.action == ControllerAction.ABSTAIN


def test_abstain_wins_tie_with_supersede() -> None:
    """S_abs ≥ θ_abs AND S_rev ≥ θ_sup — Abstain should win (precision bias).

    Constructed for transient_pref (θ_sup=0.55) so both thresholds are genuinely crossed.
    With c=0.6, e=1.0, f=0, r=1.0, rho=0 and transient weights:
        S_rev = 0.30·0.6 + 0.25·1.0 + 0.15·1.0 = 0.58 ≥ 0.55  (Supersede condition)
        S_abs = 0.50·ambiguity(0.6) + 0.50·(1−0) = 0.50·0.8 + 0.50 = 0.90 ≥ 0.50  (Abstain condition)
    """
    cfg = load_config()
    fv = _fv(c=0.6, e=1.0, f=0.0, r=1.0, rho=0.0)
    d = decide(fv, MemoryType.TRANSIENT_PREF, relation_class="contradict", config=cfg)
    assert d.s_abs >= cfg.abstain.theta_abs
    assert d.s_rev >= cfg.for_type("transient_pref").theta_sup
    assert d.action == ControllerAction.ABSTAIN


def test_transient_pref_supersedes_at_lower_threshold() -> None:
    """Same features that Keep a stable_pref should Supersede a transient_pref."""
    cfg = load_config()
    fv = _fv(c=0.70, e=0.8, f=0.8, r=0.33, rho=math.exp(-30 / 10))
    d_stable = decide(fv, MemoryType.STABLE_PREF, relation_class="contradict", config=cfg)
    d_trans  = decide(fv, MemoryType.TRANSIENT_PREF, relation_class="contradict", config=cfg)
    assert d_stable.action == ControllerAction.KEEP
    assert d_trans.action == ControllerAction.SUPERSEDE
