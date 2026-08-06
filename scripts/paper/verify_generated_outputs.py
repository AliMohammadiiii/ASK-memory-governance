#!/usr/bin/env python3
"""Fail when headline paper fragments drift from the verified public ledger."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "reports/paper_artifact_drift.json"
REQUIRED = {
    "paper/paper_1/tables/v43_main_results.tex": [
        "Action accuracy & 0.8481 & [0.8037, 0.8889] (cluster)",
        "Macro-F1 & 0.8479 & [0.8021, 0.8894] (cluster)",
        "Cohen's $\\kappa$ & 0.7722",
        "Matthews correlation & 0.7728",
    ],
    "paper/paper_1/tables/v43_confusion.tex": [
        "\\abstain{} & 142 & 30 & 8",
        "\\keep{} & 18 & 151 & 11",
        "\\supersede{} & 6 & 9 & 165",
        "$8/180=0.0444$",
    ],
    "paper/paper_1/tables/lme_v12.tex": [
        "B4 naive overwrite & 114/180 & 0.6333",
        "\\textbf{ASK governed writes} & \\textbf{137/180}",
        "$2.9\\!\\times\\!10^{-4}$",
        "over the four adjacent tests reported here",
    ],
    "paper/paper_1/tables/lme_scorecard.tex": [
        "All & 12,654 & 11,478 (90.7\\%) & 397 (3.1\\%) & 779 (6.2\\%)",
        "$f$ & marker burden & 779",
        "$r$ & signed relation and update guard & 483",
    ],
    "paper/paper_1/sections/00_abstract.tex": [
        "storage-independent governance contract",
        "reference transition semantics",
        "$12{,}654$ logged controller decisions",
        "generic reference validator is not wired into that runtime's SQLite mutation path",
        "planned natural-dialogue track remains quarantined without independent gold",
    ],
}


def verify() -> dict[str, object]:
    missing = []
    for relative, fragments in REQUIRED.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        normalized_text = " ".join(text.split())
        missing.extend(
            {"file": relative, "fragment": fragment}
            for fragment in fragments
            if " ".join(fragment.split()) not in normalized_text
        )
    return {
        "schema_version": "1.0",
        "verified_at": datetime.now(UTC).isoformat(),
        "status": "PASS" if not missing else "FAIL",
        "files_checked": len(REQUIRED),
        "fragments_checked": sum(map(len, REQUIRED.values())),
        "missing": missing,
        "scope": "headline LaTeX fragment drift; figures still require source-hash and visual review",
    }


def main() -> int:
    report = verify()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
