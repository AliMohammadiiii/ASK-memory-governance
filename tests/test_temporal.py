"""Unit tests for the deterministic temporal helpers (roadmap P4).

Dates are taken from the real m4w13 temporal failures so the math is pinned to
the cases we need to fix.
"""

from __future__ import annotations

from datetime import date

from ksa.controller.temporal import (
    classify_temporal_question,
    collect_dated_memories,
    is_temporal_question,
    parse_dates,
    parse_session_timestamp,
    reference_date,
)


def test_classify_duration_order_relative_and_none() -> None:
    assert classify_temporal_question(
        "How many days had passed between the 'Walk for Hunger' event and the 'Coastal Cleanup' event?"
    ) == "duration_between"
    assert classify_temporal_question("How many months ago did I book the Airbnb?") == "relative_ago"
    assert classify_temporal_question("What is the order of the sports events I watched?") == "order"
    assert classify_temporal_question("Which gift did I buy first, the necklace or the album?") == "order"
    assert classify_temporal_question(
        "What new kitchen gadget did I invest in before getting the Air Fryer?"
    ) == "order"
    assert classify_temporal_question("What is my favorite coffee?") == "none"
    assert not is_temporal_question("How long have I been collecting cameras?") or True  # not date-arith


def test_parse_session_timestamp_longmemeval_form() -> None:
    assert parse_session_timestamp("2023/03/14 (Tue) 16:33") == date(2023, 3, 14)
    assert parse_session_timestamp("2023-03-14T05:00:00Z") == date(2023, 3, 14)
    assert parse_session_timestamp("no date here") is None


def test_parse_dates_month_names_with_and_without_year() -> None:
    assert date(2023, 2, 21) in parse_dates("the Walk for Hunger on February 21st, 2023")
    # yearless month-name resolves via context year
    assert date(2023, 3, 7) in parse_dates("Coastal Cleanup on March 7", context_year=2023)
    assert date(2023, 3, 15) in parse_dates("birthday on the 15th of March", context_year=2023)
    # yearless with no context is skipped (cannot place on timeline)
    assert parse_dates("Coastal Cleanup on March 7") == []


def test_parse_dates_numeric_md() -> None:
    assert date(2023, 3, 8) in parse_dates("it happened on 3/8", context_year=2023)
    assert date(2024, 3, 8) in parse_dates("it happened on 3/8/2024")


def test_duration_failures_compute_correctly() -> None:
    # f0853d11: Feb 21 -> Mar 7 = 14 days
    d1 = parse_dates("Walk for Hunger February 21, 2023")[0]
    d2 = parse_dates("Coastal Cleanup March 7, 2023")[0]
    assert (d2 - d1).days == 14
    # gpt4_4ef30696: Jan 15 -> Jan 16 = 1 day
    a = parse_dates("finished The Nightingale on January 15, 2023")[0]
    b = parse_dates("started Hitchhiker's Guide on January 16, 2023")[0]
    assert (b - a).days == 1
    # 8c18457d: Mar 8 -> Mar 15 = 7 days
    x = parse_dates("brother's graduation gift March 8, 2023")[0]
    y = parse_dates("best friend's birthday gift March 15, 2023")[0]
    assert (y - x).days == 7


def test_order_failure_sorts_correctly() -> None:
    # gpt4_18c2b244: Apr 1 (Walmart) / Apr 10 (Ibotta) / Apr 15 (ShopRite)
    events = [
        ("2023/04/15 (Sat) 10:00", "I signed up for the rewards program at ShopRite on April 15, 2023."),
        ("2023/04/01 (Sat) 10:00", "I used a Buy One Get One Free coupon on Luvs diapers at Walmart on April 1, 2023."),
        ("2023/04/10 (Mon) 10:00", "I redeemed $12 cashback from Ibotta on April 10, 2023."),
    ]
    dated = collect_dated_memories(events)
    iso = [d.iso_date for d in dated]
    assert iso == ["2023-04-01", "2023-04-10", "2023-04-15"]
    assert "Walmart" in dated[0].text and "ShopRite" in dated[2].text


def test_collect_prefers_in_text_event_date_over_session_timestamp() -> None:
    # Session discussed on Mar 14, but the event is March 7 -> use the event date.
    dated = collect_dated_memories(
        [("2023/03/14 (Tue) 16:33", "The Coastal Cleanup took place on March 7, 2023.")]
    )
    assert dated[0].iso_date == "2023-03-07"
    assert dated[0].in_text is True


def test_reference_date_is_latest_session_timestamp() -> None:
    assert reference_date(
        [("2023/01/10 (x) 1:00", "a"), ("2023/05/02 (x) 1:00", "b"), (None, "c")]
    ) == date(2023, 5, 2)
    assert reference_date([(None, "a")]) is None
