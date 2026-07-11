"""Tests for the flat-vector baseline (M1-W3 §3.3).

Five contracts:
  1. The retrieved-memory block in the rendered prompt contains exactly
     the top-k indexed turns by cosine similarity to the question.
  2. With supporting evidence empty, the baseline degenerates to
     no-memory: the retrieved block reads `[no relevant memory found]`
     and the answer is non-empty.
  3. The retrieved block contains ZERO turns from the current session —
     the central anti-leakage guard.
  4. End-to-end determinism with `temperature=0.0` and a fixed seed.
  5. The `BaselineAnswer.extras` dict carries retrieval telemetry the
     §3.5 sanity-check workflow depends on.

Tests use `FakeEmbedder` (sha256-based hashing) and a `_RecordingLLM`
mirroring `tests/test_no_memory.py`'s pattern. No torch / sentence-
transformers required.
"""

from __future__ import annotations

import pytest

from ksa.baselines.embeddings import FakeEmbedder, role_tag
from ksa.baselines.flat_vector import (
    DEFAULT_SYSTEM_PROMPT,
    FlatVectorBaseline,
    build_session_corpus,
)
from ksa.baselines.flat_vector_store import FlatVectorStore
from ksa.data.longmemeval import LongMemEvalCorpusSession, LongMemEvalSession, LongMemEvalTurn
from ksa.inference.llm import LLMResponse

# faiss is required for the underlying store; skip if missing.
faiss = pytest.importorskip("faiss")


# --------------------------------------------------------------------- #
# Helpers / fixtures                                                     #
# --------------------------------------------------------------------- #


class _RecordingLLM:
    """Same Protocol-impl as in `test_no_memory.py`, copied for locality."""

    model_id = "recording-llm-v0"

    def __init__(self, response_text: str = "answer.") -> None:
        self.response_text = response_text
        self.last_prompt: str | None = None
        self.calls: int = 0

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        seed: int = 0,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        self.last_prompt = prompt
        self.calls += 1
        return LLMResponse(
            text=self.response_text,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(self.response_text.split()),
            latency_ms=0.0,
            seed=seed,
            temperature=temperature,
            model_id=self.model_id,
        )


def _session(
    sid: str,
    turns: list[tuple[str, str]],
    question: str,
    supporting: tuple[str, ...] = (),
    competency: str = "single-session-user",
    gold: str = "the gold answer",
) -> LongMemEvalSession:
    return LongMemEvalSession(
        session_id=sid,
        turns=tuple(LongMemEvalTurn(role=r, content=c) for r, c in turns),
        question=question,
        gold_answer=gold,
        competency=competency,
        supporting_session_ids=supporting,
    )


def _build_baseline(
    llm: _RecordingLLM,
    corpus_sessions: list[LongMemEvalSession],
    *,
    k: int = 5,
) -> FlatVectorBaseline:
    embedder = FakeEmbedder(embedding_dim=64)
    store = FlatVectorStore(embedder=embedder)
    corpus = build_session_corpus(corpus_sessions)
    return FlatVectorBaseline(llm=llm, store=store, corpus=corpus, k=k)


# --------------------------------------------------------------------- #
# Prompt-rendering contract                                              #
# --------------------------------------------------------------------- #


def test_render_prompt_includes_required_slots() -> None:
    """All four template slots are filled."""
    llm = _RecordingLLM()
    bl = _build_baseline(llm, [], k=3)
    sess_now = _session(
        "sess-now",
        [("user", "USER_TURN_MARKER"), ("assistant", "ASSISTANT_TURN_MARKER")],
        "QUESTION_MARKER",
    )
    rendered = bl.render_prompt(sess_now, retrieved=[])
    assert DEFAULT_SYSTEM_PROMPT in rendered
    assert "USER_TURN_MARKER" in rendered
    assert "ASSISTANT_TURN_MARKER" in rendered
    assert "QUESTION_MARKER" in rendered
    assert "RETRIEVED MEMORY" in rendered
    assert "DIALOG" in rendered
    assert "QUESTION" in rendered


