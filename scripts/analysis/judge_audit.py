#!/usr/bin/env python3
"""Judge primary/fallback confound audit over judgments.jsonl files.

Separates three mechanisms that older reports conflated under ``used_fallback``:
the declared judge-model route fallback, the deterministic substring scoring
fallback after malformed judge output, and deterministic guards that do not call
a judge. It quantifies each mechanism and its association with scored accuracy.

READ-ONLY. Stdlib only. Deterministic.

Usage:
    python3 scripts/analysis/judge_audit.py \
        --judgments runs_local/lme_final_5systems_180/controller/judgments.jsonl \
        --out runs_local/judge_audit/controller_judge_audit.json
    # or point at a run root to glob every judgments.jsonl under it:
    python3 scripts/analysis/judge_audit.py --run-root runs_local/lme_final_5systems_180
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _correct(row: dict[str, Any]) -> bool:
    if "correct" in row and row["correct"] is not None:
        return bool(row["correct"])
    return row.get("judge_score", 0) in (1, 1.0, True)


def _acc(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    k = sum(1 for r in rows if _correct(r))
    return {"n": n, "correct": k, "accuracy": round(k / n, 4) if n else None}


def audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    model_fallback = [r for r in rows if bool(r.get("used_model_fallback"))]
    scoring_fallback = [r for r in rows if bool(r.get("used_scoring_fallback"))]
    judge_called = [r for r in rows if r.get("judge_was_called", True)]
    deterministic_guard = [r for r in rows if r.get("judge_was_called") is False]
    primary_route = [
        r
        for r in judge_called
        if not bool(r.get("used_model_fallback")) and not bool(r.get("used_scoring_fallback"))
    ]

    by_comp_fallback: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "model": 0, "scoring": 0, "guard": 0}
    )
    for r in rows:
        c = str(r.get("competency", "?"))
        by_comp_fallback[c]["total"] += 1
        if bool(r.get("used_model_fallback")):
            by_comp_fallback[c]["model"] += 1
        if bool(r.get("used_scoring_fallback")):
            by_comp_fallback[c]["scoring"] += 1
        if r.get("judge_was_called") is False:
            by_comp_fallback[c]["guard"] += 1

    judges = sorted({str(r.get("judge_model_id")) for r in rows})
    requested_judges = sorted(
        {str(r.get("requested_judge_model_id")) for r in rows if r.get("requested_judge_model_id")}
    )

    primary_acc = _acc(primary_route)
    fallback_acc = _acc(model_fallback)
    split = None
    if primary_acc["accuracy"] is not None and fallback_acc["accuracy"] is not None:
        split = round(primary_acc["accuracy"] - fallback_acc["accuracy"], 4)

    return {
        "total": len(rows),
        "judge_model_ids_observed": judges,
        "requested_judge_model_ids": requested_judges,
        "n_judge_called": len(judge_called),
        "n_primary_route_clean": len(primary_route),
        "n_model_fallback": len(model_fallback),
        "n_scoring_fallback": len(scoring_fallback),
        "n_deterministic_guard": len(deterministic_guard),
        "model_fallback_rate_among_judge_calls": (
            round(len(model_fallback) / len(judge_called), 4) if judge_called else None
        ),
        "scoring_fallback_rate_among_judge_calls": (
            round(len(scoring_fallback) / len(judge_called), 4) if judge_called else None
        ),
        "accuracy_primary_route_clean": primary_acc,
        "accuracy_model_fallback": fallback_acc,
        "accuracy_scoring_fallback": _acc(scoring_fallback),
        "accuracy_deterministic_guard": _acc(deterministic_guard),
        "accuracy_split_primary_minus_fallback": split,
        "per_competency_fallback": {
            c: {
                "total": v["total"],
                "model_fallback": v["model"],
                "scoring_fallback": v["scoring"],
                "deterministic_guard": v["guard"],
                "model_fallback_rate": (round(v["model"] / v["total"], 4) if v["total"] else None),
                "scoring_fallback_rate": (
                    round(v["scoring"] / v["total"], 4) if v["total"] else None
                ),
            }
            for c, v in sorted(by_comp_fallback.items())
        },
        "interpretation": (
            "A large positive accuracy_split means fallback-graded items scored "
            "lower; disclose it. Model fallback is a routing event; scoring fallback "
            "is a malformed-output repair and must not be described as the paid judge."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--judgments",
        type=Path,
        action="append",
        default=[],
        help="explicit judgments.jsonl path (repeatable)",
    )
    ap.add_argument(
        "--run-root", type=Path, default=None, help="glob every */judgments.jsonl under this dir"
    )
    ap.add_argument("--out", type=Path, default=None, help="write JSON summary here")
    args = ap.parse_args(argv)

    paths: list[Path] = list(args.judgments)
    if args.run_root:
        paths.extend(sorted(args.run_root.rglob("judgments.jsonl")))
    paths = [p for p in paths if p.exists()]
    if not paths:
        print("FATAL: no judgments.jsonl files found. Pass --judgments or --run-root.")
        return 1

    per_file: dict[str, Any] = {}
    combined: list[dict[str, Any]] = []
    for p in paths:
        rows = _load_jsonl(p)
        per_file[str(p)] = audit(rows)
        combined.extend(rows)

    result = {
        "files": per_file,
        "combined": audit(combined),
    }

    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.out.with_suffix(args.out.suffix + ".tmp")
        tmp.write_text(text + "\n", encoding="utf-8")
        tmp.replace(args.out)
        print(f"[judge-audit] wrote {args.out}")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
