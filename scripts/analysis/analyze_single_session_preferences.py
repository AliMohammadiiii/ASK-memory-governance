#!/usr/bin/env python3
"""Analyze the single-session-preference (SSP) failure taxonomy.

Loads the machine-readable taxonomy produced for the ASK controller's
LongMemEval-M single-session-preference failures and prints:

  * headline numbers (verified from the run judgments),
  * per primary-category counts,
  * per secondary-category counts,
  * combined (primary + secondary) category mentions,
  * per pipeline-layer counts,
  * an optional per-item table.

The taxonomy JSON schema is the one emitted alongside this repo at
``artifacts/single_session_preference_error_taxonomy.json``.

Usage:
    python3 scripts/analysis/analyze_single_session_preferences.py \
        --taxonomy artifacts/single_session_preference_error_taxonomy.json
    python3 scripts/analysis/analyze_single_session_preferences.py --items
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_TAXONOMY = (
    Path(__file__).resolve().parents[2]
    / "artifacts"
    / "single_session_preference_error_taxonomy.json"
)


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _bar(count: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return ""
    filled = int(round(width * count / total))
    return "#" * filled + "." * (width - filled)


def _print_table(title: str, counts: dict[str, int], total: int) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if not counts:
        print("  (none)")
        return
    keyw = max(len(k) for k in counts)
    for key, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        pct = 100.0 * count / total if total else 0.0
        print(f"  {key:<{keyw}}  {count:>3}  {pct:5.1f}%  {_bar(count, total)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--taxonomy",
        type=Path,
        default=DEFAULT_TAXONOMY,
        help="Path to single_session_preference_error_taxonomy.json",
    )
    ap.add_argument(
        "--items",
        action="store_true",
        help="Also print the per-item table (session, primary, layers).",
    )
    args = ap.parse_args()

    doc = _load(args.taxonomy)
    items: list[dict[str, Any]] = doc.get("items", [])
    n = len(items)

    print("=" * 70)
    print("SINGLE-SESSION-PREFERENCE FAILURE TAXONOMY - ANALYSIS")
    print("=" * 70)
    hn = doc.get("headline_numbers", {})
    if hn:
        print("\nHeadline numbers (verified against run judgments):")
        for key in (
            "ssp_total",
            "ssp_correct_v7",
            "ssp_incorrect_v7",
            "ssp_accuracy_v7",
            "replay_ssp_failures_selected",
            "replay_ssp_repaired",
            "adjudicated_ssp_correct",
            "adjudicated_ssp_overrides_on_ssp",
        ):
            if key in hn:
                print(f"  {key:<34} {hn[key]}")
    print(f"\nClassified failure items: {n}")

    # Prefer stored aggregates; recompute from items as a cross-check.
    prim = Counter(r["primary_category"] for r in items)
    seco = Counter(c for r in items for c in r.get("secondary_categories", []))
    layer = Counter(l for r in items for l in r.get("pipeline_layers", []))
    comb: Counter = Counter()
    for r in items:
        comb[r["primary_category"]] += 1
        for c in r.get("secondary_categories", []):
            comb[c] += 1

    _print_table("Primary category (n=%d items)" % n, dict(prim), n)
    _print_table("Secondary category (label occurrences)", dict(seco), n)
    _print_table("Combined primary+secondary mentions", dict(comb), n)
    _print_table("Pipeline layer localization (items touching layer)", dict(layer), n)

    # Cross-check against stored aggregates if present.
    stored = doc.get("primary_category_counts")
    if stored and dict(prim) != stored:
        print(
            "\n[WARN] recomputed primary counts differ from stored "
            "primary_category_counts in the taxonomy file."
        )

    if args.items:
        print("\nPer-item detail")
        print("-" * len("Per-item detail"))
        for r in items:
            sec = ",".join(r.get("secondary_categories", [])) or "-"
            layers = ",".join(r.get("pipeline_layers", []))
            print(f"  {r['session_id']}  {r['primary_category']}  (sec: {sec})")
            print(f"       layers: {layers}")


if __name__ == "__main__":
    main()