def test_default_system_prompt_matches_no_memory_for_cross_baseline_consistency() -> None:
    """Cross-baseline numbers must not drift on system-prompt wording."""
    from ksa.baselines.no_memory import DEFAULT_SYSTEM_PROMPT as NO_MEM_SYS

    assert DEFAULT_SYSTEM_PROMPT == NO_MEM_SYS


# --------------------------------------------------------------------- #
# Top-k retrieval contract                                               #
# --------------------------------------------------------------------- #


def test_retrieved_memory_block_contains_top_k_turns_by_cosine_similarity() -> None:
    """On a 1-question fixture, the retrieved-memory block contains exactly the
    top-k indexed turns by cosine similarity to the question.

    Construct a session whose question text is identical to a specific
    indexed turn (via FakeEmbedder's deterministic hashing). That turn
    must appear at rank 0 with similarity ≈ 1.0.
    """
    llm = _RecordingLLM()
    # The "supporting" session contains 6 user turns; we make turn #3
    # match the question text.
    target_turn_text = "I prefer coffee in the morning, no sugar."
    other_session = _session(
        "sess-prior-1",
        [
            ("user", "Tell me about my last grocery list."),
            ("assistant", "You bought milk, bread, and eggs."),
            ("user", "Yes thanks."),
            # The user-tagged turn we want to retrieve. Note the role
            # tag is added inside the store (via embed_text) so the
            # query text below has to match exactly.
            ("user", target_turn_text),
            ("assistant", "Noted."),
            ("user", "Goodbye."),
        ],
        question="unused",
    )
    current_session = _session(
        "sess-now",
        [("user", "Some current dialog."), ("assistant", "An assistant reply.")],
        # The question text matches the role-tagged form of the turn we
        # planted, so the FakeEmbedder yields max similarity to it.
        question=role_tag("user", target_turn_text),
        supporting=("sess-prior-1",),
    )

    bl = _build_baseline(llm, [other_session, current_session], k=3)
    ans = bl.answer(current_session)
    rendered = ans.raw_prompt

    # The exact target turn text must appear in the retrieved block.
    assert target_turn_text in rendered
    # The retrieval telemetry confirms the rank-0 hit at session=prior-1, turn=3.
    extras = ans.extras
    assert extras["n_retrieved"] == 3
    assert extras["retrieval_session_ids"][0] == "sess-prior-1"
    assert extras["retrieval_turn_idxs"][0] == 3
    # Similarity is exactly 1.0 (same string → same hash → same vector).
    assert extras["retrieval_scores"][0] == pytest.approx(1.0, abs=1e-5)
    # Scores are descending.
    assert extras["retrieval_scores"] == sorted(
        extras["retrieval_scores"], reverse=True
    )


def test_no_current_session_leakage_in_retrieved_block() -> None:
    """The retrieved block must contain ZERO turns from the current session.

    This is the central anti-leakage check from `NOTES/m1w3_design.md`
    §2.5 — a leak here makes the flat-vector vs. no-memory comparison
    meaningless.
    """
    llm = _RecordingLLM()
    canary = "LEAK_CANARY_FROM_CURRENT_SESSION"
    other_session = _session(
        "sess-other",
        [("user", "PRIOR_TURN_OK_TO_RETRIEVE")],
        "unused",
    )
    current_session = _session(
        "sess-now",
        [("user", canary)],
        "what did the user say?",
        # supporting includes BOTH the current session and a prior one;
        # the baseline must filter out the current one.
        supporting=("sess-now", "sess-other"),
    )
    bl = _build_baseline(llm, [other_session, current_session])
    ans = bl.answer(current_session)
    extras = ans.extras

    # The retrieved-memory block in the rendered prompt must NOT include
    # any session_id == sess-now.
    assert "sess-now" not in extras["retrieval_session_ids"]
    # The dialog (current session) is rendered separately; the canary
    # appears there, but only there.
    rendered = ans.raw_prompt
    # Count occurrences: the canary must appear EXACTLY once (in the
    # DIALOG section, not in the RETRIEVED MEMORY section).
    n_occurrences = rendered.count(canary)
    assert n_occurrences == 1, (
        f"canary appeared {n_occurrences} times — expected exactly 1 "
        f"(in DIALOG section only). Prompt:\n{rendered}"
    )
    # And: the prior session's turn IS in retrieval.
    assert "sess-other" in extras["retrieval_session_ids"]


