#!/usr/bin/env python3
"""Metrics for MGP-6 v2 controller predictions."""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    from .mgp6_schema_v2 import MGP6Example, memory_value
except ImportError:
    from mgp6_schema_v2 import MGP6Example, memory_value


# Gold MGP-6 action vocabulary.
ACTIONS = ("KEEP", "SUPERSEDE", "ABSTAIN")

# Prediction-only outcomes are allowed for black-box external systems.
# INVALID_COMMIT means the system committed a conflicting state without
# completing a valid KEEP/SUPERSEDE/ABSTAIN governance transition.
# INVALID is reserved for malformed, unknown, or missing predictions.
PREDICTION_OUTCOMES = ACTIONS + ("INVALID_COMMIT", "INVALID")
REJECTION_RE = re.compile(
    r"\b(?:no|not|incorrect|wrong|false|stale|rather|instead|remains)\b",
    re.I,
)
Pair = tuple[MGP6Example, dict[str, Any]]
Metric = Callable[[list[Pair]], float]


def canonical_action(value: Any) -> str:
    """Normalize common action spellings on both prediction and gold paths."""
    raw = getattr(value, "value", value)
    key = re.sub(r"[\s\-_/]+", "_", str(raw).strip().upper())
    aliases = {
        "KEPT": "KEEP",
        "RETAIN": "KEEP",
        "RETAINED": "KEEP",
        "SUPERSEDED": "SUPERSEDE",
        "SUPERSEDES": "SUPERSEDE",
        "REPLACE": "SUPERSEDE",
        "REPLACED": "SUPERSEDE",
        "UPDATE": "SUPERSEDE",
        "UPDATED": "SUPERSEDE",
        "ABSTAINED": "ABSTAIN",
        "DEFER": "ABSTAIN",
        "DEFERRED": "ABSTAIN",
        "NO_OP": "ABSTAIN",
        "NOOP": "ABSTAIN",
    }
    return aliases.get(key, key)


