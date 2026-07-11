#!/usr/bin/env python3
"""External memory systems (Mem0 / Graphiti / Letta / MemOS) on LongMemEval.

Reuses the SAME slice, judge, and report machinery as the internal systems so
the numbers land in the same table:

  - sessions:  ksa.data.longmemeval.load_longmemeval_s (same slice file)
  - judge:     ksa.eval.judge.build_judge_backend (openai_compatible ->
               OpenRouter google/gemma-4-31b-it, same as v7/v8)
  - grading:   ksa.eval.longmemeval.LongMemEvalGrader (same guards/cache)
  - report:    ksa.eval.longmemeval.build_eval_report (same bootstrap CI)
  - outputs:   answers.jsonl / judgments.jsonl / report.json — compatible
               with scripts/win_loss.py, print_report.py and
               verify_homogeneous_run.py (--systems ext_mem0 etc.)

Protocol per question: fresh isolated store -> ingest every history session
through the system's NATIVE write path -> retrieve for the question ->
answer with the SAME answerer backbone (qwen/qwen3.5-9b via OpenRouter)
using a neutral prompt (Letta answers natively — flagged in extras).

COST WARNING: ingestion is the expensive part (each history session passes
through the external system's LLM write path). ALWAYS smoke-test first:

    source .venv/bin/activate
    export OPENROUTER_API_KEY=sk-or-...
    python scripts/run_external_lme.py --system mem0 \
      --slice data/slices/longmemeval_m_strat30_seed0.jsonl \
      --out runs/lme_ext_mem0_smoke --limit 2

Full run (resumable; re-run to continue):
    python scripts/run_external_lme.py --system mem0 \
      --slice data/slices/longmemeval_m_strat30_seed0.jsonl \
      --out runs/lme_m_strat30_seed0_ext_mem0
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
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

# external adapters live in the sibling mgp6_v2 repo
MGP6_DIR = REPO.parent / "mgp6_v2"
sys.path.insert(0, str(MGP6_DIR / "external"))
sys.path.insert(0, str(MGP6_DIR))

ANSWER_MODEL = os.environ.get("LME_EXT_ANSWER_MODEL", "qwen/qwen3.5-9b")
BASE_URL = os.environ.get("MGP6_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")

ANSWER_SYSTEM = """You are a helpful assistant answering a question about a \
user, based ONLY on memory snippets retrieved from a long-term memory system \
over the user's past chat sessions. If the memory does not contain the \
answer, say you don't have that information. Prefer the most recent value \
when the user's information changed over time. Be concise."""


def _chat(system: str, user: str, max_tokens: int = 200) -> tuple[str, int, int]:
    payload = {"model": ANSWER_MODEL, "reasoning": {"enabled": False},
               "temperature": 0, "max_tokens": max_tokens,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}]}
    data = json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {API_KEY}",
               "Content-Type": "application/json"}
    last = ""
    for attempt in range(4):
        try:
            req = urllib.request.Request(f"{BASE_URL}/chat/completions",
                                         data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            msg = body["choices"][0]["message"].get("content")
            usage = body.get("usage", {})
            if msg:
                return (msg.strip(), int(usage.get("prompt_tokens", 0)),
                        int(usage.get("completion_tokens", 0)))
            last = "empty content"
        except (urllib.error.URLError, KeyError, json.JSONDecodeError,
                TimeoutError) as exc:
            last = str(exc)
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"answerer failed: {last}")


def make_adapter(system: str):
    if system == "mem0":
        from run_mem0 import Mem0Adapter
        return Mem0Adapter()
    if system == "graphiti":
        from run_graphiti import GraphitiAdapter
        return GraphitiAdapter()
    if system == "letta":
        from run_letta import LettaAdapter
        return LettaAdapter()
    if system == "memos":
        from run_memos import MemOSAdapter
        return MemOSAdapter()
    raise SystemExit(f"unknown --system {system}")


def _session_text(corpus_session: Any) -> str:
    lines = []
    for t in corpus_session.turns:
        role = getattr(t, "role", "user")
        content = getattr(t, "content", "")
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def ingest_history(adapter: Any, session: Any, max_turn_chars: int) -> int:
    """Feed every history session through the native write path."""
    n = 0
    corpus = session.corpus_sessions or []
    for cs in corpus:
        text = _session_text(cs)[:max_turn_chars]
        if text:
            adapter.write(text)
            n += 1
    if not corpus:  # some slices carry history in .turns instead
        text = "\n".join(f"{t.role}: {t.content}" for t in session.turns
                         if t.content)[:max_turn_chars]
        if text:
            adapter.write(text)
            n += 1
    return n


