"""Regression tests for the 500-question + LongMemEval-M scale-up hardening.

These pin the fixes made to the eval harness (runner + loader + grader) when
preparing it for the full 500-question LongMemEval-S run and the larger
LongMemEval-M release, plus the truncation/judge-validity fixes recommended by
the M4-W13 benchmark analysis (Memory_Systems_Benchmark_Analysis):

  * loader: competency canonicalization, exact full-set slicing, JSON-array
    streaming, and JSONL conversion;
  * grader: numeric/currency normalization (no false-reject of "$1300" vs
    "$1,300"), degenerate-answer detection, and answerable-only / abstention
    decomposition in the report;
  * pipeline: the answer-retry trigger now fires on a bare-symbol "$".
"""

from __future__ import annotations

import json
from pathlib import Path

from ksa.baselines.base import BaselineAnswer
from ksa.data.longmemeval import (
    LongMemEvalSession,
    LongMemEvalTurn,
    canonical_competency,
    convert_to_jsonl,
    iter_longmemeval_s,
    sample_slice,
)
from ksa.eval.longmemeval import (
    LongMemEvalGrader,
    _normalize_text,
    build_eval_report,
    looks_degenerate_answer,
)
from ksa.inference.llm import LLMResponse
from ksa.pipeline.orchestrator import _answer_needs_retry, _looks_degenerate_answer

# --------------------------------------------------------------------- #
# Helpers                                                               #
# --------------------------------------------------------------------- #


class _ScriptedJudge:
    """Judge LLM returning a fixed correctness verdict; counts calls."""

    model_id = "scripted-judge-v0"

    def __init__(self, correct: bool) -> None:
        self._payload = {"correct": correct, "rationale": "scripted"}
        self.calls = 0

    def generate(self, prompt: str, *, max_new_tokens: int = 256,
                 temperature: float = 0.0, seed: int = 0,
                 stop: list[str] | None = None) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            text=json.dumps(self._payload),
            prompt_tokens=len(prompt.split()),
            completion_tokens=5,
            latency_ms=0.0,
            seed=seed,
            temperature=temperature,
            model_id=self.model_id,
        )


def _answer(sid: str, text: str) -> BaselineAnswer:
    return BaselineAnswer(
        session_id=sid, text=text, prompt_tokens=10, completion_tokens=2,
        latency_ms=1.0, raw_prompt="<p>", baseline="b",
    )


def _session(sid: str, *, competency: str, gold: str) -> LongMemEvalSession:
    return LongMemEvalSession(
        session_id=sid, turns=(LongMemEvalTurn(role="user", content="x"),),
        question="Q?", gold_answer=gold, competency=competency,
    )


def _cleaned_record(qid: str, qtype: str, answer: str) -> dict:
    return {
        "question_id": qid,
        "question_type": qtype,
        "question": "How much?",
        "answer": answer,
        "answer_session_ids": ["h1"],
        "haystack_session_ids": ["h1"],
        "haystack_sessions": [[{"role": "user", "content": "hi"}]],
    }


# --------------------------------------------------------------------- #
# Loader: competency canonicalization                                  #
# --------------------------------------------------------------------- #


def test_canonical_competency_tolerates_case_and_underscores():
    assert canonical_competency("Knowledge_Update") == "knowledge-update"
    assert canonical_competency("multi_session") == "multi-session"
    assert canonical_competency("  TEMPORAL-REASONING  ") == "temporal-reasoning"
    assert canonical_competency("single-session-user") == "single-session-user"


def test_cleaned_record_with_underscore_qtype_loads(tmp_path: Path):
    rec = _cleaned_record("q1_abs", "knowledge_update", "tea")
    p = tmp_path / "rows.jsonl"
    p.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    sessions = list(iter_longmemeval_s(p))
    assert len(sessions) == 1
    # underscore label canonicalized -> no ValueError from the dataclass
    assert sessions[0].competency == "knowledge-update"


# --------------------------------------------------------------------- #
# Loader: full-set slicing (the 500-question case)                     #
# --------------------------------------------------------------------- #


def _pool(n_multi: int, n_know: int) -> list[LongMemEvalSession]:
    pool = [_session(f"m{i:03d}", competency="multi-session", gold="g") for i in range(n_multi)]
    pool += [_session(f"k{i:03d}", competency="knowledge-update", gold="g") for i in range(n_know)]
    return pool


def test_sample_slice_full_set_returns_all_sorted():
    pool = _pool(7, 3)
    full = sample_slice(pool, n=len(pool), seed=0)
    assert len(full) == 10
    assert [s.session_id for s in full] == sorted(s.session_id for s in pool)


def test_sample_slice_oversize_still_raises():
    pool = _pool(7, 3)
    raised = False
    try:
        sample_slice(pool, n=len(pool) + 1, seed=0)
    except ValueError:
        raised = True
    assert raised, "oversize request must still raise"


def test_sample_slice_subset_is_exact_size():
    pool = _pool(40, 10)
    sub = sample_slice(pool, n=20, seed=0)
    assert len(sub) == 20
    # determinism: same seed -> identical ids
    assert [s.session_id for s in sub] == [s.session_id for s in sample_slice(pool, n=20, seed=0)]


# --------------------------------------------------------------------- #
# Loader: JSON-array streaming + JSONL conversion (LongMemEval-M path) #
# --------------------------------------------------------------------- #


