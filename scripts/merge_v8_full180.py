#!/usr/bin/env python3
"""Merge the v8 TOP-UP run (110 fresh) with the v8 failure-replay answers
(70 existing) into one full-180 controller estimate under ONE judge.

Why re-judging is required: the replay leg was judged by Qwen/Qwen3.5-9B
(same-as-answerer on Modal), while the v7/v8 protocol judge is
google/gemma-4-31b-it. Answers are the expensive part; judging is cheap.
This script therefore:

  1. takes the top-up run's judgments as-is (they are already gemma-judged);
  2. RE-JUDGES the replay leg's 70 stored answers with the same gemma judge
     (OpenRouter, cached in <out>/judge_cache.jsonl) — machine verdicts only,
     NO manual adjudication overrides;
  3. checks coverage (exactly the slice, no overlap/dupes) and judge
     homogeneity, and DISCLOSES the residual answerer heterogeneity of the
     replay leg (Modal-served Qwen3.5-9B, no 35B escalation) in the manifest;
  4. rebuilds report.json with the standard bootstrap machinery.

    export OPENROUTER_API_KEY=sk-or-...
    python scripts/merge_v8_full180.py \
      --slice data/slices/longmemeval_m_strat30_seed0.jsonl \
      --topup-run runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v8_topup110/controller \
      --replay-run runs/lme_m_modal_qwen35_9b_v8_v7_failures_nothink/controller \
      --out runs/lme_m_strat30_seed0_v8_full180_merged/controller

`--reuse-replay-judgments` skips the re-judge and keeps the replay's original
Qwen verdicts (heterogeneous judges — NOT for the paper table; useful only
for structural tests and quick previews; requires --allow-heterogeneous).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ksa.baselines.base import BaselineAnswer  # noqa: E402
from ksa.data.longmemeval import load_longmemeval_s  # noqa: E402
from ksa.eval.judge import JudgeBackendConfig, build_judge_backend  # noqa: E402
from ksa.eval.longmemeval import (  # noqa: E402
    GradeResult,
    JudgmentCache,
    LongMemEvalGrader,
    build_eval_report,
)

ANSWER_FIELDS = ("session_id", "text", "prompt_tokens", "completion_tokens",
                 "latency_ms", "raw_prompt", "seed", "model_id", "baseline",
                 "extras")
GRADE_FIELDS = ("session_id", "competency", "correct", "judge_score",
                "judge_rationale", "judge_model_id", "predicted", "gold",
                "prompt_tokens", "completion_tokens", "latency_ms",
                "used_fallback")


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", type=Path, required=True)
    parser.add_argument("--topup-run", type=Path, required=True)
    parser.add_argument("--replay-run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--judge-model", default="google/gemma-4-31b-it")
    parser.add_argument("--judge-base-url",
                        default="https://openrouter.ai/api/v1")
    parser.add_argument("--n-bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--reuse-replay-judgments", action="store_true")
    parser.add_argument("--allow-heterogeneous", action="store_true")
    args = parser.parse_args(argv)

    sessions = {s.session_id: s for s in load_longmemeval_s(args.slice)}
    slice_ids = set(sessions)

    replay_answers = {a["session_id"]: a
                      for a in jsonl(args.replay_run / "answers.jsonl")}
    replay_ids = set(replay_answers)
    topup_needed = slice_ids - replay_ids

    topup_judgments = {j["session_id"]: j
                       for j in jsonl(args.topup_run / "judgments.jsonl")
                       if j["session_id"] in topup_needed}
    topup_answers = {a["session_id"]: a
                     for a in jsonl(args.topup_run / "answers.jsonl")
                     if a["session_id"] in topup_needed}

    missing = topup_needed - set(topup_judgments)
    if missing:
        raise SystemExit(
            f"top-up run is missing {len(missing)} required sessions "
            f"(e.g. {sorted(missing)[:3]}) — resume the top-up run first")
    overlap = replay_ids & set(topup_judgments)
    if overlap:
        raise SystemExit(f"overlap between legs: {sorted(overlap)[:5]}")

    args.out.mkdir(parents=True, exist_ok=True)

    # --- replay leg: re-judge stored answers with the protocol judge ------
    if args.reuse_replay_judgments:
        if not args.allow_heterogeneous:
            raise SystemExit("--reuse-replay-judgments requires "
                             "--allow-heterogeneous (NOT for the paper)")
        replay_grades = [j for j in jsonl(args.replay_run / "judgments.jsonl")
                         if j["session_id"] in slice_ids]
        print(f"[merge] reusing {len(replay_grades)} replay judgments "
              f"(heterogeneous judges — preview only)")
    else:
        judge_cfg = JudgeBackendConfig(
            backend="openai_compatible", model_id=args.judge_model,
            openai_base_url=args.judge_base_url,
            openai_api_key_env="OPENROUTER_API_KEY",
            response_format="json")
        grader = LongMemEvalGrader(
            judge_llm=build_judge_backend(judge_cfg),
            cache=JudgmentCache(args.out / "judge_cache.jsonl"),
            seed=args.seed)
        replay_grades = []
        print(f"[merge] re-judging {len(replay_answers)} replay answers "
              f"with {args.judge_model}")
        for i, (sid, a) in enumerate(sorted(replay_answers.items()), 1):
            answer = BaselineAnswer(**{k: a[k] for k in ANSWER_FIELDS if k in a})
            grade = grader.grade(answer, sessions[sid])
            replay_grades.append(grade.to_dict())
            if i % 10 == 0:
                print(f"[merge] re-judged {i}/{len(replay_answers)}")

    # --- combine -----------------------------------------------------------
    all_grades = list(topup_judgments.values()) + replay_grades
    all_answers = list(topup_answers.values()) + list(replay_answers.values())

    ids = Counter(g["session_id"] for g in all_grades)
    dupes = {k: c for k, c in ids.items() if c > 1}
    if dupes or set(ids) != slice_ids:
        raise SystemExit(f"coverage broken: dupes={sorted(dupes)[:3]} "
                         f"missing={sorted(slice_ids - set(ids))[:3]}")

    judges = sorted({g["judge_model_id"] for g in all_grades})
    if len(judges) > 1 and not args.allow_heterogeneous:
        raise SystemExit(f"judge not homogeneous after merge: {judges}")

    with (args.out / "judgments.jsonl").open("w", encoding="utf-8") as h:
        for g in all_grades:
            h.write(json.dumps(g, ensure_ascii=False) + "\n")
    with (args.out / "answers.jsonl").open("w", encoding="utf-8") as h:
        for a in all_answers:
            h.write(json.dumps(a, ensure_ascii=False) + "\n")

    grades = [GradeResult(**{k: g[k] for k in GRADE_FIELDS if k in g})
              for g in all_grades]
    report = build_eval_report(
        baseline_name="controller", judge_model_id=judges[0],
        grades=grades, n_bootstrap=args.n_bootstrap,
        bootstrap_seed=args.seed)
    (args.out / "report.json").write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8")

    answer_models = dict(Counter(a.get("model_id") for a in all_answers))
    manifest = {
        "estimate": "v8_full180_topup_merge",
        "composition": {"topup_fresh_v8": len(topup_judgments),
                        "replay_v8_answers": len(replay_answers)},
        "judge_models_after_merge": judges,
        "replay_rejudged_with": (None if args.reuse_replay_judgments
                                 else args.judge_model),
        "manual_adjudication_overrides": 0,
        "disclosed_heterogeneity": {
            "answerer_models": answer_models,
            "note": ("replay leg answers were generated on Modal-served "
                     "Qwen3.5-9B without the 35B escalation; top-up leg via "
                     "OpenRouter with escalation. Same base model and code; "
                     "serving substrate differs for the replay leg. This "
                     "biases the replay leg conservatively (no escalation)."),
        },
        "provenance": {"slice": str(args.slice),
                       "topup_run": str(args.topup_run),
                       "replay_run": str(args.replay_run)},
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                            encoding="utf-8")

    print(f"[merge] n={len(grades)}  overall_accuracy="
          f"{report.overall_accuracy:.4f}  "
          f"CI=({report.overall_ci_low:.3f},{report.overall_ci_high:.3f})")
    print(f"[merge] judges={judges}")
    print(f"[merge] answer models={answer_models}")
    print(f"[merge] -> {args.out}/report.json (+ manifest.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
