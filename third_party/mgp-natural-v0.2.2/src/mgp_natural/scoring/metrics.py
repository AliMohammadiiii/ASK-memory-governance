"""Track-separated classification, state, evidence, lineage, calibration, and bootstrap metrics."""
from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterable
from pathlib import Path
from statistics import mean
from typing import Any

from mgp_natural.errors import ValidationError
from mgp_natural.ontology.contract import Action, canonical_value
from mgp_natural.util.io import iter_jsonl, sha256_file, write_json

ACTIONS = ("KEEP", "SUPERSEDE", "ABSTAIN")
TRACKS = ("STUDYCHAT", "WIKICONV")


def _safe_mean(values: Iterable[float]) -> float | None:
    materialized = list(values)
    return mean(materialized) if materialized else None


def classification_metrics(gold: list[str], pred: list[str]) -> dict[str, Any]:
    if len(gold) != len(pred) or not gold:
        raise ValidationError("gold and predictions must be nonempty and aligned")
    matrix = {gold_action: {pred_action: 0 for pred_action in ACTIONS} for gold_action in ACTIONS}
    for gold_action, pred_action in zip(gold, pred, strict=True):
        if gold_action not in ACTIONS or pred_action not in ACTIONS:
            raise ValidationError("invalid action")
        matrix[gold_action][pred_action] += 1
    per_class: dict[str, dict[str, float | int]] = {}
    for action in ACTIONS:
        true_positive = matrix[action][action]
        false_positive = sum(matrix[other][action] for other in ACTIONS if other != action)
        false_negative = sum(matrix[action][other] for other in ACTIONS if other != action)
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[action] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(matrix[action].values()),
        }
    return {
        "accuracy": sum(g == p for g, p in zip(gold, pred, strict=True)) / len(gold),
        "macro_f1": mean(float(per_class[action]["f1"]) for action in ACTIONS),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "support": len(gold),
    }


def evidence_metrics(gold_sets: list[set[str]], pred_sets: list[set[str]]) -> dict[str, float]:
    if len(gold_sets) != len(pred_sets) or not gold_sets:
        raise ValidationError("evidence sets must be nonempty and aligned")
    precisions: list[float] = []
    recalls: list[float] = []
    f1_values: list[float] = []
    for gold, pred in zip(gold_sets, pred_sets, strict=True):
        overlap = len(gold & pred)
        precision = overlap / len(pred) if pred else float(gold == pred)
        recall = overlap / len(gold) if gold else float(gold == pred)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        precisions.append(precision)
        recalls.append(recall)
        f1_values.append(f1)
    return {"precision": mean(precisions), "recall": mean(recalls), "f1": mean(f1_values)}


def _validate_probability_row(probabilities: dict[str, Any]) -> dict[str, float]:
    if set(probabilities) != set(ACTIONS):
        raise ValidationError("probabilities must cover exactly KEEP, SUPERSEDE, and ABSTAIN")
    values: dict[str, float] = {}
    for action in ACTIONS:
        value = probabilities[action]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError("probabilities must be finite numbers")
        converted = float(value)
        if not math.isfinite(converted) or not 0.0 <= converted <= 1.0:
            raise ValidationError("probabilities must be finite values in [0, 1]")
        values[action] = converted
    if not math.isclose(sum(values.values()), 1.0, rel_tol=0.0, abs_tol=1e-6):
        raise ValidationError("probabilities must cover actions and sum to one")
    return values


def brier_score(gold: list[str], probabilities: list[dict[str, float]]) -> float:
    if len(gold) != len(probabilities) or not gold:
        raise ValidationError("gold and probabilities must be nonempty and aligned")
    scores: list[float] = []
    for target, raw_probabilities in zip(gold, probabilities, strict=True):
        probabilities_row = _validate_probability_row(raw_probabilities)
        scores.append(
            sum(
                (probabilities_row[action] - float(action == target)) ** 2
                for action in ACTIONS
            )
        )
    return mean(scores)


