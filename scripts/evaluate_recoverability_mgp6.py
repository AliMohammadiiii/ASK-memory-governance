"""Compute MGP-6 superseded-memory recoverability from completed run outputs.

This is the lineage/auditability metric for H2. Unlike SMRR (which ties the
controller and naive overwrite because both clear stale items from the active
set), recoverability separates them: lineage-preserving Supersede keeps the
prior as an inactive row with a ``supersedes_id`` edge (recoverable), while
destructive overwrite deletes it (not recoverable).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ksa.eval.mgp6_schema import load_mgp6_jsonl  # noqa: E402
from ksa.eval.recoverability import (  # noqa: E402
    aggregate_recoverability,
    recoverability_for_scenario,
)

SYSTEM_ALIASES = ("b1", "b2", "b3", "b4", "controller")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _system_report(alias: str, run_root: Path, prior_ids: dict[str, str]) -> dict[str, Any]:
    rows = _read_jsonl(run_root / alias / "predictions.jsonl")
    results = [
        recoverability_for_scenario(prior_ids[row["scenario_id"]], row.get("memory_state") or [])
        for row in rows
    ]
    summary = aggregate_recoverability(results)
    summary["system"] = alias
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mgp6", type=Path, default=Path("data/mgp6_v1_seed0.jsonl"))
    parser.add_argument("--run-root", type=Path, default=Path("runs/m4w14"))
    # Default the outputs INTO the run root so they sit beside the run they
    # describe and the promotion gate can find them. Passing --out/--csv still
    # overrides. (Previously these hardcoded runs/m4w14/, so a --run-root run
    # silently wrote its report to the wrong directory.)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args()
    if args.out is None:
        args.out = args.run_root / "recoverability_report.json"
    if args.csv is None:
        args.csv = args.run_root / "recoverability_table.csv"

    prior_ids = {
        scenario.scenario_id: scenario.initial_memory_state[0].id
        for scenario in load_mgp6_jsonl(args.mgp6)
    }
    systems = []
    for alias in SYSTEM_ALIASES:
        if (args.run_root / alias / "predictions.jsonl").exists():
            systems.append(_system_report(alias, args.run_root, prior_ids))

    payload = {
        "metric": "MGP-6 superseded-memory recoverability (H2 lineage auditability)",
        "generated_at": datetime.now(UTC).isoformat(),
        "mgp6": str(args.mgp6),
        "run_root": str(args.run_root),
        "systems": systems,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    with args.csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["system", "n_scenarios", "n_revisions", "n_recoverable", "superseded_recoverability"],
        )
        writer.writeheader()
        for report in systems:
            writer.writerow({key: report.get(key) for key in writer.fieldnames})

    print(f"[recoverability] wrote {args.out}")
    print(f"[recoverability] wrote {args.csv}")
    for report in systems:
        print(
            f"[recoverability] {report['system']:<11} "
            f"revisions={report['n_revisions']:<3} "
            f"recoverable={report['n_recoverable']:<3} "
            f"rate={report['superseded_recoverability']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
