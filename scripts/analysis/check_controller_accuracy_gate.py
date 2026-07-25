#!/usr/bin/env python3
"""Verify the controller's explicit final-accuracy acceptance gate.

The frozen wrapper invokes this only after answer generation, judging, and the
homogeneity check. It reads completed artifacts and cannot change predictions or
judgments.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            rows.append(value)
    return rows


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def evaluate_gate(
    run_root: Path,
    *,
    expected_n: int = 180,
    threshold: float = 0.85,
) -> dict[str, Any]:
    if expected_n <= 0:
        raise ValueError("expected_n must be positive")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")

    controller_dir = run_root / "controller"
    judgments_path = controller_dir / "judgments.jsonl"
    report_path = controller_dir / "report.json"
    if not judgments_path.is_file():
        raise ValueError(f"missing controller judgments: {judgments_path}")
    if not report_path.is_file():
        raise ValueError(f"missing controller report: {report_path}")

    rows = _read_jsonl(judgments_path)
    if len(rows) != expected_n:
        raise ValueError(f"controller judgments contain {len(rows)} rows; expected {expected_n}")

    session_ids = [str(row.get("session_id") or "") for row in rows]
    if not all(session_ids):
        raise ValueError("one or more judgments have an empty session_id")
    if len(session_ids) != len(set(session_ids)):
        raise ValueError("controller judgments contain duplicate session_id values")
    if any(not isinstance(row.get("correct"), bool) for row in rows):
        raise ValueError("every judgment must contain a boolean correct field")

    correct = sum(row["correct"] for row in rows)
    accuracy = correct / expected_n
    required_correct = math.ceil((threshold * expected_n) - 1e-12)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("controller report must be a JSON object")
    report_n = report.get("n_sessions")
    report_accuracy = report.get("overall_accuracy")
    if report_n != expected_n:
        raise ValueError(f"report n_sessions is {report_n!r}; expected {expected_n}")
    if not isinstance(report_accuracy, (int, float)):
        raise ValueError("report overall_accuracy must be numeric")
    if not math.isclose(float(report_accuracy), accuracy, abs_tol=1e-12):
        raise ValueError(
            f"report/judgment accuracy mismatch: report={report_accuracy!r}, judgments={accuracy!r}"
        )

    competency_totals = Counter(str(row.get("competency") or "unknown") for row in rows)
    competency_correct = Counter(
        str(row.get("competency") or "unknown") for row in rows if row["correct"]
    )
    by_competency = []
    for competency in sorted(competency_totals):
        total = competency_totals[competency]
        competency_n_correct = competency_correct[competency]
        by_competency.append(
            {
                "accuracy": competency_n_correct / total,
                "competency": competency,
                "correct": competency_n_correct,
                "n": total,
            }
        )

    passed = correct >= required_correct
    return {
        "accuracy": accuracy,
        "authoritative_sources": {
            "judgments": str(judgments_path),
            "report": str(report_path),
        },
        "by_competency": by_competency,
        "correct": correct,
        "expected_n": expected_n,
        "generated_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "margin_correct": correct - required_correct,
        "passed": passed,
        "report_consistent": True,
        "required_correct": required_correct,
        "run": run_root.name,
        "status": "passed" if passed else "below_target",
        "threshold": threshold,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--expected-n", type=int, default=180)
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument(
        "--out",
        type=Path,
        help="Output JSON path (default: <run-root>/controller_accuracy_gate.json)",
    )
    args = parser.parse_args(argv)
    output_path = args.out or args.run_root / "controller_accuracy_gate.json"

    try:
        payload = evaluate_gate(
            args.run_root,
            expected_n=args.expected_n,
            threshold=args.threshold,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {
            "error": str(exc),
            "expected_n": args.expected_n,
            "generated_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "passed": False,
            "run": args.run_root.name,
            "status": "error",
            "threshold": args.threshold,
        }
        try:
            _atomic_write_json(output_path, payload)
        except OSError as write_exc:
            print(
                f"[controller-accuracy-gate] ERROR writing {output_path}: {write_exc}",
                file=sys.stderr,
            )
        print(f"[controller-accuracy-gate] ERROR: {exc}", file=sys.stderr)
        return 2

    _atomic_write_json(output_path, payload)
    verdict = "PASS" if payload["passed"] else "FAIL"
    print(
        f"[controller-accuracy-gate] {verdict}: "
        f"{payload['correct']}/{payload['expected_n']} "
        f"({payload['accuracy']:.2%}); required >= {payload['required_correct']} "
        f"({payload['threshold']:.2%})"
    )
    print(f"[controller-accuracy-gate] wrote {output_path}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