def expected_calibration_error(
    gold: list[str],
    pred: list[str],
    confidence: list[float],
    bins: int = 10,
) -> float:
    if len(gold) != len(pred) or len(gold) != len(confidence) or not gold:
        raise ValidationError("calibration inputs must be nonempty and aligned")
    if bins < 1:
        raise ValidationError("bins must be positive")
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in confidence):
        raise ValidationError("confidence must contain finite values in [0, 1]")
    total = len(gold)
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        selected = [
            item_index
            for item_index, value in enumerate(confidence)
            if lower <= value and (value <= upper if index == bins - 1 else value < upper)
        ]
        if not selected:
            continue
        accuracy = mean(gold[item_index] == pred[item_index] for item_index in selected)
        average_confidence = mean(confidence[item_index] for item_index in selected)
        error += len(selected) / total * abs(accuracy - average_confidence)
    return error


def cluster_bootstrap(
    rows: list[dict[str, Any]],
    cluster_key: str,
    statistic: Callable[[list[dict[str, Any]]], float],
    iterations: int = 1000,
    seed: int = 1729,
) -> dict[str, float | int]:
    if iterations < 2:
        raise ValidationError("bootstrap iterations must be at least two")
    clusters: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if cluster_key not in row:
            raise ValidationError(f"missing cluster key: {cluster_key}")
        clusters.setdefault(str(row[cluster_key]), []).append(row)
    keys = sorted(clusters)
    if not keys:
        raise ValidationError("no clusters")
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(iterations):
        sampled_keys = [rng.choice(keys) for _ in keys]
        sampled_rows = [row for key in sampled_keys for row in clusters[key]]
        values.append(statistic(sampled_rows))
    values.sort()
    lower_index = int(0.025 * (len(values) - 1))
    upper_index = int(0.975 * (len(values) - 1))
    return {
        "estimate": statistic(rows),
        "ci95_low": values[lower_index],
        "ci95_high": values[upper_index],
        "iterations": iterations,
        "seed": seed,
        "clusters": len(keys),
    }


def _lineage_edges(row: dict[str, Any]) -> set[str]:
    relations = row.get("lineage_relations") or []
    edges: set[str] = set()
    for relation in relations:
        if not isinstance(relation, dict):
            raise ValidationError("lineage_relations must contain objects")
        stable = "|".join(
            str(relation.get(key, ""))
            for key in ("predecessor_item_id", "successor_item_id", "relation", "scope", "slot")
        )
        edges.add(stable)
    return edges


def _set_micro_metrics(gold_sets: list[set[str]], pred_sets: list[set[str]]) -> dict[str, float | int]:
    true_positive = sum(len(gold & pred) for gold, pred in zip(gold_sets, pred_sets, strict=True))
    predicted = sum(len(pred) for pred in pred_sets)
    relevant = sum(len(gold) for gold in gold_sets)
    precision = true_positive / predicted if predicted else float(relevant == 0)
    recall = true_positive / relevant if relevant else float(predicted == 0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positive_edges": true_positive,
        "predicted_edges": predicted,
        "gold_edges": relevant,
    }


def _confidence_report(
    gold_actions: list[str],
    pred_actions: list[str],
    confidence: list[float],
) -> dict[str, Any]:
    strata = []
    for lower, upper in ((0.0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.0000001)):
        indices = [index for index, value in enumerate(confidence) if lower <= value < upper]
        if not indices:
            continue
        strata.append(
            {
                "lower_inclusive": lower,
                "upper_exclusive": min(upper, 1.0),
                "support": len(indices),
                "accuracy": mean(gold_actions[index] == pred_actions[index] for index in indices),
                "mean_confidence": mean(confidence[index] for index in indices),
            }
        )
    ranked = sorted(
        range(len(confidence)),
        key=lambda index: (-confidence[index], index),
    )
    selective = []
    for target_coverage in (1.0, 0.8, 0.5, 0.2):
        retained = max(1, math.ceil(len(ranked) * target_coverage))
        selected = ranked[:retained]
        accuracy = mean(gold_actions[index] == pred_actions[index] for index in selected)
        selective.append(
            {
                "target_coverage": target_coverage,
                "observed_coverage": retained / len(ranked),
                "risk": 1.0 - accuracy,
                "support": retained,
            }
        )
    return {"confidence_strata": strata, "selective_risk": selective}


