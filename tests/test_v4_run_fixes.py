"""Regression tests for the v4-run (lme_m 100-129) failure-analysis fixes.

Each test encodes one observed failure from
runs/lme_m_openrouter_qwen_gemma_minilm_100_129_seed0_v4 and pins the fixed
behavior:

1. gold-token-guard false negatives (judge layer) — sessions 3b6f954b,
   4100d0a0, 488d3006, 5025383b.
2. WORK/FINAL two-stage answer parsing — sessions 37f165cf, 4dfccbf7 (the
   no-CoT 'Unknown' failures).
3. compute-intent classifier gaps — sessions 4dfccbf7, 37f165cf.
4. conflict-block misleading verdict — session 41698283.
"""

from __future__ import annotations

from dataclasses import dataclass

from ask.controller.computation import (
    ComputeIntent,
    RetrievedEvidence,
    classify_compute_intent,
    compute_answer,
)
from ask.eval.longmemeval import LongMemEvalGrader, LongMemEvalSession
from ask.pipeline.orchestrator import (
    _conflict_block,
    _extract_final_answer,
)

# --------------------------------------------------------------------- #
# Helpers                                                                #
# --------------------------------------------------------------------- #


@dataclass
class _Resp:
    text: str
    prompt_tokens: int = 10
    completion_tokens: int = 5
    latency_ms: float = 1.0
    model_id: str = "fake-judge"


class _JudgeLLM:
    """Scripted judge; records whether it was called."""

    model_id = "fake-judge"

    def __init__(self, verdict_text: str = '{"correct": true, "rationale": "ok"}'):
        self.verdict_text = verdict_text
        self.calls = 0

    def generate(self, prompt, *, max_new_tokens, temperature, seed):
        self.calls += 1
        return _Resp(text=self.verdict_text)


@dataclass
class _Answer:
    session_id: str
    text: str
    prompt_tokens: int = 42
    completion_tokens: int = 7
    latency_ms: float = 12.0


def _session(sid: str, gold: str, competency: str = "single-session-user") -> LongMemEvalSession:
    return LongMemEvalSession(
        session_id=sid,
        turns=(),
        question="q?",
        gold_answer=gold,
        competency=competency,
        supporting_session_ids=(),
    )


class _StaticItem:
    def __init__(self, text: str, timestamp: str, role: str = "user"):
        self.text = text
        self.timestamp = timestamp
        self.role = role
        self.session_id = "s"
        self.turn_idx = 0


class _StaticHit:
    def __init__(self, text: str, timestamp: str):
        self.item = _StaticItem(text, timestamp)
        self.score = 0.5
        self.rank = 0


# --------------------------------------------------------------------- #
# 1. gold-token-guard exemptions                                         #
# --------------------------------------------------------------------- #


def test_guard_subset_prediction_defers_to_judge() -> None:
    """v4 sessions 3b6f954b / 4100d0a0 / 488d3006: prediction ⊆ gold."""
    for gold, pred in [
        ("University of Melbourne in Australia", "University of Melbourne"),
        ("A mix of Irish and Italian", "Irish and Italian"),
        ("The GR-90 trail.", "GR-90"),
    ]:
        judge = _JudgeLLM()
        grader = LongMemEvalGrader(judge_llm=judge)
        grade = grader.grade(_Answer("s", pred), _session("s", gold))
        assert judge.calls == 1, f"guard hard-rejected subset pred {pred!r}"
        assert grade.correct is True


def test_guard_morphological_variant_defers_to_judge() -> None:
    """v4 session 5025383b: 'photos' should cover gold 'photography'."""
    judge = _JudgeLLM()
    grader = LongMemEvalGrader(judge_llm=judge)
    grade = grader.grade(
        _Answer("s", "editing my photos in Lightroom and cooking"),
        _session("s", "photography and cooking"),
    )
    assert judge.calls == 1
    assert grade.correct is True


def test_guard_still_rejects_numeric_mismatch_without_judge() -> None:
    """True positives stay: off-by-one counts and wrong numeric values."""
    for gold, pred in [("3", "2"), ("5", "4"), ("a 70-200mm zoom lens", "Sony 24-70mm f/2.8")]:
        judge = _JudgeLLM()
        grader = LongMemEvalGrader(judge_llm=judge)
        grade = grader.grade(_Answer("s", pred), _session("s", gold))
        assert judge.calls == 0, f"{pred!r} vs {gold!r} should hard-reject"
        assert grade.correct is False
        assert "[gold-token-guard]" in grade.judge_rationale


def test_guard_still_rejects_wrong_sibling_value() -> None:
    """Lexical sibling mismatches defer to the semantic judge."""
    judge = _JudgeLLM('{"correct": false, "rationale": "wrong rice type"}')
    grader = LongMemEvalGrader(judge_llm=judge)
    grade = grader.grade(
        _Answer("s", "The favorite rice is long-grain rice."),
        _session("s", "Japanese short-grain rice"),
    )
    assert judge.calls == 1
    assert grade.correct is False


