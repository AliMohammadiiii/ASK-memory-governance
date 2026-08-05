#!/usr/bin/env python3
"""Strictly score future MGP-Natural predictions with release-status guards."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ask.confirmation.mgpn_scoring import score_predictions


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise SystemExit(f"{path}:{line_number}: expected a JSON object")
        rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=path.name + ".",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as handle:
        handle.write(payload)
        temporary_path = Path(handle.name)
    try:
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-provisional-smoke", action="store_true")
    parser.add_argument("--held-out-split-valid", action="store_true")
    parser.add_argument("--independent-component-count", type=int, default=0)
    args = parser.parse_args()

    result = score_predictions(
        _jsonl(args.gold),
        _jsonl(args.predictions),
        allow_provisional_smoke=args.allow_provisional_smoke,
        held_out_split_valid=args.held_out_split_valid,
        independent_component_count=args.independent_component_count,
    )
    result["input_sha256"] = {
        "gold": _sha256(args.gold),
        "predictions": _sha256(args.predictions),
        "scorer": _sha256(Path(__file__).resolve()),
    }
    _atomic_write(args.output, json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
