#!/usr/bin/env python3
"""Build a path-neutral inventory of tracked files and selected frozen evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "claims/source_inventory.json"

LOCAL_EVIDENCE = (
    ".private/benchmarks/mgp6/v4.3/hidden_gold/hidden_gold.jsonl",
    ".private/benchmarks/mgp6/v4.3/hidden_gold/scoring_contract.json",
    ".private/benchmarks/mgp6/v4.3/hidden_inputs/hidden_inputs.jsonl",
    "runs/mgp6_v43/final_hidden/live_model_controller_qwen35_9b/predictions.jsonl",
    "runs/mgp6_v43/final_hidden/live_model_controller_qwen35_9b/private_hidden_metrics.json",
    "runs/mgp6_v43/final_hidden/live_model_controller_qwen35_9b/run_manifest.json",
    "runs_local/lme_final_controller_v12_qwen_180/manifest.json",
    "runs_local/lme_final_controller_v12_qwen_180/controller/action_log.jsonl",
    "runs_local/lme_final_controller_v12_qwen_180/controller/judgments.jsonl",
    "runs_local/lme_final_controller_v12_qwen_180/controller/report.json",
    "runs_local/lme_final_controller_v12_qwen_180/b4/judgments.jsonl",
    "runs_local/lme_final_controller_v12_qwen_180/b4/report.json",
)

KNOWN_PROBLEMS = {
    "runs_local/lme_final_controller_v12_qwen_180/manifest.json": (
        "Historical manifest records resume attempts, status=running, exit_code=1, "
        "a stale launcher hash, and machine-local paths. Preserve unchanged."
    ),
    "runs_local/lme_final_controller_v12_qwen_180/controller/action_log.jsonl": (
        "Preserved V12 schema supports final-policy replay but lacks the canonical "
        "per-row configuration identity introduced later."
    ),
    ".private/benchmarks/mgp6/v4.3/hidden_gold/hidden_gold.jsonl": (
        "Consumed hidden labels. Never model-facing or public."
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tracked_files() -> list[str]:
    raw = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"])
    return sorted(
        item.decode("utf-8", errors="surrogateescape") for item in raw.split(b"\0") if item
    )


def versioned_or_candidate_files() -> list[str]:
    raw = subprocess.check_output(
        [
            "git",
            "-C",
            str(ROOT),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ]
    )
    return sorted(
        item.decode("utf-8", errors="surrogateescape") for item in raw.split(b"\0") if item
    )


def _visibility(relative: str) -> str:
    if relative.startswith(".private/"):
        return "private"
    if relative.startswith(("runs/", "runs_local/", "data/")):
        return "restricted"
    if "/annotations/human/human_independent_" in relative or relative.endswith(
        "human_vs_author_disagreements.csv"
    ):
        return "restricted"
    return "public_candidate"


def _model_facing(relative: str) -> bool:
    tokens = ("hidden_inputs", "/public/train.jsonl", "/public/dev.jsonl", "prompts/")
    return any(token in relative for token in tokens) and "hidden_gold" not in relative


def _consumed(relative: str) -> str:
    if (
        "final_hidden" in relative
        or "hidden_gold" in relative
        or "lme_final_controller_v12" in relative
    ):
        return "consumed"
    if "/dev" in relative or "development" in relative:
        return "development_consumed"
    return "not_applicable"


def _artifact_type(path: Path) -> str:
    if path.is_dir():
        return "git_submodule_or_directory"
    suffix = path.suffix.lower()
    return {
        ".py": "source_code",
        ".tex": "paper_source",
        ".bib": "bibliography",
        ".json": "json_artifact",
        ".jsonl": "jsonl_artifact",
        ".csv": "tabular_artifact",
        ".yaml": "configuration",
        ".yml": "configuration",
        ".md": "documentation",
        ".png": "figure",
        ".svg": "figure_source",
    }.get(suffix, "file")


def _generated_by(relative: str) -> str:
    if relative == "artifacts/analysis/lme_v12_scorecard_analysis.json":
        return "python scripts/analysis/analyze_lme_scorecard.py"
    if relative.startswith("paper/paper_1/tables/"):
        return "mixed: see claim ledger; drift verification required"
    if relative.startswith("paper/paper_1/figures/"):
        return "mixed: see claim ledger; drift verification required"
    if relative.startswith(("src/", "tests/", "scripts/", "docs/")):
        return "maintained source"
    return "unknown"


def build_inventory() -> dict[str, Any]:
    tracked = tracked_files()
    tracked_set = set(tracked)
    candidates = versioned_or_candidate_files()
    candidates.extend(relative for relative in LOCAL_EVIDENCE if relative not in tracked)
    rows: list[dict[str, Any]] = []
    for relative in sorted(candidates):
        path = ROOT / relative
        exists = path.exists()
        visibility = _visibility(relative)
        rows.append(
            {
                "logical_name": path.name,
                "relative_path": relative,
                "type": _artifact_type(path),
                "owner": "Ali Mohammadi/project"
                if not relative.startswith("runs_local/")
                else "project/provider run",
                "source": (
                    "git_tracked"
                    if relative in tracked_set
                    else "local_frozen_evidence"
                    if relative in LOCAL_EVIDENCE
                    else "working_tree_candidate"
                ),
                "generated_by": _generated_by(relative),
                "configuration_id": "unknown",
                "input_hashes": [],
                "output_sha256": sha256_file(path) if path.is_file() else None,
                "visibility": visibility,
                "model_facing": _model_facing(relative),
                "consumption_status": _consumed(relative),
                "referenced_by_paper": relative.startswith(("paper/", "artifacts/analysis/"))
                or relative in LOCAL_EVIDENCE,
                "reproducibility": (
                    "local_replay" if visibility in {"private", "restricted"} else "tracked_source"
                ),
                "known_problems": KNOWN_PROBLEMS.get(relative, ""),
                "exists": exists,
            }
        )
    return {
        "schema_version": "1.0",
        "repository_root": ".",
        "generator": "scripts/research/build_artifact_inventory.py",
        "tracked_file_count": len(tracked),
        "selected_local_evidence_count": len(LOCAL_EVIDENCE),
        "artifacts": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    inventory = build_inventory()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    missing = [row["relative_path"] for row in inventory["artifacts"] if not row["exists"]]
    print(
        json.dumps(
            {
                "output": output.relative_to(ROOT).as_posix(),
                "artifacts": len(inventory["artifacts"]),
                "missing_selected_evidence": missing,
            },
            sort_keys=True,
        )
    )
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