def test_guard_defers_date_alias_to_semantic_judge() -> None:
    judge = _JudgeLLM()
    grader = LongMemEvalGrader(judge_llm=judge)

    grade = grader.grade(
        _Answer("s", "Valentine's Day"),
        _session("s", "February 14th"),
    )

    assert judge.calls == 1
    assert grade.correct is True


# --------------------------------------------------------------------- #
# 2. WORK/FINAL answer parsing                                           #
# --------------------------------------------------------------------- #


def test_extract_final_answer_parses_final_line() -> None:
    text = (
        "WORK:\n"
        "- novel finished in March: 416 pages (session a, 2023/05/20)\n"
        "- novel finished in January: 440 pages (session b, 2023/05/21)\n"
        "- 416 + 440 = 856\n"
        "FINAL: 856"
    )
    assert _extract_final_answer(text) == "856"


def test_extract_final_answer_variants() -> None:
    assert _extract_final_answer("FINAL ANSWER: $65") == "$65"
    assert _extract_final_answer("**FINAL: five tops**") == "five tops"
    assert _extract_final_answer("final: Unknown") == "Unknown"
    # Last FINAL wins if the scaffold is echoed mid-reasoning.
    assert (
        _extract_final_answer("FINAL: <short answer>\nWORK: recheck\nFINAL: 24 days") == "24 days"
    )


def test_extract_final_answer_fallbacks() -> None:
    # Bare short answer without scaffold passes through.
    assert _extract_final_answer("12") == "12"
    # Multi-line completion without a FINAL line: last non-empty line.
    assert _extract_final_answer("some reasoning here\nmore\n856") == "856"
    assert _extract_final_answer("") == ""


# --------------------------------------------------------------------- #
# 3. compute-intent classifier gaps                                      #
# --------------------------------------------------------------------- #


def test_days_had_passed_since_is_date_diff() -> None:
    q = (
        "How many days had passed since I started taking ukulele lessons when "
        "I decided to take my acoustic guitar to the guitar tech for servicing?"
    )
    assert classify_compute_intent(q) is ComputeIntent.DATE_DIFF


def test_implicit_sum_over_counted_set() -> None:
    q = "What was the page count of the two novels I finished in January and March?"
    assert classify_compute_intent(q) is ComputeIntent.NUMERIC_SUM


def test_how_many_window_still_counts() -> None:
    assert (
        classify_compute_intent("How many plants did I acquire in the last month?")
        is ComputeIntent.COUNT_EVENTS
    )


def test_between_date_diff_unchanged() -> None:
    assert (
        classify_compute_intent("How many days between my trip to Paris and my trip to Rome?")
        is ComputeIntent.DATE_DIFF
    )


def test_date_diff_distinguishes_start_from_finish_for_same_title() -> None:
    question = (
        "How many days passed between the day I finished reading 'The Nightingale' "
        "and the day I started reading 'The Hitchhiker's Guide to the Galaxy'?"
    )
    evidence = [
        RetrievedEvidence(
            "nightingale-finish",
            0,
            "user",
            "I just finished reading The Nightingale today.",
            "2022/01/15 (Sat) 23:51",
        ),
        RetrievedEvidence(
            "hitchhiker-finish",
            0,
            "user",
            "I finished reading The Hitchhiker's Guide to the Galaxy today.",
            "2021/12/16 (Thu) 05:53",
        ),
        RetrievedEvidence(
            "hitchhiker-start",
            0,
            "user",
            "I started reading The Hitchhiker's Guide to the Galaxy today.",
            "2022/01/14 (Fri) 08:00",
        ),
    ]

    computed = compute_answer(question, evidence)

    assert computed is not None
    assert computed.answer == "1 day"
    assert [item.session_id for item in computed.evidence] == [
        "nightingale-finish",
        "hitchhiker-start",
    ]


def test_singular_week_ago_is_relative_and_prefers_matching_action() -> None:
    question = "Which book did I finish a week ago?"
    evidence = [
        RetrievedEvidence(
            "started-book",
            0,
            "user",
            "I started reading The Silent Patient today.",
            "2023/05/23 (Tue) 10:00",
            score=0.9,
        ),
        RetrievedEvidence(
            "finished-book",
            0,
            "user",
            "I finished reading The Nightingale today.",
            "2023/05/22 (Mon) 10:00",
            score=0.8,
        ),
    ]

    assert classify_compute_intent(question) is ComputeIntent.RELATIVE_TIME
    computed = compute_answer(question, evidence, question_date="2023/05/30 (Tue) 10:00")

    assert computed is not None
    assert computed.intent is ComputeIntent.RELATIVE_TIME
    assert computed.evidence[0].session_id == "finished-book"


