"""Deterministic temporal helpers for the answer step (roadmap P4).

Pure, dependency-free date logic so it is fully unit-testable without any model.
The answerer stays authoritative: these helpers only *surface* normalized event
dates (parsed from the memory text, not just the session timestamp) and an
optional reference "today" date as scaffolding in the answer prompt. They never
override the model, so they cannot turn a correct answer into a wrong one.

Why text dates matter: in LongMemEval the decisive date for "which happened
first" / "how many days between" is frequently stated *inside* the memory text
("the Coastal Cleanup on March 7"), while the parenthesized timestamp is only
*when it was discussed* (e.g. session date March 14). Sorting by the session
timestamp would compute the wrong answer, so we extract in-text dates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

__all__ = [
    "TemporalKind",
    "classify_temporal_question",
    "is_temporal_question",
    "parse_dates",
    "parse_session_timestamp",
    "format_iso",
]

TemporalKind = str  # "duration_between" | "relative_ago" | "order" | "none"

_DURATION_RE = [
    re.compile(r"how (?:many|much).{0,40}\bbetween\b", re.IGNORECASE),
    re.compile(r"how (?:long|much time).{0,40}\bbetween\b", re.IGNORECASE),
    re.compile(r"\bdays?\b.{0,20}\bbetween\b", re.IGNORECASE),
]
_RELATIVE_RE = [
    re.compile(r"\bhow (?:many|long)\b.{0,40}\bago\b", re.IGNORECASE),
    re.compile(r"\b(?:weeks?|days?|months?|years?)\s+ago\b", re.IGNORECASE),
    re.compile(r"\blast\s+(?:week|month|year)\b", re.IGNORECASE),
    re.compile(r"\brecently\b", re.IGNORECASE),
]
_ORDER_RE = [
    re.compile(r"\bwhich\b.{0,60}\b(?:first|earliest|latest|before|after)\b", re.IGNORECASE),
    re.compile(r"\bwhat\b.{0,80}\b(?:first|earliest|latest|before|after)\b", re.IGNORECASE),
    re.compile(r"\bwhat\b.{0,20}\bthe order\b", re.IGNORECASE),
    re.compile(r"\bwho\b.{0,40}\bfirst\b", re.IGNORECASE),
    re.compile(r"\border of\b", re.IGNORECASE),
]


def classify_temporal_question(question: str) -> TemporalKind:
    """Route a question to a temporal kind, or "none". Order is intentional:
    duration > relative > order, because "how many days between" can also match
    weaker order cues."""
    q = question or ""
    if any(p.search(q) for p in _DURATION_RE):
        return "duration_between"
    if any(p.search(q) for p in _RELATIVE_RE):
        return "relative_ago"
    if any(p.search(q) for p in _ORDER_RE):
        return "order"
    return "none"


def is_temporal_question(question: str) -> bool:
    return classify_temporal_question(question) != "none"


# --------------------------------------------------------------------------- #
# Date parsing                                                                 #
# --------------------------------------------------------------------------- #

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# 2023/03/14 (Tue) 16:33   or   2023-03-14   or   2023/3/14
_SESSION_TS_RE = re.compile(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?!\d)")
# March 7th, 2023 / March 7 2023 / Mar 7
_MONTH_NAME_RE = re.compile(
    r"\b(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b",
    re.IGNORECASE,
)
# 15th of March / 15 of March, 2023
_DAY_OF_MONTH_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+of\s+"
    r"(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
    r"(?:,?\s+(\d{4}))?\b",
    re.IGNORECASE,
)
# 3/8/2023 or 3/8 (US m/d). Guarded so it doesn't swallow the yyyy/mm/dd form.
_NUMERIC_MD_RE = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?!\d)")
# Day lists: "17th and 18th of April" / "April 17 and 18". The single-date
# regexes only catch the day adjacent to the month, so multi-day events
# ("a 2-day workshop on the 17th and 18th of April") lose all but one day —
# which breaks distinct-day counting for "how many days" questions.
_DAY_LIST_OF_MONTH_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?(?:\s*,\s*|\s+and\s+)"
    r"(\d{1,2})(?:st|nd|rd|th)?\s+of\s+"
    r"(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
    r"(?:,?\s+(\d{4}))?\b",
    re.IGNORECASE,
)
_MONTH_DAY_LIST_RE = re.compile(
    r"\b(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?(?:\s*,\s*|\s+and\s+)"
    r"(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b",
    re.IGNORECASE,
)


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_session_timestamp(text: str | None) -> date | None:
    """Parse the leading session timestamp form '2023/03/14 (Tue) 16:33'."""
    if not text:
        return None
    m = _SESSION_TS_RE.search(text)
    if not m:
        return None
    return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def parse_dates(text: str | None, *, context_year: int | None = None) -> list[date]:
    """Return all calendar dates mentioned in ``text``, de-duplicated, in order.

    ``context_year`` supplies the year for forms that omit it ("March 7",
    "3/8"); without it those forms are skipped (a yearless date cannot be
    placed on a timeline reliably).
    """
    if not text:
        return []
    found: list[date] = []

    def add(d: date | None) -> None:
        if d is not None and d not in found:
            found.append(d)

    # yyyy/mm/dd or yyyy-mm-dd (unambiguous; also covers session timestamps).
    for m in _SESSION_TS_RE.finditer(text):
        add(_safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3))))

    # Month-name forms.
    for m in _MONTH_NAME_RE.finditer(text):
        month = _MONTHS[m.group(1).lower()]
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else context_year
        if year is not None:
            add(_safe_date(year, month, day))

    # Day-of-month forms.
    for m in _DAY_OF_MONTH_RE.finditer(text):
        day = int(m.group(1))
        month = _MONTHS[m.group(2).lower()]
        year = int(m.group(3)) if m.group(3) else context_year
        if year is not None:
            add(_safe_date(year, month, day))

    # Day-list forms ("17th and 18th of April", "April 17 and 18"): emit every
    # listed day so multi-day events contribute each calendar day.
    for m in _DAY_LIST_OF_MONTH_RE.finditer(text):
        month = _MONTHS[m.group(3).lower()]
        year = int(m.group(4)) if m.group(4) else context_year
        if year is not None:
            for day_group in (m.group(1), m.group(2)):
                add(_safe_date(year, month, int(day_group)))

    for m in _MONTH_DAY_LIST_RE.finditer(text):
        month = _MONTHS[m.group(1).lower()]
        year = int(m.group(4)) if m.group(4) else context_year
        if year is not None:
            for day_group in (m.group(2), m.group(3)):
                add(_safe_date(year, month, int(day_group)))

    # Numeric m/d[/y].
    for m in _NUMERIC_MD_RE.finditer(text):
        month = int(m.group(1))
        day = int(m.group(2))
        if m.group(3):
            yr = int(m.group(3))
            year = yr + 2000 if yr < 100 else yr
        else:
            year = context_year
        if year is not None and 1 <= month <= 12 and 1 <= day <= 31:
            add(_safe_date(year, month, day))

    return found


def format_iso(d: date) -> str:
    return d.isoformat()


# --------------------------------------------------------------------------- #
# Scaffolding for the answer prompt                                            #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DatedMemory:
    iso_date: str
    in_text: bool  # True if the date came from the memory text, not the session ts
    text: str


def collect_dated_memories(
    retrieved: list[tuple[str | None, str]],
) -> list[DatedMemory]:
    """Map retrieved (timestamp, text) pairs to normalized dated memories.

    Prefers a date stated *in the text* (the event date); falls back to the
    session timestamp only to supply the context year and as a last resort.
    Returns items sorted chronologically. Items with no resolvable date are
    dropped (we never fabricate an ordering).
    """
    out: list[DatedMemory] = []
    for ts, text in retrieved:
        ctx = parse_session_timestamp(ts)
        ctx_year = ctx.year if ctx else None
        text_dates = parse_dates(text, context_year=ctx_year)
        if text_dates:
            out.append(DatedMemory(format_iso(text_dates[0]), True, text.strip()))
        elif ctx is not None:
            out.append(DatedMemory(format_iso(ctx), False, text.strip()))
    out.sort(key=lambda d: d.iso_date)
    return out


def reference_date(retrieved: list[tuple[str | None, str]]) -> date | None:
    """Proxy for 'now': the latest session timestamp among retrieved memories.

    Used for 'how many X ago' / 'last week' phrasing when the dataset's true
    question_date is unavailable. Conservative: returns None if nothing parses.
    """
    parsed_dates = [parse_session_timestamp(ts) for ts, _ in retrieved]
    valid_dates: list[date] = [d for d in parsed_dates if d is not None]
    return max(valid_dates) if valid_dates else None
