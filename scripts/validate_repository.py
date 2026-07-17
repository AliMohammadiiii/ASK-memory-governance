#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = [
    re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{24,}"),
]
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".sh",
    ".csv",
    ".tsv",
    ".bib",
    ".tex",
}

errors: list[str] = []
try:
    if not (ROOT / ".git").exists():
        raise FileNotFoundError
    listed = subprocess.check_output(
        [
            "git",
            "-C",
            str(ROOT),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        stderr=subprocess.DEVNULL,
    )
    candidate_paths = [
        ROOT / raw.decode("utf-8", errors="surrogateescape") for raw in listed.split(b"\0") if raw
    ]
except (OSError, subprocess.CalledProcessError):
    candidate_paths = [path for path in ROOT.rglob("*") if path.is_file()]

for path in candidate_paths:
    if not path.is_file():
        continue
    rel = path.relative_to(ROOT)
    if path.is_file() and (".bak" in path.name or path.name == ".DS_Store"):
        errors.append(f"repository pollution: {rel}")
    if path.suffix.lower() in TEXT_SUFFIXES and path.stat().st_size < 8_000_000:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible embedded secret: {rel}")
if not (ROOT / "src/ksa").is_dir():
    errors.append("missing src/ksa")
if not (ROOT / "benchmarks/mgp6/data/mgp6_v2.jsonl").is_file():
    errors.append("missing MGP-6 v2 data")
if errors:
    print("Repository validation failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)
print("Repository structure and secret scan: OK")
