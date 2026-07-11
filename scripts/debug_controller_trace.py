#!/usr/bin/env python3
"""Forensic diagnostic for the controller pipeline on a completed run.

One command summarises every stage so the *first failing stage* is visible
without rerunning a model:

  - extraction_trace.jsonl : empty-rate, over-extraction of questions/requests,
                             confidence distribution
  - relation_trace.jsonl   : stage-1 label mix, final relation mix, supersede count
  - judgments/predictions  : failure taxonomy + per-failed-example trace

Usage:
  python scripts/debug_controller_trace.py runs/<run>/controller
  python scripts/debug_controller_trace.py runs/<run>/controller --n 8

Send the full stdout back for diagnosis; the raw trace files are not required.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

_QUESTION_RE = re.compile(r"\?\s*$")
_REQUEST_RE = re.compile(
    r"^\s*(can you|could you|please|write|plan|provide|give me|tell me|"
    r"explain|create|generate|make|help me|do you|would you|list|draft)\b",
    re.IGNORECASE,
)


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open()] if path.exists() else []


def _items(rec: dict) -> list[dict]:
    return (rec.get("validated_output") or {}).get("items", []) or []


def section(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def extraction_summary(d: Path) -> None:
    rows = load(d / "extraction_trace.jsonl")
    section(f"EXTRACTION  ({len(rows)} calls)")
    if not rows:
        print("  (no extraction_trace.jsonl)")
        return
    empty = sum(1 for r in rows if not _items(r))
    n_items = [len(_items(r)) for r in rows]
    confs: list[float] = []
    questionish = 0
    examples_q: list[str] = []
    for r in rows:
        for it in _items(r):
            confs.append(round(float(it.get("extraction_confidence", 0.0)), 2))
            t = (it.get("text") or "").strip()
            if _QUESTION_RE.search(t) or _REQUEST_RE.match(t):
                questionish += 1
                if len(examples_q) < 8:
                    examples_q.append(t[:80])
    total_items = sum(n_items)
    print(f"  empty extractions          : {empty}/{len(rows)} ({empty/len(rows):.0%})")
    print(f"  total items extracted      : {total_items}")
    print(f"  items-per-call distribution: {dict(sorted(Counter(n_items).items()))}")
    print(f"  confidence distribution    : {dict(sorted(Counter(confs).items()))}")
    pct = f" ({questionish/total_items:.0%})" if total_items else ""
    print(f"  OVER-EXTRACTION (question/request-shaped items): {questionish}/{total_items}{pct}")
    for t in examples_q:
        print(f"     ! {t!r}")


def relation_summary(d: Path) -> None:
    rows = load(d / "relation_trace.jsonl")
    section(f"RELATION  ({len(rows)} classifications)")
    if not rows:
        print("  (no relation_trace.jsonl — controller found no priors, so SUPERSEDE is impossible)")
        return
    stage1 = Counter(r.get("raw_stage1_label") for r in rows)
    final = Counter((r.get("output") or {}).get("relation_to_prior_state") for r in rows)
    routing = Counter(r.get("deterministic_routing_reason") for r in rows)
    print(f"  stage-1 logical_relation   : {dict(stage1)}")
    print(f"  final relation_to_prior    : {dict(final)}")
    print(f"  routing reasons            : {dict(routing)}")
    eligible = final.get("supersede", 0) + final.get("contradict", 0)
    print(f"  -> SUPERSEDE-eligible (final in contradict/supersede): {eligible}/{len(rows)}")


def action_summary(d: Path) -> None:
    rows = load(d / "action_log.jsonl")
    section(f"ACTIONS  ({len(rows)} candidate decisions)")
    if not rows:
        print("  (no action_log.jsonl)")
        return
    print(f"  action distribution        : {dict(Counter(r.get('action') for r in rows))}")
    keep_prior = [r for r in rows if r.get("action") == "Keep" and r.get("prior_memory_id") is not None]
    dropped = [r for r in keep_prior if r.get("resulting_memory_id") is None]
    print(f"  KEEP w/ prior              : {len(keep_prior)}  "
          f"(of which DROPPED, not committed: {len(dropped)})")
    print("  NOTE: action_log rows are keyed by the *ingested memory session*, "
          "not the query session — do not join on session_id.")


def failure_taxonomy(d: Path, n: int) -> None:
    judg = load(d / "judgments.jsonl")
    preds = {p["session_id"]: p for p in load(d / "predictions.jsonl")}
    n_failed = sum(1 for j in judg if not j.get("correct"))
    section(f"QA FAILURES  ({n_failed}/{len(judg)} failed)")
    if not judg:
        print("  (no judgments.jsonl)")
        return
    failed = [j for j in judg if not j.get("correct")]

    def bucket(x: dict) -> str:
        r = x.get("judge_rationale", "") or ""
        pred = (x.get("predicted") or "").strip().lower()
        if pred in ("unknown", "unknown.", ""):
            return "Unknown (fact not retrieved/answered)"
        m = re.search(r"(\d+)/(\d+) gold tokens missing", r)
        if m and m.group(1) != m.group(2):
            return "partial precision (dropped a gold qualifier token)"
        if m:
            return "wrong answer (all gold tokens missing)"
        return "other/judge"

    for k, v in Counter(bucket(x) for x in failed).most_common():
        print(f"  {v:3d}  {k}")
    print(f"\n  --- first {min(n, len(failed))} failed examples ---")
    for j in failed[:n]:
        ex = preds.get(j["session_id"], {}).get("extras", {})
        print(f"\n  SESSION {j['session_id']}  competency={j.get('competency')}")
        print(f"    GOLD     : {j.get('gold')!r}")
        print(f"    PREDICTED: {j.get('predicted')!r}")
        print(f"    judge    : {(j.get('judge_rationale') or '')[:150]}")
        print(f"    retrieval: n={ex.get('n_retrieved')} sessions={ex.get('retrieval_session_ids')}")
        print(f"    bucket   : {bucket(j)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", help="path to runs/<run>/controller")
    ap.add_argument("--n", type=int, default=5, help="failed examples to show")
    args = ap.parse_args()
    d = Path(args.run_dir)
    print(f"# forensic trace for {d}")
    extraction_summary(d)
    relation_summary(d)
    action_summary(d)
    failure_taxonomy(d, args.n)


if __name__ == "__main__":
    main()
