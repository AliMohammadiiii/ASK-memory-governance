"""Scoring functions and named configuration (§I.5.5 Table).

S_rev(new, old, type) = α·c + β·e + γ·f + δ·r − ε·ρ
S_abs(new, old)       = σ · ambiguity(c) + ζ · (1 − f)
    ambiguity(c) = 1 − 2·|c − 0.5|
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .features import FeatureVector

_DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "controller_legacy_proposal.yaml"


@dataclass(frozen=True)
class TypeConfig:
    alpha: float
    beta: float
    gamma: float
    delta: float
    epsilon: float
    theta_sup: float
    tau: int


@dataclass(frozen=True)
class AbstainConfig:
    sigma: float
    zeta: float
    theta_abs: float


@dataclass(frozen=True)
class ControllerConfig:
    types: dict[str, TypeConfig]
    abstain: AbstainConfig

    def for_type(self, memory_type: str) -> TypeConfig:
        try:
            return self.types[memory_type]
        except KeyError as exc:
            raise KeyError(f"unknown memory type: {memory_type}") from exc


def load_config(path: Path | None = None) -> ControllerConfig:
    """Load proposal-era weights + thresholds from the archived legacy config."""
    p = Path(path) if path else _DEFAULT_CONFIG
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    types = {
        name: TypeConfig(
            **block["weights"],
            theta_sup=float(block["theta_sup"]),
            tau=int(block["tau"]),
        )
        for name, block in raw["types"].items()
    }
    abstain = AbstainConfig(
        sigma=float(raw["abstain"]["sigma"]),
        zeta=float(raw["abstain"]["zeta"]),
        theta_abs=float(raw["abstain"]["theta_abs"]),
    )
    return ControllerConfig(types=types, abstain=abstain)


def _ambiguity(c: float) -> float:
    return 1.0 - 2.0 * abs(c - 0.5)


def s_rev(fv: FeatureVector, tc: TypeConfig) -> float:
    """Weighted Supersede score for a given feature vector and type config."""
    return (
        tc.alpha   * fv.c
        + tc.beta  * fv.e
        + tc.gamma * fv.f
        + tc.delta * fv.r
        - tc.epsilon * fv.rho
    )


def s_abs(fv: FeatureVector, ac: AbstainConfig) -> float:
    """Abstain score. High when contradiction is ambiguous or confidence is low."""
    return ac.sigma * _ambiguity(fv.c) + ac.zeta * (1.0 - fv.f)