# --------------------------------------------------------------------- #
# Degenerate case: no supporting evidence                                #
# --------------------------------------------------------------------- #


def test_degenerates_to_no_memory_when_supporting_is_empty() -> None:
    """Empty supporting → empty retrieved block → still produces a non-empty answer.

    On the M1-W3 synthetic slice this is the path EVERY question takes
    (every supporting_session_ids is just the current session, which is
    filtered out). The baseline must not crash and must render a
    well-formed prompt.
    """
    llm = _RecordingLLM(response_text="some answer.")
    current_session = _session(
        "sess-alone",
        [("user", "hi"), ("assistant", "hi back")],
        "what did the user say?",
        supporting=("sess-alone",),  # only self → filtered → empty
    )
    bl = _build_baseline(llm, [current_session])
    ans = bl.answer(current_session)

    # Telemetry confirms the degenerate path.
    assert ans.extras["n_indexed"] == 0
    assert ans.extras["n_retrieved"] == 0
    # The answer is non-empty.
    assert ans.text == "some answer."
    # The retrieved-memory block reads as empty (the template emits a
    # `[no relevant memory found]` stub for this case).
    assert "[no relevant memory found]" in ans.raw_prompt


def test_degenerates_when_supporting_session_id_is_unresolvable() -> None:
    """Supporting IDs not in the corpus are silently dropped and logged in extras."""
    llm = _RecordingLLM()
    current_session = _session(
        "sess-now",
        [("user", "hi")],
        "q?",
        supporting=("sess-missing-1", "sess-missing-2"),
    )
    # Corpus only contains the current session; both supporting IDs are
    # unresolvable.
    bl = _build_baseline(llm, [current_session])
    ans = bl.answer(current_session)
    assert ans.extras["n_indexed"] == 0
    assert sorted(ans.extras["unresolved_supporting_ids"]) == [
        "sess-missing-1",
        "sess-missing-2",
    ]


def test_cleaned_schema_indexes_haystack_not_oracle_answer_ids() -> None:
    """Cleaned LongMemEval exposes answer_session_ids as gold labels, not a filter."""
    llm = _RecordingLLM()
    answer_text = "I now prefer green tea."
    distractor_text = "I like difficult chess puzzles."
    current = LongMemEvalSession(
        session_id="question-1",
        turns=(),
        question=role_tag("user", distractor_text),
        gold_answer="green tea",
        competency="knowledge-update",
        supporting_session_ids=("answer-session",),
        corpus_sessions=(
            LongMemEvalCorpusSession(
                session_id="distractor-session",
                turns=(LongMemEvalTurn(role="user", content=distractor_text),),
            ),
            LongMemEvalCorpusSession(
                session_id="answer-session",
                turns=(LongMemEvalTurn(role="user", content=answer_text),),
            ),
        ),
    )

    bl = _build_baseline(llm, [current], k=2)
    ans = bl.answer(current)

    assert ans.extras["supporting_session_ids"] == ["answer-session"]
    assert ans.extras["memory_session_ids"] == ["distractor-session", "answer-session"]
    assert ans.extras["n_indexed"] == 2
    assert ans.extras["retrieval_session_ids"][0] == "distractor-session"
    assert distractor_text in ans.raw_prompt


# --------------------------------------------------------------------- #
# Determinism + token-count fidelity                                     #
# --------------------------------------------------------------------- #


