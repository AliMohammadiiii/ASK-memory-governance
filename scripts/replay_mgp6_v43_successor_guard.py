"""Reapply the public-only successor guard to a completed model-response run.

This utility exists for development-time adapter fixes. It accepts only a
public labelled train/dev JSONL file, validates exact response coverage, and
never reads hidden input or private gold.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ask.eval.mgp6_v43 import (  # noqa: E402
    MGP6V43Error,
    MGP6V43Prediction,
    apply_successor_controller_guard,
    canonical_json,
    load_predictions,
    load_public_records,
    sha256_file,
    write_prediction_resume_safe,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DATA_ROOT = REPO_ROOT / "benchmarks/mgp6/mgp6_v4_3/public"
SUCCESSOR_RUN_ROOT = REPO_ROOT / "runs/mgp6_v43/postfinal_successor"


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _load_model_actions(path: Path) -> tuple[dict[str, str], dict[str, int]]:
    actions: dict[str, str] = {}
    invalid_rows = 0
    total_rows = 0
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        total_rows += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MGP6V43Error(f"{path}:{line_no}: invalid raw-response JSON") from exc
        if not row.get("valid_action"):
            invalid_rows += 1
            continue
        public_id = row.get("public_id")
        model_action = row.get("model_action")
        prediction = MGP6V43Prediction.model_validate(
            {"public_id": public_id, "action": model_action}
        )
        if prediction.public_id in actions:
            raise MGP6V43Error(
                f"{path}:{line_no}: duplicate valid model action for {prediction.public_id}"
            )
        actions[prediction.public_id] = prediction.action
    return actions, {"total_rows": total_rows, "invalid_rows": invalid_rows}


def _git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _tracked_worktree_state() -> str:
    unstaged = subprocess.run(["git", "diff", "--quiet"], check=False).returncode != 0
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], check=False).returncode != 0
    return "dirty" if unstaged or staged else "clean"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--raw-responses", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not _path_is_within(args.input, PUBLIC_DATA_ROOT):
        raise SystemExit("successor replay input must be a tracked public train/dev file")
    if not _path_is_within(args.out, SUCCESSOR_RUN_ROOT):
        raise SystemExit(
            "successor replay output must be beneath runs/mgp6_v43/postfinal_successor"
        )

    records = load_public_records(args.input, require_gold=True)
    model_actions, response_counts = _load_model_actions(args.raw_responses)
    expected_ids = {record.public_id for record in records}
    if set(model_actions) != expected_ids:
        unknown = sorted(set(model_actions) - expected_ids)
        missing = sorted(expected_ids - set(model_actions))
        raise MGP6V43Error(
            f"raw-response coverage mismatch: unknown={unknown[:10]} missing={missing[:10]}"
        )

    source_manifest: dict[str, Any] = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    if source_manifest.get("complete") is not True:
        raise MGP6V43Error("source model run is not complete")
    if source_manifest.get("hidden_gold_accessed") is not False:
        raise MGP6V43Error("source model run is not a public-only generation run")
    if source_manifest.get("dataset_sha256") != sha256_file(args.input):
        raise MGP6V43Error("source manifest dataset hash does not match public input")
    if source_manifest.get("model_id") != "qwen/qwen3.5-9b":
        raise MGP6V43Error("source model ID is not the registered successor model")
    if source_manifest.get("system") != "successor_live_model_controller":
        raise MGP6V43Error("source manifest is not a successor controller run")

    predictions_path = args.out / "predictions.jsonl"
    rule_counts: Counter[str] = Counter()
    changed = 0
    for record in records:
        model_action = model_actions[record.public_id]
        action, trace = apply_successor_controller_guard(record, model_action)
        rule_counts[str(trace["rule"])] += 1
        changed += action != model_action
        write_prediction_resume_safe(
            predictions_path,
            MGP6V43Prediction(public_id=record.public_id, action=action),
        )

    load_predictions(predictions_path, expected_ids)
    manifest = {
        "schema_version": "mgp6-v4.3-successor-guard-replay-1.0",
        "complete": True,
        "public_development_only": True,
        "hidden_gold_accessed": False,
        "dataset_path": str(args.input),
        "dataset_sha256": sha256_file(args.input),
        "source_raw_responses_path": str(args.raw_responses),
        "source_raw_responses_sha256": sha256_file(args.raw_responses),
        "source_manifest_path": str(args.source_manifest),
        "source_manifest_sha256": sha256_file(args.source_manifest),
        "source_model_id": source_manifest["model_id"],
        "source_prompt_hash": source_manifest["prompt_hash"],
        "adapter_version": "ask.mgp6_v43_adapter.v4-postfinal-dev",
        "code_commit": _git_commit(),
        "tracked_worktree_state": _tracked_worktree_state(),
        "prediction_count": len(records),
        "prediction_sha256": sha256_file(predictions_path),
        "model_action_changes": changed,
        "raw_response_counts": response_counts,
        "guard_rule_counts": dict(sorted(rule_counts.items())),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        canonical_json(
            {
                "prediction_count": len(records),
                "prediction_sha256": manifest["prediction_sha256"],
                "model_action_changes": changed,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
