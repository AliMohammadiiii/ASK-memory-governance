"""Scoring — coffee → tea worked example from proposal §I.5.5.

Prior M#42 = "User likes coffee" (stable_pref, re-confirmed 60 turns ago).
Candidate = "I actually don't like coffee anymore, I've switched to tea."

With stable_pref weights (α=0.35, β=0.30, γ=0.15, δ=0.10, ε=0.10), θ_sup=0.75:

  r=0     →  S_rev = 0.711   → below θ_sup  → Keep  (awaiting corroboration)
  r=0.33  →  S_rev = 0.744   → below θ_sup  → Keep
  r=0.67  →  S_rev = 0.777   → above θ_sup  → Supersede

And S_abs = 0.205 < θ_abs = 0.50 throughout, so Abstain does not fire.
"""

from __future__ import annotations

import math

import pytest

from ask.controller.features import (
    FeatureVector,
    explicitness,
    recency_protection,
    repetition,
)
from ask.controller.scoring import load_config, s_abs, s_rev


def test_features_coffee_to_tea_numerics() -> None:
    # Explicitness cue from the proposal
    assert explicitness("I actually don't like coffee anymore, I've switched to tea.") == 1.0

    # Repetition normalization cap=3
    assert repetition(0) == 0.0
    assert repetition(1) == pytest.approx(1 / 3)
    assert repetition(2) == pytest.approx(2 / 3)
    assert repetition(3) == 1.0
    assert repetition(10) == 1.0

    # Recency protection at the proposal's example: Δt=60, τ=40
    rho = recency_protection(60, tau=40)
    assert rho == pytest.approx(math.exp(-60 / 40))
    assert rho == pytest.approx(0.22313016, abs=1e-6)


def _fv(c: float, e: float, f: float, r: float, rho: float) -> FeatureVector:
    return FeatureVector(c=c, e=e, f=f, r=r, rho=rho)


def test_s_rev_r0_below_threshold_keep() -> None:
    config = load_config()
    tc = config.for_type("stable_pref")
    fv = _fv(c=0.88, e=1.0, f=0.83, r=0.0, rho=math.exp(-60 / 40))
    score = s_rev(fv, tc)
    assert score == pytest.approx(0.711, abs=1e-3)
    assert score < tc.theta_sup  # 0.75


def test_s_rev_crosses_threshold_at_r_0_67() -> None:
    config = load_config()
    tc = config.for_type("stable_pref")
    fv_low = _fv(c=0.88, e=1.0, f=0.83, r=0.33, rho=math.exp(-60 / 40))
    fv_high = _fv(c=0.88, e=1.0, f=0.83, r=0.67, rho=math.exp(-60 / 40))
    assert s_rev(fv_low, tc) < tc.theta_sup  # ≈ 0.744
    assert s_rev(fv_high, tc) >= tc.theta_sup  # ≈ 0.777


def test_s_abs_ambiguity_peaks_at_c_half() -> None:
    config = load_config()
    ac = config.abstain
    fv_clear = _fv(c=0.88, e=1.0, f=0.83, r=0.0, rho=0.22)
    fv_ambig = _fv(c=0.50, e=0.0, f=0.50, r=0.0, rho=0.0)
    # Clear contradiction, high extraction confidence → S_abs low.
    assert s_abs(fv_clear, ac) == pytest.approx(0.205, abs=1e-3)
    # Maximally ambiguous c and f=0.5 → S_abs = σ·1.0 + ζ·0.5 = 0.75
    assert s_abs(fv_ambig, ac) == pytest.approx(0.75, abs=1e-6)
