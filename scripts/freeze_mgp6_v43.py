#!/usr/bin/env python3
"""Freeze the selected MGP-6 v4.3 configuration without touching hidden data.

This command writes only tracked, label-free control artifacts.  It never opens
private hidden inputs or gold, and it does not generate predictions or scores.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from run_mgp6_v43 import DEFAULT_SYSTEM_PROMPTS, _hidden_run_controls  # noqa: E402

from ask.eval.mgp6_v43 import (  # noqa: E402
    ADAPTER_VERSION,
    canonical_json,
    sha256_file,
    sha256_value,
    system_allowed_actions,
)

RELEASE_FACTS_PATH = REPO / "benchmarks/mgp6/mgp6_v4_3/release_metadata/RELEASE_FACTS.json"
DEV_CONFIG_PATH = REPO / "configs/experiments/mgp6_v43/DEV_EXPERIMENTS.json"
FINAL_STATUS_PATH = REPO / "artifacts/mgp6_v43_integration/FINAL_STATUS.json"
DEFAULT_CONFIG_PATH = REPO / "experiments/mgp6_v43/FINAL_HIDDEN_CONFIG.json"
DEFAULT_AUTHORIZATION_PATH = REPO / "experiments/mgp6_v43/FINAL_HIDDEN_RUN_AUTHORIZATION.json"
PROHIBITED_KEYS = {
    "gold_action",
    "design_target",
    "source_item_id",
    "component_id",
    "private_item_id",
    "annotator_id",
    "final_consensus",
    "human_gold",
    "hidden_gold",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return value


def _git_output(*args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"git command failed: {' '.join(args)}") from exc


def _tracked_worktree_is_clean() -> bool:
    commands = (("diff", "--quiet"), ("diff", "--cached", "--quiet"))
    return all(
        subprocess.run(["git", "-C", str(REPO), *command], check=False).returncode == 0
        for command in commands
    )


def _current_ci_record(run_id: str, expected_head: str) -> dict[str, Any]:
    try:
        raw = subprocess.check_output(
            [
                "gh",
                "run",
                "view",
                run_id,
                "--json",
                "databaseId,headSha,conclusion,status,url,workflowName",
            ],
            cwd=REPO,
            text=True,
        )
        record = json.loads(raw)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot verify GitHub Actions run {run_id}") from exc
    if record.get("headSha") != expected_head:
        raise SystemExit("GitHub Actions run does not belong to the current commit")
    if record.get("status") != "completed" or record.get("conclusion") != "success":
        raise SystemExit("GitHub Actions run is not a completed success")
    return {
        "run_id": str(record["databaseId"]),
        "workflow": str(record["workflowName"]),
        "head_sha": str(record["headSha"]),
        "url": str(record["url"]),
    }


def _walk_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key in value} | set().union(
            *(_walk_keys(item) for item in value.values())
        )
    if isinstance(value, list):
        return set().union(*(_walk_keys(item) for item in value)) if value else set()
    return set()


def _assert_public_control_artifact(value: Any) -> None:
    prohibited = sorted(_walk_keys(value) & PROHIBITED_KEYS)
    if prohibited:
        raise SystemExit(f"freeze artifact contains prohibited private/label keys: {prohibited}")


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _selected_system(config: dict[str, Any]) -> dict[str, Any]:
    for system in config.get("systems", []):
        if isinstance(system, dict) and system.get("id") == "live_model_controller":
            return system
    raise SystemExit("development configuration does not register live_model_controller")


def build_freeze_artifacts(*, ci_run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a frozen config and authorization after validating public controls."""
    if not _tracked_worktree_is_clean():
        raise SystemExit("tracked worktree must be clean before configuration freeze")
    facts = _load_json(RELEASE_FACTS_PATH)
    development = _load_json(DEV_CONFIG_PATH)
    status = _load_json(FINAL_STATUS_PATH)
    head = _git_output("rev-parse", "HEAD")
    ci = _current_ci_record(ci_run_id, head)
    quality_gates = facts.get("quality_gates")
    if (
        not isinstance(quality_gates, dict)
        or quality_gates.get("failed_gates")
        or not all(value is True for key, value in quality_gates.items() if key != "failed_gates")
    ):
        raise SystemExit("release quality gates are not all passing")
    if facts.get("release_version") != development.get("release_version"):
        raise SystemExit("release version mismatch between facts and development configuration")
    if status.get("status") != "READY_FOR_CONFIG_FREEZE":
        raise SystemExit("repository is not at the configuration-freeze gate")
    for key in ("repository_tests", "repository_validation", "ruff", "mypy", "package_build"):
        if not str(status.get(key, "")).startswith("PASS"):
            raise SystemExit(f"required verification is not passing: {key}")
    selected = _selected_system(development)
    system = str(selected["id"])
    prompt_path = REPO / DEFAULT_SYSTEM_PROMPTS[system]
    system_prompt = prompt_path.read_text(encoding="utf-8")
    configured_prompt = development["prompt_templates"][system]
    if sha256_file(prompt_path) != configured_prompt["sha256"]:
        raise SystemExit("selected prompt bytes do not match the development registry")
    controls_config = development["controls"]
    adapter_spec = {
        "adapter_version": ADAPTER_VERSION,
        "system": system,
        "allowed_actions": system_allowed_actions(system),
        "recency_turns": 2,
    }
    prompt_hash = sha256_value({"system_prompt": system_prompt, "adapter": adapter_spec})
    environment_lock = {
        "python": sys.version,
        "pyproject_sha256": sha256_file(REPO / "pyproject.toml"),
    }
    runtime_controls = _hidden_run_controls(
        system=system,
        adapter_spec=adapter_spec,
        provider=str(selected["provider"]),
        model_id=str(selected["model_id"]),
        base_url=str(selected["base_url"]),
        prompt_hash=prompt_hash,
        system_prompt_hash=sha256_value(system_prompt),
        seed=int(controls_config["seed"]),
        decoding=dict(controls_config["decoding"]),
        retry_policy=dict(controls_config["retry_policy"]),
        timeout_s=float(controls_config["timeout_s"]),
        concurrency=int(controls_config["concurrency"]),
        environment_lock=environment_lock,
    )
    private_sentinels = (
        ".private/benchmarks/mgp6/v4.3/hidden_inputs/sentinel.jsonl",
        ".private/benchmarks/mgp6/v4.3/hidden_gold/sentinel.jsonl",
    )
    private_ignored = all(
        subprocess.run(
            ["git", "-C", str(REPO), "check-ignore", "-q", sentinel], check=False
        ).returncode
        == 0
        for sentinel in private_sentinels
    )
    if not private_ignored:
        raise SystemExit("private MGP-6 v4.3 boundary is not ignored")
    gate_results = {
        "release_quality_gates_pass": True,
        "repository_verification_pass": True,
        "remote_ci_pass": True,
        "tracked_worktree_clean": True,
        "private_boundary_ignored": True,
        "selected_public_dev_configuration_recorded": True,
        "all_frozen_controls_hashed": True,
    }
    frozen_config = {
        "schema_version": "mgp6-v4.3-final-hidden-config-1.0",
        "release_identity": "MGP-6 v4.3.0-human-validated-final",
        "status": "FROZEN_FOR_FINAL_HIDDEN_PREDICTION_GENERATION",
        "freeze_preparation_commit": head,
        "freeze_preparation_tracked_worktree": "clean",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "ci": ci,
        "release_facts": {
            "public_facts_sha256": sha256_file(RELEASE_FACTS_PATH),
            "item_count": facts["item_count"],
            "split_counts": facts["split_counts"],
            "split_component_counts": facts["split_component_counts"],
            "quality_gates": quality_gates,
        },
        "hidden_input_policy": {
            "expected_item_count": facts["split_counts"]["hidden"],
            "location": "ignored local private boundary; not named or hashed in this tracked artifact",
            "prediction_generation_must_not_open_hidden_gold": True,
        },
        "provider_route_limit": {
            "provider": selected["provider"],
            "base_url": selected["base_url"],
            "requested_model_id": selected["model_id"],
            "routed_model_revision": "unreported by provider metadata during public dev",
            "freeze_rule": "The requested model ID must match exactly; abort on any frozen-control mismatch.",
        },
        "hidden_run_controls": runtime_controls,
        "hidden_run_controls_sha256": sha256_value(runtime_controls),
        "gate_results": gate_results,
        "scoring_separation": "This config authorizes prediction generation only. Hash complete predictions before separate local-private scoring.",
    }
    _assert_public_control_artifact(frozen_config)
    authorization = {
        "schema_version": "mgp6-v4.3-final-hidden-authorization-1.0",
        "release_identity": frozen_config["release_identity"],
        "authorized": True,
        "authorization_scope": "One complete hidden prediction generation for the frozen controls; it does not authorize hidden-gold inspection during generation or scoring before predictions are complete and hashed.",
        "frozen_config_path": "experiments/mgp6_v43/FINAL_HIDDEN_CONFIG.json",
        "frozen_config_sha256": sha256_value(frozen_config),
        "hidden_run_controls": runtime_controls,
        "hidden_run_controls_sha256": sha256_value(runtime_controls),
        "gate_results": gate_results,
        "post_generation_requirement": "Close the model run, validate coverage, hash prediction files, then and only then use the local private scorer.",
    }
    _assert_public_control_artifact(authorization)
    return frozen_config, authorization


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ci-run-id", required=True, help="Completed successful GitHub Actions run for HEAD."
    )
    parser.add_argument("--out-config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--out-authorization", type=Path, default=DEFAULT_AUTHORIZATION_PATH)
    parser.add_argument(
        "--check", action="store_true", help="Validate gates without writing artifacts."
    )
    args = parser.parse_args()
    frozen_config, authorization = build_freeze_artifacts(ci_run_id=args.ci_run_id)
    if args.check:
        print(
            canonical_json(
                {"authorized": authorization["authorized"], "gates": authorization["gate_results"]}
            )
        )
        return 0
    _atomic_write_json(args.out_config, frozen_config)
    _atomic_write_json(args.out_authorization, authorization)
    print(f"wrote {args.out_config}")
    print(f"wrote {args.out_authorization}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
