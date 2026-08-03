#!/usr/bin/env python3
"""Check declared public/private boundaries without granting legal approval."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "release/PUBLIC_PRIVATE_MATRIX.csv"
BLOCKERS = ROOT / "reports/LICENSE_BLOCKERS.json"


def main() -> int:
    rows = list(csv.DictReader(MATRIX.read_text(encoding="utf-8").splitlines()))
    problems = []
    for index, row in enumerate(rows, start=2):
        if not all(row.values()):
            problems.append(f"matrix row {index} has an empty field")
        path = row["path_or_class"]
        if path.startswith((".private/", "runs/", "runs_local/", "data/external/")):
            if row["public_action"] != "exclude":
                problems.append(f"private class is not excluded: {path}")
    blocker_report = json.loads(BLOCKERS.read_text(encoding="utf-8"))
    if blocker_report.get("status") != "BLOCKED_HUMAN_LEGAL_DECISION":
        problems.append("legal blocker status was unexpectedly cleared")
    report = {
        "status": "PASS_BOUNDARY_DECLARATION" if not problems else "FAIL",
        "legal_clearance": False,
        "matrix_rows": len(rows),
        "problems": problems,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