def _score_subset(
    ids: list[str],
    gold_by_id: dict[str, dict[str, Any]],
    pred_by_id: dict[str, dict[str, Any]],
    bootstrap_iterations: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    gold_actions = [str(gold_by_id[item_id]["action"]) for item_id in ids]
    pred_actions = [str(pred_by_id[item_id]["action"]) for item_id in ids]
    result = classification_metrics(gold_actions, pred_actions)
    result["abstention_precision"] = result["per_class"]["ABSTAIN"]["precision"]
    result["abstention_recall"] = result["per_class"]["ABSTAIN"]["recall"]
    result["prediction_coverage"] = 1.0
    result["exclusion_aware_coverage"] = 1.0

    if all("evidence_turn_ids" in pred_by_id[item_id] for item_id in ids):
        result["evidence"] = evidence_metrics(
            [set(gold_by_id[item_id].get("evidence_turn_ids", [])) for item_id in ids],
            [set(pred_by_id[item_id].get("evidence_turn_ids", [])) for item_id in ids],
        )

    exact_matches: list[bool] = []
    canonical_matches: list[bool] = []
    joint_matches: list[bool] = []
    supersede_exact: list[bool] = []
    supersede_canonical: list[bool] = []
    for item_id, gold_action, pred_action in zip(ids, gold_actions, pred_actions, strict=True):
        gold_value = str(gold_by_id[item_id].get("resulting_value", ""))
        pred_value = str(pred_by_id[item_id].get("resulting_value", ""))
        exact = gold_value == pred_value
        canonical = canonical_value(gold_value) == canonical_value(pred_value)
        exact_matches.append(exact)
        canonical_matches.append(canonical)
        joint_matches.append(gold_action == pred_action and canonical)
        if gold_action == "SUPERSEDE":
            supersede_exact.append(exact)
            supersede_canonical.append(canonical)
    result["resulting_state_exact_match"] = mean(exact_matches)
    result["resulting_state_canonical_match"] = mean(canonical_matches)
    result["action_plus_state_joint_exact_match"] = mean(joint_matches)
    result["supersede_resulting_state_exact_match"] = _safe_mean(float(v) for v in supersede_exact)
    result["supersede_resulting_state_canonical_match"] = _safe_mean(
        float(v) for v in supersede_canonical
    )

    if any(gold_by_id[item_id].get("lineage_relations") for item_id in ids):
        result["lineage_edge"] = _set_micro_metrics(
            [_lineage_edges(gold_by_id[item_id]) for item_id in ids],
            [_lineage_edges(pred_by_id[item_id]) for item_id in ids],
        )

    probabilities: list[dict[str, float]] = []
    confidence: list[float] = []
    has_probabilities = all("probabilities" in pred_by_id[item_id] for item_id in ids)
    has_confidence = all("confidence" in pred_by_id[item_id] for item_id in ids)
    if has_probabilities:
        for item_id in ids:
            probabilities.append(_validate_probability_row(pred_by_id[item_id]["probabilities"]))
        result["brier_score"] = brier_score(gold_actions, probabilities)
        if not has_confidence:
            confidence = [max(row.values()) for row in probabilities]
    if has_confidence:
        confidence = []
        for item_id in ids:
            value = pred_by_id[item_id]["confidence"]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValidationError("confidence must be numeric")
            converted = float(value)
            if not math.isfinite(converted) or not 0.0 <= converted <= 1.0:
                raise ValidationError("confidence must be finite and in [0, 1]")
            confidence.append(converted)
    if confidence:
        result["expected_calibration_error"] = expected_calibration_error(
            gold_actions, pred_actions, confidence
        )
        result.update(_confidence_report(gold_actions, pred_actions, confidence))

    if all("cluster_id" in gold_by_id[item_id] for item_id in ids):
        bootstrap_rows = [
            {
                "cluster_id": gold_by_id[item_id]["cluster_id"],
                "gold": gold_by_id[item_id]["action"],
                "pred": pred_by_id[item_id]["action"],
            }
            for item_id in ids
        ]
        result["cluster_bootstrap"] = {
            "accuracy": cluster_bootstrap(
                bootstrap_rows,
                "cluster_id",
                lambda rows: mean(row["gold"] == row["pred"] for row in rows),
                iterations=bootstrap_iterations,
                seed=bootstrap_seed,
            ),
            "macro_f1": cluster_bootstrap(
                bootstrap_rows,
                "cluster_id",
                lambda rows: float(
                    classification_metrics(
                        [str(row["gold"]) for row in rows],
                        [str(row["pred"]) for row in rows],
                    )["macro_f1"]
                ),
                iterations=bootstrap_iterations,
                seed=bootstrap_seed,
            ),
        }
    return result


def _balanced_ids(ids: list[str], gold_by_id: dict[str, dict[str, Any]]) -> list[str]:
    by_action = {
        action: sorted(item_id for item_id in ids if gold_by_id[item_id]["action"] == action)
        for action in ACTIONS
    }
    minimum = min((len(values) for values in by_action.values()), default=0)
    if minimum == 0:
        return []
    return sorted(item_id for action in ACTIONS for item_id in by_action[action][:minimum])


def _view_ids(track: str, ids: list[str], gold_by_id: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    scopes = {item_id: str(gold_by_id[item_id]["scope"]) for item_id in ids}
    views: dict[str, list[str]] = {"prevalence_preserving_full": ids}
    balanced = _balanced_ids(ids, gold_by_id)
    if balanced:
        views["balanced_diagnostic_action"] = balanced
    if track == "STUDYCHAT":
        task_scopes = {
            "SESSION_TASK_STATE",
            "CROSS_SESSION_TASK_STATE",
            "ARTIFACT_STATE",
            "CORRECTION_STATE",
            "UNCERTAINTY_STATE",
        }
        preference_scopes = {
            "SESSION_INTERACTION_PREFERENCE",
            "CROSS_SESSION_USER_PREFERENCE",
        }
        cross_session_scopes = {
            "CROSS_SESSION_TASK_STATE",
            "CROSS_SESSION_USER_PREFERENCE",
        }
        for name, allowed in (
            ("studychat_task_state", task_scopes),
            ("studychat_preference", preference_scopes),
            ("studychat_cross_session", cross_session_scopes),
        ):
            selected = [item_id for item_id in ids if scopes[item_id] in allowed]
            if selected:
                views[name] = selected
    else:
        views["wikiconv_editorial_state"] = ids
    ambiguity = [
        item_id
        for item_id in ids
        if scopes[item_id] in {"UNCERTAINTY_STATE", "EDITORIAL_UNCERTAINTY", "DISPUTE_STATE"}
    ]
    if ambiguity:
        views["ambiguity_heavy"] = ambiguity
    return views


def _validate_gold_rows(rows: list[dict[str, Any]], allow_provisional_smoke: bool) -> bool:
    if not rows:
        raise ValidationError("empty gold")
    statuses = {row.get("annotation_status") for row in rows}
    publication_eligible = statuses == {"independently_adjudicated_gold"}
    if not publication_eligible and not allow_provisional_smoke:
        raise ValidationError("scorer refuses provisional or undocumented gold")
    for row in rows:
        action = row.get("action")
        if not isinstance(action, str):
            raise ValidationError("invalid gold action")
        try:
            Action(action)
        except (TypeError, ValueError) as exc:
            raise ValidationError("invalid gold action") from exc
        if row.get("source_track") not in TRACKS:
            raise ValidationError("gold source_track must be STUDYCHAT or WIKICONV")
        if not isinstance(row.get("scope"), str) or not row["scope"]:
            raise ValidationError("gold scope is required")
        if not isinstance(row.get("resulting_value"), str) or not row["resulting_value"].strip():
            raise ValidationError("gold resulting_value is required")
        evidence = row.get("evidence_turn_ids")
        if not isinstance(evidence, list) or not evidence or len(evidence) != len(set(evidence)):
            raise ValidationError("gold evidence_turn_ids must be nonempty and unique")
    return publication_eligible


def _index_predictions(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        blind_id = row.get("blind_id")
        if not isinstance(blind_id, str) or not blind_id:
            raise ValidationError("prediction blind_id is required")
        if blind_id in indexed:
            raise ValidationError("duplicate prediction ID")
        raw_action = row.get("action")
        if not isinstance(raw_action, str):
            raise ValidationError("invalid predicted action")
        try:
            action = Action(raw_action)
        except (TypeError, ValueError) as exc:
            raise ValidationError("invalid predicted action") from exc
        if action is Action.SUPERSEDE and not str(row.get("resulting_value", "")).strip():
            raise ValidationError("SUPERSEDE prediction requires a nonempty resulting_value")
        evidence = row.get("evidence_turn_ids")
        if evidence is not None and (
            not isinstance(evidence, list) or len(evidence) != len(set(evidence))
        ):
            raise ValidationError("prediction evidence_turn_ids must be a unique list")
        if "probabilities" in row:
            _validate_probability_row(row["probabilities"])
        indexed[blind_id] = row
    return indexed


def score_files(
    gold_path: Path,
    prediction_path: Path,
    output_path: Path,
    allow_provisional_smoke: bool = False,
    bootstrap_iterations: int = 1000,
    bootstrap_seed: int = 1729,
) -> dict[str, Any]:
    gold_rows = list(iter_jsonl(gold_path))
    prediction_rows = list(iter_jsonl(prediction_path))
    publication_eligible = _validate_gold_rows(gold_rows, allow_provisional_smoke)

    gold_by_id: dict[str, dict[str, Any]] = {}
    for row in gold_rows:
        blind_id = row.get("blind_id")
        if not isinstance(blind_id, str) or not blind_id:
            raise ValidationError("gold blind_id is required")
        if blind_id in gold_by_id:
            raise ValidationError("duplicate gold ID")
        gold_by_id[blind_id] = row
    pred_by_id = _index_predictions(prediction_rows)
    if set(gold_by_id) != set(pred_by_id):
        raise ValidationError("prediction coverage must exactly match gold")

    track_results: dict[str, Any] = {}
    view_results: dict[str, Any] = {}
    for track in TRACKS:
        track_ids = sorted(
            item_id for item_id, row in gold_by_id.items() if row["source_track"] == track
        )
        if not track_ids:
            continue
        track_results[track] = _score_subset(
            track_ids,
            gold_by_id,
            pred_by_id,
            bootstrap_iterations,
            bootstrap_seed,
        )
        for view_name, selected_ids in _view_ids(track, track_ids, gold_by_id).items():
            view_results[f"{track}:{view_name}"] = _score_subset(
                selected_ids,
                gold_by_id,
                pred_by_id,
                bootstrap_iterations,
                bootstrap_seed,
            )

    result: dict[str, Any] = {
        "schema_version": "1.0",
        "evaluator_version": "0.1.0",
        "publication_eligible": publication_eligible,
        "smoke_mode": not publication_eligible,
        "evaluation_policy": {
            "primary_metric": "macro_f1",
            "mixed_track_headline_score_emitted": False,
            "tracks_reported_separately": True,
            "exact_prediction_coverage_required": True,
        },
        "inputs": {
            "gold_sha256": sha256_file(gold_path),
            "predictions_sha256": sha256_file(prediction_path),
            "gold_rows": len(gold_rows),
            "prediction_rows": len(prediction_rows),
        },
        "track_results": track_results,
        "views": view_results,
    }
    if not publication_eligible:
        result["required_statement"] = "publication_eligible = false"
    write_json(output_path, result)
    return result