def test_determinism_same_session_same_seed() -> None:
    """End-to-end: same session + same seed → identical answer text + extras."""
    llm = _RecordingLLM(response_text="deterministic answer.")
    other_session = _session(
        "sess-prior", [("user", "prior content")], "unused"
    )
    current_session = _session(
        "sess-now",
        [("user", "current content")],
        "what was said?",
        supporting=("sess-prior",),
    )
    bl = _build_baseline(llm, [other_session, current_session], k=3)
    a = bl.answer(current_session)
    b = bl.answer(current_session)
    assert a.text == b.text
    assert a.text == "deterministic answer."
    assert a.session_id == "sess-now"
    assert a.baseline == "flat_vector"
    assert a.extras == b.extras
    # raw_prompt must be byte-identical too.
    assert a.raw_prompt == b.raw_prompt


def test_baseline_answer_shape_compatible_with_no_memory() -> None:
    """The `BaselineAnswer` shape must match `NoMemoryBaseline`'s.

    The evaluator runs duck-typed; if the shape diverges, the M1-W2
    `tests/test_longmemeval_eval.py` invariants regress.
    """
    llm = _RecordingLLM()
    sess = _session("s1", [("user", "hi")], "q?", supporting=())
    bl = _build_baseline(llm, [sess])
    ans = bl.answer(sess)
    assert ans.session_id == "s1"
    assert ans.baseline == "flat_vector"
    assert ans.model_id == "recording-llm-v0"
    # extras has the M1-W3-specific telemetry.
    assert "k" in ans.extras
    assert "n_retrieved" in ans.extras


def test_extras_carries_retrieval_telemetry() -> None:
    """The `extras` dict carries the fields §3.5 sanity-checking depends on."""
    llm = _RecordingLLM()
    other = _session("sess-prior", [("user", "x")], "unused")
    current = _session(
        "sess-now",
        [("user", "y")],
        "z?",
        supporting=("sess-prior",),
    )
    bl = _build_baseline(llm, [other, current], k=2)
    ans = bl.answer(current)
    extras = ans.extras
    # Required fields.
    for f in (
        "k",
        "n_indexed",
        "n_retrieved",
        "retrieval_scores",
        "retrieval_session_ids",
        "retrieval_turn_idxs",
        "embedder_model_id",
        "supporting_session_ids",
        "unresolved_supporting_ids",
    ):
        assert f in extras, f"extras missing {f!r}"
    assert extras["k"] == 2
    assert len(extras["retrieval_scores"]) == extras["n_retrieved"]
    assert len(extras["retrieval_session_ids"]) == extras["n_retrieved"]


# --------------------------------------------------------------------- #
# Index hygiene: per-question reset                                      #
# --------------------------------------------------------------------- #


def test_per_question_reset_does_not_leak_across_questions() -> None:
    """Indexing question N must not leave question N's items visible to question N+1."""
    llm = _RecordingLLM()
    leak_canary = "Q1_PRIOR_LEAK_CANARY"
    other_q1 = _session(
        "sess-q1-prior", [("user", leak_canary)], "unused"
    )
    q1 = _session(
        "sess-q1",
        [("user", "current")],
        "q1?",
        supporting=("sess-q1-prior",),
    )
    q2 = _session(
        "sess-q2",
        [("user", "current 2")],
        "q2?",
        supporting=(),  # nothing — should retrieve nothing
    )
    bl = _build_baseline(llm, [other_q1, q1, q2])

    ans1 = bl.answer(q1)
    assert ans1.extras["n_retrieved"] == 1

    ans2 = bl.answer(q2)
    assert ans2.extras["n_retrieved"] == 0
    # And the canary is NOT in q2's retrieved block.
    assert leak_canary not in ans2.raw_prompt


def test_baseline_name_is_flat_vector() -> None:
    """`evaluate_baseline` reads BASELINE_NAME from the class — pin it."""
    llm = _RecordingLLM()
    sess = _session("s1", [("user", "hi")], "q?", supporting=())
    bl = _build_baseline(llm, [sess])
    assert bl.BASELINE_NAME == "flat_vector"
    ans = bl.answer(sess)
    assert ans.baseline == "flat_vector"
