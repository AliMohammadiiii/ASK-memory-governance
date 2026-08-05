from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from mgp_natural.errors import ValidationError
from mgp_natural.util.io import read_json, write_json


def _run(root: Path, report_path: Path) -> dict[str, object]:
    environment = {**os.environ, "PYTHONPATH": str(root / "src")}
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/build_artifacts.py"),
            "--root",
            str(root),
            "--output",
            str(report_path),
        ],
        cwd=root,
        env=environment,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if completed.returncode != 0:
        raise ValidationError(f"build repetition failed with code {completed.returncode}")
    return read_json(report_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify deterministic wheel and sdist hashes")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--build-report", type=Path, default=Path("reports/build_artifacts.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    build_report = args.build_report if args.build_report.is_absolute() else root / args.build_report
    first = _run(root, build_report)
    second = _run(root, build_report)
    first_manifest = first.get("artifacts", [])
    second_manifest = second.get("artifacts", [])
    passed = first_manifest == second_manifest
    report = {
        "schema_version": "1.0",
        "status": "PASS" if passed else "FAIL",
        "repetitions": 2,
        "source_date_epoch": second.get("source_date_epoch"),
        "first_artifacts": first_manifest,
        "second_artifacts": second_manifest,
        "deterministic_artifact_hashes": passed,
    }
    write_json(args.output, report)
    print(json.dumps(report, sort_keys=True))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

