#!/usr/bin/env python3
"""Reject strong AI-output leakage and report weak style-signal density."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {".j2", ".md", ".rst", ".tex", ".txt"}
EXCLUDED_PREFIXES = (
    "artifacts/",
    "docs/history/",
    "docs/research/MASTER_EXECUTION_PROMPT.md",
    "third_party/",
    "thesis/template/",
    "tmp/",
)
FORBIDDEN_PATTERNS = {
    "em dash": re.compile("\N{EM DASH}"),
    "local absolute path": re.compile(r"(?<![\w.])(?:/Users/|/home/|[A-Za-z]:[\\/])"),
    "unfinished placeholder": re.compile(
        r"(?:\[(?:TO BE|TBD|TODO|INSERT|SPECIFIC TOPIC|SOURCE)[^\]]*\]"
        r"|\[(?:نام پروژه|نام و راه ارتباطی|مهلت|مبلغ|تاریخ نهایی|محل امن)[^\]]*\]"
        r"|/absolute/path|<your[-_ ][^>]+>"
        r"|SOURCE_PUBLISHER|2025-XX-XX|PASTE_URL_HERE)",
        re.IGNORECASE,
    ),
    "OpenAI internal markup": re.compile(
        r"(?:contentReference|oaicite|oai_citation|turn\d+(?:search|file)\d+|attributableIndex)"
    ),
    "other assistant markup": re.compile(
        r"(?:\[cite:\s*\d+\]|span_\d+|grok_card|attached_file|ppl-ai-file-upload|:::writing)"
    ),
    "assistant self-identification": re.compile(
        r"\bAs (?:an AI language model|a large language model)\b", re.IGNORECASE
    ),
    "knowledge-cutoff statement": re.compile(r"\bAs of my last knowledge update\b", re.IGNORECASE),
    "assistant closing": re.compile(
        r"\b(?:I hope this helps|Let me know if you need anything else|"
        r"Would you like a more detailed breakdown)\b",
        re.IGNORECASE,
    ),
    "stock assistant opening": re.compile(r"^(?:Of course|Certainly)!", re.MULTILINE),
    "ChatGPT tracking parameter": re.compile(r"utm_source=chatgpt\.com", re.IGNORECASE),
    "credential placeholder": re.compile(
        r"(?:API_KEY|TOKEN)\s*=\s*['\"]?(?:\.\.\.|sk-[^\s'\"]*\.\.\.)", re.IGNORECASE
    ),
    "stock marketing phrase": re.compile(
        r"\b(?:In today['’]s fast-paced digital landscape|"
        r"In the dynamic (?:world|landscape) of|As the world continues to evolve|"
        r"Ready to unlock your potential|Let['’]s dive in|Here['’]s the kicker|"
        r"Here['’]s what nobody is saying|But here['’]s the truth|No fluff|"
        r"Shouting into the void|It is important to note that|Generally speaking|"
        r"To some extent|From a broader perspective|Based on available information|"
        r"While specific details are (?:limited|scarce)|Despite these challenges)\b",
        re.IGNORECASE,
    ),
}
STYLE_TERMS = {
    "additionally",
    "boasts",
    "bolster",
    "crucial",
    "delve",
    "enduring",
    "enhance",
    "foster",
    "garner",
    "interplay",
    "intricate",
    "landscape",
    "meticulous",
    "pivotal",
    "robust",
    "showcase",
    "tapestry",
    "testament",
    "underscore",
    "vibrant",
    "illuminate",
    "revolutionize",
    "transformative",
    "cutting-edge",
    "realm",
    "beacon",
    "cacophony",
    "empower",
    "elevate",
    "unlock",
}


def candidate_paths(root: Path = ROOT) -> list[Path]:
    output = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    )
    paths: list[Path] = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8", errors="surrogateescape")
        if relative.startswith(EXCLUDED_PREFIXES):
            continue
        path = root / relative
        if path.suffix.lower() in TEXT_SUFFIXES and path.is_file():
            paths.append(path)
    return sorted(paths)


def inspect_prose(root: Path = ROOT) -> dict[str, object]:
    violations: list[dict[str, object]] = []
    style_counts: Counter[str] = Counter()
    total_words = 0
    scanned = candidate_paths(root)
    for path in scanned:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        words = re.findall(r"\b[\w'-]+\b", text.lower())
        total_words += len(words)
        style_counts.update(word for word in words if word in STYLE_TERMS)
        for label, pattern in FORBIDDEN_PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                violations.append({"file": relative, "line": line, "rule": label})
    density = 1000 * sum(style_counts.values()) / max(total_words, 1)
    return {
        "status": "PASS" if not violations else "FAIL",
        "files_scanned": len(scanned),
        "total_words": total_words,
        "violations": violations,
        "style_signal_count": sum(style_counts.values()),
        "style_signals_per_1000_words": round(density, 3),
        "style_terms": dict(style_counts.most_common()),
        "style_note": "Weak lexical signals are advisory and are not treated as authorship evidence.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    report = inspect_prose()
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    for violation in report["violations"]:
        print(f"{violation['file']}:{violation['line']}: {violation['rule']}")
    print(
        f"{report['status']}: {report['files_scanned']} files; "
        f"weak-style density={report['style_signals_per_1000_words']}/1000 words"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
