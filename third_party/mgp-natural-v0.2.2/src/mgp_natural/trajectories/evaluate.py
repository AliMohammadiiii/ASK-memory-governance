"""Apply MGP decisions over time and quantify propagation/recovery."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mgp_natural.errors import ValidationError
from mgp_natural.ontology.contract import Action, canonical_value
from mgp_natural.util.io import iter_jsonl, write_json


def apply_action(state: str, action: str, resulting_value: str | None) -> str:
    parsed = Action(action)
    if parsed is Action.SUPERSEDE:
        if not resulting_value or canonical_value(resulting_value) == canonical_value(state):
            raise ValidationError("trajectory SUPERSEDE requires changed value")
        return resulting_value
    return state


def evaluate_trajectory(gold: list[dict[str, Any]], pred: list[dict[str, Any]]) -> dict[str, Any]:
    if len(gold) != len(pred) or not gold:
        raise ValidationError("trajectory sequences must align")
    gold_state = gold[0]["prior_value"]
    pred_state = gold_state
    first_error = None
    stale = improper = recoveries = repeated_abstain = 0
    previous_pred_action = None
    for index, (g, p) in enumerate(zip(gold, pred, strict=True)):
        gold_state = apply_action(gold_state, g["action"], g.get("resulting_value"))
        old_pred_state = pred_state
        pred_state = apply_action(pred_state, p["action"], p.get("resulting_value"))
        if g["action"] != p["action"] and first_error is None:
            first_error = index
        if g["action"] == "SUPERSEDE" and p["action"] != "SUPERSEDE":
            stale += 1
        if g["action"] != "SUPERSEDE" and p["action"] == "SUPERSEDE":
            improper += 1
        if canonical_value(old_pred_state) != canonical_value(gold_state) and canonical_value(pred_state) == canonical_value(gold_state):
            recoveries += 1
        if p["action"] == previous_pred_action == "ABSTAIN":
            repeated_abstain += 1
        previous_pred_action = p["action"]
    return {
        "first_incorrect_write_index": first_error,
        "stale_state_events": stale,
        "improper_overwrites": improper,
        "recovery_events": recoveries,
        "repeated_abstention_events": repeated_abstain,
        "final_state_exact": pred_state == gold_state,
        "final_state_canonical": canonical_value(pred_state) == canonical_value(gold_state),
        "trajectory_items": len(gold),
    }


def evaluate_files(gold_path: Path, prediction_path: Path, output_path: Path) -> dict[str, Any]:
    gold = {row["trajectory_id"]: row for row in iter_jsonl(gold_path)}
    pred = {row["trajectory_id"]: row for row in iter_jsonl(prediction_path)}
    if set(gold) != set(pred):
        raise ValidationError("trajectory coverage mismatch")
    results = {
        key: evaluate_trajectory(gold[key]["steps"], pred[key]["steps"])
        for key in sorted(gold)
    }
    report = {"trajectories": len(results), "results": results, "natural_gold_available": False}
    write_json(output_path, report)
    return report