def test_json_array_input_is_read(tmp_path: Path):
    arr = [_cleaned_record("q1", "multi-session", "5"),
           _cleaned_record("q2", "temporal-reasoning", "Monday")]
    p = tmp_path / "release.json"
    p.write_text(json.dumps(arr), encoding="utf-8")  # top-level array shape
    sessions = list(iter_longmemeval_s(p))
    assert {s.session_id for s in sessions} == {"q1", "q2"}


def test_convert_to_jsonl_roundtrips(tmp_path: Path):
    arr = [_cleaned_record("q1", "multi-session", "5"),
           _cleaned_record("q2", "knowledge_update", "tea")]
    src = tmp_path / "release.json"
    src.write_text(json.dumps(arr), encoding="utf-8")
    dst = tmp_path / "release.jsonl"
    n = convert_to_jsonl(src, dst)
    assert n == 2
    # JSONL fast path reload preserves ids + canonical competencies
    reloaded = list(iter_longmemeval_s(dst))
    assert {s.session_id for s in reloaded} == {"q1", "q2"}
    assert {s.competency for s in reloaded} == {"multi-session", "knowledge-update"}


# --------------------------------------------------------------------- #
# Grader: numeric/currency normalization                               #
# --------------------------------------------------------------------- #


def test_normalize_text_collapses_thousands_separators():
    assert _normalize_text("$1,300") == _normalize_text("$1300") == {"1300"}
    assert _normalize_text("$400,000") == _normalize_text("$400000") == {"400000"}
    # a comma NOT between digits is still treated as ordinary punctuation, and
    # "1,2" (single digits, not a thousands group) collapses to one token too.
    assert _normalize_text("12,345") == {"12345"}
    assert "300" not in _normalize_text("$1,300")  # not split into 1 + 300


def test_currency_prediction_not_false_rejected_by_token_guard():
    """gold '$1,300' vs pred '$1300' must NOT be hard-rejected by the guard.

    Before the numeric-normalization fix the gold-token-guard rejected this as
    "1/2 gold tokens missing: ['1', '300']". Now both normalize to {1300}, so it
    reaches the LLM judge instead of being auto-failed.
    """
    judge = _ScriptedJudge(correct=True)
    grader = LongMemEvalGrader(judge_llm=judge)
    res = grader.grade(_answer("s", "$1300"), _session("s", competency="multi-session", gold="$1,300"))
    assert res.correct is True
    assert "gold-token-guard" not in res.judge_rationale
    assert judge.calls == 1  # the judge was actually consulted (not short-circuited to reject)


def test_bare_symbol_answer_is_still_wrong_and_degenerate():
    judge = _ScriptedJudge(correct=True)  # even a lenient judge must not save "$"
    grader = LongMemEvalGrader(judge_llm=judge)
    res = grader.grade(_answer("s", "$"), _session("s", competency="knowledge-update", gold="$400,000"))
    assert res.correct is False  # gold-token-guard correctly rejects the empty-content answer
    assert looks_degenerate_answer("$") is True


# --------------------------------------------------------------------- #
# Grader: degenerate-answer detection                                   #
# --------------------------------------------------------------------- #


def test_looks_degenerate_answer_classification():
    for bad in ("$", "...", "-", "  $  ", "%"):
        assert looks_degenerate_answer(bad) is True, bad
    for ok in ("3", "A", "", "$5", "3.5", "Unknown", "no"):
        assert looks_degenerate_answer(ok) is False, ok


def test_pipeline_degenerate_helper_matches_eval_helper():
    for t in ("$", "3", "", "A", "...", "$5"):
        assert _looks_degenerate_answer(t) == looks_degenerate_answer(t), t


# --------------------------------------------------------------------- #
# Pipeline: answer-retry trigger fires on bare-symbol "$"               #
# --------------------------------------------------------------------- #


def test_answer_needs_retry_fires_on_unknown_empty_and_bare_symbol():
    assert _answer_needs_retry("Unknown") is True
    assert _answer_needs_retry("") is True
    assert _answer_needs_retry("   ") is True
    assert _answer_needs_retry("$") is True          # the 852ce960 truncation case
    assert _answer_needs_retry("...") is True
    # genuine answers do NOT trigger a retry
    assert _answer_needs_retry("3") is False
    assert _answer_needs_retry("$1,300") is False
    assert _answer_needs_retry("Pennsylvania") is False


# --------------------------------------------------------------------- #
# Grader/report: answerable-only + abstention decomposition             #
# --------------------------------------------------------------------- #


def test_build_eval_report_decomposes_answerable_and_abstention():
    judge = _ScriptedJudge(correct=True)
    grader = LongMemEvalGrader(judge_llm=judge)
    grades = [
        grader.grade(_answer("a", "$1300"), _session("a", competency="multi-session", gold="$1,300")),
        grader.grade(_answer("b", "$"), _session("b", competency="knowledge-update", gold="$400,000")),
        grader.grade(
            _answer("c", "Unknown"),
            _session("c", competency="knowledge-update",
                     gold="The information provided is not enough. You mentioned X but not Y."),
        ),
    ]
    report = build_eval_report(baseline_name="b", judge_model_id="j", grades=grades, n_bootstrap=200)
    d = report.to_dict()
    assert d["answerable_n"] == 2
    assert abs(d["answerable_accuracy"] - 0.5) < 1e-9   # a correct, b wrong
    assert d["abstention_n"] == 1
    assert d["abstention_accuracy"] == 1.0              # c abstains correctly
    assert d["n_degenerate_answers"] == 1               # the bare "$"
    # markdown renders the new lines without raising
    md = report.summarize_markdown()
    assert "Answerable-only accuracy" in md
    assert "Degenerate answers" in md