def _done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out = set()
    for line in path.open(encoding="utf-8"):
        if line.strip():
            try:
                out.add(json.loads(line)["session_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", required=True,
                        choices=("mem0", "graphiti", "letta", "memos"))
    parser.add_argument("--slice", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0,
                        help="max NEW questions this call (0 = all)")
    parser.add_argument("--k", type=int, default=8, help="retrieval depth")
    parser.add_argument("--judge-model", default="google/gemma-4-31b-it")
    parser.add_argument("--judge-base-url",
                        default="https://openrouter.ai/api/v1")
    parser.add_argument("--max-session-chars", type=int, default=6000,
                        help="truncate each ingested history session")
    parser.add_argument("--n-bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    if not API_KEY:
        raise SystemExit("set OPENROUTER_API_KEY")

    out = args.out / args.system if args.out.name != args.system else args.out
    out.mkdir(parents=True, exist_ok=True)
    answers_path = out / "answers.jsonl"
    judgments_path = out / "judgments.jsonl"

    sessions = list(load_longmemeval_s(args.slice))
    have = _done_ids(judgments_path)
    todo = [s for s in sessions if s.session_id not in have]
    if args.limit > 0:
        todo = todo[: args.limit]

    judge_cfg = JudgeBackendConfig(
        backend="openai_compatible",
        model_id=args.judge_model,
        openai_base_url=args.judge_base_url,
        openai_api_key_env=("OPENROUTER_API_KEY"
                            if os.environ.get("OPENROUTER_API_KEY")
                            else "OPENAI_API_KEY"),
        response_format="json",
    )
    judge_llm = build_judge_backend(judge_cfg)
    grader = LongMemEvalGrader(
        judge_llm=judge_llm,
        cache=JudgmentCache(out / "judge_cache.jsonl"),
        seed=args.seed,
    )

    adapter = make_adapter(args.system)
    name = f"ext_{args.system}"
    print(f"[{name}] slice={args.slice.name} n={len(sessions)} "
          f"done={len(have)} todo_now={len(todo)} answerer={ANSWER_MODEL} "
          f"judge={args.judge_model}")

    errors = 0
    with answers_path.open("a", encoding="utf-8") as ah, \
            judgments_path.open("a", encoding="utf-8") as jh:
        for i, session in enumerate(todo, 1):
            t0 = time.time()
            try:
                adapter.reset(session.session_id)
                n_ingested = ingest_history(adapter, session,
                                            args.max_session_chars)
                native = (adapter.answer_natively(session.question)
                          if getattr(adapter, "answers_natively", False)
                          else None)
                if native is not None:
                    text, p_tok, c_tok = native, 0, 0
                    prompt = "[native agent answer]"
                else:
                    snippets = adapter.search(session.question, k=args.k)
                    ctx = "\n".join(f"- {s}" for s in snippets) or "- (none)"
                    date = (f"\nQuestion date: {session.question_date}"
                            if session.question_date else "")
                    prompt = (f"Memory snippets:\n{ctx}{date}\n\n"
                              f"Question: {session.question}")
                    text, p_tok, c_tok = _chat(ANSWER_SYSTEM, prompt)
                answer = BaselineAnswer(
                    session_id=session.session_id, text=text,
                    prompt_tokens=p_tok, completion_tokens=c_tok,
                    latency_ms=(time.time() - t0) * 1000.0,
                    raw_prompt=prompt, seed=args.seed,
                    model_id=ANSWER_MODEL, baseline=name,
                    extras={"n_ingested_sessions": n_ingested,
                            "native_answer": native is not None})
                grade = grader.grade(answer, session)
            except Exception as exc:  # noqa: BLE001 - resume later
                errors += 1
                print(f"[{name}] ERROR {session.session_id}: {exc}",
                      file=sys.stderr)
                continue
            ah.write(json.dumps(answer.to_dict(), ensure_ascii=False) + "\n")
            jh.write(json.dumps(grade.to_dict(), ensure_ascii=False) + "\n")
            ah.flush(); jh.flush()
            print(f"[{name}] {i}/{len(todo)} {session.session_id} "
                  f"correct={grade.correct} ({time.time() - t0:.0f}s)")
    adapter.close()

    # rebuild the report from ALL judgments on disk (resume-safe)
    grades = []
    for line in judgments_path.open(encoding="utf-8"):
        if line.strip():
            d = json.loads(line)
            grades.append(GradeResult(**{
                k: d[k] for k in ("session_id", "competency", "correct",
                                  "judge_score", "judge_rationale",
                                  "judge_model_id", "predicted", "gold",
                                  "prompt_tokens", "completion_tokens",
                                  "latency_ms", "used_fallback") if k in d}))
    report = build_eval_report(baseline_name=name,
                               judge_model_id=grader.judge_model_id,
                               grades=grades, n_bootstrap=args.n_bootstrap,
                               bootstrap_seed=args.seed)
    (out / "report.json").write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8")
    print(f"[{name}] {len(grades)}/{len(sessions)} graded  "
          f"acc={report.overall_accuracy:.3f}  -> {out / 'report.json'}")
    if errors:
        print(f"[{name}] {errors} errors — re-run the same command to resume")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
