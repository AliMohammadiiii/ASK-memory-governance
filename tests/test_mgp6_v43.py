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
    MGP6V43_RUNNABLE_SYSTEMS,
    MGP6V43_SUCCESSOR_SYSTEMS,
    MGP6V43_SYSTEMS,
    PROHIBITED_MODEL_KEYS,
    MGP6V43Error,
    MGP6V43Prediction,
    MGP6V43Record,
    adapter_version_for_system,
    apply_live_controller_guard,
    apply_successor_controller_guard,
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
    sha256_value,
    system_allowed_actions,
    validate_component_splits,
    validate_public_release,
    write_prediction_resume_safe,
)
from scripts import freeze_mgp6_v43, replay_mgp6_v43_successor_guard, run_mgp6_v43
from scripts.score_mgp6_v43 import score_public_run

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "benchmarks/mgp6/mgp6_v4_3/public"
FACTS = ROOT / "benchmarks/mgp6/mgp6_v4_3/release_metadata/RELEASE_FACTS.json"
DEV_CONFIG = ROOT / "configs/experiments/mgp6_v43/DEV_EXPERIMENTS.json"
FINAL_HIDDEN_CONFIG = ROOT / "experiments/mgp6_v43/FINAL_HIDDEN_CONFIG.json"
FINAL_HIDDEN_AUTHORIZATION = ROOT / "experiments/mgp6_v43/FINAL_HIDDEN_RUN_AUTHORIZATION.json"


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
    assert [row.public_id for row in train] == [
        row.public_id for row in load_public_records(PUBLIC / "train.jsonl")
    ]


