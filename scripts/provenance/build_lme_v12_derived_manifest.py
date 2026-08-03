#!/usr/bin/env python3
"""Create a non-revisionist derived provenance manifest for LongMemEval V12."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "runs_local/lme_final_controller_v12_qwen_180/manifest.json"
DEFAULT_OUTPUT = ROOT / "artifacts/manifests/lme_v12_derived_manifest.json"
RUN_ROOT = ROOT / "runs_local/lme_final_controller_v12_qwen_180"
OUTPUTS = (
    "controller/action_log.jsonl",
    "controller/judgments.jsonl",
    "controller/report.json",
    "b4/judgments.jsonl",
    "b4/report.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(timestamp: str | None = None) -> dict[str, Any]:
    created = timestamp or datetime.now(UTC).isoformat()
    if not PARENT.is_file():
        raise FileNotFoundError(PARENT)
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    output_hashes = {
        relative: sha256_file(RUN_ROOT / relative)
        for relative in OUTPUTS
        if (RUN_ROOT / relative).is_file()
    }
    missing = sorted(set(OUTPUTS) - output_hashes.keys())
    return {
        "schema_version": "ask-run-derived-manifest/v1",
        "run_id": "lme_final_controller_v12_qwen_180",
        "parent_run_id": parent.get("run_id"),
        "parent_manifest_path": "runs_local/lme_final_controller_v12_qwen_180/manifest.json",
        "parent_manifest_sha256": sha256_file(PARENT),
        "derived_at": created,
        "derivation": "post-hoc provenance audit; does not alter or finalize the historical manifest",
        "historical_status": parent.get("status"),
        "historical_exit_code": parent.get("exit_code"),
        "resume_history": parent.get("attempts", []),
        "dataset_hashes": {
            "full_source_sha256": parent.get("full_source_sha256"),
            "slice_sha256": parent.get("slice_sha256"),
            "evaluated_session_ids_sha256": parent.get("evaluated_session_ids_sha256"),
        },
        "configuration": {
            "freeze_version": parent.get("freeze_version"),
            "config_sha256": parent.get("config_sha256"),
            "prompt_bundle_sha256": parent.get("prompt_bundle_sha256"),
            "main_model": parent.get("main_model"),
            "judge_primary": parent.get("judge_primary"),
            "seed": parent.get("seed"),
            "shards": parent.get("shards"),
            "retry_policy": parent.get("retry_policy"),
        },
        "code_identity": {
            "git_head": parent.get("git_head"),
            "git_dirty_at_start": parent.get("git_dirty_at_start"),
            "historical_code_and_protocol_sha256": parent.get("code_and_protocol_sha256"),
        },
        "output_sha256": output_hashes,
        "missing_expected_outputs": missing,
        "authorization": {
            "paid_execution": "historical; no new execution authorized by this derived audit",
            "hidden_consumption": "not_applicable_longmemeval_slice",
        },
        "known_anomalies": [
            "The historical manifest records status=running after the completed stored outputs.",
            "The historical manifest records exit_code=1 and failed_at_utc.",
            "The run resumed multiple times and was not cleanly finalized after resume.",
            "At least one launcher hash is stale relative to later repository source.",
            "Historical path fields contain machine-local absolute paths.",
            "Historical wall-clock fields describe resumed invocations and are not a clean full-run duration.",
        ],
        "repair_scope": {
            "repaired": [
                "current output hashes",
                "path-neutral output identities",
                "explicit anomaly ledger",
            ],
            "not_repairable_retrospectively": [
                "historical launcher integrity",
                "clean start-to-finish environment identity",
                "original manifest finalization",
                "uninterrupted wall-clock duration",
            ],
        },
        "status": "DERIVED_AUDIT_ONLY",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    manifest = build()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": output.relative_to(ROOT).as_posix(), "status": manifest["status"]}))
    return 1 if manifest["missing_expected_outputs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
