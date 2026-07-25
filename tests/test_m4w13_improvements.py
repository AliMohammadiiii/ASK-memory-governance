"""Unit tests for the post-70% m4w13 failure-bucket fixes.

Each test reproduces one of the 15 graded failures from the
runs/m4w13_50_t4_quality controller run (2026-06-10) with the *actual* slice
evidence text, and asserts the new deterministic behavior:

  - duration/count/sum solvers for distributed "how many" questions
  - relative-date parsing for "last weekend/week/month"
  - chronological-order tie handling (never bypass on a coin flip)
  - GPA averaging anchored to the asked-about degrees
  - relative-time window hints for "what ... N weeks ago" questions
  - raw-user-context retrieval, query augmentation, conflict block, and the
    deterministic numeric supersede rule in the orchestrator
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np

from ask.classifier import RelationOutput
from ask.controller.computation import (
    ComputeIntent,
    RetrievedEvidence,
    classify_compute_intent,
    compute_answer,
)
from ask.controller.temporal import parse_dates
from ask.data.longmemeval import LongMemEvalSession, LongMemEvalTurn
from ask.extraction import ExtractionOutput
from ask.inference.fake import FakeLLM
from ask.pipeline import ControllerOrchestrator
from ask.pipeline.orchestrator import (
    _conflict_block,
    _same_slot_numeric_conflict,
)


def _ev(session_id: str, text: str, timestamp: str, role: str = "user", turn_idx: int = 0):
    return RetrievedEvidence(
        session_id=session_id, turn_idx=turn_idx, role=role, text=text, timestamp=timestamp
    )


# --------------------------------------------------------------------------- #
# temporal.parse_dates                                                         #
# --------------------------------------------------------------------------- #


def test_parse_dates_day_list_of_month() -> None:
    dates = parse_dates(
        "a 2-day workshop I attended on the 17th and 18th of April",
        context_year=2023,
    )
    assert date(2023, 4, 17) in dates
    assert date(2023, 4, 18) in dates


def test_parse_dates_month_day_list() -> None:
    dates = parse_dates("I visited on April 3 and 5", context_year=2023)
    assert date(2023, 4, 3) in dates
    assert date(2023, 4, 5) in dates


# --------------------------------------------------------------------------- #
# computation solvers (failure-bucket reproductions)                           #
# --------------------------------------------------------------------------- #


def test_intent_duration_hours_routes_to_count() -> None:
    q = "How many hours of jogging and yoga did I do last week?"
    assert classify_compute_intent(q) == ComputeIntent.COUNT_EVENTS


def test_duration_sum_excludes_habit_statements() -> None:
    # 7024f17c: gold '0.5 hours' — the 2-hour yoga line is a lapsed habit.
    result = compute_answer(
        "How many hours of jogging and yoga did I do last week?",
        [
            _ev(
                "a1",
                "Can you help me track my workouts? I went for a 30-minute jog "
                "around the neighborhood on Saturday, and I'd like to keep a "
                "record of that.",
                "2023/05/20 (Sat) 18:15",
            ),
            _ev(
                "a2",
                "By the way, I used to practice yoga three times a week, each "
                "time for 2 hours, but I've been slacking off for this month.",
                "2023/05/22 (Mon) 23:10",
            ),
        ],
    )
    assert result is not None
    assert result.safe_to_bypass_llm
    assert result.answer == "0.5 hours"


def test_distinct_day_count_april_workshops() -> None:
    # 10d9b85a: gold '3 days' — Apr 10 lecture + Apr 17-18 workshop.
    result = compute_answer(
        "How many days did I spend attending workshops, lectures, and conferences in April?",
        [
            _ev(
                "b1",
                "I recently attended a lecture on sustainable development at "
                "the public library on the 10th of April.",
                "2023/05/01 (Mon) 16:19",
            ),
            _ev(
                "b2",
                "I learned about it in a 2-day workshop I attended on the 17th "
                "and 18th of April.",
                "2023/05/01 (Mon) 20:24",
            ),
        ],
    )
    assert result is not None
    assert result.safe_to_bypass_llm
    assert result.answer == "3 days"


def test_missed_event_count_march_runs() -> None:
    # 21d02d0d: gold '2' — two distinct missed March fun-run dates.
    result = compute_answer(
        "How many fun runs did I miss in March due to work commitments?",
        [
            _ev(
                "c1",
                "I've been pretty busy with work lately and missed a few "
                "events, including a 5K fun run on March 26th.",
                "2023/04/26 (Wed) 01:52",
            ),
            _ev(
                "c2",
                "I was able to attend most of the weekly 5K fun runs at the "
                "local park, except for the run on March 12th.",
                "2023/04/26 (Wed) 15:47",
            ),
        ],
    )
    assert result is not None
    assert result.safe_to_bypass_llm
    assert result.answer == "2"


def test_currency_sum_matches_each_item_phrase() -> None:
    # f0e564bc: gold '$1,300' = $800 handbag + $500 skincare.
    result = compute_answer(
        "What is the total amount I spent on the designer handbag and high-end skincare products?",
        [
            _ev(
                "d1",
                "I recently treated myself to a Coach handbag, which costed "
                "$800. I'm really loving the quality.",
                "2023/05/23 (Tue) 21:13",
            ),
            _ev(
                "d2",
                "skincare routines: I've recently invested $500 in some "
                "high-end products during the Nordstrom anniversary sale.",
                "2023/05/28 (Sun) 02:12",
            ),
            _ev("d3", "I bought store-brand coffee for $4.", "2023/05/29 (Mon) 01:00"),
        ],
    )
    assert result is not None
    assert result.safe_to_bypass_llm
    assert result.answer == "$1,300"


def test_chronological_order_parses_last_weekend() -> None:
    # gpt4_2f584639: gold 'the photo album for my mom' (two weeks ago beats
    # last weekend). Both events are only relative-dated.
    result = compute_answer(
        "Which gift did I buy first, the necklace for my sister or the photo album for my mom?",
        [
            _ev(
                "e1",
                "I already got her a beautiful necklace from Tiffany's last "
                "weekend, which I think she'll love.",
                "2023/05/30 (Tue) 09:00",
            ),
            _ev(
                "e2",
                "I ordered a customized photo album from Shutterfly two weeks "
                "ago for my mom's anniversary.",
                "2023/05/30 (Tue) 03:18",
            ),
        ],
    )
    assert result is not None
    assert result.safe_to_bypass_llm
    assert "photo album" in result.answer


def test_chronological_order_tie_never_bypasses() -> None:
    result = compute_answer(
        "Which did I visit first, the museum or the aquarium?",
        [
            _ev("t1", "I visited the museum and loved it.", "2023/05/30 (Tue) 09:00"),
            _ev("t2", "The aquarium trip was fun.", "2023/05/30 (Tue) 03:18"),
        ],
    )
    assert result is not None
    assert not result.safe_to_bypass_llm
    assert "tie" in result.computation


def test_relative_window_hint_for_what_questions() -> None:
    # eac54add: gold 'I signed a contract with my first client.' The solver
    # cannot answer a WHAT question, but it must point the LLM at the right
    # calendar window (ref 2023-03-29 minus four weeks ≈ 2023-03-01).
    result = compute_answer(
        "What was the significant buisiness milestone I mentioned four weeks ago?",
        [
            _ev(
                "f1",
                "I just signed a contract with my first client today, and I "
                "want to make sure I'm covering all my bases.",
                "2023/03/01 (Wed) 02:43",
            ),
            _ev("f2", "I just launched my website.", "2023/02/10 (Fri) 02:03"),
            _ev("f3", "unrelated recent chat", "2023/03/29 (Wed) 10:00"),
        ],
    )
    assert result is not None
    assert not result.safe_to_bypass_llm
    assert "2023-03-01" in result.computation
    assert "signed a contract" in result.computation


def test_order_timeline_hint_lists_dated_events() -> None:
    # gpt4_45189cb4: no extractable option phrases → dated timeline hint.
    result = compute_answer(
        "What is the order of the sports events I watched in January?",
        [
            _ev(
                "g1",
                "I just went to a NBA game there with my coworkers today.",
                "2023/01/05 (Thu) 16:31",
            ),
            _ev(
                "g2",
                "I'm still riding high from the College Football National "
                "Championship game I watched with my family at home yesterday.",
                "2023/01/15 (Sun) 00:46",
            ),
            _ev(
                "g3",
                "I'm still on a high from watching the Chiefs win the NFL "
                "playoffs game last weekend.",
                "2023/01/22 (Sun) 12:52",
            ),
        ],
    )
    assert result is not None
    assert not result.safe_to_bypass_llm
    lines = result.computation.splitlines()
    assert lines[1].startswith("- 2023-01-05")
    assert lines[2].startswith("- 2023-01-14")
    assert lines[3].startswith("- 2023-01-21")


def test_gpa_average_pairs_degrees_and_ignores_requirements() -> None:
    # 8cf4d046: gold '3.83' — pair the user's two degree GPAs, skip the
    # program-requirement 3.5 that previously poisoned the average.
    result = compute_answer(
        "What is the average GPA of my undergraduate and graduate studies?",
        [
            _ev(
                "h1",
                "I graduated with a First-Class distinction, with an overall "
                "percentage of 83%, equivalent to a GPA of 3.86 out of 4.0.",
                "2023/05/30 (Tue) 04:37",
            ),
            _ev(
                "h2",
                "I recently completed my Master's degree in Data Science, "
                "where my GPA was 3.8.",
                "2023/05/30 (Tue) 04:37",
            ),
            _ev(
                "h3",
                "Most programs require a minimum GPA of 3.5 for admission.",
                "2023/05/24 (Wed) 10:17",
                role="assistant",
            ),
        ],
    )
    assert result is not None
    assert result.safe_to_bypass_llm
    assert result.answer == "3.83"


def test_duration_sum_ignores_assistant_advice_and_habit_frequency() -> None:
    # The live retrieval pool contains assistant advice with durations
    # ("arrive 10-15 minutes before yoga class") and extracted habit facts
    # whose 'used to' hedge was dropped — neither is a user event last week.
    result = compute_answer(
        "How many hours of jogging and yoga did I do last week?",
        [
            _ev(
                "a1",
                "I went for a 30-minute jog around the neighborhood on Saturday.",
                "2023/05/20 (Sat) 18:15",
            ),
            _ev(
                "a2",
                "User practices yoga three times a week, each time for 2 hours.",
                "2023/05/22 (Mon) 23:10",
            ),
            _ev(
                "a3",
                "Arrive at least 10-15 minutes before your yoga class starts.",
                "2023/05/23 (Tue) 18:03",
                role="assistant",
            ),
        ],
    )
    assert result is not None
    assert result.safe_to_bypass_llm
    assert result.answer == "0.5 hours"


def test_relative_window_spans_to_newest_session_without_question_date() -> None:
    # eac54add's haystack ends the same day the contract was signed; with no
    # question_date, "four weeks ago" must cover [ref - 4w, ref], not a point
    # four weeks before the newest session.
    result = compute_answer(
        "What was the significant buisiness milestone I mentioned four weeks ago?",
        [
            _ev(
                "f1",
                "I just signed a contract with my first client today.",
                "2023/03/01 (Wed) 02:43",
            ),
            _ev("f2", "I just launched my website.", "2023/02/10 (Fri) 02:03"),
        ],
    )
    assert result is not None
    assert not result.safe_to_bypass_llm
    assert "signed a contract" in result.computation


def test_gpa_average_ambiguous_inputs_never_bypass() -> None:
    result = compute_answer(
        "What is the average GPA of my undergraduate and graduate studies?",
        [
            _ev("h1", "My GPA was 3.2 back then.", "2023/05/01 (Mon) 00:00"),
            _ev("h2", "My GPA is 3.9 now.", "2023/05/02 (Tue) 00:00"),
            _ev("h3", "A friend's GPA of 2.8 surprised me.", "2023/05/03 (Wed) 00:00"),
        ],
    )
    assert result is not None
    assert not result.safe_to_bypass_llm
    assert "3.2" in result.computation and "3.9" in result.computation


# --------------------------------------------------------------------------- #
# orchestrator: conflict block + deterministic numeric supersede               #
# --------------------------------------------------------------------------- #


def test_same_slot_numeric_conflict_detects_mortgage_update() -> None:
    older = "I got pre-approved for $350,000 from Wells Fargo for my mortgage."
    newer = "Remember when I got pre-approved for $400,000 from Wells Fargo for my mortgage?"
    assert _same_slot_numeric_conflict(older, newer)
    # Different slots: shared tokens stay below the anchor threshold.
    assert not _same_slot_numeric_conflict(
        "I spent $40 on groceries at the market.",
        "My new headphones cost $90 online.",
    )
    # Same slot, same number: an update without disagreement is no conflict.
    assert not _same_slot_numeric_conflict(older, older)


class _StaticItem:
    def __init__(self, text: str, timestamp: str) -> None:
        self.text = text
        self.timestamp = timestamp
        self.role = "user"
        self.session_id = "s"
        self.turn_idx = 0


class _StaticHit:
    def __init__(self, text: str, timestamp: str) -> None:
        self.item = _StaticItem(text, timestamp)
        self.score = 0.9
        self.rank = 0


def test_conflict_block_orders_newest_first() -> None:
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
    # v4-run rewrite (session 41698283): neutral header, newest first, and no
    # assertive "Most recent (...) is the correct one" verdict — the greedy
    # pairing could crown an older value when the true newest evidence fell
    # outside the pair, actively injecting a wrong answer.
    assert "DIFFERING DATED VALUES" in block
    assert block.index("2023-11-30") < block.index("2023-08-11")
    assert "Most recent" not in block
    assert "$400,000" in block and "$350,000" in block


def test_conflict_block_empty_without_conflicts() -> None:
    assert (
        _conflict_block(
            [
                _StaticHit("I spent $40 on groceries.", "2023/08/11 (Fri) 00:01"),
                _StaticHit("My headphones cost $90.", "2023/11/30 (Thu) 00:36"),
            ]
        )
        == ""
    )


class _EchoExtractor:
    """Extract the raw user turn as one episodic fact (identity extractor)."""

    def extract(self, turn, window, *, max_new_tokens=512, temperature=0.0, seed=0):
        from ask.extraction import EvidenceSpan, ExtractedItem

        return ExtractionOutput(
            items=[
                ExtractedItem(
                    text=turn["content"],
                    type_guess="episodic_fact",
                    evidence_span=EvidenceSpan(
                        session_id=turn["session_id"],
                        turn_idx=turn["turn_idx"],
                        char_start=0,
                        char_end=len(turn["content"]),
                    ),
                    extraction_confidence=0.95,
                    negation_marker=False,
                    hedge_marker=False,
                )
            ],
            no_extractable_content=False,
        )


class _NoExtractor:
    def extract(self, turn, window, *, max_new_tokens=512, temperature=0.0, seed=0):
        return ExtractionOutput(items=[], no_extractable_content=True, coverage_note="none")


class _CountingIndependentClassifier:
    def __init__(self) -> None:
        self.calls = 0

    def classify(self, candidate, prior, *, max_new_tokens=128, temperature=0.0, seed=0):
        self.calls += 1
        return RelationOutput(
            logical_relation="independent",
            temporal="unknown",
            same_subject=False,
            relation_to_prior_state="unclear",
            stage1_rationale="fake",
            stage2_rationale="fake",
        )


class _ConstantEmbedder:
    """All texts collapse to one direction → cosine similarity 1 everywhere."""

    embedding_dim = 2
    model_id = "fake/constant"

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.tile(np.asarray([[1.0, 0.0]], dtype=np.float32), (len(texts), 1))


def _mk_session(
    session_id: str,
    user_text: str,
    timestamp: str,
    question: str = "What was the amount I was pre-approved for?",
    supporting: tuple[str, ...] = (),
) -> LongMemEvalSession:
    return LongMemEvalSession(
        session_id=session_id,
        turns=(
            LongMemEvalTurn(role="user", content=user_text, timestamp=timestamp),
            LongMemEvalTurn(role="assistant", content="noted", timestamp=timestamp),
        ),
        question=question,
        gold_answer="$400,000",
        competency="knowledge-update",
        supporting_session_ids=tuple(supporting),
    )


def test_deterministic_numeric_supersede_skips_relation_llm(tmp_path: Path) -> None:
    older = _mk_session(
        "s-old",
        "I got pre-approved for $350,000 from Wells Fargo for my mortgage.",
        "2023/08/11 (Fri) 00:01",
    )
    newer = _mk_session(
        "s-new",
        "Remember when I got pre-approved for $400,000 from Wells Fargo for my mortgage?",
        "2023/11/30 (Thu) 00:36",
    )
    current = _mk_session(
        "s-current",
        "Just checking in.",
        "2023/12/01 (Fri) 00:00",
        supporting=("s-old", "s-new"),
    )
    classifier = _CountingIndependentClassifier()
    llm = FakeLLM()
    llm.queue("$400,000")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=_EchoExtractor(),
        classifier=classifier,
        corpus={"s-old": older, "s-new": newer, "s-current": current},
        embedder=_ConstantEmbedder(),
        k=5,
        action_log_path=tmp_path / "log.jsonl",
        prior_top_k=3,
        prior_similarity_threshold=0.45,
        deterministic_numeric_supersede=True,
    )
    answer = orchestrator.answer(current)
    counts = answer.extras["action_counts"]
    assert counts["Supersede"] >= 1
    # The mortgage pair was decided in code. The single LLM call on record
    # comes from the current session's own turn ("Just checking in.") being
    # compared against a prior after the answer was produced.
    assert classifier.calls <= 1
    # The superseded $350k memory must no longer reach the answer prompt.
    assert "$350,000" not in (answer.raw_prompt.split("----- DIALOG -----")[0])


def test_raw_user_context_restores_prefilter_misses(tmp_path: Path) -> None:
    # 86f00804-shaped: the extractor yields nothing (prefilter/extraction
    # miss), but the raw user turn must still reach the answer prompt.
    book = _mk_session(
        "s-book",
        "I'm currently devouring The Seven Husbands of Evelyn Hugo and it's hard to put down!",
        "2023/05/23 (Tue) 11:27",
        question="What book am I currently reading?",
    )
    current = _mk_session(
        "s-current",
        "Any tips for reading more?",
        "2023/06/01 (Thu) 00:00",
        question="What book am I currently reading?",
        supporting=("s-book",),
    )
    llm = FakeLLM()
    llm.queue("The Seven Husbands of Evelyn Hugo")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=_NoExtractor(),
        classifier=_CountingIndependentClassifier(),
        corpus={"s-book": book, "s-current": current},
        embedder=_ConstantEmbedder(),
        k=5,
        include_raw_user_context=True,
    )
    answer = orchestrator.answer(current)
    assert "Evelyn Hugo" in answer.raw_prompt

    # Control: without the flag the fact never reaches the prompt.
    llm2 = FakeLLM()
    llm2.queue("Unknown")
    orchestrator_off = ControllerOrchestrator(
        llm=llm2,
        extractor=_NoExtractor(),
        classifier=_CountingIndependentClassifier(),
        corpus={"s-book": book, "s-current": current},
        embedder=_ConstantEmbedder(),
        k=5,
        include_raw_user_context=False,
    )
    answer_off = orchestrator_off.answer(current)
    assert "Evelyn Hugo" not in answer_off.raw_prompt


def test_query_augmentation_adds_calendar_window_items(tmp_path: Path) -> None:
    # eac54add-shaped: the milestone session is semantically far from the
    # question, but its timestamp sits four weeks before the newest session.
    milestone = _mk_session(
        "s-milestone",
        "I just signed a contract with my first client today.",
        "2023/03/01 (Wed) 02:43",
        question="What was the significant buisiness milestone I mentioned four weeks ago?",
    )
    recent = _mk_session(
        "s-recent",
        "Let's talk about garden landscaping ideas.",
        "2023/03/29 (Wed) 10:00",
        question="What was the significant buisiness milestone I mentioned four weeks ago?",
    )
    current = _mk_session(
        "s-current",
        "hello",
        "2023/03/29 (Wed) 12:00",
        question="What was the significant buisiness milestone I mentioned four weeks ago?",
        supporting=("s-milestone", "s-recent"),
    )

    class _QuestionAverseEmbedder:
        """Question matches the garden session, not the milestone session."""

        embedding_dim = 2
        model_id = "fake/question-averse"

        def embed(self, texts: list[str]) -> np.ndarray:
            rows = []
            for text in texts:
                if "milestone" in text.casefold() or "garden" in text.casefold():
                    rows.append([1.0, 0.0])
                else:
                    rows.append([0.0, 1.0])
            return np.asarray(rows, dtype=np.float32)

    llm = FakeLLM()
    llm.queue("I signed a contract with my first client.")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=_NoExtractor(),
        classifier=_CountingIndependentClassifier(),
        corpus={"s-milestone": milestone, "s-recent": recent, "s-current": current},
        embedder=_QuestionAverseEmbedder(),
        k=1,
        include_raw_user_context=True,
        retrieval_query_augmentation=True,
    )
    answer = orchestrator.answer(current)
    assert "signed a contract with my first client" in answer.raw_prompt
