#!/usr/bin/env python3
"""Audit the five-dimensional ASK scorecard from a LongMemEval action log.

The action log is the primary runtime artifact: every row contains the five
features, both scores, both type-conditional thresholds, and the committed
action. This script independently replays the decision rule, summarizes the
features by memory type and action, and runs explicitly labelled
leave-one-dimension-out counterfactuals.

The counterfactuals are mechanism probes, not causal estimates. Omitting a
dimension removes its terms from both scores; omitting the relation dimension
also disables the discrete relation-update guard required for SUPERSEDE.

Usage:
    python3 scripts/analysis/analyze_lme_scorecard.py \
        --action-log runs_local/lme_final_controller_v12_qwen_180/controller/action_log.jsonl \
        --output artifacts/analysis/lme_v12_scorecard_analysis.json
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ACTION_LOG = (
    ROOT / "runs_local/lme_final_controller_v12_qwen_180/controller/action_log.jsonl"
)
DEFAULT_OUTPUT = ROOT / "artifacts/analysis/lme_v12_scorecard_analysis.json"

ACTIONS = ("Keep", "Supersede", "Abstain")
MEMORY_TYPES = ("stable_pref", "episodic_fact", "transient_pref")
FEATURES = ("c", "e", "f", "r", "rho")
FIELD_BY_FEATURE = {feature: f"feature_{feature}" for feature in FEATURES}
WEIGHTS = {"c": 1.0, "e": 0.8, "f": 0.7, "r": 1.2, "rho": 0.5}
COMMON_THRESHOLDS = {"theta_sup": 0.75, "theta_abs": 0.70}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank line {line_number} in {path}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number} in {path} is not an object")
            rows.append(value)
    return rows


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("cannot summarize an empty value list")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_values(values: Iterable[float]) -> dict[str, float]:
    collected = list(values)
    if not collected:
        return {}
    return {
        "min": min(collected),
        "median": percentile(collected, 0.50),
        "mean": sum(collected) / len(collected),
        "p95": percentile(collected, 0.95),
        "max": max(collected),
    }


def _feature(row: Mapping[str, Any], name: str) -> float:
    value = row.get(FIELD_BY_FEATURE[name])
    if not isinstance(value, int | float):
        raise ValueError(f"row {row.get('id')} lacks numeric {FIELD_BY_FEATURE[name]}")
    return float(value)


def score(
    row: Mapping[str, Any],
    *,
    omitted: frozenset[str] = frozenset(),
    rho_override: float | None = None,
) -> tuple[float, float, float]:
    c_value = _feature(row, "c")
    e_value = _feature(row, "e")
    f_value = _feature(row, "f")
    r_value = _feature(row, "r")
    rho_value = _feature(row, "rho") if rho_override is None else rho_override

    update_pressure = 0.0 if "r" in omitted else max(0.0, -r_value)
    s_sup = 0.0
    if "c" not in omitted:
        s_sup += WEIGHTS["c"] * c_value
    if "e" not in omitted:
        s_sup += WEIGHTS["e"] * e_value
    if "f" not in omitted:
        s_sup -= WEIGHTS["f"] * f_value
    if "r" not in omitted:
        s_sup += WEIGHTS["r"] * update_pressure
    if "rho" not in omitted:
        s_sup -= WEIGHTS["rho"] * rho_value

    s_abs = 0.0
    if "c" not in omitted:
        s_abs += 1.0 - c_value
    if "f" not in omitted:
        s_abs += f_value
    if "r" not in omitted:
        s_abs += 1.0 - abs(r_value)
    return s_sup, s_abs, update_pressure


def replay_action(
    row: Mapping[str, Any],
    *,
    omitted: frozenset[str] = frozenset(),
    theta_sup: float | None = None,
    theta_abs: float | None = None,
    rho_override: float | None = None,
    require_relation_guard: bool = True,
) -> str:
    s_sup, s_abs, update_pressure = score(
        row,
        omitted=omitted,
        rho_override=rho_override,
    )
    sup_threshold = float(row["theta_sup"]) if theta_sup is None else theta_sup
    abs_threshold = float(row["theta_abs"]) if theta_abs is None else theta_abs
    if s_abs > abs_threshold:
        return "Abstain"
    relation_allows_update = update_pressure > 0.0 or not require_relation_guard
    if s_sup > sup_threshold and relation_allows_update:
        return "Supersede"
    return "Keep"


def _counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row[field]) for row in rows).items()))


def _rates(counts: Mapping[str, int], denominator: int) -> dict[str, float]:
    return {key: value / denominator for key, value in counts.items()}


def _feature_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {
        feature: summarize_values(_feature(row, feature) for row in rows) for feature in FEATURES
    }


def _transition_summary(
    rows: list[dict[str, Any]],
    predicted: list[str],
) -> dict[str, Any]:
    observed = [str(row["action"]) for row in rows]
    transitions = Counter(
        f"{before}->{after}"
        for before, after in zip(observed, predicted, strict=True)
        if before != after
    )
    by_type: dict[str, int] = Counter()
    for row, before, after in zip(rows, observed, predicted, strict=True):
        if before != after:
            by_type[str(row["candidate_type"])] += 1
    changes = sum(transitions.values())
    return {
        "changed": changes,
        "changed_rate": changes / len(rows),
        "action_counts": dict(sorted(Counter(predicted).items())),
        "transitions": dict(sorted(transitions.items())),
        "changes_by_memory_type": dict(sorted(by_type.items())),
    }


def analyze(rows: list[dict[str, Any]], *, source: Path) -> dict[str, Any]:
    if not rows:
        raise ValueError("action log is empty")

    observed_actions = [str(row["action"]) for row in rows]
    replayed = [replay_action(row) for row in rows]
    score_mismatches: list[dict[str, Any]] = []
    max_s_sup_error = 0.0
    max_s_abs_error = 0.0
    for index, row in enumerate(rows, 1):
        replayed_s_sup, replayed_s_abs, _ = score(row)
        logged_s_sup = float(row["s_rev"])
        logged_s_abs = float(row["s_abs"])
        s_sup_error = abs(replayed_s_sup - logged_s_sup)
        s_abs_error = abs(replayed_s_abs - logged_s_abs)
        max_s_sup_error = max(max_s_sup_error, s_sup_error)
        max_s_abs_error = max(max_s_abs_error, s_abs_error)
        if not (
            math.isclose(replayed_s_sup, logged_s_sup, abs_tol=1e-12)
            and math.isclose(replayed_s_abs, logged_s_abs, abs_tol=1e-12)
        ):
            score_mismatches.append(
                {
                    "line": index,
                    "id": row.get("id"),
                    "logged_s_sup": logged_s_sup,
                    "replayed_s_sup": replayed_s_sup,
                    "logged_s_abs": logged_s_abs,
                    "replayed_s_abs": replayed_s_abs,
                }
            )
    mismatches = [
        {
            "line": index,
            "id": row.get("id"),
            "observed": observed,
            "replayed": replay,
        }
        for index, (row, observed, replay) in enumerate(
            zip(rows, observed_actions, replayed, strict=True),
            1,
        )
        if observed != replay
    ]

    by_type: dict[str, Any] = {}
    for memory_type in MEMORY_TYPES:
        group = [row for row in rows if row.get("candidate_type") == memory_type]
        action_counts = _counts(group, "action")
        by_type[memory_type] = {
            "n": len(group),
            "share": len(group) / len(rows),
            "action_counts": action_counts,
            "action_rates": _rates(action_counts, len(group)),
            "theta_sup": sorted({float(row["theta_sup"]) for row in group}),
            "theta_abs": sorted({float(row["theta_abs"]) for row in group}),
            "feature_summary": _feature_summary(group),
            "score_summary": {
                "s_sup": summarize_values(float(row["s_rev"]) for row in group),
                "s_abs": summarize_values(float(row["s_abs"]) for row in group),
                "sup_margin": summarize_values(
                    float(row["s_rev"]) - float(row["theta_sup"]) for row in group
                ),
                "abs_margin": summarize_values(
                    float(row["s_abs"]) - float(row["theta_abs"]) for row in group
                ),
            },
        }

    by_action: dict[str, Any] = {}
    for action in ACTIONS:
        group = [row for row in rows if row.get("action") == action]
        by_action[action] = {
            "n": len(group),
            "share": len(group) / len(rows),
            "memory_type_counts": _counts(group, "candidate_type"),
            "feature_summary": _feature_summary(group),
        }

    keep_rows = [row for row in rows if row.get("action") == "Keep"]
    keep_above_sup = [row for row in keep_rows if float(row["s_rev"]) > float(row["theta_sup"])]
    keep_guard_blocked = [row for row in keep_above_sup if max(0.0, -_feature(row, "r")) == 0.0]

    dimension_ablations: dict[str, Any] = {}
    for feature in FEATURES:
        predicted = [replay_action(row, omitted=frozenset({feature})) for row in rows]
        dimension_ablations[feature] = _transition_summary(rows, predicted)

    without_guard = [replay_action(row, require_relation_guard=False) for row in rows]
    common_thresholds = [
        replay_action(
            row,
            theta_sup=COMMON_THRESHOLDS["theta_sup"],
            theta_abs=COMMON_THRESHOLDS["theta_abs"],
        )
        for row in rows
    ]
    common_prior = [replay_action(row, rho_override=0.60) for row in rows]
    fully_type_neutral = [
        replay_action(
            row,
            theta_sup=COMMON_THRESHOLDS["theta_sup"],
            theta_abs=COMMON_THRESHOLDS["theta_abs"],
            rho_override=0.60,
        )
        for row in rows
    ]

    action_counts = _counts(rows, "action")
    type_counts = _counts(rows, "candidate_type")
    return {
        "source": str(source),
        "n_decisions": len(rows),
        "decision_rule": {
            "features": {
                "c": "extraction confidence",
                "e": "evidence quality: span specificity plus recency",
                "f": "negation/hedge marker burden",
                "r": "signed relation: support positive, update pressure negative",
                "rho": "type-conditional stability prior",
            },
            "weights": WEIGHTS,
            "s_sup": "1.0*c + 0.8*e - 0.7*f + 1.2*max(0,-r) - 0.5*rho",
            "s_abs": "(1-c) + f + (1-|r|)",
            "order": [
                "ABSTAIN if S_abs > theta_abs[type]",
                "else SUPERSEDE if S_sup > theta_sup[type] and max(0,-r) > 0",
                "else KEEP",
            ],
            "common_threshold_counterfactual": COMMON_THRESHOLDS,
        },
        "replay_validation": {
            "actions": {
                "matched": len(rows) - len(mismatches),
                "mismatched": len(mismatches),
                "fidelity": (len(rows) - len(mismatches)) / len(rows),
                "mismatch_examples": mismatches[:20],
            },
            "scores": {
                "matched": len(rows) - len(score_mismatches),
                "mismatched": len(score_mismatches),
                "fidelity": (len(rows) - len(score_mismatches)) / len(rows),
                "max_s_sup_absolute_error": max_s_sup_error,
                "max_s_abs_absolute_error": max_s_abs_error,
                "mismatch_examples": score_mismatches[:20],
            },
        },
        "observed": {
            "action_counts": action_counts,
            "action_rates": _rates(action_counts, len(rows)),
            "memory_type_counts": type_counts,
            "memory_type_rates": _rates(type_counts, len(rows)),
            "feature_summary": _feature_summary(rows),
            "by_memory_type": by_type,
            "by_action": by_action,
        },
        "mechanism": {
            "keep_above_sup_threshold": len(keep_above_sup),
            "keep_above_sup_threshold_rate": len(keep_above_sup) / len(keep_rows),
            "keep_blocked_by_relation_guard": len(keep_guard_blocked),
            "keep_blocked_by_relation_guard_rate": len(keep_guard_blocked) / len(keep_rows),
            "without_relation_guard": _transition_summary(rows, without_guard),
            "leave_one_dimension_out": dimension_ablations,
            "type_channels": {
                "common_thresholds_only": _transition_summary(rows, common_thresholds),
                "common_stability_prior_only": _transition_summary(rows, common_prior),
                "fully_type_neutral": _transition_summary(rows, fully_type_neutral),
            },
        },
        "interpretation_guard": (
            "Leave-one-dimension-out and type-neutral results are deterministic "
            "counterfactual replays of this fixed log. They diagnose rule dependence; "
            "they do not estimate retrained-system or population causal effects."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action-log", type=Path, default=DEFAULT_ACTION_LOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_jsonl(args.action_log)
    result = analyze(rows, source=args.action_log)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {args.output} "
        f"({result['n_decisions']} decisions; "
        "action/score replay fidelity "
        f"{result['replay_validation']['actions']['fidelity']:.4f}/"
        f"{result['replay_validation']['scores']['fidelity']:.4f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
