from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analysis/audit_mgp6_validity.py"
SPEC = importlib.util.spec_from_file_location("audit_mgp6_validity", SCRIPT)
assert SPEC and SPEC.loader
audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_module)


def test_type_only_lookup_exposes_held_out_label_leakage() -> None:
    rows = audit_module.load_jsonl(ROOT / "benchmarks/mgp6/data/mgp6_v2.jsonl")
    train_dev = [row for row in rows if row["split"] in {"train", "dev"}]
    test = [row for row in rows if row["split"] == "test"]

    result = audit_module.evaluate_lookup(train_dev, test, ("type",))

    assert result["test_accuracy"] > 0.95
    assert result["test_macro_f1"] > 0.94
    assert result["unseen_feature_combinations"] == 0

    conflict_result = audit_module.evaluate_lookup(train_dev, test, ("conflict_type",))
    assert conflict_result["test_accuracy"] == 1.0


def test_zero_events_has_nonzero_finite_sample_upper_bound() -> None:
    rows = [
        {
            "scenario_id": f"s{i}",
            "gold_action": "ABSTAIN",
            "template_family_id": f"f{i}",
        }
        for i in range(10)
    ]
    predictions = {
        row["scenario_id"]: {"predicted_action": "ABSTAIN", "confidence": 0.9}
        for row in rows
    }

    result = audit_module.prediction_metrics(rows, predictions)

    assert result["false_commit_rate"] == 0.0
    assert 0.0 < result["false_commit_one_sided_95_upper"] < 1.0


def test_cluster_bootstrap_is_deterministic_for_seed() -> None:
    rows = [
        {"scenario_id": "a", "template_family_id": "f1"},
        {"scenario_id": "b", "template_family_id": "f1"},
        {"scenario_id": "c", "template_family_id": "f2"},
    ]
    values = {"a": 1.0, "b": 0.0, "c": 1.0}

    left = audit_module.cluster_bootstrap(
        rows,
        values,
        lambda row: row["template_family_id"],
        samples=200,
        seed=7,
    )
    right = audit_module.cluster_bootstrap(
        rows,
        values,
        lambda row: row["template_family_id"],
        samples=200,
        seed=7,
    )

    assert left == right
    assert left["n_clusters"] == 2
