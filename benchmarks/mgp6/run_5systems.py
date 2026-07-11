#!/usr/bin/env python3
"""Run all five MGP-6 v2 systems and score each with metrics_mgp6.

For every system this writes:
    <out>/<system>/predictions.jsonl   two-stage closed-book predictions
    <out>/<system>/report.json         metrics_mgp6 report (with bootstrap CIs)

Then an aggregate table is written to <out>/summary.json.

Usage:
    python3 run_5systems.py --gold data/mgp6_v2.jsonl --out runs/ref_5systems \
        --bootstrap 1000
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from systems.policies import SYSTEM_LABELS, SYSTEMS  # noqa: E402


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_predictions(system: str, scenarios: list[dict[str, Any]], out: Path) -> Path:
    predict = SYSTEMS[system]
    pred_path = out / "predictions.jsonl"
    out.mkdir(parents=True, exist_ok=True)
    with pred_path.open("w", encoding="utf-8") as handle:
        for scenario in scenarios:
            prediction = predict(scenario)
            prediction["scenario_id"] = scenario["scenario_id"]
            handle.write(json.dumps(prediction, ensure_ascii=False) + "\n")
    return pred_path


def score(gold: Path, pred: Path, bootstrap: int) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(HERE / "metrics_mgp6.py"),
        "--gold",
        str(gold),
        "--pred",
        str(pred),
        "--bootstrap",
        str(bootstrap),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"metrics failed for {pred}:\n{result.stderr}")
    return json.loads(result.stdout)


def _point(node: Any) -> Any:
    """Pull the point estimate out of a {value, ci95:[lo,hi]} node."""
    if isinstance(node, dict) and "value" in node:
        return node["value"]
    return node


HEADLINE = (
    "action_accuracy",
    "macro_f1",
    "abstention_precision",
    "abstention_recall",
    "artifact_semantic_accuracy",
    "lineage_correctness",
    "over_forgetting_rate",
    "under_forgetting_rate",
    "stale_retrieval_rate",
    "invalid_commit_rate",
    "duplicate_write_rate",
    "transient_contamination_rate",
    "fama_presence_absence_conjunction",
    "premise_resistance_rate",
    "implicit_application_accuracy",
    "cue_dependence_gap",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=HERE / "data" / "mgp6_v2.jsonl")
    parser.add_argument("--out", type=Path, default=HERE / "runs" / "ref_5systems")
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument(
        "--systems",
        default="controller,b4,b3,b2,b1",
        help="comma-separated system order",
    )
    args = parser.parse_args(argv)

    scenarios = load_scenarios(args.gold)
    order = [s.strip() for s in args.systems.split(",") if s.strip()]
    summary: dict[str, Any] = {
        "gold": str(args.gold),
        "n_scenarios": len(scenarios),
        "bootstrap": args.bootstrap,
        "systems": {},
    }

    for system in order:
        if system not in SYSTEMS:
            raise SystemExit(f"unknown system: {system}")
        sys_out = args.out / system
        print(f"[run] {system:11s} -> {sys_out}")
        pred_path = write_predictions(system, scenarios, sys_out)
        report = score(args.gold, pred_path, args.bootstrap)
        (sys_out / "report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
        full = report["full"]
        summary["systems"][system] = {
            "label": SYSTEM_LABELS[system],
            "headline": {k: _point(full.get(k)) for k in HEADLINE},
        }

    (args.out).mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"[done] summary -> {args.out / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
