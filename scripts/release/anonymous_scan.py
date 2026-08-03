#!/usr/bin/env python3
"""Scan a manuscript tree for common double-blind identity leaks."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

TEXT_SUFFIXES = {".bib", ".md", ".tex", ".txt", ".yaml", ".yml", ".json"}
PATTERNS = {
    "author_name": re.compile(r"\bAli\s+Mohammadi\b", re.IGNORECASE),
    "email": re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE),
    "local_path": re.compile(r"/(?:Users|home)/[^\s{}]+"),
    "non_anonymous_author": re.compile(r"\\author\{(?!Anonymous)", re.IGNORECASE),
}


def scan(root: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            for category, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(
                        {
                            "file": path.relative_to(root).as_posix(),
                            "line": line_number,
                            "category": category,
                        }
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("paper/paper_1"))
    parser.add_argument("--out", type=Path, default=Path("reports/anonymous_scan.json"))
    args = parser.parse_args()
    findings = scan(args.root)
    report = {
        "schema_version": "1.0",
        "scanned_at": datetime.now(UTC).isoformat(),
        "root": args.root.as_posix(),
        "status": "PASS" if not findings else "FAIL",
        "limitations": [
            "source-text scan only; final PDF metadata and rendered visual inspection are still required"
        ],
        "findings": findings,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report["status"])
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
