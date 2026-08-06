"""Strict post-adjudication scoring for MGP-Natural predictions."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .blinding import canonical_hash

ACTIONS = ("KEEP", "SUPERSEDE", "ABSTAIN")
ACTION_SET = frozenset(ACTIONS)


def _unique_by_id(rows: list[dict[str, Any]], id_key: str, kind: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        value = row.get(id_key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{kind} row {index} has an empty {id_key}")
        if value in result:
            raise ValueError(f"duplicate {kind} {id_key}: {value}")
        result[value] = row
    return result


def _classification(gold: list[str], pred: list[str]) -> dict[str, Any]:
    per_class: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    for action in ACTIONS:
        tp = sum(g == action and p == action for g, p in zip(gold, pred, strict=True))
        fp = sum(g != action and p == action for g, p in zip(gold, pred, strict=True))
        fn = sum(g == action and p != action for g, p in zip(gold, pred, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[action] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(value == action for value in gold),
        }
        f1_values.append(f1)
    return {
        "accuracy": sum(g == p for g, p in zip(gold, pred, strict=True)) / len(gold)
        if gold
        else 0.0,
        "macro_f1": sum(f1_values) / len(f1_values),
        "per_class": per_class,
        "confusion": {
            gold_action: {
                pred_action: sum(
                    g == gold_action and p == pred_action for g, p in zip(gold, pred, strict=True)
                )
                for pred_action in ACTIONS
            }
            for gold_action in ACTIONS
        },
    }


def _set_f1(gold: list[str], pred: list[str]) -> float:
    gold_set, pred_set = set(gold), set(pred)
    if not gold_set and not pred_set:
        return 1.0
    intersection = len(gold_set & pred_set)
    precision = intersection / len(pred_set) if pred_set else 0.0
    recall = intersection / len(gold_set) if gold_set else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def score_predictions(
    gold_rows: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    *,
    allow_provisional_smoke: bool = False,
    held_out_split_valid: bool = False,
    independent_component_count: int = 0,
) -> dict[str, Any]:
    """Score exact-coverage predictions and refuse provisional gold by default."""

    gold_by_id = _unique_by_id(gold_rows, "blind_id", "gold")
    pred_by_id = _unique_by_id(predictions, "blind_id", "prediction")
    statuses = Counter(str(row.get("annotation_status", "")) for row in gold_rows)
    final_gold = set(statuses) == {"independently_adjudicated_gold"}
    if not final_gold and not allow_provisional_smoke:
        raise ValueError("refusing to score provisional or undocumented gold")

    missing = sorted(set(gold_by_id) - set(pred_by_id))
    extra = sorted(set(pred_by_id) - set(gold_by_id))
    if missing or extra:
        raise ValueError(
            f"prediction ID coverage mismatch: missing={missing[:5]}, extra={extra[:5]}"
        )

    gold_actions: list[str] = []
    pred_actions: list[str] = []
    state_hits: list[bool] = []
    lineage_hits: list[bool] = []
    evidence_scores: list[float] = []
    for blind_id, gold in gold_by_id.items():
        prediction = pred_by_id[blind_id]
        gold_action = str(gold.get("gold_action", ""))
        predicted_action = str(prediction.get("predicted_action", "")).upper()
        if gold_action not in ACTION_SET or predicted_action not in ACTION_SET:
            raise ValueError(f"invalid action for {blind_id}")
        gold_actions.append(gold_action)
        pred_actions.append(predicted_action)

        if "predicted_resulting_state" in prediction:
            state_hits.append(
                canonical_hash(prediction["predicted_resulting_state"])
                == canonical_hash(gold.get("resulting_state"))
            )
        if "predicted_lineage" in prediction:
            lineage_hits.append(
                canonical_hash(prediction["predicted_lineage"])
                == canonical_hash(gold.get("lineage"))
            )
        if "predicted_evidence_turn_ids" in prediction:
            evidence_scores.append(
                _set_f1(
                    list(map(str, gold.get("evidence_turn_ids") or [])),
                    list(map(str, prediction.get("predicted_evidence_turn_ids") or [])),
                )
            )

    item_count = len(gold_rows)
    publication_eligible = bool(
        final_gold and held_out_split_valid and independent_component_count >= 3
    )
    return {
        "schema_version": "1.0",
        "item_count": item_count,
        "action": _classification(gold_actions, pred_actions),
        "state_object_exact_match": {
            "coverage": len(state_hits) / item_count if item_count else 0.0,
            "score": sum(state_hits) / len(state_hits) if state_hits else None,
        },
        "lineage_object_exact_match": {
            "coverage": len(lineage_hits) / item_count if item_count else 0.0,
            "score": sum(lineage_hits) / len(lineage_hits) if lineage_hits else None,
        },
        "evidence_turn_f1": {
            "coverage": len(evidence_scores) / item_count if item_count else 0.0,
            "score": sum(evidence_scores) / len(evidence_scores) if evidence_scores else None,
        },
        "annotation_status_counts": dict(sorted(statuses.items())),
        "provisional_smoke": not final_gold,
        "held_out_split_valid": held_out_split_valid,
        "independent_component_count": independent_component_count,
        "confidence_intervals_reported": False,
        "publication_eligible": publication_eligible,
        "leaderboard_eligible": publication_eligible,
    }
