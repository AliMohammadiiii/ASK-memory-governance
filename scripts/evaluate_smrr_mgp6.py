"""Compute MGP-6 stale-active-memory diagnostics from completed run outputs.

MGP-6 has gold supersession state but no retrieval event stream. This script
therefore computes the stale rate over each prediction's active memory state:
an active predicted item is stale when its normalized text matches an initial
memory that the MGP-6 gold state no longer keeps active.
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
from ksa.eval.smrr import compute_smrr, mgp6_stale_items  # noqa: E402

SYSTEM_ALIASES = ("b1", "b2", "b3", "b4", "controller")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _active_items(memory_state: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in memory_state if item.get("status", "active") == "active"]


def _system_report(alias: str, run_root: Path, scenarios: dict[str, Any]) -> dict[str, Any]:
    predictions_path = run_root / alias / "predictions.jsonl"
    rows = _read_jsonl(predictions_path)
    scenario_rows = []
    stale_total = 0
    denominator_total = 0

    for row in rows:
        scenario = scenarios[row["scenario_id"]]
        result = compute_smrr(
            _active_items(row.get("memory_state") or []),
            mgp6_stale_items(scenario),
        )
        stale_total += result.stale_retrieval_count
        denominator_total += result.smrr_denominator
        scenario_rows.append(
            {
                "scenario_id": row["scenario_id"],
                "system": alias,
                "gold_action": row.get("gold_action"),
                "predicted_action": row.get("predicted_action"),
                "stale_active_count": result.stale_retrieval_count,
                "active_denominator": result.smrr_denominator,
                "stale_active_rate": result.smrr,
            }
        )

    return {
        "system": alias,
        "n_scenarios": len(rows),
        "stale_active_count": stale_total,
        "active_denominator": denominator_total,
        "stale_active_rate": None if denominator_total == 0 else stale_total / denominator_total,
        "scenario_rows": scenario_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mgp6", type=Path, default=Path("data/mgp6_v1_seed0.jsonl"))
    parser.add_argument("--run-root", type=Path, default=Path("runs/m4w14"))
    parser.add_argument("--out", type=Path, default=Path("runs/m4w14/smrr_report.json"))
    parser.add_argument("--csv", type=Path, default=Path("runs/m4w14/smrr_table.csv"))
    args = parser.parse_args()

    scenarios = {row.scenario_id: row for row in load_mgp6_jsonl(args.mgp6)}
    reports = [_system_report(alias, args.run_root, scenarios) for alias in SYSTEM_ALIASES]
    payload = {
        "metric": "MGP-6 stale-active-memory rate",
        "metric_note": (
            "MGP-6 has gold supersession state but no retrieval stream; denominator "
            "is active predicted memory items, not retrieved LongMemEval items."
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "mgp6": str(args.mgp6),
        "run_root": str(args.run_root),
        "systems": [
            {key: value for key, value in report.items() if key != "scenario_rows"}
            for report in reports
        ],
        "scenario_rows": [
            scenario_row
            for report in reports
            for scenario_row in report["scenario_rows"]
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    with args.csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "system",
                "n_scenarios",
                "stale_active_count",
                "active_denominator",
                "stale_active_rate",
            ],
        )
        writer.writeheader()
        for report in reports:
            writer.writerow({key: report[key] for key in writer.fieldnames})

    print(f"[smrr] wrote {args.out}")
    print(f"[smrr] wrote {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