def test_relative_purchase_treats_got_my_own_as_buy_action() -> None:
    question = "What did I buy four weeks ago?"
    evidence = [
        RetrievedEvidence(
            "competition-chat",
            0,
            "user",
            "I discussed ideas for the sculpture competition today.",
            "2023/03/04 (Sat) 10:00",
            score=0.95,
        ),
        RetrievedEvidence(
            "tool-purchase",
            2,
            "user",
            "I got my own set of sculpting tools today.",
            "2023/03/04 (Sat) 16:28",
            score=0.8,
        ),
    ]

    computed = compute_answer(question, evidence, question_date="2023/04/01 (Sat) 06:39")

    assert computed is not None
    assert computed.intent is ComputeIntent.RELATIVE_TIME
    assert computed.evidence[0].session_id == "tool-purchase"


def test_total_of_two_labeled_statistics_is_summed_exactly() -> None:
    question = "What was the total number of goals and assists I had during the tournament?"
    evidence = [
        RetrievedEvidence(
            "match-summary",
            0,
            "user",
            "Across the tournament I scored 3 goals and recorded 2 assists.",
            "2023/05/22 (Mon) 10:00",
            score=0.9,
        )
    ]

    computed = compute_answer(question, evidence)

    assert computed is not None
    assert computed.intent is ComputeIntent.NUMERIC_SUM
    assert computed.answer == "5"
    assert computed.safe_to_bypass_llm is True
    assert {item.event_label for item in computed.evidence} == {"goals", "assists"}


def test_total_of_two_labeled_statistics_accepts_spelled_number() -> None:
    question = "What was the total number of goals and assists I had during the tournament?"
    evidence = [
        RetrievedEvidence(
            "match-summary",
            0,
            "user",
            "Across the tournament I scored 3 goals and recorded two assists.",
            "2023/05/22 (Mon) 10:00",
            score=0.9,
        )
    ]

    computed = compute_answer(question, evidence)

    assert computed is not None
    assert computed.intent is ComputeIntent.NUMERIC_SUM
    assert computed.answer == "5"
    assert computed.safe_to_bypass_llm is True


def test_years_older_uses_two_explicit_relational_ages() -> None:
    question = "How many years older is my grandma than me?"
    evidence = [
        RetrievedEvidence(
            "self-age",
            2,
            "user",
            "Do you think 32 is considered young or old in the grand scheme of things?",
            "2024/02/05 (Mon) 08:13",
            score=0.9,
        ),
        RetrievedEvidence(
            "grandma-age",
            0,
            "user",
            "My grandma's 75th birthday celebration was really inspiring.",
            "2024/02/05 (Mon) 09:14",
            score=0.9,
        ),
    ]

    assert classify_compute_intent(question) is ComputeIntent.NUMERIC_DIFF
    computed = compute_answer(question, evidence)

    assert computed is not None
    assert computed.intent is ComputeIntent.NUMERIC_DIFF
    assert computed.answer == "43"
    assert computed.confidence >= 0.9
    assert computed.safe_to_bypass_llm is True
    assert {item.event_label for item in computed.evidence} == {"self age", "grandma age"}


def test_years_older_does_not_subtract_unrelated_numbers() -> None:
    question = "How many years older is my grandma than me?"
    evidence = [
        RetrievedEvidence(
            "grandma-age",
            0,
            "user",
            "My grandma is 75 years old and owns 12 antique brooches.",
            "2024/02/05 (Mon) 09:14",
            score=0.9,
        ),
        RetrievedEvidence(
            "distractor",
            0,
            "user",
            "I bought 32 candles for the party.",
            "2024/02/05 (Mon) 09:14",
            score=0.9,
        ),
    ]

    assert compute_answer(question, evidence) is None


# --------------------------------------------------------------------- #
# 4. conflict block                                                      #
# --------------------------------------------------------------------- #


def test_conflict_block_never_asserts_a_winner() -> None:
    block = _conflict_block(
        [
            _StaticHit(
                "I got pre-approved for $350,000 from Wells Fargo for my mortgage.",
                "2023/08/11 (Fri) 00:01",
            ),
            _StaticHit(
                "Remember when I got pre-approved for $400,000 from Wells Fargo for my mortgage?",
                "2023/11/30 (Thu) 00:36",
            ),
        ]
    )
    assert "DIFFERING DATED VALUES" in block
    assert "Most recent" not in block
    assert "correct, current one" not in block


def test_conflict_block_question_gate_suppresses_off_topic_pairs() -> None:
    """v4 session 41698283: numeric pairs unrelated to the question must not
    surface (the old block declared an off-cluster older value 'current')."""
    hits = [
        _StaticHit(
            "I got pre-approved for $350,000 from Wells Fargo for my mortgage.",
            "2023/08/11 (Fri) 00:01",
        ),
        _StaticHit(
            "Remember when I got pre-approved for $400,000 from Wells Fargo for my mortgage?",
            "2023/11/30 (Thu) 00:36",
        ),
    ]
    block = _conflict_block(hits, question="What type of camera lens did I purchase most recently?")
    assert block == ""
    # With a matching question the group still surfaces.
    block2 = _conflict_block(hits, question="How much was I pre-approved for on my mortgage?")
    assert "DIFFERING DATED VALUES" in block2
