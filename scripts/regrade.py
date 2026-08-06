"""Re-grade a run from its persisted answers + judge cache, no Ollama call.

Use after a grader-side change (e.g. M1-W2 hotfix #2: the empty-judge
substring fallback) to refresh `report.json`, `judgments.jsonl`, and
`results.md` without re-spending the 25 min of model time.

Inputs (per `--run` directory):
    answers.jsonl       BaselineAnswer per session, one per line
    judge_cache.jsonl   raw judge outputs keyed by sha256(judge_prompt + model)

Outputs (overwritten in place):
    report.json
    judgments.jsonl
    results.md

Reuses the same slice via `--slice` so the per-session competency / gold can
be looked up.

Example:
    python scripts/regrade.py \
        --run runs/m1w2/no_memory \
        --slice data/slices/longmemeval_s_50_seed0.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.baselines.base import BaselineAnswer  # noqa: E402
from ask.data.longmemeval import iter_longmemeval_s  # noqa: E402
from ask.eval.longmemeval import (  # noqa: E402
    JudgmentCache,
    LongMemEvalGrader,
    evaluate_baseline,
)


class _ReplayBaseline:
    """Replays answers from answers.jsonl as if generated fresh."""

    def __init__(self, baseline_name: str, by_session: dict[str, BaselineAnswer]) -> None:
        self.BASELINE_NAME = baseline_name
        self._by_session = by_session

    def answer(self, session) -> BaselineAnswer:  # noqa: ANN001
        return self._by_session[session.session_id]


class _CacheOnlyJudge:
    """No-op judge — every prompt MUST be a cache hit. Errors loudly otherwise."""

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id

    def generate(self, prompt: str, **_kwargs):  # noqa: ANN001, ANN003
        raise RuntimeError(
            "regrade.py expected every judge call to hit the cache, but a "
            "miss happened — the answers may have drifted from the cache "
            "(e.g. someone re-ran answers.jsonl). Re-run finalize_m1w2.sh."
        )


def _load_answers(path: Path) -> dict[str, BaselineAnswer]:
    out: dict[str, BaselineAnswer] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        # `extras` may be missing in older artifacts.
        d.setdefault("extras", {})
        out[d["session_id"]] = BaselineAnswer(**d)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--run",
        required=True,
        type=Path,
        help="Run directory containing answers.jsonl + judge_cache.jsonl",
    )
    p.add_argument("--slice", required=True, type=Path)
    p.add_argument("--n-bootstrap", type=int, default=1000)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    run_dir: Path = args.run
    answers_path = run_dir / "answers.jsonl"
    cache_path = run_dir / "judge_cache.jsonl"
    report_path = run_dir / "report.json"
    judgments_path = run_dir / "judgments.jsonl"
    md_path = run_dir / "results.md"

    if not answers_path.exists():
        raise SystemExit(f"missing {answers_path}")
    if not cache_path.exists():
        raise SystemExit(f"missing {cache_path}")

    by_session = _load_answers(answers_path)
    print(f"[regrade] loaded {len(by_session)} cached answers from {answers_path}", flush=True)

    # Use the judge_model_id recorded on the existing report so the cache
    # keys still match.
    prev: dict[str, object] = {}
    if report_path.exists():
        prev = json.loads(report_path.read_text(encoding="utf-8"))
        judge_model_id = prev["judge_model_id"]
        baseline_name = prev["baseline_name"]
    else:
        # Fallback: probe the cache.
        first_line = cache_path.read_text(encoding="utf-8").splitlines()[0]
        rec = json.loads(first_line)
        judge_model_id = rec["value"].get("judge_model_id", "unknown-judge")
        baseline_name = next(iter(by_session.values())).baseline

    cache = JudgmentCache(cache_path)
    grader = LongMemEvalGrader(
        judge_llm=_CacheOnlyJudge(judge_model_id),
        cache=cache,
        seed=args.seed,
    )
    baseline = _ReplayBaseline(baseline_name, by_session)

    sessions = [s for s in iter_longmemeval_s(args.slice) if s.session_id in by_session]
    print(f"[regrade] regrading {len(sessions)} sessions (judge={judge_model_id})", flush=True)

    report = evaluate_baseline(
        baseline,
        sessions,
        grader,
        n_bootstrap=args.n_bootstrap,
        bootstrap_seed=args.seed,
        judgments_path=judgments_path,
    )

    payload = report.to_dict()
    for key in ("wall_clock_seconds", "slice_path", "seed", "scorecard"):
        if key in prev:
            payload[key] = prev[key]
    payload["regrade"] = True
    payload["fallback_count"] = sum(1 for g in report.grades if g.used_fallback)
    payload["fallback_breakdown"] = {}
    for g in report.grades:
        if g.used_fallback:
            payload["fallback_breakdown"].setdefault(g.competency, 0)
            payload["fallback_breakdown"][g.competency] += 1

    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(report.summarize_markdown(), encoding="utf-8")

    print()
    print("=" * 72, flush=True)
    print(
        f"[regrade] overall={report.overall_accuracy * 100:.1f}% "
        f"(95% CI {report.overall_ci_low * 100:.1f} – {report.overall_ci_high * 100:.1f})",
        flush=True,
    )
    print(f"[regrade] fallback grades: {payload['fallback_count']}/{report.n_sessions}", flush=True)
    if payload["fallback_breakdown"]:
        print(f"[regrade] fallback by competency: {payload['fallback_breakdown']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
