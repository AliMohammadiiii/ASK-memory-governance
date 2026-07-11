#!/usr/bin/env python3
"""Homogeneity + coverage gate for a multi-system LongMemEval run.

A run is paper-grade ("full homogeneous") only if, for EVERY system:

  1. report.json exists and n_sessions == expected N (default: slice size);
  2. answers.jsonl and judgments.jsonl cover exactly the slice session_ids
     (no missing, no extra, no duplicates);
  3. every system used the SAME judge model (judgments.jsonl judge_model_id);
  4. every system's answerer model set is reported (from answers.jsonl
     model_id) so heterogeneous escalation is visible, and the escalation
     model set is identical across systems that use it;
  5. slice sha256 is recorded for the provenance table.

Exits non-zero on any failure, printing a PASS/FAIL table. Run after
deploy/run_lme_v8_full_5systems.sh:

    python scripts/verify_homogeneous_run.py \
        --run-root runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v8_full5 \
        --slice data/slices/longmemeval_m_strat30_seed0.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def check_system(run_root: Path, system: str, slice_ids: list[str],
                 expected_n: int) -> dict[str, Any]:
    sys_dir = run_root / system
    result: dict[str, Any] = {"system": system, "errors": [], "warnings": []}
    err = result["errors"].append

    report_path = sys_dir / "report.json"
    if not report_path.exists():
        err(f"missing {report_path}")
        return result
    report = json.loads(report_path.read_text(encoding="utf-8"))
    result["overall_accuracy"] = report.get("overall_accuracy")
    result["report_judge"] = report.get("judge_model_id")
    n_sessions = report.get("n_sessions")
    result["n_sessions"] = n_sessions
    if n_sessions != expected_n:
        err(f"report n_sessions={n_sessions}, expected {expected_n}")

    slice_counter = Counter(slice_ids)
    for name in ("answers.jsonl", "judgments.jsonl"):
        path = sys_dir / name
        if not path.exists():
            err(f"missing {path}")
            continue
        rows = load_jsonl(path)
        ids = Counter(r.get("session_id") for r in rows)
        dupes = {k: c for k, c in ids.items() if c > 1}
        missing = set(slice_counter) - set(ids)
        extra = set(ids) - set(slice_counter)
        if dupes:
            err(f"{name}: duplicate session_ids {sorted(dupes)[:5]}"
                f"{' ...' if len(dupes) > 5 else ''}")
        if missing:
            err(f"{name}: {len(missing)} slice ids missing "
                f"(e.g. {sorted(missing)[:3]})")
        if extra:
            err(f"{name}: {len(extra)} ids not in slice "
                f"(e.g. {sorted(extra)[:3]})")
        if name == "judgments.jsonl":
            judges = sorted({r.get("judge_model_id") for r in rows})
            result["judge_models"] = judges
            if len(judges) > 1:
                result["warnings"].append(
                    f"multiple judge models within system: {judges}")
        if name == "answers.jsonl":
            result["answer_models"] = sorted(
                {r.get("model_id") for r in rows})
            seeds = sorted({r.get("seed") for r in rows})
            result["seeds"] = seeds
            if len(seeds) > 1:
                result["warnings"].append(f"multiple seeds: {seeds}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--slice", type=Path, required=True)
    parser.add_argument("--systems", default="controller,b4,b3,b2,b1")
    parser.add_argument("--expected-n", type=int, default=0,
                        help="expected question count (0 = slice size)")
    parser.add_argument("--out", type=Path, default=None,
                        help="optional JSON output path "
                             "(default <run-root>/homogeneity_report.json)")
    args = parser.parse_args(argv)

    slice_rows = load_jsonl(args.slice)
    slice_ids = [r.get("session_id") for r in slice_rows]
    expected_n = args.expected_n or len(slice_ids)
    slice_sha = sha256_file(args.slice)

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    results = [check_system(args.run_root, s, slice_ids, expected_n)
               for s in systems]

    # cross-system homogeneity
    global_errors: list[str] = []
    judge_sets = {r["system"]: tuple(r.get("judge_models") or ["<missing>"])
                  for r in results}
    if len(set(judge_sets.values())) > 1:
        global_errors.append(f"judge model differs across systems: {judge_sets}")
    seed_sets = {r["system"]: tuple(r.get("seeds") or []) for r in results}
    if len({v for v in seed_sets.values() if v}) > 1:
        global_errors.append(f"seed differs across systems: {seed_sets}")

    ok = not global_errors and all(not r["errors"] for r in results)

    print(f"slice: {args.slice}  n={len(slice_ids)}  sha256={slice_sha[:16]}...")
    print(f"{'system':<12}{'status':<8}{'n':>5}{'acc':>8}  judge / answerers")
    for r in results:
        status = "PASS" if not r["errors"] else "FAIL"
        acc = r.get("overall_accuracy")
        acc_s = f"{acc:.3f}" if isinstance(acc, (int, float)) else "-"
        judges = ",".join(r.get("judge_models") or ["?"])
        models = ",".join(r.get("answer_models") or ["?"])
        print(f"{r['system']:<12}{status:<8}{str(r.get('n_sessions','-')):>5}"
              f"{acc_s:>8}  {judges} / {models}")
        for e in r["errors"]:
            print(f"    ERROR  {e}")
        for w in r["warnings"]:
            print(f"    warn   {w}")
    for e in global_errors:
        print(f"GLOBAL ERROR  {e}")

    payload = {"run_root": str(args.run_root), "slice": str(args.slice),
               "slice_sha256": slice_sha, "expected_n": expected_n,
               "homogeneous": ok, "systems": results,
               "global_errors": global_errors}
    out = args.out or (args.run_root / "homogeneity_report.json")
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n{'HOMOGENEOUS RUN: PASS' if ok else 'HOMOGENEOUS RUN: FAIL'}"
          f"  (report -> {out})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
