#!/usr/bin/env python3
"""Evaluate single-session-preference (SSP) accuracy for a ASK controller run.

Selects the ``single-session-preference`` items from a LongMemEval-format slice
(and/or a run's ``judgments.jsonl``) and reports SSP accuracy with a stratified
percentile bootstrap 95% confidence interval.

SSP items are matched on the competency/question-type field CONTAINING the
substring ``preference`` (case-insensitive), which is how LongMemEval-M labels
the ``single-session-preference`` competency.

Inputs
------
* ``--run-dir``   : controller output dir holding ``judgments.jsonl`` (which
                    carries ``session_id``, ``competency`` and ``correct``).
                    You may instead pass ``--judgments`` directly.
* ``--slice``     : optional LongMemEval slice file (``range_*.jsonl`` style with
                    ``competency``/``session_id``/``gold_answer``). When given, the
                    SSP session set is defined by the slice and intersected with
                    the judged rows (guards against silent competency drift).

Bootstrap
---------
The CI is a stratified percentile bootstrap. Strata default to the value of
``--stratify-by`` (``competency``); for an SSP-only selection that is a single
stratum, i.e. an ordinary item bootstrap. If your slice tags a preference
SUBTYPE (e.g. ``question_subtype``), pass ``--stratify-by question_subtype`` to
get a subtype-stratified interval. Deterministic under ``--seed``.

Usage
-----
    python3 scripts/evaluation/evaluate_single_session_preferences.py \
        --run-dir "runs/.../controller" \
        --slice   "runs/.../range_0_179.jsonl"

    python3 scripts/evaluation/evaluate_single_session_preferences.py \
        --judgments path/to/judgments.jsonl --json
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

PREFERENCE_TOKEN = "preference"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _competency(row: dict[str, Any]) -> str:
    for key in ("competency", "question_type", "type", "task"):
        if key in row and row[key] is not None:
            return str(row[key])
    return ""


def _is_preference(row: dict[str, Any]) -> bool:
    return PREFERENCE_TOKEN in _competency(row).lower()


def stratified_bootstrap_accuracy_ci(
    items: list[dict[str, Any]],
    *,
    stratify_by: str = "competency",
    n_resamples: int = 20_000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Return (point_accuracy, ci_low, ci_high) via stratified percentile bootstrap.

    ``items`` are dicts with a boolean ``correct`` and the stratification field.
    """
    if not items:
        return (0.0, 0.0, 0.0)
    point = sum(bool(it["correct"]) for it in items) / len(items)

    strata: dict[str, list[bool]] = defaultdict(list)
    for it in items:
        strata[str(it.get(stratify_by, "_all"))].append(bool(it["correct"]))

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_resamples):
        pooled: list[bool] = []
        for outcomes in strata.values():
            pooled.extend(rng.choice(outcomes) for _ in outcomes)
        means.append(sum(pooled) / len(pooled))
    means.sort()
    lo = means[int((alpha / 2) * n_resamples)]
    hi = means[int((1 - alpha / 2) * n_resamples)]
    return (point, lo, hi)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, help="Controller dir with judgments.jsonl")
    ap.add_argument("--judgments", type=Path, help="Explicit judgments.jsonl path")
    ap.add_argument("--slice", type=Path, help="LongMemEval slice file (range_*.jsonl)")
    ap.add_argument("--stratify-by", default="competency", help="Bootstrap stratum field")
    ap.add_argument("--n-bootstrap", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true", help="Emit a JSON summary line")
    args = ap.parse_args()

    judg_path = args.judgments
    if judg_path is None:
        if args.run_dir is None:
            ap.error("provide --judgments or --run-dir")
        judg_path = args.run_dir / "judgments.jsonl"
    if not judg_path.exists():
        ap.error(f"judgments file not found: {judg_path}")

    judgments = _load_jsonl(judg_path)
    judged_by_sid = {str(r.get("session_id")): r for r in judgments}

    # Define the SSP session set.
    if args.slice:
        slice_rows = _load_jsonl(args.slice)
        ssp_ids = {str(r["session_id"]) for r in slice_rows if _is_preference(r)}
        selected = [judged_by_sid[s] for s in ssp_ids if s in judged_by_sid]
        missing = sorted(ssp_ids - set(judged_by_sid))
    else:
        selected = [r for r in judgments if _is_preference(r)]
        missing = []

    if not selected:
        print("No single-session-preference items found. Check inputs.")
        return

    # Normalize a boolean 'correct'.
    for r in selected:
        r["correct"] = bool(r.get("correct", r.get("judge_score", 0) in (1, 1.0, True)))

    total = len(selected)
    correct = sum(bool(r["correct"]) for r in selected)
    point, lo, hi = stratified_bootstrap_accuracy_ci(
        selected,
        stratify_by=args.stratify_by,
        n_resamples=args.n_bootstrap,
        seed=args.seed,
    )

    summary = {
        "judgments": str(judg_path),
        "slice": str(args.slice) if args.slice else None,
        "ssp_total": total,
        "ssp_correct": correct,
        "ssp_accuracy": round(point, 4),
        "bootstrap": {
            "stratify_by": args.stratify_by,
            "n_resamples": args.n_bootstrap,
            "seed": args.seed,
            "ci95": [round(lo, 4), round(hi, 4)],
        },
        "slice_ids_missing_from_judgments": missing,
    }

    if args.json:
        print(json.dumps(summary))
        return

    print("=" * 60)
    print("SINGLE-SESSION-PREFERENCE EVALUATION")
    print("=" * 60)
    print(f"judgments : {judg_path}")
    if args.slice:
        print(f"slice     : {args.slice}")
    print(f"SSP items : {total}")
    print(f"correct   : {correct}")
    print(f"accuracy  : {point:.4f}  ({correct}/{total})")
    print(
        f"95% CI    : [{lo:.4f}, {hi:.4f}]  "
        f"(stratified bootstrap by '{args.stratify_by}', "
        f"n={args.n_bootstrap}, seed={args.seed})"
    )
    if missing:
        print(f"[WARN] {len(missing)} slice SSP ids missing from judgments: {missing}")


if __name__ == "__main__":
    main()
