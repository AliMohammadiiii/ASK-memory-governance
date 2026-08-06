"""Regression matrix for deterministic computation-intent routing."""

from __future__ import annotations

import pytest

from ask.controller.computation import ComputeIntent, classify_compute_intent


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What was the third item on my packing list?", ComputeIntent.ORDINAL_LIST_ITEM),
        ("How many years older is Alex than Sam?", ComputeIntent.NUMERIC_DIFF),
        ("How many days had passed since I started X when Y happened?", ComputeIntent.DATE_DIFF),
        ("How many weeks were between the two trips?", ComputeIntent.DATE_DIFF),
        ("How many hours did I jog last week?", ComputeIntent.COUNT_EVENTS),
        ("What did I buy one day ago?", ComputeIntent.RELATIVE_TIME),
        ("Which gift did I buy first?", ComputeIntent.CHRONOLOGICAL_ORDER),
        ("What was the average price?", ComputeIntent.NUMERIC_AVERAGE),
        ("What percent of the positions are filled?", ComputeIntent.PERCENTAGE),
        ("How much did I save by taking the train instead of a taxi?", ComputeIntent.NUMERIC_DIFF),
        ("What was the difference in price?", ComputeIntent.NUMERIC_DIFF),
        ("What was the combined cost?", ComputeIntent.NUMERIC_SUM),
        ("What was the page count of the two novels?", ComputeIntent.NUMERIC_SUM),
        ("How many plants did I acquire?", ComputeIntent.COUNT_EVENTS),
        ("What is my favorite coffee?", ComputeIntent.NONE),
    ],
)
def test_classify_compute_intent_rules(question: str, expected: ComputeIntent) -> None:
    assert classify_compute_intent(question) is expected


def test_duration_total_precedes_relative_time_marker() -> None:
    assert (
        classify_compute_intent("How many minutes did I exercise last week?")
        is ComputeIntent.COUNT_EVENTS
    )


def test_date_difference_precedes_generic_count() -> None:
    assert (
        classify_compute_intent("How many months were between booking and arrival?")
        is ComputeIntent.DATE_DIFF
    )
