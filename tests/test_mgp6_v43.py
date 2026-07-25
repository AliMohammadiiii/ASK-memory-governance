"""Release and leakage-regression tests for MGP-6 v4.3."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from ask.eval.mgp6_v43 import (
    MGP6V43_SYSTEMS,
    PROHIBITED_MODEL_KEYS,
    MGP6V43Error,
    MGP6V43Prediction,
    MGP6V43Record,
    apply_live_controller_guard,
    assert_model_safe,
    build_decision_prompt,
    cluster_bootstrap,
    linked_evidence_view,
    load_predictions,
    load_public_records,
    model_input_for_system,
    public_evidence_policy_action,
    rules_controller_action,
    score_actions,
    system_allowed_actions,
    validate_component_splits,
    validate_public_release,
    write_prediction_resume_safe,
)
from scripts import run_mgp6_v43
from scripts.score_mgp6_v43 import score_public_run

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "benchmarks/mgp6/mgp6_v4_3/public"
FACTS = ROOT / "benchmarks/mgp6/mgp6_v4_3/release_metadata/RELEASE_FACTS.json"
DEV_CONFIG = ROOT / "configs/experiments/mgp6_v43/DEV_EXPERIMENTS.json"


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


def test_development_registry_covers_implemented_systems_and_prompt_hashes() -> None:
    config = json.loads(DEV_CONFIG.read_text(encoding="utf-8"))
    assert {entry["id"] for entry in config["systems"]} == set(MGP6V43_SYSTEMS)
    assert set(config["execution_contract"]["implemented_by_scripts_run_mgp6_v43"]) == set(MGP6V43_SYSTEMS)
    for entry in config["prompt_templates"].values():
        path = ROOT / entry["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]


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


def test_system_views_are_distinct_and_label_free(release) -> None:
    record = release[0][0]
    views = {
        system: model_input_for_system(record, system, recency_turns=2)
        for system in MGP6V43_SYSTEMS
    }
    assert "memory_before" not in views["b1"]
    assert "flat_retrieved_memory" in views["b2"]
    assert len(views["b3"]["recent_dialogue"]) == 2
    for view in views.values():
        assert_model_safe(view)
        assert not (set(_keys(view)) & PROHIBITED_MODEL_KEYS)
    assert system_allowed_actions("b4") == ("KEEP", "SUPERSEDE")
    assert system_allowed_actions("ablation_no_abstain") == ("KEEP", "SUPERSEDE")


def test_live_controller_routes_only_publicly_indexed_evidence(release) -> None:
    train, dev, _ = release
    for record in [*train, *dev]:
        view = linked_evidence_view(record)
        assert view["evidence_routing"] == {
            "indexed_message_count": 2,
            "available_numbered_message_count": 6,
            "unindexed_messages_excluded": 4,
        }
        assert len(view["indexed_evidence"]) == 2
        assert [item["message_position"] for item in view["indexed_evidence"]] == sorted(
            item["message_position"] for item in view["indexed_evidence"]
        )
        assert_model_safe(view)
        assert not (set(_keys(view)) & PROHIBITED_MODEL_KEYS)


def test_live_controller_guard_uses_public_evidence_only() -> None:
    def record(*, first: str, second: str) -> MGP6V43Record:
        return MGP6V43Record(
            public_id="MGP43-00000000000000000000",
            memory_before={"memory_slot": "setting", "principal": "Ari", "standing_value": "old"},
            dialogue=[
                {"speaker": "USER", "text": "The index attaches the first and second messages to this setting."},
                {"speaker": "USER", "text": f"The first message says: {first} The second message says: {second}"},
                {"speaker": "USER", "text": "The requested value is new."},
            ],
            evaluation_query="Choose KEEP, SUPERSEDE, or ABSTAIN.",
        )

    keep_record = record(
        first="The current official record lists old.",
        second="An informal note mentions new.",
    )
    supersede_record = record(
        first="A signed form confirms the setting changed to new.",
        second="The submission was recorded.",
    )
    abstain_record = record(
        first="The notice has no closing date.",
        second="There is no later instruction.",
    )
    assert public_evidence_policy_action(keep_record)[0] == "KEEP"
    assert public_evidence_policy_action(supersede_record)[0] == "SUPERSEDE"
    assert public_evidence_policy_action(abstain_record)[0] == "ABSTAIN"
    final_action, trace = apply_live_controller_guard(keep_record, "ABSTAIN")
    assert final_action == "KEEP"
    assert trace["overrode_model_abstention"] is True
    unchanged, unchanged_trace = apply_live_controller_guard(keep_record, "SUPERSEDE")
    assert unchanged == "SUPERSEDE"
    assert unchanged_trace["overrode_model_abstention"] is False
    assert_model_safe(trace)


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key, child in value.items()} | set().union(
            *(_keys(child) for child in value.values())
        )
    if isinstance(value, list):
        return set().union(*(_keys(child) for child in value)) if value else set()
    return set()


def test_rules_controller_uses_only_public_evidence() -> None:
    def record(*, standing: str, dialogue: list[dict[str, str]]) -> MGP6V43Record:
        return MGP6V43Record(
            public_id="MGP43-00000000000000000000",
            memory_before={"standing_value": standing},
            dialogue=dialogue,
            evaluation_query="Choose KEEP, SUPERSEDE, or ABSTAIN.",
        )

    supersede, supersede_trace = rules_controller_action(
        record(
            standing="declined",
            dialogue=[
                {"text": "The signed form records approved."},
                {"text": "The requested value is approved."},
            ],
        )
    )
    keep, keep_trace = rules_controller_action(
        record(
            standing="declined",
            dialogue=[{"text": "The requested value is declined."}],
        )
    )
    abstain, abstain_trace = rules_controller_action(
        record(
            standing="declined",
            dialogue=[
                {"text": "The note does not identify the relevant setting."},
                {"text": "The requested value is approved."},
            ],
        )
    )
    assert (supersede, keep, abstain) == ("SUPERSEDE", "KEEP", "ABSTAIN")
    for trace in (supersede_trace, keep_trace, abstain_trace):
        assert_model_safe(trace)
        assert not (set(_keys(trace)) & PROHIBITED_MODEL_KEYS)


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


def test_public_scorer_reports_public_metrics_without_component_map(tmp_path: Path, release) -> None:
    dev = release[1]
    prediction_path = tmp_path / "predictions.jsonl"
    prediction_path.write_text(
        "".join(
            json.dumps({"public_id": record.public_id, "action": "KEEP"}) + "\n"
            for record in dev
        ),
        encoding="utf-8",
    )
    result = score_public_run(dataset_path=PUBLIC / "dev.jsonl", prediction_path=prediction_path)
    assert result["n_items"] == 180
    assert result["coverage"] == 1.0
    assert result["component_cluster_bootstrap"]["available"] is False


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
    manifest = json.loads((tmp_path / "smoke/run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decoding"]["max_new_tokens"] == 128
    assert manifest["retry_policy"] == {"parse_max_attempts": 2, "transport_max_attempts": 3}
    assert manifest["adapter_version"] == "ask.mgp6_v43_adapter.v3"
    assert manifest["failure_count"] == 0
    assert manifest["invalid_response_count"] == 0
    raw_rows = [(json.loads(line)) for line in (tmp_path / "smoke/raw_responses.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["valid_action"] for row in raw_rows} == {True}
    rerun = subprocess.run([sys.executable, "scripts/run_mgp6_v43.py", "--limit", "2", "--action", "ABSTAIN", "--out", str(tmp_path / "smoke")], cwd=ROOT, capture_output=True, text=True, check=False)
    assert rerun.returncode == 0, rerun.stderr
    assert len((tmp_path / "smoke/raw_responses.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_v43_runner_supports_rule_and_registered_model_systems(tmp_path: Path) -> None:
    run = subprocess.run(
        [
            sys.executable,
            "scripts/run_mgp6_v43.py",
            "--system",
            "rules_controller",
            "--input",
            "benchmarks/mgp6/mgp6_v4_3/public/train.jsonl",
            "--limit",
            "2",
            "--out",
            str(tmp_path / "rules"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    manifest = json.loads((tmp_path / "rules/run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["provider"] == "local-rule"
    b1 = subprocess.run(
        [sys.executable, "scripts/run_mgp6_v43.py", "--system", "b1", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert b1.returncode == 0, b1.stderr


def test_v43_runner_openrouter_reasoning_extra_body() -> None:
    assert run_mgp6_v43._openrouter_reasoning_body(None) is None
    assert run_mgp6_v43._openrouter_reasoning_body("none") == {"reasoning": {"effort": "none"}}