def load_gold(path: Path) -> list[MGP6Example]:
    rows: list[MGP6Example] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank gold line {line_number}")
            try:
                rows.append(MGP6Example.model_validate_json(line))
            except ValueError as exc:
                raise ValueError(f"invalid gold line {line_number}: {exc}") from exc
    ids = [row.scenario_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("gold has duplicate scenario_id values")
    return rows


def load_predictions(path: Path) -> dict[str, dict[str, Any]]:
    predictions: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank prediction line {line_number}")
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid prediction JSON on line {line_number}: {exc}") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("scenario_id"), str):
                raise ValueError(f"prediction line {line_number} needs string scenario_id")
            scenario_id = payload["scenario_id"]
            if scenario_id in predictions:
                raise ValueError(f"duplicate prediction for {scenario_id}")
            action = canonical_action(payload.get("predicted_action", "INVALID"))
            payload["predicted_action"] = action if action in PREDICTION_OUTCOMES else "INVALID"
            state = payload.get("predicted_memory_state", [])
            payload["predicted_memory_state"] = state if isinstance(state, list) else []
            answer = payload.get("predicted_answer", "")
            payload["predicted_answer"] = answer if isinstance(answer, str) else ""
            confidence = payload.get("confidence")
            if confidence is not None:
                if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
                    raise ValueError(f"confidence for {scenario_id} must be in [0, 1]")
                payload["confidence"] = float(confidence)
            predictions[scenario_id] = payload
    return predictions


def align(gold: list[MGP6Example], predictions: dict[str, dict[str, Any]]) -> list[Pair]:
    gold_ids = {row.scenario_id for row in gold}
    extra = sorted(set(predictions) - gold_ids)
    if extra:
        raise ValueError(f"predictions contain unknown scenario ids: {extra[:5]}")
    missing = {
        "predicted_action": "INVALID",
        "predicted_memory_state": [],
        "predicted_answer": "",
        "confidence": None,
    }
    return [(row, predictions.get(row.scenario_id, missing)) for row in gold]


def safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def rate(
    pairs: list[Pair], predicate: Callable[[Pair], bool], eligible: Callable[[Pair], bool]
) -> float:
    selected = [pair for pair in pairs if eligible(pair)]
    return safe_mean([1.0 if predicate(pair) else 0.0 for pair in selected])


def action_accuracy(pairs: list[Pair]) -> float:
    return safe_mean(
        [
            float(canonical_action(g.gold_action) == canonical_action(p["predicted_action"]))
            for g, p in pairs
        ]
    )


def action_precision(pairs: list[Pair], label: str) -> float:
    return rate(
        pairs,
        lambda pair: canonical_action(pair[0].gold_action) == canonical_action(label),
        lambda pair: canonical_action(pair[1]["predicted_action"]) == canonical_action(label),
    )


def action_recall(pairs: list[Pair], label: str) -> float:
    return rate(
        pairs,
        lambda pair: canonical_action(pair[1]["predicted_action"]) == canonical_action(label),
        lambda pair: canonical_action(pair[0].gold_action) == canonical_action(label),
    )


def action_f1(pairs: list[Pair], label: str) -> float:
    precision = action_precision(pairs, label)
    recall = action_recall(pairs, label)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def canonical_memory_value(text: Any) -> str:
    value = str(text)
    if "=" in value:
        value = value.split("=", 1)[1]
    value = value.casefold().replace("_", " ").replace("-", " ")
    value = re.sub(r"[^a-z0-9:.x ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def active_signature(state: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    result: set[tuple[str, str, str]] = set()
    for record in state:
        if not isinstance(record, dict) or record.get("status") != "active":
            continue
        result.add(
            (
                str(record.get("semantic_slot", "")).casefold(),
                str(record.get("type", "")).casefold(),
                canonical_memory_value(record.get("text", "")),
            )
        )
    return result


def normalized_state(state: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "id",
        "type",
        "text",
        "confidence",
        "status",
        "supersedes_id",
        "valid_from",
        "semantic_slot",
        "source",
    )
    records = [
        {field: record.get(field) for field in fields}
        for record in state
        if isinstance(record, dict)
    ]
    return sorted(records, key=lambda record: str(record.get("id")))


def gold_state_dicts(gold: MGP6Example) -> list[dict[str, Any]]:
    return [record.model_dump(mode="json") for record in gold.gold_memory_state]


def artifact_exact(pairs: list[Pair]) -> float:
    return safe_mean(
        [
            float(
                normalized_state(p["predicted_memory_state"])
                == normalized_state(gold_state_dicts(g))
            )
            for g, p in pairs
        ]
    )


def artifact_semantic(pairs: list[Pair]) -> float:
    return safe_mean(
        [
            float(
                active_signature(p["predicted_memory_state"])
                == active_signature(gold_state_dicts(g))
            )
            for g, p in pairs
        ]
    )


def over_forgetting(pairs: list[Pair]) -> float:
    def failed_to_preserve(pair: Pair) -> bool:
        gold, pred = pair
        predicted = active_signature(pred["predicted_memory_state"])
        durable = {
            (r.semantic_slot.casefold(), r.type.casefold(), canonical_memory_value(r.text))
            for r in gold.gold_memory_state
            if r.status == "active" and r.type != "transient_pref"
        }
        return not durable.issubset(predicted)

    return rate(pairs, failed_to_preserve, lambda pair: pair[0].gold_action != "SUPERSEDE")


def under_forgetting(pairs: list[Pair]) -> float:
    def retained_stale(pair: Pair) -> bool:
        gold, pred = pair
        active_text = " ".join(
            text for _, _, text in active_signature(pred["predicted_memory_state"])
        )
        stale = [
            memory_value(r.text).casefold()
            for r in gold.gold_memory_state
            if r.status == "superseded"
        ]
        current = {
            canonical_memory_value(r.text) for r in gold.gold_memory_state if r.status == "active"
        }
        predicted_texts = {text for _, _, text in active_signature(pred["predicted_memory_state"])}
        return (
            pred["predicted_action"] != "SUPERSEDE"
            or any(value in active_text for value in stale)
            or not current.issubset(predicted_texts)
        )

    return rate(pairs, retained_stale, lambda pair: pair[0].gold_action == "SUPERSEDE")


def stale_retrieval(pairs: list[Pair]) -> float:
    return rate(
        pairs,
        lambda pair: any(
            re.search(pattern, pair[1]["predicted_answer"], re.I)
            for pattern in pair[0].forbidden_answer_patterns
        ),
        lambda pair: bool(pair[0].forbidden_answer_patterns),
    )


def lineage_row(gold: MGP6Example, prediction: dict[str, Any]) -> float:
    state = [record for record in prediction["predicted_memory_state"] if isinstance(record, dict)]
    by_id = {record.get("id"): record for record in state}
    old = [record for record in gold.gold_memory_state if record.status == "superseded"]
    new = [
        record
        for record in gold.gold_memory_state
        if record.status == "active" and record.supersedes_id
    ]
    if not old or not new:
        return 0.0
    old_gold, new_gold = old[0], new[0]
    old_pred = by_id.get(old_gold.id, {})
    new_pred = by_id.get(new_gold.id, {})
    active_same_slot = [
        record
        for record in state
        if record.get("status") == "active" and record.get("semantic_slot") == gold.semantic_slot
    ]
    points = [
        old_pred.get("status") == "superseded",
        new_pred.get("status") == "active" and new_pred.get("text") == new_gold.text,
        new_pred.get("supersedes_id") == old_gold.id,
        not any(record.get("text") == old_gold.text for record in active_same_slot),
        len([record for record in active_same_slot if record.get("type") == new_gold.type]) == 1,
    ]
    return safe_mean([float(point) for point in points])


def lineage_correctness(pairs: list[Pair]) -> float:
    eligible = [pair for pair in pairs if pair[0].gold_action == "SUPERSEDE"]
    return safe_mean([lineage_row(*pair) for pair in eligible])


def duplicate_write(pairs: list[Pair]) -> float:
    def has_duplicate(pair: Pair) -> bool:
        state = pair[1]["predicted_memory_state"]
        active = [
            (
                str(record.get("semantic_slot", "")).casefold(),
                str(record.get("type", "")).casefold(),
                canonical_memory_value(record.get("text", "")),
            )
            for record in state
            if isinstance(record, dict) and record.get("status") == "active"
        ]
        return len(active) != len(set(active))

    return safe_mean([float(has_duplicate(pair)) for pair in pairs])


def invalid_commit(pairs: list[Pair]) -> float:
    """Legacy MGP-6 metric: commit violation on gold-ABSTAIN examples."""

    def committed(pair: Pair) -> bool:
        gold, pred = pair
        if pred["predicted_action"] != "ABSTAIN":
            return True
        predicted = active_signature(pred["predicted_memory_state"])
        allowed = active_signature(gold_state_dicts(gold))
        return bool(predicted - allowed)

    return rate(
        pairs,
        committed,
        lambda pair: pair[0].gold_action == "ABSTAIN",
    )


def invalid_commit_outcome(pairs: list[Pair]) -> float:
    """Rate of explicit INVALID_COMMIT prediction outcomes over all examples."""
    return safe_mean([float(pred["predicted_action"] == "INVALID_COMMIT") for _, pred in pairs])


def dual_active_outcome(pairs: list[Pair]) -> float:
    """Rate of predictions whose adapter observed old and new as simultaneously active."""
    return safe_mean(
        [float(bool((pred.get("extras") or {}).get("dual_active"))) for _, pred in pairs]
    )


def transient_contamination(pairs: list[Pair]) -> float:
    def contaminated(pair: Pair) -> bool:
        gold, pred = pair
        for record in pred["predicted_memory_state"]:
            if not isinstance(record, dict):
                continue
            if record.get("status") != "active" or record.get("type") != "stable_pref":
                continue
            text = str(record.get("text", ""))
            if any(re.search(pattern, text, re.I) for pattern in gold.forbidden_answer_patterns):
                return True
        return False

    return rate(pairs, contaminated, lambda pair: pair[0].type == "T5")


def judge_flags(gold: MGP6Example, answer: str) -> tuple[bool, bool]:
    include = all(re.search(pattern, answer, re.I) for pattern in gold.judge_spec.include)
    exclude = not any(re.search(pattern, answer, re.I) for pattern in gold.judge_spec.not_include)
    return include, exclude


def judge_rate(pairs: list[Pair], which: str) -> float:
    values: list[float] = []
    for gold, pred in pairs:
        include, exclude = judge_flags(gold, pred["predicted_answer"])
        values.append(
            float({"include": include, "exclude": exclude, "both": include and exclude}[which])
        )
    return safe_mean(values)


def premise_resistance(pairs: list[Pair]) -> float:
    def passed(pair: Pair) -> bool:
        gold, pred = pair
        include, exclude = judge_flags(gold, pred["predicted_answer"])
        rejects = bool(REJECTION_RE.search(pred["predicted_answer"]))
        return include and exclude and rejects

    return rate(pairs, passed, lambda pair: pair[0].query_mode == "premise_resistance")


def implicit_application(pairs: list[Pair]) -> float:
    return rate(
        pairs,
        lambda pair: all(judge_flags(pair[0], pair[1]["predicted_answer"])),
        lambda pair: pair[0].query_mode == "implicit_application",
    )


def implicit_conflict_recall(pairs: list[Pair]) -> float:
    return rate(
        pairs,
        lambda pair: pair[1]["predicted_action"] == "SUPERSEDE",
        lambda pair: pair[0].subtype == "implicit_conflict",
    )


def explicit_supersede_recall(pairs: list[Pair]) -> float:
    return rate(
        pairs,
        lambda pair: pair[1]["predicted_action"] == "SUPERSEDE",
        lambda pair: pair[0].type in {"T1", "T2", "T3"} and pair[0].subtype == "explicit_cue",
    )


def cue_dependence_gap(pairs: list[Pair]) -> float:
    return explicit_supersede_recall(pairs) - implicit_conflict_recall(pairs)


class BootstrapReporter:
    def __init__(self, pairs: list[Pair], iterations: int, seed: int = 62026) -> None:
        self.pairs = pairs
        rng = random.Random(seed)
        strata: dict[tuple[str, str], list[int]] = defaultdict(list)
        for index, (gold, _) in enumerate(pairs):
            strata[(gold.type, gold.gold_action)].append(index)
        self.samples: list[list[Pair]] = []
        for _ in range(iterations):
            indices: list[int] = []
            for members in strata.values():
                indices.extend(rng.choice(members) for _ in members)
            self.samples.append([pairs[index] for index in indices])

    @staticmethod
    def percentile(values: list[float], quantile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        position = (len(ordered) - 1) * quantile
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    def measure(self, metric: Metric) -> dict[str, Any]:
        value = metric(self.pairs)
        replicates = [metric(sample) for sample in self.samples]
        low = self.percentile(replicates, 0.025)
        high = self.percentile(replicates, 0.975)
        return {"value": round(value, 6), "ci95": [round(low, 6), round(high, 6)]}

    def sample_size(self) -> dict[str, Any]:
        size = len(self.pairs)
        return {"value": size, "ci95": [size, size]}


def metric_report(pairs: list[Pair], bootstrap: int, seed: int) -> dict[str, Any]:
    reporter = BootstrapReporter(pairs, bootstrap, seed)
    metrics: dict[str, Any] = {
        "sample_size": reporter.sample_size(),
        "action_accuracy": reporter.measure(action_accuracy),
        "macro_f1": reporter.measure(
            lambda sample: safe_mean([action_f1(sample, a) for a in ACTIONS])
        ),
        "artifact_exact_accuracy": reporter.measure(artifact_exact),
        "artifact_semantic_accuracy": reporter.measure(artifact_semantic),
        "over_forgetting_rate": reporter.measure(over_forgetting),
        "under_forgetting_rate": reporter.measure(under_forgetting),
        "stale_retrieval_rate": reporter.measure(stale_retrieval),
        "lineage_correctness": reporter.measure(lineage_correctness),
        "transient_contamination_rate": reporter.measure(transient_contamination),
        "abstention_precision": reporter.measure(
            lambda sample: action_precision(sample, "ABSTAIN")
        ),
        "abstention_recall": reporter.measure(lambda sample: action_recall(sample, "ABSTAIN")),
        # Backward-compatible key: commit violation on gold-ABSTAIN cases.
        "invalid_commit_rate": reporter.measure(invalid_commit),
        "abstention_invalid_commit_rate": reporter.measure(invalid_commit),
        # Prediction-level invalid governance outcome across the full slice.
        "invalid_commit_outcome_rate": reporter.measure(invalid_commit_outcome),
        "dual_active_rate": reporter.measure(dual_active_outcome),
        "duplicate_write_rate": reporter.measure(duplicate_write),
        "premise_resistance_rate": reporter.measure(premise_resistance),
        "implicit_application_accuracy": reporter.measure(implicit_application),
        "fama_presence_absence_conjunction": reporter.measure(
            lambda sample: judge_rate(sample, "both")
        ),
        "judge_include_rate": reporter.measure(lambda sample: judge_rate(sample, "include")),
        "judge_exclude_rate": reporter.measure(lambda sample: judge_rate(sample, "exclude")),
        "judge_conjunction_rate": reporter.measure(lambda sample: judge_rate(sample, "both")),
        "implicit_conflict_recall": reporter.measure(implicit_conflict_recall),
        "explicit_cue_supersede_recall": reporter.measure(explicit_supersede_recall),
        "cue_dependence_gap": reporter.measure(cue_dependence_gap),
    }
    metrics["per_action"] = {
        action: {
            "precision": reporter.measure(lambda sample, a=action: action_precision(sample, a)),
            "recall": reporter.measure(lambda sample, a=action: action_recall(sample, a)),
            "f1": reporter.measure(lambda sample, a=action: action_f1(sample, a)),
        }
        for action in ACTIONS
    }
    metrics["confusion_matrix"] = {
        gold_action: {
            predicted_action: reporter.measure(
                lambda sample, g=gold_action, p=predicted_action: float(
                    sum(
                        1
                        for gold, pred in sample
                        if (gold.gold_action == g and pred["predicted_action"] == p)
                    )
                )
            )
            for predicted_action in PREDICTION_OUTCOMES
        }
        for gold_action in ACTIONS
    }
    return metrics


def breakdowns(pairs: list[Pair], bootstrap: int) -> dict[str, Any]:
    dimensions: dict[str, Callable[[MGP6Example], str]] = {
        "type": lambda row: row.type,
        "query_mode": lambda row: row.query_mode,
        "subtype": lambda row: row.subtype,
        "difficulty": lambda row: row.difficulty,
    }
    output: dict[str, Any] = {}
    for dimension, getter in dimensions.items():
        values = sorted({getter(gold) for gold, _ in pairs})
        output[dimension] = {}
        for offset, value in enumerate(values):
            subset = [pair for pair in pairs if getter(pair[0]) == value]
            reporter = BootstrapReporter(subset, bootstrap, 71000 + offset + len(dimension))
            output[dimension][value] = {
                "sample_size": reporter.sample_size(),
                "action_accuracy": reporter.measure(action_accuracy),
                "artifact_semantic_accuracy": reporter.measure(artifact_semantic),
                "answer_presence_absence_conjunction": reporter.measure(
                    lambda sample: judge_rate(sample, "both")
                ),
            }
    return output


def risk_coverage(pairs: list[Pair], bootstrap: int) -> dict[str, Any] | None:
    if not pairs or any(pred.get("confidence") is None for _, pred in pairs):
        return None
    ordered = sorted(pairs, key=lambda pair: (-pair[1]["confidence"], pair[0].scenario_id))
    curve: dict[str, Any] = {}
    for step in range(1, 11):
        coverage = step / 10
        count = max(1, math.ceil(len(ordered) * coverage))
        subset = ordered[:count]
        reporter = BootstrapReporter(subset, bootstrap, 82000 + step)
        accuracy = reporter.measure(action_accuracy)
        curve[f"{coverage:.1f}"] = {
            "action_accuracy": accuracy,
            "risk": {
                "value": round(1 - accuracy["value"], 6),
                "ci95": [round(1 - accuracy["ci95"][1], 6), round(1 - accuracy["ci95"][0], 6)],
            },
        }
    return curve


def paired_mcnemar(pairs_a: list[Pair], pairs_b: list[Pair]) -> dict[str, Any]:
    by_id_b = {gold.scenario_id: (gold, pred) for gold, pred in pairs_b}
    a_only = 0
    b_only = 0
    for gold, pred_a in pairs_a:
        pred_b = by_id_b[gold.scenario_id][1]
        correct_a = pred_a["predicted_action"] == gold.gold_action
        correct_b = pred_b["predicted_action"] == gold.gold_action
        a_only += int(correct_a and not correct_b)
        b_only += int(correct_b and not correct_a)
    discordant = a_only + b_only
    if discordant == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(discordant, k) for k in range(min(a_only, b_only) + 1)) / (
            2**discordant
        )
        p_value = min(1.0, 2 * tail)
    return {
        "a_only_correct": a_only,
        "b_only_correct": b_only,
        "exact_two_sided_p": round(p_value, 8),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--pred", required=True, type=Path)
    parser.add_argument("--compare", type=Path, help="optional second prediction file for McNemar")
    parser.add_argument("--bootstrap", type=int, default=1000)
    args = parser.parse_args(argv)
    if args.bootstrap < 1:
        parser.error("--bootstrap must be at least 1")

    try:
        gold = load_gold(args.gold)
        pairs = align(gold, load_predictions(args.pred))
        test_pairs = [pair for pair in pairs if pair[0].split == "test"]
        report: dict[str, Any] = {
            "full": metric_report(pairs, args.bootstrap, 62026),
            "test": metric_report(test_pairs, args.bootstrap, 62027),
            "breakdowns": breakdowns(pairs, args.bootstrap),
            "risk_coverage": risk_coverage(pairs, args.bootstrap),
        }
        if args.compare:
            compare_pairs = align(gold, load_predictions(args.compare))
            report["paired_mcnemar"] = paired_mcnemar(pairs, compare_pairs)
    except (OSError, ValueError) as exc:
        print(f"METRICS ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
