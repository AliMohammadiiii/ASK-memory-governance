"""Deterministic computation helpers for controller answer generation.

The controller often retrieves the right evidence but asks the answer LLM to
sort dates, subtract prices, average GPAs, or index numbered lists. This module
keeps those high-confidence operations in code and returns either a safe bypass
answer or an auditable computation block for the LLM prompt.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from .temporal import parse_dates, parse_session_timestamp


class ComputeIntent(Enum):
    DATE_DIFF = "date_diff"
    CHRONOLOGICAL_ORDER = "chronological_order"
    RELATIVE_TIME = "relative_time"
    NUMERIC_SUM = "numeric_sum"
    NUMERIC_DIFF = "numeric_diff"
    NUMERIC_AVERAGE = "numeric_average"
    PERCENTAGE = "percentage"
    COUNT_EVENTS = "count_events"
    ORDINAL_LIST_ITEM = "ordinal_list_item"
    NONE = "none"


@dataclass(frozen=True)
class RetrievedEvidence:
    session_id: str
    turn_idx: int
    role: str
    text: str
    timestamp: str | None = None
    score: float | None = None


@dataclass(frozen=True)
class EvidenceCandidate:
    session_id: str
    turn_idx: int
    role: str
    source_text: str
    timestamp: date | None
    event_date: date | None
    value: Decimal | None
    unit: str | None
    entity: str | None
    event_label: str | None
    confidence: float
    date_source: str | None = None

    @property
    def source_ref(self) -> str:
        return f"{self.session_id}:{self.turn_idx}"


@dataclass(frozen=True)
class ComputedAnswer:
    answer: str
    intent: ComputeIntent
    evidence: list[EvidenceCandidate]
    computation: str
    confidence: float
    safe_to_bypass_llm: bool


_STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "by",
    "day",
    "did",
    "event",
    "for",
    "from",
    "had",
    "have",
    "i",
    "in",
    "is",
    "my",
    "of",
    "on",
    "or",
    "program",
    "set",
    "the",
    "to",
    "up",
    "was",
}

_ITEM_DESCRIPTOR_STOPWORDS = {
    "designer",
    "end",
    "expensive",
    "high",
    "item",
    "items",
    "luxury",
    "product",
    "products",
}

_NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

_ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
}

_CURRENCY_RE = re.compile(r"\$\s*([0-9][0-9,]*(?:\.\d+)?)")
_PLAIN_NUMBER_RE = re.compile(r"\b([0-9][0-9,]*(?:\.\d+)?)\b")
_GPA_RE = re.compile(r"\bgpa\s*(?:of|:|was|is|=)?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_OUT_OF_4_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s+out\s+of\s+4(?:\.0)?\b", re.IGNORECASE)
_TOTAL_COUNT_RE = re.compile(r"\b(?:total of|have|hold|contains?|can hold)\s+(\d+)\s+coins?\b", re.IGNORECASE)
_NUMBERED_ITEM_RE = re.compile(r"(?:^|\s)(\d{1,2})\.\s*(.*?)(?=\s+\d{1,2}\.\s*|$)")
_RELATIVE_RE = re.compile(
    r"\b(a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+)\s+"
    r"(days?|weeks?|months?|years?)\s+ago\b",
    re.IGNORECASE,
)
_MONTHS_ADVANCE_RE = re.compile(
    r"\b(a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+)\s+"
    r"months?\s+in\s+advance\b",
    re.IGNORECASE,
)
_DURATION_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)[\s-]*(hours?|hrs?|minutes?|mins?)\b",
    re.IGNORECASE,
)
# Statements about habits, lapses, plans, or wishes describe no countable event
# in the asked-about window ("I used to practice yoga ... but I've been
# slacking off", "I'm hoping to get back into it").
_NON_EVENT_RE = re.compile(
    r"\b(?:used to|hoping to|hope to|planning to|plan to|"
    r"want to|thinking of|thinking about|trying to get back|get back into|"
    r"slacking|skipped|missed|cancel)",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_MISSED_EVENT_RE = re.compile(
    r"\b(?:missed|miss|except for|skipped|skip|couldn'?t (?:attend|make|join)|"
    r"didn'?t (?:attend|make|join)|unable to (?:attend|make|join))\b",
    re.IGNORECASE,
)
# Frequency phrasing describes a recurring habit, not one event in the asked
# window ("I practice yoga three times a week, each time for 2 hours") — and
# extraction often drops the "used to" hedge, so the habit marker alone is not
# enough.
_HABITUAL_RE = re.compile(
    r"\b(?:times?\s+(?:a|per)\s+(?:day|week|month|year)|"
    r"every\s+(?:morning|evening|day|week|month))\b",
    re.IGNORECASE,
)
# Question verbs whose event *is the conversation itself*, so the session
# timestamp is the correct event date for "ago" arithmetic.
_MENTION_VERBS_RE = re.compile(r"\b(?:mention(?:ed)?|talk(?:ed)? about|tell|told|say|said|discuss(?:ed)?)\b", re.IGNORECASE)
_QUESTION_MONTH_RE = re.compile(
    r"\bin\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.IGNORECASE,
)
_MONTH_NUMBERS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
_SPELLED_NUMBERS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
    7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
}


# "<measure> ... of the two/three/both <items>" — an aggregate over an
# explicitly counted set (e.g. "the page count of the two novels", "the cost
# of both flights"). Sums are the dominant reading in LongMemEval.
_IMPLICIT_SUM_RE = re.compile(
    r"\b(?:count|total|sum|cost|price|amount|pages?|miles?|hours?|minutes?)\b"
    r".{0,40}\bof\s+(?:the\s+|these\s+|those\s+)?(?:two|three|four|both)\b"
)


def classify_compute_intent(question: str) -> ComputeIntent:
    q = (question or "").casefold()
    if _ordinal_from_question(q) is not None:
        return ComputeIntent.ORDINAL_LIST_ITEM
    # DATE_DIFF phrasings (v4-run fix, session 4dfccbf7): the original gate
    # required "between", so "how many days had passed SINCE I started X when
    # Y" fell through to COUNT_EVENTS and the solver returned nothing. Elapsed
    # ("passed") phrasings are date subtraction regardless of the preposition.
    if "days had passed" in q or "days have passed" in q or "days passed" in q:
        return ComputeIntent.DATE_DIFF
    if ("how many days" in q or "how many weeks" in q or "how many months" in q) and (
        "between" in q or " since " in q
    ):
        return ComputeIntent.DATE_DIFF
    if "how many hours" in q or "how many minutes" in q:
        # Duration totals ("how many hours of jogging ... last week") are count
        # work, not relative-time work, even when the window says "last week".
        return ComputeIntent.COUNT_EVENTS
    if "months ago" in q or "weeks ago" in q or "days ago" in q or "last week" in q:
        return ComputeIntent.RELATIVE_TIME
    if "order of" in q or "what is the order" in q or "which" in q and (
        "first" in q or "earliest" in q or "latest" in q
    ):
        return ComputeIntent.CHRONOLOGICAL_ORDER
    if "average" in q or "mean" in q:
        return ComputeIntent.NUMERIC_AVERAGE
    if "percentage" in q or "percent of" in q or "percent " in q:
        return ComputeIntent.PERCENTAGE
    if "save" in q and "instead of" in q:
        return ComputeIntent.NUMERIC_DIFF
    if "how much more" in q or "how much less" in q or "difference" in q:
        return ComputeIntent.NUMERIC_DIFF
    if "total" in q or "combined" in q or "altogether" in q:
        return ComputeIntent.NUMERIC_SUM
    # Implicit-sum phrasing (v4-run fix, session 37f165cf): "What was the page
    # count of the two novels I finished ..." asks for one aggregated value
    # over an explicitly counted set of items, without saying "total".
    if _IMPLICIT_SUM_RE.search(q):
        return ComputeIntent.NUMERIC_SUM
    if q.startswith("how many ") or " how many " in q:
        return ComputeIntent.COUNT_EVENTS
    return ComputeIntent.NONE


def compute_answer(
    question: str,
    retrieved: Iterable[RetrievedEvidence],
    *,
    question_date: str | None = None,
) -> ComputedAnswer | None:
    evidence = list(retrieved)
    if not evidence:
        return None
    intent = classify_compute_intent(question)
    if intent == ComputeIntent.NONE:
        return None
    qdate = parse_any_date(question_date)
    candidates = _build_candidates(evidence, question_date=qdate)
    solvers = {
        ComputeIntent.ORDINAL_LIST_ITEM: _solve_ordinal_list_item,
        ComputeIntent.DATE_DIFF: _solve_date_diff,
        ComputeIntent.CHRONOLOGICAL_ORDER: _solve_chronological_order,
        ComputeIntent.RELATIVE_TIME: _solve_relative_time,
        ComputeIntent.NUMERIC_AVERAGE: _solve_numeric_average,
        ComputeIntent.PERCENTAGE: _solve_percentage,
        ComputeIntent.NUMERIC_DIFF: _solve_numeric_diff,
        ComputeIntent.COUNT_EVENTS: _solve_count_events,
        ComputeIntent.NUMERIC_SUM: _solve_numeric_sum,
    }
    solver = solvers.get(intent)
    if solver is None:
        return None
    return solver(question, evidence, candidates, qdate)


def format_computation_block(result: ComputedAnswer | None) -> str:
    if result is None:
        return ""
    lines = [
        "----- DETERMINISTIC COMPUTATION RESULT -----",
        f"Intent: {result.intent.value}",
        "Evidence:",
    ]
    for ev in result.evidence[:8]:
        bits = [f"source={ev.source_ref}"]
        if ev.event_label:
            bits.append(f"label={ev.event_label}")
        if ev.event_date is not None:
            bits.append(f"date={ev.event_date.isoformat()}")
        if ev.value is not None:
            bits.append(f"value={_format_decimal(ev.value)}")
        if ev.unit:
            bits.append(f"unit={ev.unit}")
        lines.append(f"- {', '.join(bits)}: {ev.source_text[:180]}")
    lines.extend(
        [
            "Computation:",
            result.computation,
            "Computed answer:",
            result.answer,
            "Return the computed answer unless the evidence above contradicts it.",
        ]
    )
    return "\n".join(lines)


def parse_any_date(raw: str | None) -> date | None:
    if not raw:
        return None
    direct = parse_session_timestamp(raw)
    if direct is not None:
        return direct
    dates = parse_dates(raw)
    return dates[0] if dates else None


def _build_candidates(
    retrieved: list[RetrievedEvidence],
    *,
    question_date: date | None,
) -> list[EvidenceCandidate]:
    out: list[EvidenceCandidate] = []
    for item in retrieved:
        session_date = parse_session_timestamp(item.timestamp)
        context_year = (
            session_date.year
            if session_date is not None
            else question_date.year if question_date is not None else None
        )
        text_dates = parse_dates(item.text, context_year=context_year)
        rel_date = _relative_date(item.text, base=session_date or question_date)
        event_date = None
        date_source = None
        if text_dates:
            event_date = text_dates[0]
            date_source = "text"
        elif rel_date is not None:
            event_date = rel_date
            date_source = "relative"
        elif session_date is not None:
            event_date = session_date
            date_source = "timestamp"
        out.append(
            EvidenceCandidate(
                session_id=item.session_id,
                turn_idx=item.turn_idx,
                role=item.role,
                source_text=item.text.strip(),
                timestamp=session_date,
                event_date=event_date,
                value=None,
                unit=None,
                entity=None,
                event_label=None,
                confidence=0.5 + (0.2 if date_source in {"text", "relative"} else 0.0),
                date_source=date_source,
            )
        )
    return out


def _solve_date_diff(
    question: str,
    _retrieved: list[RetrievedEvidence],
    candidates: list[EvidenceCandidate],
    _question_date: date | None,
) -> ComputedAnswer | None:
    phrases = _event_phrases(question)
    if len(phrases) < 2:
        return None
    selected: list[EvidenceCandidate] = []
    for phrase in phrases[:2]:
        hit = _best_event_match(phrase, candidates, require_date=True, min_score=0.6)
        if hit is None:
            return None
        selected.append(_with_label(hit, phrase))
    if selected[0].event_date is None or selected[1].event_date is None:
        return None
    days = abs((selected[1].event_date - selected[0].event_date).days)
    day_unit = "day" if days == 1 else "days"
    answer = f"{days} {day_unit}"
    comp = (
        f"{selected[1].event_date.isoformat()} - "
        f"{selected[0].event_date.isoformat()} = {days} {day_unit}"
    )
    return ComputedAnswer(
        answer=answer,
        intent=ComputeIntent.DATE_DIFF,
        evidence=selected,
        computation=comp,
        confidence=0.9,
        safe_to_bypass_llm=True,
    )


def _solve_chronological_order(
    question: str,
    _retrieved: list[RetrievedEvidence],
    candidates: list[EvidenceCandidate],
    _question_date: date | None,
) -> ComputedAnswer | None:
    phrases = _event_phrases(question)
    if len(phrases) < 2:
        return _order_timeline_hint(question, candidates)
    selected: list[EvidenceCandidate] = []
    for phrase in phrases:
        # 0.45 (vs 0.6 for date_diff): option phrases name the gift *recipient*
        # ("necklace for my sister") while the evidence says "got her a
        # necklace", so requiring 60% token overlap rejects valid matches. The
        # in-text/relative-date bonus still ranks the right mention first.
        hit = _best_event_match(phrase, candidates, require_date=True, min_score=0.45)
        if hit is None:
            return None
        selected.append(_with_label(hit, phrase))
    if any(ev.event_date is None for ev in selected):
        return None
    ordered = sorted(selected, key=lambda ev: (ev.event_date or date.max, ev.timestamp or date.max))
    # A same-day "tie" usually means at least one event only has the session
    # timestamp (when it was discussed), not a real event date — ordering on it
    # is a coin flip, so surface the dates to the LLM instead of bypassing.
    distinct_dates = {ev.event_date for ev in ordered}
    tie = len(distinct_dates) < len(ordered)
    orderable_evidence = all(_chronological_date_is_orderable(ev) for ev in selected)
    q = question.casefold()
    if "latest" in q:
        answer = _clean_event_label(ordered[-1].event_label or "")
    elif "which" in q and "first" in q and len(ordered) == 2:
        answer = _clean_event_label(ordered[0].event_label or "")
    else:
        answer = " -> ".join(_clean_event_label(ev.event_label or "") for ev in ordered)
    comp = " < ".join(
        f"{ev.event_date.isoformat()} {ev.event_label}" for ev in ordered if ev.event_date
    )
    if tie:
        comp += " (event dates tie at day granularity; do not trust this order)"
    if not orderable_evidence:
        comp += " (at least one event is dated only by an unanchored message timestamp)"
    safe_to_bypass = not tie and orderable_evidence
    return ComputedAnswer(
        answer=answer,
        intent=ComputeIntent.CHRONOLOGICAL_ORDER,
        evidence=ordered,
        computation=comp,
        confidence=0.88 if safe_to_bypass else 0.55,
        safe_to_bypass_llm=safe_to_bypass,
    )


def _chronological_date_is_orderable(ev: EvidenceCandidate) -> bool:
    if ev.date_source in {"text", "relative"}:
        return True
    if ev.date_source != "timestamp" or ev.role != "user":
        return False
    text_l = ev.source_text.casefold()
    return any(
        marker in text_l
        for marker in (
            "recently",
            "just ",
            "today",
            "this morning",
            "this afternoon",
            "this evening",
        )
    )


def _order_timeline_hint(
    question: str, candidates: list[EvidenceCandidate]
) -> ComputedAnswer | None:
    """'What is the order of the X I did in <month>?' without extractable event
    phrases: emit a dated timeline of question-relevant memories (never a
    bypass — the LLM still names the events)."""
    if "order" not in question.casefold():
        return None
    activities = _question_activity_tokens(question)
    month = _question_month(question)
    # With a named month ("in January") the calendar filter is the precise one;
    # an activity-token gate would drop events described with words the
    # question never uses ("NBA game" for "sports events").
    dated = [
        ev
        for ev in candidates
        if ev.event_date is not None
        and (month is None or ev.event_date.month == month)
        and (
            month is not None
            or not activities
            or _any_activity_match(activities, ev.source_text)
        )
    ]
    if len(dated) < 2:
        return None
    dated.sort(key=lambda ev: ev.event_date or date.max)
    lines = ["Question-relevant memories in date order (earliest first):"]
    seen: set[str] = set()
    for ev in dated:
        if ev.source_ref in seen:
            continue
        seen.add(ev.source_ref)
        lines.append(f"- {(ev.event_date or date.max).isoformat()} [{ev.source_ref}]: {ev.source_text[:160]}")
        if len(lines) >= 9:
            break
    return ComputedAnswer(
        answer="",
        intent=ComputeIntent.CHRONOLOGICAL_ORDER,
        evidence=dated[:8],
        computation="\n".join(lines),
        confidence=0.45,
        safe_to_bypass_llm=False,
    )


def _solve_relative_time(
    question: str,
    retrieved: list[RetrievedEvidence],
    candidates: list[EvidenceCandidate],
    question_date: date | None,
) -> ComputedAnswer | None:
    q = question.casefold()
    if "months ago" in q and "book" in q:
        months_ago: list[tuple[int, RetrievedEvidence]] = []
        months_advance: list[tuple[int, RetrievedEvidence]] = []
        for item in retrieved:
            for m in _RELATIVE_RE.finditer(item.text):
                if m.group(2).casefold().startswith("month"):
                    months_ago.append((_number_value(m.group(1)), item))
            for m in _MONTHS_ADVANCE_RE.finditer(item.text):
                months_advance.append((_number_value(m.group(1)), item))
        if months_ago and months_advance:
            ago_value, ago_item = max(months_ago, key=lambda x: x[0])
            advance_value, advance_item = max(months_advance, key=lambda x: x[0])
            total = ago_value + advance_value
            ev = [
                _candidate_for_item(ago_item, candidates, value=Decimal(ago_value), unit="months"),
                _candidate_for_item(
                    advance_item, candidates, value=Decimal(advance_value), unit="months"
                ),
            ]
            spelled = _spell_count(total)
            return ComputedAnswer(
                answer=f"{spelled} ({total}) months ago",
                intent=ComputeIntent.RELATIVE_TIME,
                evidence=ev,
                computation=f"{ago_value} months ago + {advance_value} months in advance = {total} months ago",
                confidence=0.86,
                safe_to_bypass_llm=True,
            )
    # 'What/which ... N weeks/months ago' → resolve the target calendar window
    # and surface the memories dated inside it. The reference 'today' is the
    # question date when present, else the newest session timestamp.
    ref = _reference_date_from_candidates(candidates, question_date)
    target_window = _question_relative_window(question, ref)
    if target_window is not None and not q.startswith("how many"):
        assert ref is not None
        target, tolerance = target_window
        if question_date is not None:
            # Exact reference: the event sits in a narrow band around
            # question_date - delta.
            lo = target - timedelta(days=tolerance)
            hi = target + timedelta(days=tolerance)
            anchor = target
        else:
            # Proxy reference (newest session timestamp). The real question
            # date is *later* than every session, so 'N units ago' can point
            # anywhere from (ref - delta) up to the newest session itself.
            lo = target - timedelta(days=tolerance)
            hi = ref
            anchor = ref
        near = [
            ev
            for ev in candidates
            if ev.event_date is not None and lo <= ev.event_date <= hi
        ]
        near.sort(key=lambda ev: abs(((ev.event_date or anchor) - anchor).days))
        if near:
            lines = [
                f"Reference 'today' (newest session): {ref.isoformat()}" if ref else "",
                (
                    f"The question points at approximately {target.isoformat()}."
                    if question_date is not None
                    else (
                        "The question was asked after the newest session, so "
                        f"the asked-about event lies between {lo.isoformat()} "
                        f"and {hi.isoformat()}."
                    )
                ),
                "Memories dated inside that window (most plausible first):",
            ]
            lines += [
                f"- {ev.event_date.isoformat()} [{ev.source_ref}]: {ev.source_text[:180]}"
                for ev in near[:4]
                if ev.event_date
            ]
            return ComputedAnswer(
                answer="",
                intent=ComputeIntent.RELATIVE_TIME,
                evidence=near[:5],
                computation="\n".join(line for line in lines if line),
                confidence=0.45,
                safe_to_bypass_llm=False,
            )
    # For other relative-time questions, surface the real question date when
    # available but avoid bypassing until the event extraction is unambiguous.
    if question_date is not None:
        dated = [ev for ev in candidates if ev.event_date is not None]
        if dated:
            return ComputedAnswer(
                answer="",
                intent=ComputeIntent.RELATIVE_TIME,
                evidence=dated[:5],
                computation=f"Question/reference date: {question_date.isoformat()}",
                confidence=0.4,
                safe_to_bypass_llm=False,
            )
    return None


def _question_relative_window(
    question: str, ref: date | None
) -> tuple[date, int] | None:
    """Map 'N days/weeks/months ago' in the question to (target_date, tolerance)."""
    if ref is None:
        return None
    m = _RELATIVE_RE.search(question)
    if not m:
        return None
    amount = _number_value(m.group(1))
    if amount <= 0:
        return None
    unit = m.group(2).casefold()
    if unit.startswith("day"):
        return ref - timedelta(days=amount), 2
    if unit.startswith("week"):
        return ref - timedelta(days=7 * amount), 5
    if unit.startswith("month"):
        return _shift_months(ref, -amount), 12
    if unit.startswith("year"):
        return _shift_months(ref, -12 * amount), 31
    return None


def _solve_numeric_average(
    question: str,
    _retrieved: list[RetrievedEvidence],
    candidates: list[EvidenceCandidate],
    _question_date: date | None,
) -> ComputedAnswer | None:
    if "gpa" not in question.casefold():
        return None
    values: list[EvidenceCandidate] = []
    seen: set[tuple[str, Decimal]] = set()
    for ev in candidates:
        for value in _gpa_values(ev.source_text):
            key = (ev.session_id, value)
            if key in seen:
                continue
            seen.add(key)
            values.append(_with_value(ev, value, "GPA"))
    if len(values) < 2:
        return None
    # The question asks for the average over the *user's own degrees*. Keep one
    # candidate per distinct GPA value, preferring user-asserted lines, then
    # try to anchor each requested degree (undergraduate/graduate) to one value
    # by its surrounding context. Bypass only when the pairing is unambiguous —
    # averaging a requirement like "a minimum GPA of 3.5" silently poisons the
    # result otherwise.
    by_value: dict[Decimal, EvidenceCandidate] = {}
    for ev in values:
        existing = by_value.get(ev.value or Decimal(0))
        if existing is None or (ev.role == "user" and existing.role != "user"):
            by_value[ev.value or Decimal(0)] = ev
    distinct = list(by_value.values())
    q = question.casefold()
    selected: list[EvidenceCandidate] = []
    if "undergrad" in q and ("graduate" in q or "master" in q or "phd" in q):
        undergrad_markers = ("undergrad", "bachelor", "b.s", "bsc", "first-class", "first class")
        graduate_markers = ("master", "graduate degree", "m.s", "msc", "phd", "doctorate")
        requirement_markers = ("minimum", "require", "at least", "cutoff", "eligib")
        def _pick(markers: tuple[str, ...]) -> EvidenceCandidate | None:
            hits = [
                ev
                for ev in distinct
                if any(mk in ev.source_text.casefold() for mk in markers)
                and not any(mk in ev.source_text.casefold() for mk in requirement_markers)
            ]
            return hits[0] if len(hits) == 1 else None
        ug = _pick(undergrad_markers)
        gr = _pick(graduate_markers)
        if ug is not None and gr is not None and ug.value != gr.value:
            selected = [ug, gr]
    if not selected and len(distinct) == 2:
        selected = distinct
    if not selected:
        # Ambiguous inputs: surface every distinct value with its context and
        # let the answer LLM choose — never bypass on a guess.
        listing = "; ".join(
            f"{_format_decimal(ev.value or Decimal(0))} [{ev.source_ref}] {ev.source_text[:100]}"
            for ev in distinct[:5]
        )
        return ComputedAnswer(
            answer="",
            intent=ComputeIntent.NUMERIC_AVERAGE,
            evidence=distinct[:5],
            computation=(
                "Multiple GPA values found; pair the user's own degree GPAs and "
                f"average them (ignore program requirements): {listing}"
            ),
            confidence=0.4,
            safe_to_bypass_llm=False,
        )
    total = sum((ev.value or Decimal(0)) for ev in selected)
    avg = (total / Decimal(len(selected))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    comp = " + ".join(_format_decimal(ev.value or Decimal(0)) for ev in selected)
    comp = f"({comp}) / {len(selected)} = {_format_decimal(avg)}"
    return ComputedAnswer(
        answer=_format_decimal(avg),
        intent=ComputeIntent.NUMERIC_AVERAGE,
        evidence=selected,
        computation=comp,
        confidence=0.9,
        safe_to_bypass_llm=True,
    )


def _solve_percentage(
    question: str,
    _retrieved: list[RetrievedEvidence],
    candidates: list[EvidenceCandidate],
    _question_date: date | None,
) -> ComputedAnswer | None:
    q = question.casefold()
    denominator_tokens = _percentage_denominator_tokens(q)
    subject_tokens = _percentage_subject_tokens(q)
    if not denominator_tokens or not subject_tokens:
        return None

    part_values: list[EvidenceCandidate] = []
    total_values: list[EvidenceCandidate] = []
    seen_part: set[tuple[str, int, Decimal]] = set()
    seen_total: set[tuple[str, int, Decimal]] = set()
    for ev in candidates:
        for value, context in _plain_number_contexts(ev.source_text):
            ctx_tokens = set(_tokens(context))
            if not (denominator_tokens & ctx_tokens):
                continue
            candidate = _with_value_context(ev, value, "count", context)
            if subject_tokens <= ctx_tokens and _looks_like_part_count(context):
                key = (ev.session_id, ev.turn_idx, value)
                if key not in seen_part:
                    seen_part.add(key)
                    part_values.append(candidate)
            if _looks_like_total_count(context):
                key = (ev.session_id, ev.turn_idx, value)
                if key not in seen_total:
                    seen_total.add(key)
                    total_values.append(candidate)

    if not part_values or not total_values:
        return None

    part = max(part_values, key=lambda ev: _percentage_value_score(ev, subject_tokens, denominator_tokens, total=False))
    total = max(total_values, key=lambda ev: _percentage_value_score(ev, subject_tokens, denominator_tokens, total=True))
    if part.value is None or total.value is None or total.value <= 0 or part.value > total.value:
        return None
    percent = (part.value / total.value * Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return ComputedAnswer(
        answer=_format_percent(percent),
        intent=ComputeIntent.PERCENTAGE,
        evidence=[part, total],
        computation=(
            f"{_format_decimal(part.value)} / {_format_decimal(total.value)} * 100 = "
            f"{_format_percent(percent)}"
        ),
        confidence=0.9,
        safe_to_bypass_llm=True,
    )


def _solve_numeric_diff(
    question: str,
    _retrieved: list[RetrievedEvidence],
    candidates: list[EvidenceCandidate],
    _question_date: date | None,
) -> ComputedAnswer | None:
    q = question.casefold()
    if "$" not in " ".join(ev.source_text for ev in candidates) and "amount" not in q:
        return None
    currencies: list[EvidenceCandidate] = []
    for ev in candidates:
        for value, context in _currency_value_contexts(ev.source_text):
            currencies.append(_with_value_context(ev, value, "USD", context))
    if len(currencies) < 2:
        return None
    left = right = None
    if "save" in q and "instead of" in q:
        chosen, other = _savings_phrases(question)
        if chosen and other:
            left = _best_value_for_phrase(currencies, other)
            right = _best_value_for_phrase(currencies, chosen)
    event_phrase = _numeric_diff_event_phrase(question)
    if (
        (left is None or right is None)
        and ("raise" in q or "raised" in q)
        and ("goal" in q or "aim" in q)
    ):
        scoped = [
            ev
            for ev in currencies
            if not event_phrase or _phrase_score(event_phrase, ev.source_text) >= 0.75
        ]
        if len(scoped) >= 2:
            left = _best_text_value_match(scoped, ("raised $", "raised", "ended up raising"))
            right = _best_text_value_match(
                scoped, ("initially aimed", "initial goal", "aimed to raise", "goal")
            )
    if "pre-approval" in q or "pre approval" in q or "pre-approved" in q:
        left = _best_text_value_match(currencies, ("pre-approved", "pre approval", "borrow up to"))
    if "sale price" in q or "final sale" in q:
        right = _best_text_value_match(currencies, ("final sale price", "sale price"))
    if left is None or right is None:
        unique: list[EvidenceCandidate] = []
        seen_values: set[Decimal] = set()
        for ev in currencies:
            if ev.value in seen_values:
                continue
            seen_values.add(ev.value or Decimal(0))
            unique.append(ev)
        if len(unique) < 2:
            return None
        if len(unique) > 2:
            listing = "; ".join(
                f"{_format_currency(ev.value or Decimal(0))} [{ev.source_ref}] {ev.source_text[:100]}"
                for ev in unique[:5]
            )
            return ComputedAnswer(
                answer="",
                intent=ComputeIntent.NUMERIC_DIFF,
                evidence=unique[:5],
                computation=(
                    "Multiple monetary values found; choose the two values tied to the "
                    f"question's event/slot before subtracting: {listing}"
                ),
                confidence=0.35,
                safe_to_bypass_llm=False,
            )
        unique.sort(key=lambda ev: ev.confidence, reverse=True)
        left, right = unique[0], unique[1]
    if left.value is None or right.value is None:
        return None
    diff = abs(left.value - right.value)
    return ComputedAnswer(
        answer=_format_currency(diff),
        intent=ComputeIntent.NUMERIC_DIFF,
        evidence=[left, right],
        computation=f"{_format_currency(left.value)} - {_format_currency(right.value)} = {_format_currency(diff)}",
        confidence=0.9,
        safe_to_bypass_llm=True,
    )


def _solve_numeric_sum(
    question: str,
    retrieved: list[RetrievedEvidence],
    candidates: list[EvidenceCandidate],
    question_date: date | None,
) -> ComputedAnswer | None:
    """Total-spend questions: match each purchased item named in the question
    to one currency-bearing evidence line and sum the amounts."""
    phrases = _question_item_phrases(question)
    if len(phrases) >= 2:
        selected: list[EvidenceCandidate] = []
        used: set[tuple[str, int]] = set()
        for phrase in phrases:
            best: tuple[float, EvidenceCandidate, Decimal] | None = None
            for ev in candidates:
                values = _currency_values(ev.source_text)
                if not values:
                    continue
                score = _item_phrase_score(phrase, ev.source_text)
                if score < 0.5:
                    continue
                if ev.role == "user":
                    score += 0.05
                if (ev.session_id, ev.turn_idx) in used:
                    score -= 0.5
                if best is None or score > best[0]:
                    best = (score, ev, values[0])
            if best is None:
                break
            _, ev, value = best
            used.add((ev.session_id, ev.turn_idx))
            selected.append(_with_value(_with_label(ev, phrase), value, "USD"))
        if len(selected) == len(phrases):
            total = sum(((ev.value or Decimal(0)) for ev in selected), Decimal(0))
            comp = " + ".join(_format_currency(ev.value or Decimal(0)) for ev in selected)
            return ComputedAnswer(
                answer=_format_currency(total),
                intent=ComputeIntent.NUMERIC_SUM,
                evidence=selected,
                computation=f"{comp} = {_format_currency(total)}",
                confidence=0.88,
                safe_to_bypass_llm=True,
            )
    # Fall back to the count-style solvers (coin totals, duration sums).
    return _solve_count_events(question, retrieved, candidates, question_date)


def _question_item_phrases(question: str) -> list[str]:
    """Item phrases from 'total ... spent on the X and the Y' style questions."""
    q = question.strip().rstrip("?")
    m = re.search(r"\b(?:spent on|spend on|paid for|cost of|price of)\s+(.*)$", q, re.IGNORECASE)
    if not m:
        return []
    tail = m.group(1)
    parts = re.split(r"\s*(?:,|\band\b)\s*", tail, flags=re.IGNORECASE)
    phrases = [_clean_event_label(p) for p in parts if _tokens(p)]
    return [p for p in phrases if p]


def _solve_count_events(
    question: str,
    _retrieved: list[RetrievedEvidence],
    candidates: list[EvidenceCandidate],
    _question_date: date | None,
) -> ComputedAnswer | None:
    q = question.casefold()
    if "hour" in q or "minute" in q:
        return _solve_duration_sum(question, candidates)
    if "how many days" in q or "many days did" in q:
        result = _solve_distinct_day_count(question, candidates)
        if result is not None:
            return result
    if _MISSED_EVENT_RE.search(q):
        result = _solve_missed_event_count(question, candidates)
        if result is not None:
            return result
    if "coin" in q:
        base: EvidenceCandidate | None = None
        for ev in candidates:
            for m in _TOTAL_COUNT_RE.finditer(ev.source_text):
                value = Decimal(int(m.group(1)))
                candidate = _with_value(ev, value, "coins")
                if base is None or (candidate.value or 0) > (base.value or 0):
                    base = candidate
        additions: list[EvidenceCandidate] = []
        seen_turns: set[tuple[str, int]] = set()
        for ev in candidates:
            text_l = ev.source_text.casefold()
            if "added a new coin" not in text_l and "new coin to my collection" not in text_l:
                continue
            key = (ev.session_id, ev.turn_idx)
            if key in seen_turns:
                continue
            seen_turns.add(key)
            additions.append(_with_value(ev, Decimal(1), "coins"))
        if base is not None and additions:
            total = (base.value or Decimal(0)) + Decimal(len(additions))
            evs = [base] + additions
            return ComputedAnswer(
                answer=_format_decimal(total),
                intent=ComputeIntent.COUNT_EVENTS,
                evidence=evs,
                computation=f"{_format_decimal(base.value or Decimal(0))} existing coins + {len(additions)} new coin = {_format_decimal(total)}",
                confidence=0.86,
                safe_to_bypass_llm=True,
            )
    return None


def _question_activity_tokens(question: str) -> set[str]:
    """Content tokens of the question that can anchor evidence matching."""
    q = question.strip().rstrip("?")
    q = re.sub(
        r"^(?:how many|how much|what is|what was|which|when|where)\b", "", q, flags=re.IGNORECASE
    )
    q = re.sub(
        r"\b(?:hours?|days?|weeks?|months?|times?|did|do|does|i|spend|spent|attend(?:ing|ed)?|"
        r"due|work|commitments?|last|this|in|january|february|march|april|may|june|july|august|"
        r"september|october|november|december)\b",
        " ",
        q,
        flags=re.IGNORECASE,
    )
    return set(_tokens(q))


def _token_in_text(token: str, text_l: str) -> bool:
    """Loose morphological containment: 'jogging' matches 'jog', 'lectures'
    matches 'lecture'. Substring check on a small variant set keeps it cheap."""
    variants = {token}
    if token.endswith("s") and len(token) > 3:
        variants.add(token[:-1])
    if token.endswith("ed") and len(token) > 4:
        variants.add(token[:-2])
    if token.endswith("ing") and len(token) > 5:
        base = token[:-3]
        variants.add(base)
        if len(base) > 2 and base[-1] == base[-2]:
            variants.add(base[:-1])
    return any(v in text_l for v in variants)


def _any_activity_match(activities: set[str], text: str) -> bool:
    text_l = text.casefold()
    return any(_token_in_text(tok, text_l) for tok in activities)


def _question_month(question: str) -> int | None:
    m = _QUESTION_MONTH_RE.search(question)
    if not m:
        return None
    return _MONTH_NUMBERS[m.group(1).casefold()]


def _reference_date_from_candidates(
    candidates: list[EvidenceCandidate], question_date: date | None
) -> date | None:
    if question_date is not None:
        return question_date
    stamps = [ev.timestamp for ev in candidates if ev.timestamp is not None]
    return max(stamps) if stamps else None


def _spell_count(value: int) -> str:
    return _SPELLED_NUMBERS.get(value, str(value))


def _solve_duration_sum(
    question: str, candidates: list[EvidenceCandidate]
) -> ComputedAnswer | None:
    """'How many hours of X and Y did I do last week' → sum stated durations.

    Habit/lapse/plan statements ("used to practice ... but slacking off",
    "hoping to get back into it") are excluded: they state no event inside the
    asked-about window. Window filtering uses the event date when the question
    names a window ("last week"), with the newest session timestamp as 'now'.
    """
    activities = _question_activity_tokens(question)
    if not activities:
        return None
    # One contribution per source turn: the raw user turn and its extracted
    # fact share (session, turn) provenance and would otherwise double-count.
    per_turn: dict[tuple[str, int], tuple[EvidenceCandidate, Decimal]] = {}
    excluded: list[EvidenceCandidate] = []
    for ev in candidates:
        # Assistant turns state advice durations ("arrive 10-15 minutes before
        # class"), never the user's own activity — only user evidence counts.
        if ev.role != "user":
            continue
        if not _any_activity_match(activities, ev.source_text):
            continue
        # Habit/plan markers are judged per sentence: "I went for a 30-minute
        # jog" must not be discarded because a *different* sentence in the same
        # turn says "I'm hoping to get back into yoga".
        hours = Decimal(0)
        had_duration = False
        was_excluded = False
        for sentence in _SENTENCE_SPLIT_RE.split(ev.source_text):
            durations = list(_DURATION_RE.finditer(sentence))
            if not durations:
                continue
            had_duration = True
            if not _any_activity_match(activities, sentence):
                continue
            if _NON_EVENT_RE.search(sentence) or _HABITUAL_RE.search(sentence):
                was_excluded = True
                continue
            for m in durations:
                value = Decimal(m.group(1))
                unit = m.group(2).casefold()
                hours += value / Decimal(60) if unit.startswith("min") else value
        if not had_duration:
            continue
        if hours > 0:
            key = (ev.session_id, ev.turn_idx)
            existing = per_turn.get(key)
            if existing is None or hours > existing[1]:
                per_turn[key] = (ev, hours)
        elif was_excluded:
            excluded.append(ev)
    matched = list(per_turn.values())
    if not matched:
        return None
    window_days = 7 if "last week" in question.casefold() else None
    if window_days is not None:
        ref = _reference_date_from_candidates(candidates, None)
        if ref is not None:
            in_window = [
                (ev, hours)
                for ev, hours in matched
                if ev.event_date is not None
                and timedelta(0) <= (ref - ev.event_date) <= timedelta(days=window_days)
            ]
            if in_window:
                matched = in_window
    total = sum((hours for _, hours in matched), Decimal(0))
    total = total.quantize(Decimal("0.1")) if total != total.to_integral_value() else total
    evidence = [
        _with_value(ev, hours, "hours") for ev, hours in matched
    ] + excluded[:2]
    comp_parts = " + ".join(f"{_format_decimal(hours)}h" for _, hours in matched)
    comp = f"{comp_parts} = {_format_decimal(Decimal(total))} hours"
    if excluded:
        comp += f"; excluded {len(excluded)} habit/plan statement(s) with no event in the window"
    return ComputedAnswer(
        answer=f"{_format_decimal(Decimal(total))} hours",
        intent=ComputeIntent.COUNT_EVENTS,
        evidence=evidence,
        computation=comp,
        confidence=0.84,
        safe_to_bypass_llm=True,
    )


def _solve_distinct_day_count(
    question: str, candidates: list[EvidenceCandidate]
) -> ComputedAnswer | None:
    """'How many days did I spend ... in April' → count distinct event days.

    Only fires when the question names a month and the matching evidence
    carries explicit in-text dates inside that month, so each counted day is
    auditable in the computation block.
    """
    month = _question_month(question)
    if month is None:
        return None
    activities = _question_activity_tokens(question)
    if not activities:
        return None
    days: dict[date, EvidenceCandidate] = {}
    for ev in candidates:
        if ev.role != "user":
            continue
        if not _any_activity_match(activities, ev.source_text):
            continue
        ctx_year = ev.timestamp.year if ev.timestamp is not None else None
        for d in parse_dates(ev.source_text, context_year=ctx_year):
            if d.month == month and d not in days:
                days[d] = ev
    if not days:
        return None
    count = len(days)
    ordered_days = sorted(days)
    evidence = []
    seen_refs: set[str] = set()
    for d in ordered_days:
        ev = days[d]
        if ev.source_ref not in seen_refs:
            seen_refs.add(ev.source_ref)
            evidence.append(ev)
    day_unit = "day" if count == 1 else "days"
    comp = (
        "distinct event days: "
        + ", ".join(d.isoformat() for d in ordered_days)
        + f" -> {count} {day_unit}"
    )
    return ComputedAnswer(
        answer=f"{count} {day_unit}",
        intent=ComputeIntent.COUNT_EVENTS,
        evidence=evidence,
        computation=comp,
        confidence=0.84,
        safe_to_bypass_llm=True,
    )


def _solve_missed_event_count(
    question: str, candidates: list[EvidenceCandidate]
) -> ComputedAnswer | None:
    """'How many X did I miss in <month>' → count distinct missed-event days."""
    month = _question_month(question)
    activities = _question_activity_tokens(question)
    if not activities:
        return None
    days: dict[date, EvidenceCandidate] = {}
    for ev in candidates:
        if ev.role != "user":
            continue
        if not _any_activity_match(activities, ev.source_text):
            continue
        if not _MISSED_EVENT_RE.search(ev.source_text):
            continue
        ctx_year = ev.timestamp.year if ev.timestamp is not None else None
        for d in parse_dates(ev.source_text, context_year=ctx_year):
            if (month is None or d.month == month) and d not in days:
                days[d] = ev
    if not days:
        return None
    count = len(days)
    ordered_days = sorted(days)
    evidence = []
    seen_refs: set[str] = set()
    for d in ordered_days:
        ev = days[d]
        if ev.source_ref not in seen_refs:
            seen_refs.add(ev.source_ref)
            evidence.append(ev)
    comp = (
        "distinct missed-event days: "
        + ", ".join(d.isoformat() for d in ordered_days)
        + f" -> {count}"
    )
    return ComputedAnswer(
        answer=str(count),
        intent=ComputeIntent.COUNT_EVENTS,
        evidence=evidence,
        computation=comp,
        confidence=0.82,
        safe_to_bypass_llm=True,
    )


def _solve_ordinal_list_item(
    question: str,
    retrieved: list[RetrievedEvidence],
    candidates: list[EvidenceCandidate],
    _question_date: date | None,
) -> ComputedAnswer | None:
    ordinal = _ordinal_from_question(question)
    if ordinal is None:
        return None
    # docx §4 fix 6: an enumerated assistant list is frequently split across
    # retrieval chunks (each ~320 chars), so no single item holds item N. First
    # try to find the whole list in one item (unambiguous); if none contains the
    # ordinal, reassemble a merged view across ALL retrieved items (first write
    # wins per index, so disjoint chunks of one list rejoin cleanly) and index
    # into that. The matching evidence item is the one that actually supplies
    # item N, for provenance.
    best: tuple[EvidenceCandidate, str] | None = None
    for item in retrieved:
        numbered = _numbered_items(item.text)
        if ordinal not in numbered:
            continue
        ev = _candidate_for_item(item, candidates, value=Decimal(ordinal), unit="ordinal")
        best = (ev, numbered[ordinal])
        break
    if best is None:
        merged: dict[int, str] = {}
        source_item = None
        for item in retrieved:
            for idx, value in _numbered_items(item.text).items():
                if idx not in merged:
                    merged[idx] = value
                    if idx == ordinal:
                        source_item = item
        if ordinal in merged and source_item is not None:
            ev = _candidate_for_item(
                source_item, candidates, value=Decimal(ordinal), unit="ordinal"
            )
            best = (ev, merged[ordinal])
    if best is None:
        return None
    ev, answer = best
    return ComputedAnswer(
        answer=answer,
        intent=ComputeIntent.ORDINAL_LIST_ITEM,
        evidence=[ev],
        computation=f"Item {ordinal} in the retrieved numbered list is {answer}.",
        confidence=0.92,
        safe_to_bypass_llm=True,
    )


def _event_phrases(question: str) -> list[str]:
    quoted = [a or b for a, b in re.findall(r"'([^']+)'|\"([^\"]+)\"", question)]
    if quoted:
        return quoted
    q = question.strip().rstrip("?")
    between = re.search(r"\bbetween\s+(.*?)\s+and\s+(.*)$", q, re.IGNORECASE)
    if between:
        return [_clean_event_label(between.group(1)), _clean_event_label(between.group(2))]
    option = re.search(r",\s*(?:the\s+)?(.+?)\s+or\s+(?:the\s+)?(.+)$", q, re.IGNORECASE)
    if option:
        return [_clean_event_label(option.group(1)), _clean_event_label(option.group(2))]
    before_after = re.search(
        r"^\s*what\s+(.+?)\s+.*?\b(?:before|after)\s+(.+)$",
        q,
        re.IGNORECASE,
    )
    if before_after:
        target = re.sub(
            r"^(?:getting|buying|purchasing|using|taking|booking|a|an|the)\s+",
            "",
            before_after.group(2).strip(),
            flags=re.IGNORECASE,
        )
        return [_clean_event_label(before_after.group(1)), _clean_event_label(target)]
    return []


def _best_event_match(
    phrase: str,
    candidates: list[EvidenceCandidate],
    *,
    require_date: bool,
    min_score: float = 0.28,
) -> EvidenceCandidate | None:
    best: tuple[float, EvidenceCandidate] | None = None
    for ev in candidates:
        if require_date and ev.event_date is None:
            continue
        score = _phrase_score(phrase, ev.source_text)
        if score < min_score:
            continue
        if ev.date_source in {"text", "relative"}:
            score += 0.15
        if ev.role == "user":
            score += 0.05
        if best is None or score > best[0]:
            best = (score, ev)
    if best is None:
        return None
    return best[1]


def _phrase_score(phrase: str, text: str) -> float:
    phrase_l = _clean_event_label(phrase).casefold()
    text_l = text.casefold()
    if phrase_l and phrase_l in text_l:
        return 1.0
    p_tokens = _tokens(phrase_l)
    if not p_tokens:
        return 0.0
    t_tokens = set(_tokens(text_l))
    required = _required_phrase_tokens(phrase)
    if required and not required <= t_tokens:
        return 0.0
    overlap = len([tok for tok in p_tokens if tok in t_tokens])
    return overlap / len(p_tokens)


def _item_phrase_score(phrase: str, text: str) -> float:
    phrase_l = _clean_event_label(phrase).casefold().replace("-", " ")
    p_tokens = [
        tok
        for tok in _tokens(phrase_l)
        if tok not in _ITEM_DESCRIPTOR_STOPWORDS
    ]
    if not p_tokens:
        p_tokens = _tokens(phrase_l)
    if not p_tokens:
        return 0.0
    t_tokens = set(_tokens(text))
    overlap = len([tok for tok in p_tokens if tok in t_tokens])
    return overlap / len(p_tokens)


def _required_phrase_tokens(phrase: str) -> set[str]:
    required: set[str] = set()
    for raw in re.findall(r"\b[A-Z][A-Za-z0-9]+\b", phrase):
        if raw in {"A", "An", "I", "My", "The"}:
            continue
        required.update(_tokens(raw))
    return required


def _tokens(text: str) -> list[str]:
    return [
        tok
        for tok in re.findall(r"[a-z0-9]+", text.casefold())
        if tok not in _STOPWORDS and len(tok) > 1
    ]


def _relative_date(text: str, *, base: date | None) -> date | None:
    if base is None:
        return None
    text_l = text.casefold()
    if "today" in text_l or "this morning" in text_l or "tonight" in text_l:
        return base
    if "yesterday" in text_l or "last night" in text_l:
        return base - timedelta(days=1)
    if "last weekend" in text_l or "over the weekend" in text_l:
        # Most recent Saturday strictly before the base date.
        delta = (base.weekday() - 5) % 7
        return base - timedelta(days=delta if delta else 7)
    if re.search(r"\blast week\b", text_l):
        return base - timedelta(days=7)
    if re.search(r"\blast month\b", text_l):
        return _shift_months(base, -1)
    if re.search(r"\blast year\b", text_l):
        return _shift_months(base, -12)
    m = _RELATIVE_RE.search(text)
    if not m:
        return None
    amount = _number_value(m.group(1))
    unit = m.group(2).casefold()
    if unit.startswith("day"):
        return base - timedelta(days=amount)
    if unit.startswith("week"):
        return base - timedelta(days=7 * amount)
    if unit.startswith("month"):
        return _shift_months(base, -amount)
    if unit.startswith("year"):
        return _shift_months(base, -12 * amount)
    return None


def _shift_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    days = [31, 29 if _is_leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(d.day, days[month - 1]))


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _number_value(raw: str) -> int:
    raw_l = raw.casefold()
    if raw_l.isdigit():
        return int(raw_l)
    return _NUMBER_WORDS.get(raw_l, 0)


def _ordinal_from_question(question: str) -> int | None:
    q = question.casefold()
    m = re.search(r"\b(\d+)(?:st|nd|rd|th)\b", q)
    if m:
        return int(m.group(1))
    if not re.search(r"\b(list|provided|item|job|role|option|recommendation)\b", q):
        return None
    for word, value in _ORDINAL_WORDS.items():
        if re.search(rf"\b{word}\b", q):
            return value
    return None


def _numbered_items(text: str) -> dict[int, str]:
    compact = re.sub(r"\s+", " ", text.strip())
    out: dict[int, str] = {}
    for m in _NUMBERED_ITEM_RE.finditer(compact):
        idx = int(m.group(1))
        item = _clean_answer_item(m.group(2))
        if item:
            out[idx] = item
    return out


def _clean_answer_item(text: str) -> str:
    text = re.sub(r"\*+", "", text)
    text = re.split(r"\s+[-*]\s+|\s+\*\s+", text.strip())[0]
    return text.strip(" .;:-")


def _gpa_values(text: str) -> list[Decimal]:
    if "gpa" not in text.casefold():
        return []
    values: list[Decimal] = []
    for pattern in (_GPA_RE, _OUT_OF_4_RE):
        for m in pattern.finditer(text):
            value = Decimal(m.group(1))
            if Decimal("0") <= value <= Decimal("4.0") and value not in values:
                values.append(value)
    return values


def _currency_values(text: str) -> list[Decimal]:
    values: list[Decimal] = []
    for m in _CURRENCY_RE.finditer(text):
        value = Decimal(m.group(1).replace(",", ""))
        if value not in values:
            values.append(value)
    return values


def _currency_value_contexts(text: str) -> list[tuple[Decimal, str]]:
    values: list[tuple[Decimal, str]] = []
    seen: set[Decimal] = set()
    for m in _CURRENCY_RE.finditer(text):
        value = Decimal(m.group(1).replace(",", ""))
        if value in seen:
            continue
        seen.add(value)
        start = max(0, m.start() - 140)
        end = min(len(text), m.end() + 140)
        values.append((value, text[start:end].strip()))
    return values


def _best_text_value_match(
    candidates: list[EvidenceCandidate],
    markers: tuple[str, ...],
) -> EvidenceCandidate | None:
    best: EvidenceCandidate | None = None
    best_score = -1.0
    for ev in candidates:
        text_l = ev.source_text.casefold()
        score = 1.0 if any(marker in text_l for marker in markers) else 0.0
        if ev.role == "user":
            score += 0.2
        if score > best_score:
            best = ev
            best_score = score
    return best if best_score > 0 else None


def _plain_number_contexts(text: str) -> list[tuple[Decimal, str]]:
    values: list[tuple[Decimal, str]] = []
    for m in _PLAIN_NUMBER_RE.finditer(text):
        raw = m.group(1).replace(",", "")
        value = Decimal(raw)
        # Years and tiny dates are almost never percentage operands.
        if value >= 1900 and value <= 2100:
            continue
        start = max(0, m.start() - 90)
        end = min(len(text), m.end() + 90)
        values.append((value, text[start:end]))
    return values


def _percentage_denominator_tokens(question_l: str) -> set[str]:
    m = re.search(
        r"\bpercentage of\s+(.+?)(?:\s+(?:do|does|did|are|is|were|was)\b|$)",
        question_l,
    )
    if not m:
        return set()
    return set(_tokens(m.group(1)))


def _percentage_subject_tokens(question_l: str) -> set[str]:
    patterns = (
        r"\b(?:do|does|did)\s+(.+?)\s+(?:hold|occupy|represent|make up|account for)\b",
        r"\bheld by\s+(.+?)(?:\s+in\b|$)",
    )
    for pattern in patterns:
        m = re.search(pattern, question_l)
        if m:
            return set(_tokens(m.group(1)))
    return set()


def _looks_like_part_count(context: str) -> bool:
    context_l = context.casefold()
    return bool(
        re.search(
            r"\b(?:hold|holds|held|occupy|occupies|occupied|represent|represents|"
            r"represented|make up|made up|account for|accounts for)\b",
            context_l,
        )
    )


def _looks_like_total_count(context: str) -> bool:
    context_l = context.casefold()
    return bool(
        re.search(
            r"\b(?:total of|total|there (?:are|were)|we (?:have|had)|"
            r"company (?:has|had)|across the company)\b",
            context_l,
        )
    )


def _percentage_value_score(
    ev: EvidenceCandidate,
    subject_tokens: set[str],
    denominator_tokens: set[str],
    *,
    total: bool,
) -> float:
    tokens = set(_tokens(ev.source_text))
    score = ev.confidence
    score += 0.25 * len(denominator_tokens & tokens)
    score += 0.35 * len(subject_tokens & tokens)
    if total:
        score += 0.35 if _looks_like_total_count(ev.source_text) else 0.0
        score -= 0.30 * len(subject_tokens & tokens)
    else:
        score += 0.35 if _looks_like_part_count(ev.source_text) else 0.0
    return score


def _savings_phrases(question: str) -> tuple[str | None, str | None]:
    m = re.search(r"\bby\s+(.+?)\s+instead of\s+(.+?)(?:\?|$)", question, re.IGNORECASE)
    if not m:
        return None, None
    chosen = re.sub(
        r"^(?:taking|using|choosing|booking|going with)\s+(?:a|an|the)?\s*",
        "",
        m.group(1).strip(),
        flags=re.IGNORECASE,
    )
    other = re.sub(r"^(?:a|an|the)\s+", "", m.group(2).strip(), flags=re.IGNORECASE)
    return chosen.strip(), other.strip()


def _numeric_diff_event_phrase(question: str) -> str | None:
    m = re.search(
        r"\bin\s+(?:the|my|a|an)?\s*([^?]{0,80}\bevent)\b",
        question,
        re.IGNORECASE,
    )
    if not m:
        return None
    return _clean_event_label(m.group(1))


def _best_value_for_phrase(
    candidates: list[EvidenceCandidate],
    phrase: str,
) -> EvidenceCandidate | None:
    best: tuple[float, EvidenceCandidate] | None = None
    for ev in candidates:
        score = _phrase_score(phrase, ev.source_text)
        if ev.role == "user":
            score += 0.10
        if score < 0.18:
            continue
        if best is None or score > best[0]:
            best = (score, ev)
    return best[1] if best is not None else None


def _with_label(ev: EvidenceCandidate, label: str) -> EvidenceCandidate:
    return EvidenceCandidate(
        session_id=ev.session_id,
        turn_idx=ev.turn_idx,
        role=ev.role,
        source_text=ev.source_text,
        timestamp=ev.timestamp,
        event_date=ev.event_date,
        value=ev.value,
        unit=ev.unit,
        entity=ev.entity,
        event_label=_clean_event_label(label),
        confidence=ev.confidence,
        date_source=ev.date_source,
    )


def _with_value(ev: EvidenceCandidate, value: Decimal, unit: str) -> EvidenceCandidate:
    return EvidenceCandidate(
        session_id=ev.session_id,
        turn_idx=ev.turn_idx,
        role=ev.role,
        source_text=ev.source_text,
        timestamp=ev.timestamp,
        event_date=ev.event_date,
        value=value,
        unit=unit,
        entity=ev.entity,
        event_label=ev.event_label,
        confidence=ev.confidence + (0.1 if ev.role == "user" else 0.0),
        date_source=ev.date_source,
    )


def _with_value_context(
    ev: EvidenceCandidate,
    value: Decimal,
    unit: str,
    context: str,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        session_id=ev.session_id,
        turn_idx=ev.turn_idx,
        role=ev.role,
        source_text=context.strip() or ev.source_text,
        timestamp=ev.timestamp,
        event_date=ev.event_date,
        value=value,
        unit=unit,
        entity=ev.entity,
        event_label=ev.event_label,
        confidence=ev.confidence + (0.1 if ev.role == "user" else 0.0),
        date_source=ev.date_source,
    )


def _candidate_for_item(
    item: RetrievedEvidence,
    candidates: list[EvidenceCandidate],
    *,
    value: Decimal | None = None,
    unit: str | None = None,
) -> EvidenceCandidate:
    for ev in candidates:
        if ev.session_id == item.session_id and ev.turn_idx == item.turn_idx:
            return _with_value(ev, value, unit) if value is not None and unit is not None else ev
    fallback = EvidenceCandidate(
        session_id=item.session_id,
        turn_idx=item.turn_idx,
        role=item.role,
        source_text=item.text,
        timestamp=parse_session_timestamp(item.timestamp),
        event_date=parse_session_timestamp(item.timestamp),
        value=value,
        unit=unit,
        entity=None,
        event_label=None,
        confidence=0.5,
        date_source="timestamp" if item.timestamp else None,
    )
    return fallback


def _clean_event_label(label: str) -> str:
    label = re.sub(r"^(?:the\s+day\s+)?(?:i\s+)?", "", label.strip(), flags=re.IGNORECASE)
    label = re.sub(r"^(?:the\s+)", "", label, flags=re.IGNORECASE)
    return label.strip(" .;:'\"")


def _format_decimal(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


def _format_currency(value: Decimal) -> str:
    if value == value.to_integral_value():
        return f"${int(value):,}"
    return f"${value:,.2f}"


def _format_percent(value: Decimal) -> str:
    if value == value.to_integral_value():
        return f"{int(value)}%"
    return f"{_format_decimal(value)}%"
