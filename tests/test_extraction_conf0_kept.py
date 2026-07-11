"""Regression: a genuine user fact emitted at confidence 0.0 must be KEPT.

Forensic context (2026-05-30 debug pass over the LongMemEval controller run
runs/m4w13_modal_hf_b1_controller): small local extractors (Qwen2.5-3B,
llama3) routinely parrot the prompt template's example ``extraction_confidence``
of 0.0 onto otherwise-valid items. An earlier ``extractor_postprocessor_v1``
dropped every item whose confidence was <= 0.0, which silently emptied 390/400
extractions on LongMemEval and sank MGP-6 T1 recall to 0.0.

The shipped fix (src/ksa/extraction/extractor.py) only drops *strictly negative*
confidence. This test pins that contract against a non-placeholder fact so the
drop bug cannot regress, and it is the model-free half of the forensic
before/after: under the old rule these items vanished; under the current rule
they survive.
"""

from __future__ import annotations

from ksa.extraction.extractor import _is_non_assertion, _postprocess_output
from ksa.extraction.schema import EvidenceSpan, ExtractedItem, ExtractionOutput


def _item(text: str, confidence: float) -> ExtractedItem:
    return ExtractedItem(
        text=text,
        type_guess="episodic_fact",
        evidence_span=EvidenceSpan(
            session_id="s1", turn_idx=2, char_start=0, char_end=len(text)
        ),
        extraction_confidence=confidence,
        negation_marker=False,
        hedge_marker=False,
        polarity_subject="user",
    )


def test_genuine_fact_at_confidence_zero_is_kept() -> None:
    """A real user fact stamped conf=0.0 must survive postprocessing."""
    text = "User graduated with a degree in Business Administration."
    out = _postprocess_output(
        ExtractionOutput(items=[_item(text, 0.0)], no_extractable_content=False),
        {"session_id": "s1", "turn_idx": 2, "content": "irrelevant turn body"},
    )
    assert out.no_extractable_content is False
    assert [i.text for i in out.items] == [text]
    assert out.items[0].extraction_confidence == 0.0


def test_confidence_is_not_used_for_filtering() -> None:
    """Confidence plays no filtering role: the schema clamps it to [0,1], so the
    postprocessor's ``< 0.0`` guard is unreachable. Any in-range confidence is
    kept. This documents that extraction quality cannot be controlled via the
    confidence channel — small models stamp 0.0 on both good facts and junk
    request-paraphrases, so a separate assertion-vs-request signal is required
    if over-extraction needs to be curbed."""
    for conf in (0.0, 0.01, 0.5, 1.0):
        out = _postprocess_output(
            ExtractionOutput(
                items=[_item("User dislikes loud cafes.", conf)],
                no_extractable_content=False,
            ),
            {"session_id": "s1", "turn_idx": 2, "content": "no rule-based fact here"},
        )
        assert [i.text for i in out.items] == ["User dislikes loud cafes."], conf


# --- over-extraction filter (question/request paraphrases) ------------------ #


def test_pure_questions_and_requests_are_dropped() -> None:
    for text in (
        "Which one do you think would be best for a beginner?",
        "Do you think she'd be interested in playing basketball?",
        "Can you plan a class about radiation therapy?",
        "What kind of festivals are celebrated in Monmouth?",
        "Write a case study for my portfolio page.",
    ):
        assert _is_non_assertion(text), text


def test_facts_with_trailing_questions_are_kept() -> None:
    """Declarative-led turns carrying a real fact must survive even if they end
    with a question — the filter is start-anchored, not '?'-anchored."""
    for text in (
        "I just got it from Best Buy for $350, what a steal, right?",
        "I'm planning to join a triathlon in June, any advice?",
        "User prefers green tea in the morning.",
        "My sister lives in Dallas.",
    ):
        assert not _is_non_assertion(text), text


def test_postprocess_drops_question_item_but_keeps_fact_item() -> None:
    q = _item("Do you think she'd like basketball?", 0.8)
    fact = _item("User plays basketball on Sundays.", 0.8)
    out = _postprocess_output(
        ExtractionOutput(items=[q, fact], no_extractable_content=False),
        {"session_id": "s1", "turn_idx": 2, "content": "no rule-based fact here"},
    )
    assert [i.text for i in out.items] == ["User plays basketball on Sundays."]
