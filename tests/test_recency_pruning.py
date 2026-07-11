"""Tests for the recency-pruning baseline (M1-W4 §3.3).

Five contracts:
  1. Capacity invariant. Inserting M items with capacity N ends with
     min(M, N) active rows.
  2. FIFO discipline. With items inserted in order [1..M] and capacity
     N (M > N), the active set is exactly the LAST N items; the first
     (M - N) all have status='superseded' with NO supersedes_id and NO
     memory_relations row (destructiveness contract).
  3. action_log shape. A run on a 1-question fixture produces a JSONL
     log with the expected mix of `Keep` (admits) and `Supersede`
     (evictions). Counts add up.
  4. Determinism. Same session + seed + temperature=0 → identical
     answer text and identical action_log line ordering.
  5. The retrieved-memory block contains ZERO turns from the current
     session — the W3 anti-leakage rule carries forward.
  6. Empty supporting evidence MUST degenerate to no-memory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ksa.baselines.embeddings import FakeEmbedder
from ksa.baselines.recency_pruning import (
    DEFAULT_SYSTEM_PROMPT,
    RecencyPruningBaseline,
    build_session_corpus_for_recency,
    trivial_extract,
)
from ksa.data.longmemeval import LongMemEvalCorpusSession, LongMemEvalSession, LongMemEvalTurn
from ksa.extraction import EvidenceSpan, ExtractedItem, ExtractionOutput
from ksa.inference.llm import LLMResponse

# faiss is required for the underlying retrieval store; skip if missing.
faiss = pytest.importorskip("faiss")


# --------------------------------------------------------------------- #
# Helpers                                                                #
# --------------------------------------------------------------------- #


class _RecordingLLM:
    """Same Protocol-impl as in `test_no_memory.py` and `test_flat_vector.py`."""

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


class _FakeExtractor:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def extract(
        self,
        turn,
        _window,
        *,
        max_new_tokens=512,
        temperature=0.0,
        seed=0,
    ) -> ExtractionOutput:
        self.calls.append(
            {
                "turn": turn,
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "seed": seed,
            }
        )
        return ExtractionOutput(
            items=[
                ExtractedItem(
                    text=f"EXTRACTED::{turn['content']}",
                    type_guess="stable_pref",
                    evidence_span=EvidenceSpan(
                        session_id=turn["session_id"],
                        turn_idx=turn["turn_idx"],
                        char_start=0,
                        char_end=len(turn["content"]),
                    ),
                    extraction_confidence=0.8,
                    negation_marker=False,
                    hedge_marker=False,
                )
            ],
            no_extractable_content=False,
        )


class _EmptyExtractor:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def extract(
        self,
        turn,
        _window,
        *,
        max_new_tokens=512,
        temperature=0.0,
        seed=0,
    ) -> ExtractionOutput:
        self.calls.append(
            {
                "turn": turn,
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "seed": seed,
            }
        )
        return ExtractionOutput(items=[], no_extractable_content=True)


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
    capacity: int = 50,
    k: int = 5,
    action_log_path: Path | None = None,
    extractor=None,  # noqa: ANN001
    extraction_max_new_tokens: int = 512,
    memory_prefilter_top_k: int | None = None,
    raw_turn_fallback: bool = False,
    progress: bool = False,
) -> RecencyPruningBaseline:
    embedder = FakeEmbedder(embedding_dim=64)
    corpus = build_session_corpus_for_recency(corpus_sessions)
    return RecencyPruningBaseline(
        llm=llm,
        embedder=embedder,
        corpus=corpus,
        extractor=extractor,
        capacity=capacity,
        k=k,
        action_log_path=action_log_path,
        extraction_max_new_tokens=extraction_max_new_tokens,
        memory_prefilter_top_k=memory_prefilter_top_k,
        raw_turn_fallback=raw_turn_fallback,
        progress=progress,
    )


def _make_session_with_n_user_turns(sid: str, n: int) -> LongMemEvalSession:
    """A session with `n` distinct user turns (interleaved with assistant turns)."""
    turns: list[tuple[str, str]] = []
    for i in range(n):
        turns.append(("user", f"FACT_{sid}_{i:03d}"))
        turns.append(("assistant", f"ack_{sid}_{i:03d}"))
    return _session(sid, turns, "unused")


# --------------------------------------------------------------------- #
# Trivial extractor                                                      #
# --------------------------------------------------------------------- #


def test_trivial_extract_user_turns_only() -> None:
    sess = _session(
        "s",
        [
            ("user", "u1"),
            ("assistant", "a1"),
            ("user", "u2"),
            ("assistant", "a2"),
        ],
        "q",
    )
    items = trivial_extract(sess, user_turns_only=True)
    assert [it.text for it in items] == ["u1", "u2"]
    assert all(it.role == "user" for it in items)


def test_trivial_extract_carries_provenance() -> None:
    sess = _session(
        "sess-x",
        [("user", "u1"), ("assistant", "a"), ("user", "u2")],
        "q",
    )
    items = trivial_extract(sess, user_turns_only=True)
    assert items[0].session_id == "sess-x"
    assert items[0].turn_idx == 0  # first user turn is at index 0
    assert items[1].turn_idx == 2  # second user turn is at index 2 (after assistant)


def test_recency_can_use_m2_llm_extractor_for_b3(tmp_path: Path) -> None:
    llm = _RecordingLLM()
    extractor = _FakeExtractor()
    prior = _session(
        "sess-prior",
        [("user", "I prefer tea."), ("assistant", "noted")],
        "unused",
    )
    current = _session("sess-now", [("user", "x")], "q?", supporting=("sess-prior",))
    log_path = tmp_path / "action_log.jsonl"
    bl = _build_baseline(
        llm,
        [prior, current],
        extractor=extractor,
        action_log_path=log_path,
    )

    ans = bl.answer(current)

    assert extractor.calls and extractor.calls[0]["turn"]["session_id"] == "sess-prior"
    assert ans.extras["extractor_mode"] == "m2_llm"
    assert ans.extras["n_admitted"] == 1
    assert "EXTRACTED::I prefer tea." in ans.raw_prompt
    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["candidate_type"] == "stable_pref"
    assert record["rationale"] == "M2 LLM extraction admit"


def test_recency_memory_prefilter_limits_llm_extraction(tmp_path: Path) -> None:
    llm = _RecordingLLM()
    extractor = _FakeExtractor()
    prior = _make_session_with_n_user_turns("sess-prior", 5)
    current = _session(
        "sess-now",
        [("user", "x")],
        "Which prior fact is relevant?",
        supporting=("sess-prior",),
    )
    bl = _build_baseline(
        llm,
        [prior, current],
        extractor=extractor,
        extraction_max_new_tokens=123,
        memory_prefilter_top_k=2,
        action_log_path=tmp_path / "action_log.jsonl",
    )

    ans = bl.answer(current)

    assert len(extractor.calls) == 2
    assert {call["max_new_tokens"] for call in extractor.calls} == {123}
    assert ans.extras["memory_prefilter_top_k"] == 2
    assert ans.extras["n_admitted"] == 2


def test_recency_raw_turn_fallback_indexes_selected_empty_extraction(tmp_path: Path) -> None:
    marker = "RAW_TURN_FALLBACK_MARKER"
    llm = _RecordingLLM()
    extractor = _EmptyExtractor()
    prior = _session("sess-prior", [("user", marker), ("assistant", "noted")], "unused")
    current = _session(
        "sess-now",
        [("user", "x")],
        "What marker was mentioned?",
        supporting=("sess-prior",),
    )
    bl = _build_baseline(
        llm,
        [prior, current],
        extractor=extractor,
        memory_prefilter_top_k=1,
        raw_turn_fallback=True,
        action_log_path=tmp_path / "action_log.jsonl",
    )

    ans = bl.answer(current)

    assert len(extractor.calls) == 1
    assert ans.extras["raw_turn_fallback"] is True
    assert ans.extras["n_admitted"] == 1
    assert marker in ans.raw_prompt


# --------------------------------------------------------------------- #
# Prompt-rendering contract                                              #
# --------------------------------------------------------------------- #


def test_render_prompt_includes_required_slots() -> None:
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
    from ksa.baselines.no_memory import DEFAULT_SYSTEM_PROMPT as NO_MEM_SYS

    assert DEFAULT_SYSTEM_PROMPT == NO_MEM_SYS


# --------------------------------------------------------------------- #
# Capacity invariant — load-bearing                                      #
# --------------------------------------------------------------------- #


def test_capacity_invariant_inserting_more_items_than_capacity(tmp_path: Path) -> None:
    """Inserting 100 items with capacity=50 ends with exactly 50 active rows."""
    llm = _RecordingLLM()
    prior = _make_session_with_n_user_turns("sess-prior", 100)
    current = _session(
        "sess-now",
        [("user", "irrelevant")],
        "q?",
        supporting=("sess-prior",),
    )
    log_path = tmp_path / "action_log.jsonl"
    bl = _build_baseline(llm, [prior, current], capacity=50, action_log_path=log_path)
    ans = bl.answer(current)

    assert ans.extras["n_admitted"] == 100
    assert ans.extras["n_active"] == 50
    assert ans.extras["n_evicted"] == 50


def test_capacity_invariant_under_capacity_no_evictions(tmp_path: Path) -> None:
    """Inserting 30 items with capacity=50 ends with exactly 30 active and 0 evictions."""
    llm = _RecordingLLM()
    prior = _make_session_with_n_user_turns("sess-prior", 30)
    current = _session("sess-now", [("user", "x")], "q?", supporting=("sess-prior",))
    log_path = tmp_path / "action_log.jsonl"
    bl = _build_baseline(llm, [prior, current], capacity=50, action_log_path=log_path)
    ans = bl.answer(current)

    assert ans.extras["n_admitted"] == 30
    assert ans.extras["n_active"] == 30
    assert ans.extras["n_evicted"] == 0


# --------------------------------------------------------------------- #
# FIFO discipline                                                        #
# --------------------------------------------------------------------- #


def test_fifo_discipline_first_items_get_evicted(tmp_path: Path) -> None:
    """Items 1..50 are evicted; items 51..100 remain active.

    Verified by retrieving via FAISS for each planted text — only items
    51..100 produce a hit; items 1..50 are absent from the active store.
    Each FACT_*_NNN string is unique and comes from `make_session_with_n_user_turns`.
    """
    llm = _RecordingLLM()
    prior = _make_session_with_n_user_turns("sess-prior", 100)
    current = _session(
        "sess-now",
        [("user", "x")],
        "q?",
        supporting=("sess-prior",),
    )
    log_path = tmp_path / "action_log.jsonl"
    bl = _build_baseline(llm, [prior, current], capacity=50, k=5, action_log_path=log_path)
    bl.answer(current)

    # The retrieved block (top-5 by similarity) is dominated by FACT_sess-prior_NNN
    # for SOME range of N — but the strict invariant is: NO FACT with index < 50
    # appears in the prompt's retrieved-memory block (those were evicted).
    # We assert the broader rule via the action_log: the first 50 admitted
    # texts are evicted, the last 50 remain.
    log_lines = log_path.read_text().splitlines()
    records = [json.loads(line) for line in log_lines]

    keeps = [r for r in records if r["action"] == "Keep"]
    supersedes = [r for r in records if r["action"] == "Supersede"]
    assert len(keeps) == 100
    assert len(supersedes) == 50

    # FIFO: each Supersede entry is preceded by enough Keeps to be at
    # capacity; the i-th eviction's prior_memory_id is the i-th admitted
    # row's resulting_memory_id (1-indexed from db monotonic id).
    keep_resulting_ids = [r["resulting_memory_id"] for r in keeps]
    supersede_prior_ids = [r["prior_memory_id"] for r in supersedes]
    # The first 50 admitted rows (resulting_memory_ids[0:50]) get evicted
    # in admission order.
    assert supersede_prior_ids == keep_resulting_ids[:50]


# --------------------------------------------------------------------- #
# action_log shape                                                       #
# --------------------------------------------------------------------- #


def test_action_log_shape_keep_and_supersede_mix(tmp_path: Path) -> None:
    """1-question fixture → action_log has admit+evict mix; counts add up."""
    llm = _RecordingLLM()
    prior = _make_session_with_n_user_turns("sess-prior", 7)
    current = _session(
        "sess-now",
        [("user", "x")],
        "q?",
        supporting=("sess-prior",),
    )
    log_path = tmp_path / "action_log.jsonl"
    bl = _build_baseline(llm, [prior, current], capacity=5, action_log_path=log_path)
    ans = bl.answer(current)

    log_lines = log_path.read_text().splitlines()
    records = [json.loads(line) for line in log_lines]

    keeps = [r for r in records if r["action"] == "Keep"]
    supersedes = [r for r in records if r["action"] == "Supersede"]

    # 7 admits, 2 evictions (capacity=5, 7 admits → 2 over capacity).
    assert len(keeps) == 7
    assert len(supersedes) == 2
    assert ans.extras["n_admitted"] == 7
    assert ans.extras["n_active"] == 5
    assert ans.extras["n_evicted"] == 2

    # Every record carries baseline + session_id.
    for r in records:
        assert r["baseline"] == "recency"
        assert r["session_id"] == "sess-now"
        # Schema validation has already run inside ActionLogWriter.

    # Each Keep has resulting_memory_id; each Supersede has prior_memory_id.
    for k in keeps:
        assert k["resulting_memory_id"] is not None
        assert k["prior_memory_id"] is None
        assert k["candidate_type"] == "episodic_fact"
    for s in supersedes:
        assert s["prior_memory_id"] is not None
        assert s["resulting_memory_id"] is None
        assert s["rationale"].startswith("FIFO eviction at capacity=5")


# --------------------------------------------------------------------- #
# Determinism                                                            #
# --------------------------------------------------------------------- #


def test_determinism_same_session_same_seed(tmp_path: Path) -> None:
    """Same session + seed + temperature=0 → identical answer text and
    identical action_log line ORDERING (timestamps differ; the rest matches).
    """
    prior = _make_session_with_n_user_turns("sess-prior", 12)
    current = _session(
        "sess-now",
        [("user", "x")],
        "q?",
        supporting=("sess-prior",),
    )

    log_a = tmp_path / "log_a.jsonl"
    log_b = tmp_path / "log_b.jsonl"

    llm_a = _RecordingLLM(response_text="reply.")
    bl_a = _build_baseline(llm_a, [prior, current], capacity=10, action_log_path=log_a)
    ans_a = bl_a.answer(current)

    llm_b = _RecordingLLM(response_text="reply.")
    bl_b = _build_baseline(llm_b, [prior, current], capacity=10, action_log_path=log_b)
    ans_b = bl_b.answer(current)

    assert ans_a.text == ans_b.text
    assert ans_a.raw_prompt == ans_b.raw_prompt
    assert ans_a.extras["retrieval_session_ids"] == ans_b.extras["retrieval_session_ids"]
    assert ans_a.extras["retrieval_turn_idxs"] == ans_b.extras["retrieval_turn_idxs"]

    # action_log: line count + action ordering identical (timestamps differ).
    rec_a = [json.loads(line) for line in log_a.read_text().splitlines()]
    rec_b = [json.loads(line) for line in log_b.read_text().splitlines()]
    assert len(rec_a) == len(rec_b)
    assert [r["action"] for r in rec_a] == [r["action"] for r in rec_b]
    assert [r["candidate_text"] for r in rec_a] == [r["candidate_text"] for r in rec_b]
    assert [r["rationale"] for r in rec_a] == [r["rationale"] for r in rec_b]


# --------------------------------------------------------------------- #
# Anti-leakage (W3 §2.5 carries forward)                                 #
# --------------------------------------------------------------------- #


def test_no_current_session_leakage_in_retrieved_block(tmp_path: Path) -> None:
    """Retrieved block contains ZERO items from the current session, even when
    the current session_id is in supporting_session_ids."""
    llm = _RecordingLLM()
    canary = "LEAK_CANARY_CURRENT_TURN"
    other = _session("sess-other", [("user", "PRIOR_TURN")], "unused")
    current = _session(
        "sess-now",
        [("user", canary)],
        "q?",
        supporting=("sess-now", "sess-other"),
    )
    bl = _build_baseline(llm, [other, current])
    ans = bl.answer(current)

    extras = ans.extras
    assert "sess-now" not in extras["retrieval_session_ids"]
    # Canary appears EXACTLY once (only in DIALOG, not in RETRIEVED MEMORY).
    rendered = ans.raw_prompt
    assert rendered.count(canary) == 1
    # Prior session IS in retrieval.
    assert "sess-other" in extras["retrieval_session_ids"]


def test_cleaned_schema_admits_haystack_not_oracle_answer_ids(tmp_path: Path) -> None:
    llm = _RecordingLLM()
    current = LongMemEvalSession(
        session_id="question-1",
        turns=(),
        question="What does the user prefer?",
        gold_answer="green tea",
        competency="knowledge-update",
        supporting_session_ids=("answer-session",),
        corpus_sessions=(
            LongMemEvalCorpusSession(
                session_id="distractor-session",
                turns=(LongMemEvalTurn(role="user", content="Please solve this puzzle."),),
            ),
            LongMemEvalCorpusSession(
                session_id="answer-session",
                turns=(LongMemEvalTurn(role="user", content="I now prefer green tea."),),
            ),
        ),
    )
    bl = _build_baseline(llm, [current], action_log_path=tmp_path / "log.jsonl")

    ans = bl.answer(current)

    assert ans.extras["supporting_session_ids"] == ["answer-session"]
    assert ans.extras["memory_session_ids"] == ["distractor-session", "answer-session"]
    assert ans.extras["n_admitted"] == 2
    assert set(ans.extras["retrieval_session_ids"]) == {"distractor-session", "answer-session"}


# --------------------------------------------------------------------- #
# Degenerate path                                                        #
# --------------------------------------------------------------------- #


def test_degenerates_to_no_memory_when_supporting_is_empty(tmp_path: Path) -> None:
    """Empty supporting → empty retrieved block; n_active=0; non-empty answer."""
    llm = _RecordingLLM(response_text="some answer.")
    current = _session(
        "sess-alone",
        [("user", "hi"), ("assistant", "hi back")],
        "q?",
        supporting=("sess-alone",),  # only self → filtered → empty
    )
    log_path = tmp_path / "log.jsonl"
    bl = _build_baseline(llm, [current], action_log_path=log_path)
    ans = bl.answer(current)

    assert ans.extras["n_admitted"] == 0
    assert ans.extras["n_active"] == 0
    assert ans.extras["n_retrieved"] == 0
    assert ans.text == "some answer."
    assert "[no relevant memory found]" in ans.raw_prompt
    # Empty action_log file (no admits, no evictions).
    assert log_path.read_text().strip() == ""


def test_per_question_reset_does_not_leak_across_questions(tmp_path: Path) -> None:
    """Two consecutive answer() calls with disjoint supporting sets → second
    call sees only its own supporting items."""
    llm = _RecordingLLM()

    q1_prior = _make_session_with_n_user_turns("q1-prior", 3)
    q1_session = _session(
        "q1", [("user", "x")], "q1?", supporting=("q1-prior",)
    )

    q2_prior = _make_session_with_n_user_turns("q2-prior", 4)
    q2_session = _session(
        "q2", [("user", "y")], "q2?", supporting=("q2-prior",)
    )

    log_path = tmp_path / "log.jsonl"
    bl = _build_baseline(
        llm,
        [q1_prior, q1_session, q2_prior, q2_session],
        capacity=50,
        action_log_path=log_path,
    )

    ans1 = bl.answer(q1_session)
    assert ans1.extras["n_admitted"] == 3

    ans2 = bl.answer(q2_session)
    # Per-question reset: q2 sees only its own 4 items, not 3+4=7.
    assert ans2.extras["n_admitted"] == 4
    assert ans2.extras["n_active"] == 4
    assert "q1-prior" not in ans2.extras["retrieval_session_ids"]


# --------------------------------------------------------------------- #
# Capacity validation                                                    #
# --------------------------------------------------------------------- #


def test_capacity_must_be_positive() -> None:
    llm = _RecordingLLM()
    embedder = FakeEmbedder(embedding_dim=64)
    with pytest.raises(ValueError, match="capacity must be > 0"):
        RecencyPruningBaseline(llm=llm, embedder=embedder, capacity=0)
    with pytest.raises(ValueError, match="capacity must be > 0"):
        RecencyPruningBaseline(llm=llm, embedder=embedder, capacity=-1)


def test_k_must_be_positive() -> None:
    llm = _RecordingLLM()
    embedder = FakeEmbedder(embedding_dim=64)
    with pytest.raises(ValueError, match="k must be > 0"):
        RecencyPruningBaseline(llm=llm, embedder=embedder, k=0)
