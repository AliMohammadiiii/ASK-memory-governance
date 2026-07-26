#!/usr/bin/env python3
"""Run one optional external memory backend on public MGP-6 v4.3 records.

This is a public-development runner only.  It has no hidden-input or
hidden-gold option, sends no development labels to backends, and emits a
derived (not native) MGP-6 action from observable backend state.
"""

from __future__ import annotations

import argparse
import importlib
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
    MGP6V43Prediction,
    assert_model_safe,
    load_predictions_allow_partial,
    load_public_records,
    sha256_file,
    sha256_value,
    write_prediction_resume_safe,
)
from ask.eval.mgp6_v43_external import (  # noqa: E402
    EXTERNAL_DERIVATION_VERSION,
    EXTERNAL_MGP6V43_BACKENDS,
    run_external_record,
)

DEFAULT_INPUT = REPO_ROOT / "benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl"

_ADAPTER_IMPORTS = {
    "mem0": ("benchmarks.mgp6.external.run_mem0", "Mem0Adapter"),
    "graphiti": ("benchmarks.mgp6.external.run_graphiti", "GraphitiAdapter"),
    "letta": ("benchmarks.mgp6.external.run_letta", "LettaAdapter"),
    "memos": ("benchmarks.mgp6.external.run_memos", "MemOSAdapter"),
}


def _public_input(path: Path) -> Path:
    resolved = path.resolve()
    public_root = (REPO_ROOT / "benchmarks/mgp6/mgp6_v4_3/public").resolve()
    try:
        resolved.relative_to(public_root)
    except ValueError as exc:
        raise SystemExit(
            "external v4.3 runner accepts tracked public train/dev input only"
        ) from exc
    if resolved.name not in {"train.jsonl", "dev.jsonl"}:
        raise SystemExit("external v4.3 runner accepts only public train.jsonl or dev.jsonl")
    return resolved


def _git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _existing_prediction_ids(path: Path) -> set[str]:
    """Return completed IDs, treating a fresh output directory as empty."""
    if not path.exists():
        return set()
    return {row.public_id for row in load_predictions_allow_partial(path)}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _adapter(backend: str):
    module_name, class_name = _ADAPTER_IMPORTS[backend]
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise SystemExit(
            f"cannot import {backend} adapter ({exc}); install the pinned packages in "
            "benchmarks/mgp6/external/requirements-external.txt"
        ) from exc
    try:
        return getattr(module, class_name)()
    except ImportError as exc:
        raise SystemExit(
            f"{backend} dependencies are unavailable ({exc}); install the pinned packages in "
            "benchmarks/mgp6/external/requirements-external.txt and follow its service setup"
        ) from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, choices=EXTERNAL_MGP6V43_BACKENDS)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="maximum new records (0 = all)")
    parser.add_argument("--retrieval-k", type=int, default=5)
    parser.add_argument("--no-progress", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.limit < 0 or args.retrieval_k < 1:
        raise SystemExit("--limit must be non-negative and --retrieval-k must be positive")
    input_path = _public_input(args.input)
    out = args.out.resolve()
    records = load_public_records(input_path, require_gold=False)
    predictions_path = out / "predictions.jsonl"
    existing = _existing_prediction_ids(predictions_path)
    todo = [record for record in records if record.public_id not in existing]
    if args.limit:
        todo = todo[: args.limit]

    out.mkdir(parents=True, exist_ok=True)
    adapter = _adapter(args.backend)
    manifest = {
        "schema_version": "mgp6-v4.3-external-backend-run-v1",
        "release_version": "4.3.0-human-validated-final",
        "backend": args.backend,
        "input": str(input_path),
        "dataset_sha256": sha256_file(input_path),
        "derivation_version": EXTERNAL_DERIVATION_VERSION,
        "retrieval_k": args.retrieval_k,
        "code_commit": _git_commit(),
        "runner_sha256": sha256_file(Path(__file__)),
        "adapter_protocol_sha256": sha256_value(EXTERNAL_DERIVATION_VERSION),
        "public_data_only": True,
        "hidden_gold_accessed": False,
        "adapter_meta": adapter.meta(),
    }
    assert_model_safe(manifest)
    _write_json(out / "run_manifest.json", manifest)
    raw_path = out / "external_observations.jsonl"
    errors = 0
    progress = None
    if not args.no_progress and sys.stderr.isatty():
        try:
            from tqdm import tqdm

            progress = tqdm(total=len(todo), desc=f"MGP-6 v4.3 {args.backend}", unit="item")
        except ImportError:
            progress = None
    started = time.monotonic()
    try:
        for index, record in enumerate(todo, start=1):
            try:
                observation = run_external_record(adapter, record, retrieval_k=args.retrieval_k)
                assert_model_safe(observation)
                prediction = MGP6V43Prediction(
                    public_id=record.public_id, action=observation["derived_action"]
                )
                _append_jsonl(raw_path, observation)
                write_prediction_resume_safe(predictions_path, prediction)
            except (
                Exception
            ) as exc:  # Resume only records whose durable prediction was not written.
                errors += 1
                print(f"[{args.backend}] ERROR {record.public_id}: {exc}", file=sys.stderr)
            if progress is not None:
                progress.update(1)
            elif index % 10 == 0 or index == len(todo):
                elapsed = max(time.monotonic() - started, 0.001)
                rate = index / elapsed
                remaining = (len(todo) - index) / rate if rate else 0.0
                print(
                    f"[{args.backend}] {index}/{len(todo)} ({100 * index / len(todo):.1f}%) "
                    f"ETA {remaining:.0f}s"
                )
    finally:
        if progress is not None:
            progress.close()
        adapter.close()

    # An adapter may fail before producing its first durable prediction (for
    # example, when its Docker service is unavailable).  That is a legitimate
    # resumable state, so do not turn the useful per-item error report into a
    # secondary FileNotFoundError while computing the summary.
    completed = len(_existing_prediction_ids(predictions_path))
    print(
        f"[mgp6-v43-external] backend={args.backend} completed={completed}/{len(records)} errors={errors}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
