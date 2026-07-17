#!/usr/bin/env python3
"""Audit MGP-6 construct leakage and cluster-aware uncertainty.

This analysis is intentionally diagnostic.  It does not turn the author-designed
MGP-6 v2 collection into an independent test set; instead, it quantifies the
shortcuts and dependence structure that limit claims made from the collection.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ACTIONS = ("KEEP", "SUPERSEDE", "ABSTAIN")
DEFAULT_GOLD = ROOT / "benchmarks/mgp6/data/mgp6_v2.jsonl"
DEFAULT_PREDICTIONS = {
    "rule": ROOT / "artifacts/mgp6_v2/ref_5systems/controller/predictions.jsonl",
    "llm_structured": ROOT / "artifacts/mgp6_v2/llm_qwen35_9b/controller/predictions.jsonl",
    "llm_zero_shot": ROOT / "artifacts/mgp6_v2/llm_decision_zero/controller/predictions.jsonl",
}
DEFAULT_JSON = ROOT / "artifacts/analysis/mgp6_validity_audit.json"
DEFAULT_MARKDOWN = ROOT / "artifacts/analysis/mgp6_validity_audit.md"
SHORTCUT_FIELDS = (
    "type",
    "conflict_type",
    "evidence_source",
    "source_reliability",
    "temporal_scope",
)


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


def prediction_map(path: Path) -> dict[str, dict[str, Any]]:
    rows = load_jsonl(path)
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        scenario_id = row.get("scenario_id")
        if not isinstance(scenario_id, str):
            raise ValueError(f"prediction without scenario_id in {path}")
        if scenario_id in result:
            raise ValueError(f"duplicate prediction {scenario_id} in {path}")
        result[scenario_id] = row
    return result


def accuracy(gold: Iterable[str], predicted: Iterable[str]) -> float:
    pairs = list(zip(gold, predicted, strict=True))
    return sum(g == p for g, p in pairs) / len(pairs) if pairs else 0.0


def f1_for(gold: list[str], predicted: list[str], label: str) -> float:
    tp = sum(g == label and p == label for g, p in zip(gold, predicted, strict=True))
    fp = sum(g != label and p == label for g, p in zip(gold, predicted, strict=True))
    fn = sum(g == label and p != label for g, p in zip(gold, predicted, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def macro_f1(gold: list[str], predicted: list[str]) -> float:
    return sum(f1_for(gold, predicted, label) for label in ACTIONS) / len(ACTIONS)


def entropy(labels: Iterable[str]) -> float:
    counts = Counter(labels)
    total = sum(counts.values())
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def conditional_entropy(rows: list[dict[str, Any]], field: str) -> float:
    groups: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(field))].append(row["gold_action"])
    total = len(rows)
    return sum((len(labels) / total) * entropy(labels) for labels in groups.values())


def majority_label(labels: Iterable[str]) -> str:
    counts = Counter(labels)
    return min(ACTIONS, key=lambda label: (-counts[label], ACTIONS.index(label)))


def fit_lookup(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> tuple[dict[tuple[str, ...], str], str]:
    groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for row in rows:
        key = tuple(str(row.get(field)) for field in fields)
        groups[key].append(row["gold_action"])
    return {key: majority_label(labels) for key, labels in groups.items()}, majority_label(
        row["gold_action"] for row in rows
    )


def evaluate_lookup(
    train: list[dict[str, Any]], test: list[dict[str, Any]], fields: tuple[str, ...]
) -> dict[str, Any]:
    lookup, fallback = fit_lookup(train, fields)
    predicted = [lookup.get(tuple(str(row.get(field)) for field in fields), fallback) for row in test]
    gold = [row["gold_action"] for row in test]
    return {
        "features": list(fields),
        "fit_n": len(train),
        "test_n": len(test),
        "unseen_feature_combinations": sum(
            tuple(str(row.get(field)) for field in fields) not in lookup for row in test
        ),
        "test_accuracy": accuracy(gold, predicted),
        "test_macro_f1": macro_f1(gold, predicted),
        "predicted_counts": dict(sorted(Counter(predicted).items())),
    }


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def cluster_bootstrap(
    rows: list[dict[str, Any]],
    values: dict[str, float],
    cluster_key: Callable[[dict[str, Any]], str],
    *,
    samples: int,
    seed: int,
) -> dict[str, Any]:
    clusters: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        clusters[cluster_key(row)].append(row["scenario_id"])
    keys = sorted(clusters)
    point = sum(values[row["scenario_id"]] for row in rows) / len(rows)
    family_point = sum(
        sum(values[scenario_id] for scenario_id in ids) / len(ids) for ids in clusters.values()
    ) / len(clusters)
    rng = random.Random(seed)
    item_weighted: list[float] = []
    cluster_macro: list[float] = []
    for _ in range(samples):
        sampled = [rng.choice(keys) for _ in keys]
        sampled_ids = [scenario_id for key in sampled for scenario_id in clusters[key]]
        item_weighted.append(sum(values[scenario_id] for scenario_id in sampled_ids) / len(sampled_ids))
        cluster_macro.append(
            sum(
                sum(values[scenario_id] for scenario_id in clusters[key]) / len(clusters[key])
                for key in sampled
            )
            / len(sampled)
        )
    return {
        "n_items": len(rows),
        "n_clusters": len(keys),
        "item_weighted_point": point,
        "item_weighted_ci95": [percentile(item_weighted, 0.025), percentile(item_weighted, 0.975)],
        "cluster_macro_point": family_point,
        "cluster_macro_ci95": [percentile(cluster_macro, 0.025), percentile(cluster_macro, 0.975)],
    }


def prediction_metrics(rows: list[dict[str, Any]], predictions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing = [row["scenario_id"] for row in rows if row["scenario_id"] not in predictions]
    predicted = [predictions.get(row["scenario_id"], {}).get("predicted_action", "INVALID") for row in rows]
    gold = [row["gold_action"] for row in rows]
    false_commits = sum(g == "ABSTAIN" and p != "ABSTAIN" for g, p in zip(gold, predicted, strict=True))
    abstain_n = sum(g == "ABSTAIN" for g in gold)
    missed_updates = sum(g == "SUPERSEDE" and p != "SUPERSEDE" for g, p in zip(gold, predicted, strict=True))
    update_n = sum(g == "SUPERSEDE" for g in gold)
    unnecessary_abstentions = sum(
        g != "ABSTAIN" and p == "ABSTAIN" for g, p in zip(gold, predicted, strict=True)
    )
    non_abstain_n = sum(g != "ABSTAIN" for g in gold)
    result: dict[str, Any] = {
        "n": len(rows),
        "missing_predictions": missing,
        "action_accuracy": accuracy(gold, predicted),
        "macro_f1": macro_f1(gold, predicted),
        "false_commit_definition": "gold action ABSTAIN and predicted action is not ABSTAIN",
        "false_commit_rate": false_commits / abstain_n if abstain_n else None,
        "false_commit_count": [false_commits, abstain_n],
        "missed_update_rate": missed_updates / update_n if update_n else None,
        "missed_update_count": [missed_updates, update_n],
        "unnecessary_abstention_rate": unnecessary_abstentions / non_abstain_n if non_abstain_n else None,
        "unnecessary_abstention_count": [unnecessary_abstentions, non_abstain_n],
        "per_action_f1": {label: f1_for(gold, predicted, label) for label in ACTIONS},
    }
    if false_commits == 0 and abstain_n:
        result["false_commit_one_sided_95_upper"] = 1 - math.pow(0.05, 1 / abstain_n)

    confidences = [predictions.get(row["scenario_id"], {}).get("confidence") for row in rows]
    if all(isinstance(value, (int, float)) for value in confidences):
        conf = [float(value) for value in confidences]
        correct = [float(g == p) for g, p in zip(gold, predicted, strict=True)]
        result["top_label_brier"] = sum((c - y) ** 2 for c, y in zip(conf, correct, strict=True)) / len(rows)
        bins: list[dict[str, Any]] = []
        ece = 0.0
        for index in range(10):
            low, high = index / 10, (index + 1) / 10
            members = [i for i, value in enumerate(conf) if low <= value <= high if index == 9 or value < high]
            if not members:
                continue
            mean_confidence = sum(conf[i] for i in members) / len(members)
            mean_accuracy = sum(correct[i] for i in members) / len(members)
            ece += (len(members) / len(rows)) * abs(mean_confidence - mean_accuracy)
            bins.append(
                {
                    "range": [low, high],
                    "n": len(members),
                    "mean_confidence": mean_confidence,
                    "accuracy": mean_accuracy,
                }
            )
        result["top_label_ece_10bin"] = ece
        result["calibration_bins"] = bins
        ordered = sorted(range(len(rows)), key=lambda i: (-conf[i], rows[i]["scenario_id"]))
        result["risk_coverage"] = []
        for coverage in (0.25, 0.5, 0.75, 1.0):
            count = max(1, math.ceil(len(rows) * coverage))
            selected = ordered[:count]
            selected_accuracy = sum(correct[i] for i in selected) / count
            result["risk_coverage"].append(
                {"coverage": coverage, "n": count, "accuracy": selected_accuracy, "risk": 1 - selected_accuracy}
            )
    return result


def expected_cost(rows: list[dict[str, Any]], predictions: dict[str, dict[str, Any]]) -> dict[str, float]:
    regimes = {
        "balanced": {"false_commit": 1.0, "missed_update": 1.0, "other": 1.0},
        "commit_averse": {"false_commit": 5.0, "missed_update": 1.0, "other": 2.0},
        "update_responsive": {"false_commit": 2.0, "missed_update": 5.0, "other": 2.0},
    }
    totals = {name: 0.0 for name in regimes}
    for row in rows:
        gold = row["gold_action"]
        predicted = predictions.get(row["scenario_id"], {}).get("predicted_action", "INVALID")
        if gold == predicted:
            continue
        error = "false_commit" if gold == "ABSTAIN" and predicted != "ABSTAIN" else "missed_update" if gold == "SUPERSEDE" else "other"
        for name, costs in regimes.items():
            totals[name] += costs[error]
    return {name: total / len(rows) for name, total in totals.items()}


def paired_cluster_difference(
    rows: list[dict[str, Any]],
    left: dict[str, dict[str, Any]],
    right: dict[str, dict[str, Any]],
    *,
    samples: int,
    seed: int,
) -> dict[str, Any]:
    values: dict[str, float] = {}
    for row in rows:
        scenario_id = row["scenario_id"]
        gold = row["gold_action"]
        left_correct = left.get(scenario_id, {}).get("predicted_action") == gold
        right_correct = right.get(scenario_id, {}).get("predicted_action") == gold
        values[scenario_id] = float(left_correct) - float(right_correct)
    return cluster_bootstrap(
        rows,
        values,
        lambda row: row["template_family_id"],
        samples=samples,
        seed=seed,
    )


def audit(
    gold_path: Path,
    prediction_paths: dict[str, Path],
    *,
    bootstrap: int,
    seed: int,
) -> dict[str, Any]:
    rows = load_jsonl(gold_path)
    ids = [row["scenario_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate gold scenario_id")
    train_dev = [row for row in rows if row["split"] in {"train", "dev"}]
    test = [row for row in rows if row["split"] == "test"]
    action_entropy = entropy(row["gold_action"] for row in rows)
    shortcut: dict[str, Any] = {}
    for field in SHORTCUT_FIELDS:
        cond = conditional_entropy(rows, field)
        shortcut[field] = {
            "conditional_entropy_bits": cond,
            "normalized_information_gain": 1 - cond / action_entropy if action_entropy else 0.0,
            "full_distribution": {
                value: dict(sorted(Counter(row["gold_action"] for row in rows if str(row.get(field)) == value).items()))
                for value in sorted({str(row.get(field)) for row in rows})
            },
            "train_dev_lookup": evaluate_lookup(train_dev, test, (field,)),
        }
    shortcut["metadata_tuple"] = {
        "train_dev_lookup": evaluate_lookup(
            train_dev,
            test,
            ("evidence_source", "source_reliability", "temporal_scope"),
        )
    }

    predictions = {name: prediction_map(path) for name, path in prediction_paths.items()}
    systems: dict[str, Any] = {}
    for offset, (name, values) in enumerate(predictions.items()):
        test_metrics = prediction_metrics(test, values)
        correctness = {
            row["scenario_id"]: float(values.get(row["scenario_id"], {}).get("predicted_action") == row["gold_action"])
            for row in test
        }
        test_metrics["template_family_bootstrap"] = cluster_bootstrap(
            test,
            correctness,
            lambda row: row["template_family_id"],
            samples=bootstrap,
            seed=seed + offset,
        )
        test_metrics["minimal_pair_cluster_bootstrap"] = cluster_bootstrap(
            test,
            correctness,
            lambda row: row.get("minimal_pair_group_id") or row["scenario_id"],
            samples=bootstrap,
            seed=seed + 100 + offset,
        )
        test_metrics["expected_cost"] = expected_cost(test, values)
        systems[name] = {"source": str(prediction_paths[name].relative_to(ROOT)), "test": test_metrics}

    paired: dict[str, Any] = {}
    if "rule" in predictions and "llm_structured" in predictions:
        paired["rule_minus_llm_structured_test_accuracy"] = paired_cluster_difference(
            test,
            predictions["rule"],
            predictions["llm_structured"],
            samples=bootstrap,
            seed=seed + 500,
        )

    return {
        "schema_version": "1.0",
        "scope": "construct-validity audit of an author-designed diagnostic; not independent validation",
        "gold": str(gold_path.relative_to(ROOT)),
        "n": len(rows),
        "split_counts": dict(sorted(Counter(row["split"] for row in rows).items())),
        "action_counts": dict(sorted(Counter(row["gold_action"] for row in rows).items())),
        "template_families": len({row["template_family_id"] for row in rows}),
        "minimal_pair_groups": len({row["minimal_pair_group_id"] for row in rows if row.get("minimal_pair_group_id")}),
        "shortcut_audit": shortcut,
        "systems": systems,
        "paired_cluster_bootstrap": paired,
        "claim_boundary": [
            "Type-only and metadata-only results quantify label leakage; they are not competitive memory systems.",
            "Cluster bootstrap addresses within-collection dependence but cannot establish external validity.",
            "No non-inferiority or equivalence claim is licensed because no margin was pre-specified.",
            "Zero observed action false commits receive a finite-sample upper bound, never a zero-risk interpretation.",
        ],
        "bootstrap": {"samples": bootstrap, "seed": seed},
    }


def markdown(report: dict[str, Any]) -> str:
    type_lookup = report["shortcut_audit"]["type"]["train_dev_lookup"]
    conflict_lookup = report["shortcut_audit"]["conflict_type"]["train_dev_lookup"]
    lines = [
        "# MGP-6 v2 construct-validity audit",
        "",
        "> This is a diagnostic audit of an author-designed collection, not independent validation.",
        "",
        "## Shortcut results",
        "",
        "| Baseline fitted on train+dev | Held-out test accuracy | Macro-F1 |",
        "| --- | ---: | ---: |",
        f"| Type-only lookup | {type_lookup['test_accuracy']:.4f} | {type_lookup['test_macro_f1']:.4f} |",
        f"| Conflict-type-only lookup | {conflict_lookup['test_accuracy']:.4f} | {conflict_lookup['test_macro_f1']:.4f} |",
        "",
        "A perfect or near-perfect shortcut result is evidence of construct leakage, not model quality. It means the current collection cannot isolate evidence reasoning from scenario-family recognition.",
        "",
        "## Test-set system diagnostics",
        "",
        "| System | Accuracy | Family-cluster 95% CI | False commit | Missed update | Unnecessary abstention | ECE |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, payload in report["systems"].items():
        metrics = payload["test"]
        ci = metrics["template_family_bootstrap"]["cluster_macro_ci95"]
        ece = metrics.get("top_label_ece_10bin")
        lines.append(
            f"| {name} | {metrics['action_accuracy']:.4f} | [{ci[0]:.4f}, {ci[1]:.4f}] | "
            f"{metrics['false_commit_rate']:.4f} | {metrics['missed_update_rate']:.4f} | "
            f"{metrics['unnecessary_abstention_rate']:.4f} | {ece:.4f} |"
        )
    lines.extend(["", "## Claim boundary", ""])
    lines.extend(f"- {item}" for item in report["claim_boundary"])
    lines.extend(
        [
            "",
            "The independent, balanced, multi-action-per-family successor set remains required before any external-generalization or population-safety claim.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_prediction_arg(values: list[str] | None) -> dict[str, Path]:
    if not values:
        return DEFAULT_PREDICTIONS.copy()
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--prediction must use NAME=PATH")
        name, raw_path = value.split("=", 1)
        if not name or name in result:
            raise ValueError(f"invalid or duplicate prediction name: {name!r}")
        result[name] = Path(raw_path).resolve()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--prediction", action="append", help="NAME=PATH; repeatable")
    parser.add_argument("--bootstrap", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260715)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args(argv)
    if args.bootstrap < 100:
        parser.error("--bootstrap must be at least 100")

    report = audit(
        args.gold.resolve(),
        parse_prediction_arg(args.prediction),
        bootstrap=args.bootstrap,
        seed=args.seed,
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_out.write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"json": str(args.json_out), "markdown": str(args.markdown_out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
