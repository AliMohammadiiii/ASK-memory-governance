"""Merge session-sharded LongMemEval run outputs into one run directory.

Session-level parallelism runs N independent `run_baseline` subprocesses over
disjoint, round-robin session shards (each its own sqlite, caches, action log),
then this module concatenates the per-shard artifacts and rebuilds the aggregate
report from the union of grades. Because each session is graded identically
regardless of which shard ran it (temperature 0, fixed seed), the merged report
is the same as a single serial run — only wall-clock changes.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .longmemeval import EvalReport, GradeResult, build_eval_report

# Line-oriented artifacts that simply concatenate across shards.
_JSONL_ARTIFACTS = (
    "answers.jsonl",
    "predictions.jsonl",
    "judgments.jsonl",
    "action_log.jsonl",
    "extraction_trace.jsonl",
    "relation_trace.jsonl",
    "extraction_cache.jsonl",
    "relation_cache.jsonl",
    "judge_cache.jsonl",
)


def grade_from_dict(row: dict[str, Any]) -> GradeResult | None:
    fields = dataclasses.fields(GradeResult)
    field_names = {f.name for f in fields}
    required_names = {
        f.name
        for f in fields
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
    }
    payload = {k: row[k] for k in field_names if k in row}
    if required_names - payload.keys():
        return None
    try:
        return GradeResult(**payload)
    except Exception:
        return None


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def merge_run_shards(
    shard_dirs: list[Path],
    out_dir: Path,
    *,
    baseline_name: str,
    judge_model_id: str,
    n_bootstrap: int = 1000,
    bootstrap_seed: int = 0,
) -> EvalReport:
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) concatenate line-oriented artifacts (dedup judgments/answers by session).
    seen_judg: set[str] = set()
    seen_ans: set[str] = set()
    for name in _JSONL_ARTIFACTS:
        lines: list[str] = []
        for d in shard_dirs:
            for row in _iter_jsonl(d / name):
                sid = row.get("session_id")
                if name == "judgments.jsonl" and isinstance(sid, str):
                    if sid in seen_judg:
                        continue
                    seen_judg.add(sid)
                if name in ("answers.jsonl", "predictions.jsonl") and isinstance(sid, str):
                    key = f"{name}:{sid}"
                    if key in seen_ans:
                        continue
                    seen_ans.add(key)
                lines.append(json.dumps(row, ensure_ascii=False))
        if lines:
            (out_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 2) rebuild the aggregate report from the union of grades.
    grades = [
        g
        for row in _iter_jsonl(out_dir / "judgments.jsonl")
        if (g := grade_from_dict(row)) is not None
    ]
    report = build_eval_report(
        baseline_name=baseline_name,
        judge_model_id=judge_model_id,
        grades=grades,
        n_bootstrap=n_bootstrap,
        bootstrap_seed=bootstrap_seed,
    )
    (out_dir / "report.json").write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / "results.md").write_text(report.summarize_markdown(), encoding="utf-8")
    return report
