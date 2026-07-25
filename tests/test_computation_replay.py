"""No-cost replay tests for the computation answerer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ask.controller.computation import RetrievedEvidence, compute_answer
from ask.eval.computation_replay import (
    retrieved_from_prompt,
    simulate_computation_on_slice,
)

SLICE = Path(__file__).resolve().parents[1] / "data/slices/longmemeval_s_cleaned_50_seed0.jsonl"

pytestmark = pytest.mark.skipif(
    not SLICE.exists(),
    reason="optional LongMemEval computation fixture is not redistributed",
)


def test_supporting_oracle_computation_fixtures_without_llm() -> None:
    rows = {
        str(row["session_id"]): row
        for row in simulate_computation_on_slice(SLICE, mode="supporting")
    }

    assert rows["1903aded"]["computed_answer"] == "Transcriptionist"
    assert rows["3fe836c9"]["computed_answer"] == "$25,000"
    assert rows["69fee5aa"]["computed_answer"] == "38"
    assert rows["8c18457d"]["computed_answer"] == "7 days"
    assert rows["8cf4d046"]["computed_answer"] == "3.83"
    assert rows["982b5123"]["computed_answer"] == "five (5) months ago"
    assert rows["f0853d11"]["computed_answer"] == "14 days"
    assert rows["f0e564bc"]["computed_answer"] == "$1,300"
    assert rows["gpt4_4ef30696"]["computed_answer"] == "1 day"
    assert rows["gpt4_65aabe59"]["computed_answer"] == "smart thermostat"

    coupon_answer = str(rows["gpt4_18c2b244"]["computed_answer"])
    assert "Walmart" in coupon_answer
    assert "Ibotta" in coupon_answer
    assert "ShopRite" in coupon_answer
    assert rows["gpt4_18c2b244"]["safe_to_bypass"] is True


def test_haystack_abstention_questions_do_not_bypass() -> None:
    rows = simulate_computation_on_slice(SLICE, mode="haystack")
    abstention_rows = [row for row in rows if str(row["session_id"]).endswith("_abs")]

    assert abstention_rows
    assert all(row["safe_to_bypass"] is False for row in abstention_rows)


def test_retrieved_from_prompt_parses_controller_prompt() -> None:
    raw_prompt = """
----- RETRIEVED MEMORY (top-2 active memory_items by cosine similarity to question) -----
[0.921] USER (session s-a, turn 3, 2023/05/21 (Sun) 17:30): I fixed the fence.
The goats are secure now.
[0.812] ASSISTANT (session s-b, turn 4): 1. Analyst 2. Transcriptionist
----- NORMALIZED EVENT DATES -----
[0.999] USER (session should-not-parse, turn 0): ignored
----- DIALOG -----
USER: Can you answer?
"""

    rows = retrieved_from_prompt(raw_prompt)

    assert len(rows) == 2
    assert rows[0].session_id == "s-a"
    assert rows[0].turn_idx == 3
    assert rows[0].role == "user"
    assert rows[0].timestamp == "2023/05/21 (Sun) 17:30"
    assert rows[0].score == 0.921
    assert "goats are secure" in rows[0].text
    assert rows[1].session_id == "s-b"


def test_simulation_rows_are_json_serializable() -> None:
    rows = simulate_computation_on_slice(SLICE, mode="supporting", session_id="f0853d11")

    encoded = json.dumps(rows, sort_keys=True)
    assert '"computed_answer": "14 days"' in encoded


def test_chronological_prompt_replay_does_not_bypass_assistant_timestamp_guess() -> None:
    raw_prompt = """
----- RETRIEVED MEMORY (top-2 active memory_items by cosine similarity to question) -----
[0.900] USER (session gift-a, turn 0, 2023/05/30 (Tue) 09:00): I got her a beautiful necklace from Tiffany's last weekend.
[0.800] ASSISTANT (session gift-b, turn 7, 2023/05/30 (Tue) 03:18): I'm sure your mom will appreciate the customized photo album.
----- NORMALIZED EVENT DATES -----
2023-05-16: I ordered a customized photo album from Shutterfly two weeks ago.
----- QUESTION -----
Which gift did I buy first, the necklace for my sister or the photo album for my mom?
"""
    evidence = retrieved_from_prompt(raw_prompt)

    result = compute_answer(
        "Which gift did I buy first, the necklace for my sister or the photo album for my mom?",
        evidence,
    )

    assert result is not None
    assert result.intent.value == "chronological_order"
    assert result.safe_to_bypass_llm is False


def test_percentage_computation_uses_part_and_total_counts() -> None:
    evidence = [
        RetrievedEvidence(
            session_id="women",
            turn_idx=2,
            role="user",
            text="Women occupy 20 of the leadership positions in our company.",
            timestamp="2023/05/24 (Wed) 01:01",
        ),
        RetrievedEvidence(
            session_id="total",
            turn_idx=0,
            role="user",
            text="We have a total of 100 leadership positions across the company.",
            timestamp="2023/05/24 (Wed) 17:47",
        ),
    ]

    result = compute_answer(
        "What percentage of leadership positions do women hold in my company?",
        evidence,
    )

    assert result is not None
    assert result.intent.value == "percentage"
    assert result.answer == "20%"
    assert result.safe_to_bypass_llm is True


def test_savings_computation_matches_question_modes() -> None:
    evidence = [
        RetrievedEvidence(
            session_id="train",
            turn_idx=4,
            role="user",
            text="Taking the train from the airport to my hotel is around $10.",
            timestamp="2023/05/20 (Sat) 19:51",
        ),
        RetrievedEvidence(
            session_id="taxi",
            turn_idx=6,
            role="user",
            text="Taking a taxi from the airport to my hotel would cost around $60.",
            timestamp="2023/05/22 (Mon) 17:40",
        ),
    ]

    result = compute_answer(
        "How much will I save by taking the train from the airport to my hotel instead of a taxi?",
        evidence,
    )

    assert result is not None
    assert result.intent.value == "numeric_diff"
    assert result.answer == "$50"
    assert result.safe_to_bypass_llm is True


def test_raise_goal_diff_ignores_other_charity_events() -> None:
    evidence = [
        RetrievedEvidence(
            session_id="goal",
            turn_idx=8,
            role="user",
            text=(
                "I recently participated in a charity cycling event where I initially "
                "aimed to raise $200 in donations."
            ),
            timestamp="2023/05/24 (Wed) 07:38",
        ),
        RetrievedEvidence(
            session_id="raised",
            turn_idx=0,
            role="user",
            text="I recently participated in a charity cycling event and raised $250 in donations.",
            timestamp="2023/05/25 (Thu) 07:38",
        ),
        RetrievedEvidence(
            session_id="poison",
            turn_idx=0,
            role="user",
            text='At the "Walk for Hunger" event we raised $2,500 for the local food bank.',
            timestamp="2023/05/25 (Thu) 08:33",
        ),
    ]

    result = compute_answer(
        "How much more money did I raise than my initial goal in the charity cycling event?",
        evidence,
    )

    assert result is not None
    assert result.answer == "$50"
    assert result.safe_to_bypass_llm is True


def test_ambiguous_monetary_diff_does_not_bypass() -> None:
    evidence = [
        RetrievedEvidence("a", 0, "user", "One option cost $10."),
        RetrievedEvidence("b", 0, "user", "Another option cost $20."),
        RetrievedEvidence("c", 0, "user", "A third option cost $30."),
    ]

    result = compute_answer("What is the difference in cost?", evidence)

    assert result is not None
    assert result.safe_to_bypass_llm is False
