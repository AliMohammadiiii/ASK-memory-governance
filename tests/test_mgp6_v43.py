"""Release and leakage-regression tests for MGP-6 v4.3."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from ask.eval.mgp6_v43 import (
    PROHIBITED_MODEL_KEYS,
    MGP6V43Error,
    MGP6V43Prediction,
    assert_model_safe,
    build_decision_prompt,
    cluster_bootstrap,
    load_predictions,
    load_public_records,
    score_actions,
    validate_component_splits,
    validate_public_release,
    write_prediction_resume_safe,
)

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "benchmarks/mgp6/mgp6_v4_3/public"
FACTS = ROOT / "benchmarks/mgp6/mgp6_v4_3/release_metadata/RELEASE_FACTS.json"


@pytest.fixture(scope="module")
def release():
    train = load_public_records(PUBLIC / "train.jsonl")
    dev = load_public_records(PUBLIC / "dev.jsonl")
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    return train, dev, facts


def test_release_counts_balance_uniqueness_and_determinism(release) -> None:
    train, dev, facts = release
    validate_public_release(train, dev, facts)
    assert len(train) + len(dev) + facts["split_counts"]["hidden"] == 900
    assert facts["component_count"] == 100
    assert facts["split_component_counts"] == {"train": 20, "dev": 20, "hidden": 60}
    assert Counter(row.gold_action for row in train) == Counter(KEEP=60, SUPERSEDE=60, ABSTAIN=60)
    assert Counter(row.gold_action for row in dev) == Counter(KEEP=60, SUPERSEDE=60, ABSTAIN=60)
    assert [row.public_id for row in train] == sorted(row.public_id for row in train)
    assert [row.public_id for row in train] == [row.public_id for row in load_public_records(PUBLIC / "train.jsonl")]


def test_component_isolation_contract() -> None:
    component_to_split = {**{f"t{i}": "train" for i in range(20)}, **{f"d{i}": "dev" for i in range(20)}, **{f"h{i}": "hidden" for i in range(60)}}
    validate_component_splits(component_to_split)
    component_to_split["bad"] = "train"
    with pytest.raises(MGP6V43Error):
        validate_component_splits(component_to_split)


def test_model_input_prompt_and_logs_are_label_free(release) -> None:
    record = release[0][0]
    payload = record.model_input()
    assert not (set(payload) & PROHIBITED_MODEL_KEYS)
    assert "gold_action" not in build_decision_prompt(record, "system")
    for key in ("gold_action", "design_target", "source_item_id", "component_id", "private_item_id", "annotator_id", "final_consensus", "human_gold", "hidden_gold"):
        with pytest.raises(MGP6V43Error):
            assert_model_safe({key: "forbidden"})


def test_prediction_validation_and_resume_safety(tmp_path: Path, release) -> None:
    ids = [row.public_id for row in release[0][:2]]
    path = tmp_path / "predictions.jsonl"
    first = MGP6V43Prediction(public_id=ids[0], action="KEEP")
    assert write_prediction_resume_safe(path, first) is True
    assert write_prediction_resume_safe(path, first) is False
    with pytest.raises(MGP6V43Error):
        write_prediction_resume_safe(path, MGP6V43Prediction(public_id=ids[0], action="ABSTAIN"))
    with pytest.raises(MGP6V43Error, match="missing"):
        load_predictions(path, ids)
    path.write_text(path.read_text(encoding="utf-8") + json.dumps({"public_id": "MGP43-FFFFFFFFFFFFFFFFFFFF", "action": "KEEP"}) + "\n", encoding="utf-8")
    with pytest.raises(MGP6V43Error, match="unknown"):
        load_predictions(path, ids)


def test_metric_correctness_and_cluster_bootstrap_reproducibility() -> None:
    gold = {"a": "KEEP", "b": "SUPERSEDE", "c": "ABSTAIN", "d": "KEEP"}
    predictions = {"a": "KEEP", "b": "KEEP", "c": "ABSTAIN", "d": "SUPERSEDE"}
    result = score_actions(gold, predictions)
    assert result["accuracy"] == 0.5
    assert result["confusion_matrix"]["SUPERSEDE"]["KEEP"] == 1
    component_map = {"a": "x", "b": "x", "c": "y", "d": "y"}
    assert cluster_bootstrap(gold, predictions, component_map, seed=7, replicates=100) == cluster_bootstrap(gold, predictions, component_map, seed=7, replicates=100)


def test_private_boundary_is_ignored() -> None:
    candidate = ".private/benchmarks/mgp6/v4.3/hidden_gold/hidden_gold.jsonl"
    result = subprocess.run(["git", "check-ignore", "-q", candidate], cwd=ROOT, check=False)
    assert result.returncode == 0


def test_v43_runner_dry_run_and_engineering_fixture(tmp_path: Path) -> None:
    dry_run = subprocess.run([sys.executable, "scripts/run_mgp6_v43.py", "--limit", "2", "--dry-run"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert dry_run.returncode == 0, dry_run.stderr
    run = subprocess.run([sys.executable, "scripts/run_mgp6_v43.py", "--limit", "2", "--action", "ABSTAIN", "--out", str(tmp_path / "smoke")], cwd=ROOT, capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    assert len((tmp_path / "smoke/predictions.jsonl").read_text(encoding="utf-8").splitlines()) == 2
