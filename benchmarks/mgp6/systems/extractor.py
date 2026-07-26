"""Shared closed-book evidence extractor for MGP-6 v2.

All memory-using systems (B2, B3, B4, controller) call this SAME extractor so
that the comparison isolates *write governance*, not extraction quality (the
spec requires every memory-using system to receive identical raw evidence).

The extractor sees only the closed-book inputs: ``base_dialogue_prefix``,
``initial_memory_state`` and ``perturbation_event``. It never reads gold
fields, source/temporal annotations, ``conflict_type`` or ``semantic_slot``
top-level labels. The slot name is taken from the prior *memory record*, which
is a legitimate model input, not a gold annotation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def memory_value(text: str) -> str:
    """Return the value side of an auditable ``slot = value`` record."""
    return text.split("=", 1)[1].strip() if "=" in text else text.strip()


# --- governance signal cue phrases (all matched case-insensitively) ---------

_THIRD_PARTY_CUES = (
    r"shared note quotes",
    r"no indication of who wrote",
    r"a note reads",
    r"someone wrote",
    r"unattributed",
    r"a forum post reads",
    r"a stranger",
)
_LAUNDERING_CUES = (
    r"garbled",
    r"\[inaudible\]",
    r"the extractor (?:still )?logged",
    r"the assistant guessed",
    r"assistant inferred",
    r"a recommendation tool suggested",
    r"never confirmed",
    r"voice note",
    r"low[- ]confidence",
    r"could work once",
    r"might (?:be|prefer|have)",
    r"maybe\b",
)
_TEMP_OVERRIDE_CLEAR = (
    r"just for tonight",
    r"just for today",
    r"only for (?:today|tonight|now|this)",
    r"for tonight only",
    r"my usual still stands",
    r"temporarily",
    r"this once",
)
_TEMP_HEDGED = (
    r"maybe .* for now",
    r"not sure",
    r"might switch",
    r"thinking about",
    r"i guess",
    r"perhaps",
)
_DURABLE_CUES = (
    r"\bnow\b",
    r"instead of",
    r"i switched",
    r"actually",
    r"please remember",
    r"from now on",
    r"for good",
    r"going forward",
)


def _any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


# --- candidate value extraction ---------------------------------------------

_VALUE_PATTERNS = (
    # explicit "slot = value" laundered form: "... logged dietary preference = vegetarian at 0.98"
    r"=\s*(?P<v>[^.;]+?)(?:\s+at\s+[\d.]|[.;]|$)",
    # "use X for my ... preference"
    r"\buse\s+(?P<v>.+?)\s+for\s+(?:my|the)\b",
    # "guessed their ... might be X" / "suggested X for"
    r"might be\s+(?P<v>[^.;]+?)(?:[.;]|$)",
    r"tool suggested\s+(?P<v>.+?)\s+for\b",
    # leading "X has become ...", "X has been ...", "X stay(s) ..."
    r"^(?P<v>.+?)\s+has\s+become\b",
    r"^(?P<v>.+?)\s+has\s+been\b",
    r"^(?P<v>.+?)\s+stays?\s+on\b",
    # "I eat X food", "I look for somewhere X", "I make X"
    r"\bi\s+eat\s+(?P<v>.+?)\s+food\b",
    r"\blook\s+for\s+somewhere\s+(?P<v>[^.,;]+)",
    # "Write all of my ... in X"
    r"\bin\s+(?P<v>[^.,;]+?)(?:[.;]|$)",
    # times/dates: "at 4:00 PM", "lists May 16 as", "a 9:25 AM train"
    r"\bat\s+(?P<v>\d{1,2}:\d{2}\s*[AP]M)\b",
    r"\blists\s+(?P<v>[A-Z][a-z]+\s+\d{1,2})\s+as\b",
    r"\ba\s+(?P<v>\d{1,2}:\d{2}\s*[AP]M)\s+train\b",
    r"\bshows?\s+(?P<v>[^.,;]+?)(?:\s+as|[.;]|$)",
    # captions family: "Captions stay on", "captions on"
    r"\b(?P<v>captions?\s+on)\b",
)

_STRIP = " \t\n\"'-.,"
_TAIL = r"(?:,\s*not\b|\s+for good\b|\s+as\b|\s+at\s+[\d.]|[.;]|$)"


def _slot_phrases(slot: str) -> list[str]:
    """Surface phrasings of a snake_case slot, longest first."""
    base = slot.replace("_", " ").strip()
    phrases = {base}
    trimmed = re.sub(
        r"\s+(preference|date|time|style|mode|channel|format|unit|scheme)$", "", base
    ).strip()
    if trimmed:
        phrases.add(trimmed)
    phrases.add(re.sub(r"\s+preference$", "", base).strip())
    return sorted((p for p in phrases if p), key=len, reverse=True)


def _clean(v: str) -> str | None:
    v = v.strip(_STRIP)
    v = re.sub(r"\s+(preference|food)$", "", v, flags=re.I).strip(_STRIP)
    return v if 0 < len(v) <= 40 else None


def extract_value(
    perturbation: str,
    quoted_inner: str | None = None,
    slot: str | None = None,
) -> str | None:
    """Best-effort candidate value from raw perturbation text (no gold peek)."""
    text = quoted_inner if quoted_inner is not None else perturbation

    # 1) slot-anchored: "<slot phrase> (is|=|over to|to|:) VALUE <tail>"
    if slot:
        for phrase in _slot_phrases(slot):
            pat = re.escape(phrase) + r"\s*(?:is|are|=|over to|:|to)\s+(?P<v>.+?)" + _TAIL
            m = re.search(pat, text, re.I)
            if m and (v := _clean(m.group("v"))):
                return v

    # 2) generic template patterns
    for pat in _VALUE_PATTERNS:
        m = re.search(pat, text, re.I)
        if m and (v := _clean(m.group("v"))):
            return v

    # 3) copula fallback: "... is VALUE, not OLD" / "... is VALUE."
    m = re.search(r"\bis\s+(?P<v>.+?)(?:,\s*not\b|[.;]|$)", text, re.I)
    if m and (v := _clean(m.group("v"))):
        return v
    return None


_QUOTE_RE = re.compile(r'["“”\'‘’](?P<q>[^"“”]+)["“”\'‘’]')


def quoted_inner(perturbation: str) -> str | None:
    m = _QUOTE_RE.search(perturbation)
    return m.group("q") if m else None


@dataclass
class Evidence:
    """Structured, closed-book reading of one perturbation."""

    slot: str
    prior_value: str
    prior_record: dict[str, Any]
    candidate_value: str | None
    # governance signals inferred purely from surface text
    third_party_unattributed: bool = False
    laundered_or_noisy: bool = False
    temporary_clear: bool = False
    temporary_hedged: bool = False
    durable_cue: bool = False
    quality_flags: list[str] = field(default_factory=list)

    @property
    def has_candidate(self) -> bool:
        return bool(self.candidate_value)

    @property
    def candidate_conflicts(self) -> bool:
        return self.has_candidate and self.candidate_value.casefold() != self.prior_value.casefold()


def active_prior(initial_memory_state: list[dict[str, Any]]) -> dict[str, Any] | None:
    actives = [r for r in initial_memory_state if r.get("status") == "active"]
    return actives[0] if actives else None


def read_evidence(scenario: dict[str, Any]) -> Evidence | None:
    """Parse the closed-book evidence for a scenario. Returns None if no prior."""
    prior = active_prior(scenario.get("initial_memory_state", []))
    if prior is None:
        return None
    slot = prior.get("semantic_slot", "")
    perturbation = scenario.get("perturbation_event", "")

    q = quoted_inner(perturbation)
    third_party = _any(_THIRD_PARTY_CUES, perturbation)
    laundered = _any(_LAUNDERING_CUES, perturbation)
    temp_clear = _any(_TEMP_OVERRIDE_CLEAR, perturbation)
    temp_hedged = _any(_TEMP_HEDGED, perturbation) and not temp_clear

    # For an unattributed quote, the *value* lives inside the quote.
    cand = extract_value(
        perturbation,
        quoted_inner=q if third_party else None,
        slot=slot,
    )

    return Evidence(
        slot=slot,
        prior_value=memory_value(prior.get("text", "")),
        prior_record=prior,
        candidate_value=cand,
        third_party_unattributed=third_party,
        laundered_or_noisy=laundered,
        temporary_clear=temp_clear,
        temporary_hedged=temp_hedged,
        durable_cue=_any(_DURABLE_CUES, perturbation),
    )