def test_development_registry_covers_implemented_systems_and_prompt_hashes() -> None:
    config = json.loads(DEV_CONFIG.read_text(encoding="utf-8"))
    assert {entry["id"] for entry in config["systems"]} == set(MGP6V43_SYSTEMS)
    assert set(config["execution_contract"]["implemented_by_scripts_run_mgp6_v43"]) == set(
        MGP6V43_SYSTEMS
    )
    for entry in config["prompt_templates"].values():
        path = ROOT / entry["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]


def test_component_isolation_contract() -> None:
    component_to_split = {
        **{f"t{i}": "train" for i in range(20)},
        **{f"d{i}": "dev" for i in range(20)},
        **{f"h{i}": "hidden" for i in range(60)},
    }
    validate_component_splits(component_to_split)
    component_to_split["bad"] = "train"
    with pytest.raises(MGP6V43Error):
        validate_component_splits(component_to_split)


def test_model_input_prompt_and_logs_are_label_free(release) -> None:
    record = release[0][0]
    payload = record.model_input()
    assert not (set(payload) & PROHIBITED_MODEL_KEYS)
    assert "gold_action" not in build_decision_prompt(record, "system")
    for key in (
        "gold_action",
        "design_target",
        "source_item_id",
        "component_id",
        "private_item_id",
        "annotator_id",
        "final_consensus",
        "human_gold",
        "hidden_gold",
    ):
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
                {
                    "speaker": "USER",
                    "text": "The index attaches the first and second messages to this setting.",
                },
                {
                    "speaker": "USER",
                    "text": f"The first message says: {first} The second message says: {second}",
                },
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


def test_postfinal_successor_guard_is_public_only_and_not_a_hidden_retry() -> None:
    def record(*, first: str, second: str, standing: str = "old") -> MGP6V43Record:
        return MGP6V43Record(
            public_id="MGP43-00000000000000000000",
            memory_before={
                "memory_slot": "setting",
                "principal": "Ari",
                "standing_value": standing,
            },
            dialogue=[
                {
                    "speaker": "USER",
                    "text": "The index attaches the first and second messages to this setting.",
                },
                {
                    "speaker": "USER",
                    "text": f"The first message says: {first} The second message says: {second}",
                },
                {"speaker": "USER", "text": "The requested value is new."},
            ],
            evaluation_query="Choose KEEP, SUPERSEDE, or ABSTAIN.",
        )

    unresolved = record(
        first="The repair notice has no closing date.",
        second="There is no later work-location instruction.",
    )
    unmet_condition = record(
        first="The policy permits new after encryption is enabled.",
        second="Encryption is disabled, and the entry remains old.",
    )
    durable_change = record(
        first="Ari signed a recurring authorization that names new.",
        second="The authorization is stored with the current records.",
    )
    undecided = record(
        first="A colleague mentioned new.",
        second="The old record is not present in this excerpt.",
    )

    assert apply_successor_controller_guard(unresolved, "KEEP")[0] == "ABSTAIN"
    assert apply_successor_controller_guard(unmet_condition, "SUPERSEDE")[0] == "KEEP"
    assert apply_successor_controller_guard(durable_change, "KEEP")[0] == "SUPERSEDE"
    assert apply_successor_controller_guard(undecided, "ABSTAIN")[0] == "ABSTAIN"
    prior_guard_record = record(
        first="The current official record lists old.",
        second="An informal note mentions new.",
    )
    composed_action, composed_trace = apply_successor_controller_guard(
        prior_guard_record, "ABSTAIN"
    )
    assert composed_action == "KEEP"
    assert composed_trace["prior_guard_action"] == "KEEP"
    assert composed_trace["prior_guard_overrode_model_abstention"] is True
    assert MGP6V43_SUCCESSOR_SYSTEMS == ("successor_live_model_controller",)
    assert set(MGP6V43_RUNNABLE_SYSTEMS) == set(MGP6V43_SYSTEMS) | set(MGP6V43_SUCCESSOR_SYSTEMS)
    assert adapter_version_for_system("live_model_controller").endswith(".v3")
    assert adapter_version_for_system("successor_live_model_controller").endswith(
        ".v4-postfinal-dev"
    )
    assert_model_safe(model_input_for_system(unresolved, "successor_live_model_controller"))


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
    path.write_text(
        path.read_text(encoding="utf-8")
        + json.dumps({"public_id": "MGP43-FFFFFFFFFFFFFFFFFFFF", "action": "KEEP"})
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(MGP6V43Error, match="unknown"):
        load_predictions(path, ids)


def test_metric_correctness_and_cluster_bootstrap_reproducibility() -> None:
    gold = {"a": "KEEP", "b": "SUPERSEDE", "c": "ABSTAIN", "d": "KEEP"}
    predictions = {"a": "KEEP", "b": "KEEP", "c": "ABSTAIN", "d": "SUPERSEDE"}
    result = score_actions(gold, predictions)
    assert result["accuracy"] == 0.5
    assert result["confusion_matrix"]["SUPERSEDE"]["KEEP"] == 1
    component_map = {"a": "x", "b": "x", "c": "y", "d": "y"}
    assert cluster_bootstrap(
        gold, predictions, component_map, seed=7, replicates=100
    ) == cluster_bootstrap(gold, predictions, component_map, seed=7, replicates=100)


def test_public_scorer_reports_public_metrics_without_component_map(
    tmp_path: Path, release
) -> None:
    dev = release[1]
    prediction_path = tmp_path / "predictions.jsonl"
    prediction_path.write_text(
        "".join(
            json.dumps({"public_id": record.public_id, "action": "KEEP"}) + "\n" for record in dev
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


def test_public_resume_allows_only_provenance_commit_change_with_same_runtime() -> None:
    current = {
        "release_version": "4.3.0-human-validated-final",
        "dataset_sha256": "dataset",
        "system": "b1",
        "adapter_spec_hash": "adapter",
        "provider": "openrouter",
        "model_id": "qwen/qwen3.5-9b",
        "prompt_hash": "prompt",
        "seed": 4301,
        "n_selected": 180,
        "runtime_hashes": {"runner": "current", "evaluator_and_adapters": "evaluator"},
        "run_config": {"code_commit": "new", "timeout_s": 120.0, "seed": 4301},
    }
    previous = {
        **current,
        "runtime_hashes": {
            "runner": next(iter(run_mgp6_v43.PUBLIC_RESUME_COMPATIBLE_PREDECESSOR_RUNNER_HASHES)),
            "evaluator_and_adapters": "evaluator",
        },
        "run_config": {**current["run_config"], "code_commit": "old"},
    }
    event = run_mgp6_v43._resume_provenance_if_compatible(previous, current, hidden_input=False)
    assert event == {
        "previous_code_commit": "old",
        "current_code_commit": "new",
        "reason": "public_resume_with_audited_predecessor_runner",
    }
    with pytest.raises(SystemExit, match="hidden input"):
        run_mgp6_v43._resume_provenance_if_compatible(previous, current, hidden_input=True)
    unknown_runner = {
        **previous,
        "runtime_hashes": {"runner": "unknown", "evaluator_and_adapters": "evaluator"},
    }
    with pytest.raises(SystemExit, match="runtime hashes"):
        run_mgp6_v43._resume_provenance_if_compatible(unknown_runner, current, hidden_input=False)


def test_v43_runner_dry_run_and_engineering_fixture(tmp_path: Path) -> None:
    dry_run = subprocess.run(
        [sys.executable, "scripts/run_mgp6_v43.py", "--limit", "2", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert dry_run.returncode == 0, dry_run.stderr
    run = subprocess.run(
        [
            sys.executable,
            "scripts/run_mgp6_v43.py",
            "--limit",
            "2",
            "--action",
            "ABSTAIN",
            "--out",
            str(tmp_path / "smoke"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert len((tmp_path / "smoke/predictions.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    manifest = json.loads((tmp_path / "smoke/run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decoding"]["max_new_tokens"] == 128
    assert manifest["retry_policy"] == {"parse_max_attempts": 2, "transport_max_attempts": 3}
    assert manifest["adapter_version"] == "ask.mgp6_v43_adapter.v3"
    assert manifest["run_config_hash"] == sha256_value(manifest["run_config"])
    assert manifest["failure_count"] == 0
    assert manifest["invalid_response_count"] == 0
    raw_rows = [
        (json.loads(line))
        for line in (tmp_path / "smoke/raw_responses.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert {row["valid_action"] for row in raw_rows} == {True}
    rerun = subprocess.run(
        [
            sys.executable,
            "scripts/run_mgp6_v43.py",
            "--limit",
            "2",
            "--action",
            "ABSTAIN",
            "--out",
            str(tmp_path / "smoke"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rerun.returncode == 0, rerun.stderr
    assert (
        len((tmp_path / "smoke/raw_responses.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    )


def test_v43_runner_rejects_unimplemented_in_process_concurrency() -> None:
    run = subprocess.run(
        [sys.executable, "scripts/run_mgp6_v43.py", "--concurrency", "2", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode != 0
    assert "not implemented" in run.stderr


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
    successor = subprocess.run(
        [
            sys.executable,
            "scripts/run_mgp6_v43.py",
            "--system",
            "successor_live_model_controller",
            "--dry-run",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert successor.returncode == 0, successor.stderr


def test_postfinal_successor_runner_rejects_hidden_input(tmp_path: Path) -> None:
    run = subprocess.run(
        [
            sys.executable,
            "scripts/run_mgp6_v43.py",
            "--system",
            "successor_live_model_controller",
            "--hidden-input",
            "--input",
            ".private/benchmarks/mgp6/v4.3/hidden_inputs/never-read.jsonl",
            "--out",
            str(tmp_path / "never-created"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode != 0
    assert "restricted to public train/dev" in run.stderr
    assert not (tmp_path / "never-created").exists()


def test_successor_guard_replay_rejects_nonpublic_input_before_read(tmp_path: Path) -> None:
    private_input = ROOT / ".private/benchmarks/mgp6/v4.3/hidden_inputs/never-read.jsonl"
    assert replay_mgp6_v43_successor_guard._path_is_within(
        PUBLIC / "dev.jsonl", replay_mgp6_v43_successor_guard.PUBLIC_DATA_ROOT
    )
    assert not replay_mgp6_v43_successor_guard._path_is_within(
        private_input, replay_mgp6_v43_successor_guard.PUBLIC_DATA_ROOT
    )
    run = subprocess.run(
        [
            sys.executable,
            "scripts/replay_mgp6_v43_successor_guard.py",
            "--input",
            str(private_input),
            "--raw-responses",
            str(tmp_path / "never-read-raw.jsonl"),
            "--source-manifest",
            str(tmp_path / "never-read-manifest.json"),
            "--out",
            str(tmp_path / "never-created"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode != 0
    assert "must be a tracked public train/dev file" in run.stderr
    assert not (tmp_path / "never-created").exists()


def test_v43_runner_openrouter_reasoning_extra_body() -> None:
    assert run_mgp6_v43._openrouter_reasoning_body(None) is None
    assert run_mgp6_v43._openrouter_reasoning_body("none") == {"reasoning": {"effort": "none"}}


def test_hidden_run_authorization_binds_every_runtime_control(tmp_path: Path) -> None:
    adapter_spec = {
        "adapter_version": "ask.mgp6_v43_adapter.v3",
        "system": "live_model_controller",
        "allowed_actions": ("KEEP", "SUPERSEDE", "ABSTAIN"),
        "recency_turns": 2,
    }
    controls = run_mgp6_v43._hidden_run_controls(
        system="live_model_controller",
        adapter_spec=adapter_spec,
        provider="openrouter",
        model_id="qwen/qwen3.5-9b",
        base_url="https://openrouter.ai/api/v1",
        prompt_hash="prompt",
        system_prompt_hash="system",
        seed=4301,
        decoding={"temperature": 0.0, "max_new_tokens": 128, "reasoning_effort": "none"},
        retry_policy={"transport_max_attempts": 3, "parse_max_attempts": 2},
        timeout_s=120.0,
        concurrency=1,
        environment_lock={"python": "test", "pyproject_sha256": "lock"},
    )
    authorization_path = tmp_path / "authorization.json"
    authorization_path.write_text(
        json.dumps(
            {
                "authorized": True,
                "hidden_run_controls": controls,
                "hidden_run_controls_sha256": sha256_value(controls),
            }
        ),
        encoding="utf-8",
    )
    run_mgp6_v43._require_hidden_run_authorization(authorization_path, controls)
    changed = {**controls, "model_id": "different-model"}
    with pytest.raises(SystemExit, match="do not match"):
        run_mgp6_v43._require_hidden_run_authorization(authorization_path, changed)


def test_freeze_artifacts_reject_private_or_label_keys() -> None:
    with pytest.raises(SystemExit, match="prohibited"):
        freeze_mgp6_v43._assert_public_control_artifact({"hidden_gold": "forbidden"})


def test_final_hidden_freeze_artifacts_are_authorized_and_label_free() -> None:
    config = json.loads(FINAL_HIDDEN_CONFIG.read_text(encoding="utf-8"))
    authorization = json.loads(FINAL_HIDDEN_AUTHORIZATION.read_text(encoding="utf-8"))
    freeze_mgp6_v43._assert_public_control_artifact(config)
    freeze_mgp6_v43._assert_public_control_artifact(authorization)
    assert config["status"] == "FROZEN_FOR_FINAL_HIDDEN_PREDICTION_GENERATION"
    assert config["freeze_preparation_commit"] == config["ci"]["head_sha"]
    assert config["hidden_input_policy"]["expected_item_count"] == 540
    assert authorization["authorized"] is True
    assert authorization["hidden_run_controls"] == config["hidden_run_controls"]
    assert authorization["hidden_run_controls_sha256"] == sha256_value(
        config["hidden_run_controls"]
    )
    assert authorization["frozen_config_sha256"] == sha256_value(config)
