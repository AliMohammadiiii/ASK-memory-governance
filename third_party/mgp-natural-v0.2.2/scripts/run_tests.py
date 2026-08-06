from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _totals(root: ET.Element) -> dict[str, int]:
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    return {
        "tests": sum(int(suite.attrib.get("tests", 0)) for suite in suites),
        "failures": sum(int(suite.attrib.get("failures", 0)) for suite in suites),
        "errors": sum(int(suite.attrib.get("errors", 0)) for suite in suites),
        "skipped": sum(int(suite.attrib.get("skipped", 0)) for suite in suites),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pytest and write a machine-readable summary")
    parser.add_argument("--xml", type=Path, default=Path("reports/pytest.xml"))
    parser.add_argument("--output", type=Path, default=Path("reports/pytest_results.json"))
    parser.add_argument("pytest_args", nargs="*")
    args = parser.parse_args()
    args.xml.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "pytest", "-q", f"--junitxml={args.xml}", *args.pytest_args]
    completed = subprocess.run(command, check=False)
    report: dict[str, object] = {
        "schema_version": "1.0",
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
        "python": platform.python_version(),
        "command": "python -m pytest -q --junitxml=reports/pytest.xml",
        "timing_note": "Runtime timing remains in the JUnit XML and is excluded from this deterministic claim artifact.",
        "warning_note": (
            "The tamper-detection test intentionally creates a duplicate ZIP member and can emit "
            "one zipfile warning."
        ),
    }
    if args.xml.exists():
        report.update(_totals(ET.parse(args.xml).getroot()))
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()

