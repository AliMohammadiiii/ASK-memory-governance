#!/usr/bin/env python3
"""Run a public MGP-6 v4.3 external backend in resumable process shards.

Each shard has its own native-memory adapter instance and output directory.
Only after every shard has complete, disjoint public-ID coverage are their
predictions and observations merged into the requested output directory.
This keeps a stopped run resumable without concurrent JSONL writers.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for import_root in (REPO_ROOT, REPO_ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from ask.eval.mgp6_v43 import (  # noqa: E402
    assert_model_safe,
    load_predictions_allow_partial,
    load_public_records,
    sha256_file,
    sha256_value,
)
from ask.eval.mgp6_v43_external import EXTERNAL_MGP6V43_BACKENDS  # noqa: E402
from scripts.run_mgp6_v43_external import DEFAULT_INPUT  # noqa: E402


def _write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _prediction_rows(path: Path) -> list[dict[str, str]]:
    return [
        {"public_id": prediction.public_id, "action": prediction.action}
        for prediction in load_predictions_allow_partial(path)
    ]


def _observation_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict) or not isinstance(value.get("public_id"), str):
                    raise ValueError(f"invalid observation row in {path}")
                assert_model_safe(value)
                rows.append(value)
    return rows


def merge_shards(*, input_path: Path, shards_root: Path, out: Path, shard_count: int) -> None:
    """Validate exact coverage before atomically publishing merged artifacts."""
    records = load_public_records(input_path, require_gold=False)
    expected_ids = {record.public_id for record in records}
    predictions: list[dict[str, str]] = []
    observations: list[dict[str, Any]] = []
    for index in range(shard_count):
        shard = shards_root / f"shard-{index:02d}"
        predictions.extend(_prediction_rows(shard / "predictions.jsonl"))
        observations.extend(_observation_rows(shard / "external_observations.jsonl"))

    prediction_ids = [row["public_id"] for row in predictions]
    observation_ids = [str(row["public_id"]) for row in observations]
    if len(set(prediction_ids)) != len(prediction_ids):
        raise ValueError("duplicate public IDs across prediction shards")
    if set(prediction_ids) != expected_ids:
        raise ValueError("shard predictions do not cover exactly the public input IDs")
    if len(set(observation_ids)) != len(observation_ids) or set(observation_ids) != expected_ids:
        raise ValueError("shard observations do not cover exactly the public input IDs")

    predictions.sort(key=lambda row: row["public_id"])
    observations.sort(key=lambda row: str(row["public_id"]))
    _write_jsonl_atomic(out / "predictions.jsonl", predictions)
    _write_jsonl_atomic(out / "external_observations.jsonl", observations)
    manifest = {
        "schema_version": "mgp6-v4.3-external-sharded-run-v1",
        "input": str(input_path),
        "dataset_sha256": sha256_file(input_path),
        "shard_count": shard_count,
        "merged_public_ids_sha256": sha256_value([row["public_id"] for row in predictions]),
        "prediction_count": len(predictions),
        "observation_count": len(observations),
        "public_data_only": True,
        "hidden_gold_accessed": False,
    }
    assert_model_safe(manifest)
    temporary = out / "run_manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(out / "run_manifest.json")


def _count_predictions(path: Path) -> int:
    return len(load_predictions_allow_partial(path)) if path.exists() else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, choices=EXTERNAL_MGP6V43_BACKENDS)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--retrieval-k", type=int, default=5)
    parser.add_argument("--no-progress", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 2 <= args.shards <= 8 or args.retrieval_k < 1:
        raise SystemExit("--shards must be between 2 and 8 and --retrieval-k must be positive")
    input_path = args.input.resolve()
    out = args.out.resolve()
    records = load_public_records(input_path, require_gold=False)
    out.mkdir(parents=True, exist_ok=True)
    shards_root = out / "_shards"
    logs_root = shards_root / "logs"
    logs_root.mkdir(parents=True, exist_ok=True)

    processes: list[subprocess.Popen[str]] = []
    handles = []
    for index in range(args.shards):
        shard_out = shards_root / f"shard-{index:02d}"
        command = [
            sys.executable,
            "scripts/run_mgp6_v43_external.py",
            "--backend",
            args.backend,
            "--input",
            str(input_path),
            "--out",
            str(shard_out),
            "--retrieval-k",
            str(args.retrieval_k),
            "--shard-count",
            str(args.shards),
            "--shard-index",
            str(index),
            "--no-progress",
        ]
        handle = (logs_root / f"shard-{index:02d}.log").open("a", encoding="utf-8")
        handles.append(handle)
        processes.append(
            subprocess.Popen(
                command, cwd=REPO_ROOT, stdout=handle, stderr=subprocess.STDOUT, text=True
            )
        )

    progress = None
    if not args.no_progress and sys.stderr.isatty():
        try:
            from tqdm import tqdm

            progress = tqdm(
                total=len(records), desc=f"MGP-6 v4.3 {args.backend} shards", unit="item"
            )
        except ImportError:
            pass
    seen = 0
    try:
        while any(process.poll() is None for process in processes):
            completed = sum(
                _count_predictions(shards_root / f"shard-{index:02d}" / "predictions.jsonl")
                for index in range(args.shards)
            )
            if progress is not None and completed > seen:
                progress.update(completed - seen)
            seen = completed
            time.sleep(1.0)
    finally:
        if progress is not None:
            progress.close()
        for handle in handles:
            handle.close()

    return_codes = [process.wait() for process in processes]
    if any(return_code != 0 for return_code in return_codes):
        raise SystemExit(f"one or more shards failed; resume from {shards_root}")
    merge_shards(input_path=input_path, shards_root=shards_root, out=out, shard_count=args.shards)
    print(
        f"[mgp6-v43-external-sharded] backend={args.backend} completed={len(records)}/{len(records)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
