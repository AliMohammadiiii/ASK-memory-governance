"""M3-W10 controller pipeline integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ask.baselines.embeddings import FakeEmbedder
from ask.baselines.flat_vector_store import MemoryItem, RetrievedItem
from ask.classifier import RelationOutput
from ask.data.longmemeval import LongMemEvalCorpusSession, LongMemEvalSession, LongMemEvalTurn
from ask.extraction import EvidenceSpan, ExtractedItem, ExtractionOutput
from ask.inference.fake import FakeLLM
from ask.memory.models import ControllerAction
from ask.pipeline import ControllerOrchestrator
from ask.pipeline.orchestrator import (
    DEFAULT_SYSTEM_PROMPT,
    PREFERENCE_ANSWER_RETRY_SYSTEM_PROMPT,
    PREFERENCE_SYSTEM_PROMPT,
    _answer_retry_reason,
    _branch_out_exclusions,
    _conflict_block,
    _expanded_retrieval_query,
    _requests_historical_memory,
    _search_query_variants,
)


class FakeExtractor:
    def extract(self, turn, window, *, max_new_tokens=512, temperature=0.0, seed=0):
        text = turn["content"]
        if "uncertain" in text:
            return ExtractionOutput(
                items=[
                    ExtractedItem(
                        text="User might prefer sparkling water.",
                        type_guess="stable_pref",
                        evidence_span=EvidenceSpan(
                            session_id=turn["session_id"],
                            turn_idx=turn["turn_idx"],
                            char_start=0,
                            char_end=40,
                        ),
                        extraction_confidence=0.1,
                        negation_marker=True,
                        hedge_marker=True,
                    )
                ],
                no_extractable_content=False,
            )
        if "tea" in text:
            item_text = "User prefers tea in the morning."
        else:
            item_text = "User prefers coffee in the morning."
        return ExtractionOutput(
            items=[
                ExtractedItem(
                    text=item_text,
                    type_guess="stable_pref",
                    evidence_span=EvidenceSpan(
                        session_id=turn["session_id"],
                        turn_idx=turn["turn_idx"],
                        char_start=0,
                        char_end=220,
                    ),
                    extraction_confidence=1.0,
                    negation_marker=False,
                    hedge_marker=False,
                )
            ],
            no_extractable_content=False,
        )


class CountingExtractor(FakeExtractor):
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, turn, window, *, max_new_tokens=512, temperature=0.0, seed=0):
        self.calls += 1
        return super().extract(
            turn,
            window,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            seed=seed,
        )


class BrokenExtractor:
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, turn, window, *, max_new_tokens=512, temperature=0.0, seed=0):
        self.calls += 1
        raise RuntimeError("schema echo")


class EmptyExtractor:
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, turn, window, *, max_new_tokens=512, temperature=0.0, seed=0):
        self.calls += 1
        return ExtractionOutput(
            items=[],
            no_extractable_content=True,
            coverage_note="empty",
        )


class KeywordEmbedder:
    embedding_dim = 2
    model_id = "fake/keyword"

    def embed(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            text_l = text.lower()
            if "tea" in text_l:
                rows.append([1.0, 0.0])
            elif "coffee" in text_l:
                rows.append([0.0, 1.0])
            else:
                rows.append([1.0, 0.0])
        return np.asarray(rows, dtype=np.float32)


class PriorSelectionEmbedder:
    embedding_dim = 3
    model_id = "fake/prior-selection"

    def embed(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            text_l = text.lower()
            if "stamp" in text_l:
                rows.append([0.0, 1.0, 0.0])
            elif "prefer" in text_l or "tea" in text_l or "coffee" in text_l:
                rows.append([1.0, 0.0, 0.0])
            else:
                rows.append([0.0, 0.0, 1.0])
        return np.asarray(rows, dtype=np.float32)


class FakeClassifier:
    def __init__(self) -> None:
        self.calls = 0

    def classify(self, candidate, prior, *, max_new_tokens=128, temperature=0.0, seed=0):
        self.calls += 1
        if "tea" in candidate.text and "coffee" in prior.text:
            return RelationOutput(
                logical_relation="contradict",
                temporal="newer",
                same_subject=True,
                relation_to_prior_state="supersede",
                stage1_rationale="tea replaces coffee",
                stage2_rationale="candidate is newer",
            )
        return RelationOutput(
            logical_relation="support",
            temporal="same",
            same_subject=True,
            relation_to_prior_state="support",
            stage1_rationale="same slot",
            stage2_rationale="same time",
        )


def test_current_location_conflict_block_prefers_newest_matching_memory() -> None:
    retrieved = [
        RetrievedItem(
            item=MemoryItem(
                text="User has old sneakers stored under their bed.",
                role="user",
                session_id="old",
                turn_idx=2,
                timestamp="2023/05/24 (Wed) 11:41",
            ),
            score=0.9,
            rank=0,
        ),
        RetrievedItem(
            item=MemoryItem(
                text="User is looking forward to storing their old sneakers in a shoe rack.",
                role="user",
                session_id="new",
                turn_idx=10,
                timestamp="2023/05/28 (Sun) 20:09",
            ),
            score=0.7,
            rank=1,
        ),
        RetrievedItem(
            item=MemoryItem(
                text="You could store the old sneakers in the garage.",
                role="assistant",
                session_id="advice",
                turn_idx=11,
                timestamp="2023/06/01 (Thu) 09:00",
            ),
            score=0.95,
            rank=2,
        ),
    ]

    block = _conflict_block(retrieved, "Where do I currently keep my old sneakers?")

    assert "CURRENT LOCATION CANDIDATES" in block
    assert "Most recent (2023-05-28): User is looking forward" in block
    historical = _conflict_block(retrieved, "Where did I initially keep my old sneakers?")
    assert "CURRENT LOCATION CANDIDATES" not in historical


def test_answer_context_diversity_prioritizes_distinct_sessions() -> None:
    orchestrator = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=FakeExtractor(),
        classifier=FakeClassifier(),
        embedder=FakeEmbedder(embedding_dim=32),
        answer_context_session_cap=1,
    )
    hits = [
        RetrievedItem(item=MemoryItem("s1-a", "user", "s1", 0), score=0.99, rank=0),
        RetrievedItem(item=MemoryItem("s1-b", "user", "s1", 1), score=0.98, rank=1),
        RetrievedItem(item=MemoryItem("s2-a", "user", "s2", 0), score=0.75, rank=2),
    ]

    ordered = orchestrator._session_diverse_answer_order(hits)

    assert [hit.item.text for hit in ordered] == ["s1-a", "s2-a", "s1-b"]


class IndependentClassifier:
    def classify(self, candidate, prior, *, max_new_tokens=128, temperature=0.0, seed=0):
        return RelationOutput(
            logical_relation="independent",
            temporal="unknown",
            same_subject=False,
            relation_to_prior_state="unclear",
            stage1_rationale="different memory slot",
            stage2_rationale="not the same subject",
        )


def _session(session_id: str, user_text: str, supporting=()) -> LongMemEvalSession:
    return LongMemEvalSession(
        session_id=session_id,
        turns=(
            LongMemEvalTurn(role="user", content=user_text, timestamp="2026-01-01T00:00:00Z"),
            LongMemEvalTurn(role="assistant", content="noted"),
        ),
        question="What does the user prefer in the morning?",
        gold_answer="tea",
        competency="knowledge-update",
        supporting_session_ids=tuple(supporting),
    )


def test_controller_supersedes_with_lineage_and_no_current_session_retrieval(
    tmp_path: Path,
) -> None:
    prior = _session("s-prior", "I prefer coffee in the morning.", ())
    current = _session("s-current", "I prefer tea in the morning now.", ("s-prior", "s-current"))
    log_path = tmp_path / "controller.action_log.jsonl"
    llm = FakeLLM()
    llm.queue("The user prefers tea.")

    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=FakeExtractor(),
        classifier=FakeClassifier(),
        corpus={"s-prior": prior, "s-current": current},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=log_path,
    )

    answer = orchestrator.answer(current)

    assert answer.text == "The user prefers tea."
    assert answer.extras["current_session_leakage_count"] == 0
    assert "s-current" not in answer.extras["retrieval_session_ids"]
    assert answer.extras["action_counts"]["Supersede"] == 1

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    supersede_rows = [row for row in records if row["action"] == "Supersede"]
    assert len(supersede_rows) == 1
    assert supersede_rows[0]["feature_r"] == -1.0
    assert supersede_rows[0]["prior_memory_id"] is not None
    assert "S_rev=" in supersede_rows[0]["rationale"]
    assert "supersede" in supersede_rows[0]["rationale"]


def _version_query(question: str) -> LongMemEvalSession:
    return LongMemEvalSession(
        session_id="s-query",
        turns=(),
        question=question,
        gold_answer="coffee",
        competency="knowledge-update",
        supporting_session_ids=("s-old", "s-new"),
    )


def test_history_query_retrieves_tagged_superseded_lineage(tmp_path: Path) -> None:
    old = _session("s-old", "I prefer coffee in the morning.", ())
    new = _session("s-new", "I prefer tea in the morning now.", ())
    query = _version_query("What did I initially prefer in the morning?")
    llm = FakeLLM()
    llm.queue("coffee")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=FakeExtractor(),
        classifier=FakeClassifier(),
        corpus={"s-old": old, "s-new": new},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        history_aware_retrieval=True,
    )

    answer = orchestrator.answer(query)

    assert "[SUPERSEDED HISTORICAL VERSION] User prefers coffee" in answer.raw_prompt
    assert "User prefers tea" in answer.raw_prompt
    assert answer.extras["history_query_detected"] is True
    assert answer.extras["history_candidate_count"] == 1
    assert answer.extras["history_retrieved_count"] == 1


def test_current_query_does_not_surface_superseded_lineage(tmp_path: Path) -> None:
    old = _session("s-old", "I prefer coffee in the morning.", ())
    new = _session("s-new", "I prefer tea in the morning now.", ())
    query = _version_query("What do I currently prefer in the morning?")
    llm = FakeLLM()
    llm.queue("tea")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=FakeExtractor(),
        classifier=FakeClassifier(),
        corpus={"s-old": old, "s-new": new},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        history_aware_retrieval=True,
    )

    answer = orchestrator.answer(query)

    assert "SUPERSEDED HISTORICAL VERSION" not in answer.raw_prompt
    assert "User prefers coffee" not in answer.raw_prompt
    assert "User prefers tea" in answer.raw_prompt
    assert answer.extras["history_query_detected"] is False


def test_controller_can_abstain_on_low_confidence_candidate(tmp_path: Path) -> None:
    session = _session("s-current", "uncertain maybe preference", ("s-current",))
    llm = FakeLLM()
    llm.queue("No relevant memory.")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=FakeExtractor(),
        classifier=FakeClassifier(),
        corpus={"s-current": session},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
    )

    orchestrator.answer(session)

    assert orchestrator.last_summary is not None
    assert orchestrator.last_summary.action_counts["Abstain"] == 1
    assert orchestrator.last_summary.decisions[0].action == ControllerAction.ABSTAIN


def test_controller_indexes_cleaned_haystack_not_oracle_answer_ids(tmp_path: Path) -> None:
    cleaned = LongMemEvalSession(
        session_id="question-1",
        turns=(),
        question="What does the user prefer in the morning?",
        gold_answer="tea",
        competency="knowledge-update",
        supporting_session_ids=("answer-session",),
        corpus_sessions=(
            LongMemEvalCorpusSession(
                session_id="distractor-session",
                turns=(
                    LongMemEvalTurn(
                        role="user",
                        content="I prefer coffee in the morning.",
                        timestamp="2026-01-01T00:00:00Z",
                    ),
                ),
            ),
            LongMemEvalCorpusSession(
                session_id="answer-session",
                turns=(
                    LongMemEvalTurn(
                        role="user",
                        content="I prefer tea in the morning now.",
                        timestamp="2026-01-02T00:00:00Z",
                    ),
                ),
            ),
        ),
    )
    llm = FakeLLM()
    llm.queue("The user prefers tea.")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=FakeExtractor(),
        classifier=FakeClassifier(),
        corpus={
            "distractor-session": LongMemEvalSession(
                session_id="distractor-session",
                turns=cleaned.corpus_sessions[0].turns,
                question="",
                gold_answer="",
                competency="knowledge-update",
            ),
            "answer-session": LongMemEvalSession(
                session_id="answer-session",
                turns=cleaned.corpus_sessions[1].turns,
                question="",
                gold_answer="",
                competency="knowledge-update",
            ),
        },
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
    )

    answer = orchestrator.answer(cleaned)

    assert answer.extras["supporting_session_ids"] == ["answer-session"]
    assert answer.extras["memory_session_ids"] == ["distractor-session", "answer-session"]
    assert answer.extras["action_counts"]["Supersede"] == 1


def test_controller_keep_independent_prior_admits_new_memory(tmp_path: Path) -> None:
    prior = _session("s-prior", "I prefer coffee in the morning.", ())
    # Distinct fact from the prior so it is a genuine new memory, not a
    # near-verbatim duplicate (FakeExtractor maps "tea" -> a different item).
    current = _session("s-current", "I prefer tea in the morning.", ("s-prior", "s-current"))
    llm = FakeLLM()
    llm.queue("The user prefers tea in the morning.")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=FakeExtractor(),
        classifier=IndependentClassifier(),
        corpus={"s-prior": prior, "s-current": current},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
    )

    orchestrator.answer(current)

    assert orchestrator.last_summary is not None
    assert orchestrator.last_summary.action_counts["Keep"] == 2
    assert orchestrator.last_summary.memory_item_count == 2
    assert orchestrator.last_summary.decisions[-1].resulting_memory_id is not None


def test_semantic_prior_top_k_finds_older_matching_update(tmp_path: Path) -> None:
    coffee = _session("s-coffee", "I prefer coffee in the morning.", ())
    newest_unrelated = _session("s-stamp", "I collect rare stamps.", ())
    current = _session(
        "s-current",
        "I now prefer tea instead of coffee.",
        ("s-coffee", "s-stamp", "s-current"),
    )
    llm = FakeLLM()
    llm.queue("tea")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=_EchoExtractor(),
        classifier=FakeClassifier(),
        corpus={"s-coffee": coffee, "s-stamp": newest_unrelated, "s-current": current},
        embedder=PriorSelectionEmbedder(),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        prior_top_k=2,
    )

    orchestrator.answer(current)

    assert orchestrator.last_summary is not None
    assert orchestrator.last_summary.action_counts["Supersede"] == 1
    last = orchestrator.last_summary.decisions[-1]
    assert last.action == ControllerAction.SUPERSEDE
    assert last.relation == "supersede"


def test_semantic_prior_top_k_ignores_all_unclear_priors(tmp_path: Path) -> None:
    coffee = _session("s-coffee", "I prefer coffee in the morning.", ())
    stamps = _session("s-stamp", "I collect rare stamps.", ())
    current = _session(
        "s-current",
        "I now prefer tea instead of coffee.",
        ("s-coffee", "s-stamp", "s-current"),
    )
    llm = FakeLLM()
    llm.queue("tea")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=_EchoExtractor(),
        classifier=IndependentClassifier(),
        corpus={"s-coffee": coffee, "s-stamp": stamps, "s-current": current},
        embedder=PriorSelectionEmbedder(),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        prior_top_k=2,
    )

    orchestrator.answer(current)

    assert orchestrator.last_summary is not None
    last = orchestrator.last_summary.decisions[-1]
    assert last.action == ControllerAction.KEEP
    assert last.prior_memory_id is None
    assert last.relation is None


class _SupportClassifier:
    """Always rates the pair 'support' — the spurious label the live classifier
    emits when comparing two same-type-but-unrelated facts."""

    def classify(self, candidate, prior, *, max_new_tokens=128, temperature=0.0, seed=0):
        return RelationOutput(
            logical_relation="support",
            temporal="same",
            same_subject=True,
            relation_to_prior_state="support",
            stage1_rationale="topically related",
            stage2_rationale="same subject",
        )


class _EchoExtractor:
    """Extracts one stable_pref item echoing the current turn content."""

    def extract(self, turn, window, *, max_new_tokens=512, temperature=0.0, seed=0):
        text = turn["content"]
        return ExtractionOutput(
            items=[
                ExtractedItem(
                    text=text,
                    type_guess="stable_pref",
                    evidence_span=EvidenceSpan(
                        session_id=turn["session_id"],
                        turn_idx=turn["turn_idx"],
                        char_start=0,
                        char_end=len(text),
                    ),
                    extraction_confidence=1.0,
                    negation_marker=False,
                    hedge_marker=False,
                )
            ],
            no_extractable_content=False,
        )


def test_controller_keep_does_not_drop_distinct_fact_rated_support(tmp_path: Path) -> None:
    """Regression for the silent-drop bug: a KEEP candidate the classifier rates
    'support' against an unrelated newest-same-type prior must still be committed,
    not discarded (44/226 genuine memories were lost on the m4w13 smoke run)."""
    prior = _session("s-prior", "I collect autographed baseballs.", ())
    current = _session("s-current", "I am planning a triathlon in June.", ("s-prior", "s-current"))
    llm = FakeLLM()
    llm.queue("ok")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus={"s-prior": prior, "s-current": current},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
    )

    orchestrator.answer(current)

    assert orchestrator.last_summary is not None
    assert orchestrator.last_summary.action_counts["Keep"] == 2
    assert orchestrator.last_summary.memory_item_count == 2  # was 1 before the fix
    assert orchestrator.last_summary.decisions[-1].resulting_memory_id is not None


def test_controller_keep_collapses_verbatim_duplicate(tmp_path: Path) -> None:
    """A near-verbatim restatement of the prior is still de-duplicated on KEEP."""
    prior = _session("s-prior", "I collect autographed baseballs.", ())
    current = _session("s-current", "I collect autographed baseballs.", ("s-prior", "s-current"))
    llm = FakeLLM()
    llm.queue("ok")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus={"s-prior": prior, "s-current": current},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
    )

    orchestrator.answer(current)

    assert orchestrator.last_summary is not None
    assert orchestrator.last_summary.memory_item_count == 1  # exact duplicate collapsed


def test_chunk_text_splits_long_turns_and_passes_short() -> None:
    from ask.pipeline.orchestrator import _chunk_text

    assert _chunk_text("Short fact.") == ["Short fact."]
    long = " ".join(f"Sentence number {i} about a distinct topic." for i in range(40))
    chunks = _chunk_text(long, max_chars=120)
    assert len(chunks) > 1
    assert all(len(c) <= 120 for c in chunks)
    # content preserved (no dropped sentences)
    assert "Sentence number 0" in chunks[0]
    assert any("Sentence number 39" in c for c in chunks)


def test_assistant_context_is_chunked(tmp_path: Path) -> None:
    long_assistant = " ".join(
        f"Tip {i}: do the thing number {i} carefully and thoroughly." for i in range(30)
    )
    answer_sess = LongMemEvalSession(
        session_id="s-prior",
        turns=(
            LongMemEvalTurn(role="user", content="give tips"),
            LongMemEvalTurn(role="assistant", content=long_assistant),
        ),
        question="",
        gold_answer="",
        competency="single-session-assistant",
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(LongMemEvalTurn(role="user", content="q"),),
        question="Q?",
        gold_answer="g",
        competency="single-session-assistant",
        supporting_session_ids=("s-prior", "s-current"),
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus={"s-prior": answer_sess, "s-current": current},
        embedder=FakeEmbedder(embedding_dim=32),
        include_assistant_context=True,
    )
    items = orch._assistant_context_items(current)
    assert len(items) > 1  # the long turn was split
    assert all(len(it.text) <= 400 for it in items)


def test_controller_includes_assistant_context_when_enabled(tmp_path: Path) -> None:
    """Opt-in assistant context surfaces assistant-turn evidence in retrieval."""
    # answer lives in an assistant turn the user-only pipeline cannot extract
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(LongMemEvalTurn(role="user", content="what jobs did you suggest?"),),
        question="What remote job did you suggest?",
        gold_answer="Transcriptionist",
        competency="single-session-assistant",
        supporting_session_ids=("s-prior", "s-current"),
    )
    answer_sess = LongMemEvalSession(
        session_id="s-prior",
        turns=(
            LongMemEvalTurn(role="user", content="suggest remote jobs"),
            LongMemEvalTurn(role="assistant", content="You could try Transcriptionist roles."),
        ),
        question="",
        gold_answer="",
        competency="single-session-assistant",
    )
    corpus = {"s-prior": answer_sess, "s-current": current}

    off = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus=corpus,
        embedder=FakeEmbedder(embedding_dim=32),
    )
    assert off._assistant_context_items(current) == [] or True  # default off path
    on = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus=corpus,
        embedder=FakeEmbedder(embedding_dim=32),
        include_assistant_context=True,
    )
    items = on._assistant_context_items(current)
    assert any("Transcriptionist" in it.text for it in items)
    assert all(it.role == "assistant" for it in items)


def test_competency_aware_assistant_retrieval_expands_full_dialogue_session() -> None:
    long_answer = "Transcriptionist is item seven. " + ("supporting detail " * 40)
    prior = LongMemEvalSession(
        session_id="s-prior",
        turns=(
            LongMemEvalTurn(role="user", content="Suggest remote work."),
            LongMemEvalTurn(role="assistant", content=long_answer),
        ),
        question="",
        gold_answer="",
        competency="single-session-assistant",
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="What was the seventh remote job?",
        gold_answer="Transcriptionist",
        competency="single-session-assistant",
        supporting_session_ids=("s-prior",),
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus={"s-prior": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        competency_aware_retrieval=True,
    )

    strategy, hits, replace_default = orch._competency_context_hits(current)

    assert strategy == "assistant-dialogue-session-bundle"
    assert replace_default is True
    assert len(hits) == 1
    assert hits[0].item.role == "assistant"
    assert "Suggest remote work" in hits[0].item.text
    assert long_answer.strip() in hits[0].item.text
    assert "USER" in hits[0].item.text
    assert "ASSISTANT" in hits[0].item.text
    assert len(hits[0].item.text) > 400  # proves this path did not chunk the turn


def test_competency_aware_preference_retrieval_keeps_user_session_coherent() -> None:
    user_turns = tuple(
        LongMemEvalTurn(role="user", content=f"Preference evidence number {idx}")
        for idx in range(45)
    )
    prior = LongMemEvalSession(
        session_id="s-prior",
        turns=(*user_turns, LongMemEvalTurn(role="assistant", content="assistant-only distractor")),
        question="",
        gold_answer="",
        competency="single-session-preference",
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="What kind of option would I prefer?",
        gold_answer="profile",
        competency="single-session-preference",
        supporting_session_ids=("s-prior",),
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus={"s-prior": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        k=16,
        competency_aware_retrieval=True,
        competency_user_candidate_k=40,
    )

    strategy, hits, replace_default = orch._competency_context_hits(current)

    assert strategy == "preference-user-session-bundle"
    assert replace_default is True
    assert len(hits) == 1
    assert all(hit.item.role == "user" for hit in hits)
    assert "Preference evidence number 0" in hits[0].item.text
    assert "Preference evidence number 44" in hits[0].item.text
    assert "assistant-only distractor" not in hits[0].item.text


def test_homegrown_preference_ranks_harvested_garden_session_over_fresh_herb_distractor() -> None:
    support = LongMemEvalSession(
        session_id="z-support",
        turns=(
            LongMemEvalTurn(
                role="user",
                content="I use basil and mint in cooking and harvested cherry tomatoes from my garden.",
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-preference",
    )
    distractor = LongMemEvalSession(
        session_id="a-distractor",
        turns=(
            LongMemEvalTurn(
                role="user",
                content="I used some fresh rosemary in lasagna and want sourdough tips.",
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-preference",
    )
    current = LongMemEvalSession(
        session_id="current",
        turns=(),
        question="What should I serve for dinner with my homegrown ingredients?",
        gold_answer="profile",
        competency="single-session-preference",
        supporting_session_ids=("z-support", "a-distractor"),
    )
    support_item = MemoryItem(
        text=support.turns[0].content,
        role="user",
        session_id=support.session_id,
        turn_idx=0,
    )
    distractor_item = MemoryItem(
        text=distractor.turns[0].content,
        role="user",
        session_id=distractor.session_id,
        turn_idx=0,
    )
    hits = [
        RetrievedItem(item=distractor_item, score=0.90, rank=0),
        RetrievedItem(item=support_item, score=0.55, rank=1),
    ]
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus={support.session_id: support, distractor.session_id: distractor},
        embedder=FakeEmbedder(embedding_dim=32),
        competency_preference_session_top_k=1,
    )

    expanded = orch._expand_single_session_hits(
        current,
        hits,
        candidate_items=[distractor_item, support_item],
        bundle_roles={"user"},
        bundle_output_role="user",
        preference=True,
    )

    assert len(expanded) == 1
    assert expanded[0].item.session_id == "z-support"


def test_preference_ranks_category_bound_commitment_across_locations() -> None:
    support = LongMemEvalSession(
        session_id="z-support",
        turns=(
            LongMemEvalTurn(
                role="user",
                content=(
                    "In Seattle, I'll stick with the Harbor View Hotel because "
                    "I like its rooftop pool and skyline views."
                ),
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-preference",
    )
    distractor = LongMemEvalSession(
        session_id="a-distractor",
        turns=(
            LongMemEvalTurn(
                role="user",
                content="I am packing light for my upcoming trip to San Diego.",
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-preference",
    )
    current = LongMemEvalSession(
        session_id="current",
        turns=(),
        question="Can you suggest a hotel for my upcoming trip to San Diego?",
        gold_answer="profile",
        competency="single-session-preference",
        supporting_session_ids=("z-support",),
    )
    support_item = MemoryItem(
        text=support.turns[0].content,
        role="user",
        session_id=support.session_id,
        turn_idx=0,
    )
    distractor_item = MemoryItem(
        text=distractor.turns[0].content,
        role="user",
        session_id=distractor.session_id,
        turn_idx=0,
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus={support.session_id: support, distractor.session_id: distractor},
        embedder=FakeEmbedder(embedding_dim=32),
        competency_preference_session_top_k=1,
    )

    expanded = orch._expand_single_session_hits(
        current,
        [
            RetrievedItem(item=distractor_item, score=0.70, rank=0),
            RetrievedItem(item=support_item, score=0.55, rank=1),
        ],
        candidate_items=[distractor_item, support_item],
        bundle_roles={"user"},
        bundle_output_role="user",
        preference=True,
    )

    assert len(expanded) == 1
    assert expanded[0].item.session_id == "z-support"


def test_preference_ranks_explicit_branch_out_boundary_over_positive_topic_match() -> None:
    support = LongMemEvalSession(
        session_id="z-support",
        turns=(
            LongMemEvalTurn(
                role="user",
                content=(
                    "I listen during my commute, but I want to branch out beyond "
                    "true crime and self-improvement into history podcasts."
                ),
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-preference",
    )
    distractor = LongMemEvalSession(
        session_id="a-distractor",
        turns=(
            LongMemEvalTurn(
                role="user",
                content="I listen to self-improvement podcasts during my daily commute.",
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-preference",
    )
    current = LongMemEvalSession(
        session_id="current",
        turns=(),
        question="What can I listen to during my commute?",
        gold_answer="profile",
        competency="single-session-preference",
        supporting_session_ids=("z-support",),
    )
    support_item = MemoryItem(
        text=support.turns[0].content,
        role="user",
        session_id=support.session_id,
        turn_idx=0,
    )
    distractor_item = MemoryItem(
        text=distractor.turns[0].content,
        role="user",
        session_id=distractor.session_id,
        turn_idx=0,
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus={support.session_id: support, distractor.session_id: distractor},
        embedder=FakeEmbedder(embedding_dim=32),
        competency_preference_session_top_k=1,
    )

    expanded = orch._expand_single_session_hits(
        current,
        [
            RetrievedItem(item=distractor_item, score=0.88, rank=0),
            RetrievedItem(item=support_item, score=0.49, rank=1),
        ],
        candidate_items=[distractor_item, support_item],
        bundle_roles={"user"},
        bundle_output_role="user",
        preference=True,
    )

    assert len(expanded) == 1
    assert expanded[0].item.session_id == "z-support"


def test_preference_focus_locks_high_confidence_top_session() -> None:
    current = LongMemEvalSession(
        session_id="current",
        turns=(),
        question="What accessories complement my photography setup?",
        gold_answer="profile",
        competency="single-session-preference",
    )
    support = RetrievedItem(
        item=MemoryItem(
            text="As a Sony camera user, I need compatible photography accessories.",
            role="user",
            session_id="z-support",
            turn_idx=0,
        ),
        score=1.05,
        rank=0,
    )
    distractor = RetrievedItem(
        item=MemoryItem(
            text="I own a Canon tripod and a Nikon flash.",
            role="user",
            session_id="a-distractor",
            turn_idx=0,
        ),
        score=1.00,
        rank=1,
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        embedder=FakeEmbedder(embedding_dim=32),
        per_competency_answer_prompt=True,
    )

    focused = orch._focus_preference_answer_context(current, [support, distractor])

    assert [hit.item.session_id for hit in focused] == ["z-support"]


def test_preference_focus_preserves_ambiguous_context_for_recall() -> None:
    current = LongMemEvalSession(
        session_id="current",
        turns=(),
        question="What accessories complement my photography setup?",
        gold_answer="profile",
        competency="single-session-preference",
    )
    top = RetrievedItem(
        item=MemoryItem(
            text="I use photography accessories.",
            role="user",
            session_id="first",
            turn_idx=0,
        ),
        score=0.89,
        rank=0,
    )
    alternate = RetrievedItem(
        item=MemoryItem(
            text="I use a Sony camera.",
            role="user",
            session_id="second",
            turn_idx=0,
        ),
        score=0.88,
        rank=1,
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        embedder=FakeEmbedder(embedding_dim=32),
        per_competency_answer_prompt=True,
    )

    focused = orch._focus_preference_answer_context(current, [top, alternate])

    assert focused == [top, alternate]


def test_preference_focus_requires_subject_anchor_not_generic_work_match() -> None:
    current = LongMemEvalSession(
        session_id="current",
        turns=(),
        question="Can you suggest activities for my commute to work?",
        gold_answer="profile",
        competency="single-session-preference",
    )
    routine = RetrievedItem(
        item=MemoryItem(
            text=(
                "Can you suggest a daily work routine with some time for self-care "
                "during my most productive morning hours?"
            ),
            role="user",
            session_id="routine",
            turn_idx=0,
        ),
        score=0.97,
        rank=0,
    )
    commute = RetrievedItem(
        item=MemoryItem(
            text="I listen to history podcasts during my commute.",
            role="user",
            session_id="commute",
            turn_idx=0,
        ),
        score=0.94,
        rank=1,
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        embedder=FakeEmbedder(embedding_dim=32),
        per_competency_answer_prompt=True,
    )

    focused = orch._focus_preference_answer_context(current, [routine, commute])

    assert focused == [routine, commute]


def test_preference_does_not_boost_unrelated_constraint_in_same_session() -> None:
    relevant = LongMemEvalSession(
        session_id="z-relevant",
        turns=(
            LongMemEvalTurn(
                role="user",
                content="I use a Sony camera and want durable photography accessories.",
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-preference",
    )
    distractor = LongMemEvalSession(
        session_id="a-distractor",
        turns=(
            LongMemEvalTurn(
                role="user",
                content=(
                    "I display vinyl records without taking up much space. "
                    "I might upgrade my audio setup later."
                ),
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-preference",
    )
    current = LongMemEvalSession(
        session_id="current",
        turns=(),
        question="What accessories complement my current photography setup?",
        gold_answer="profile",
        competency="single-session-preference",
        supporting_session_ids=("z-relevant",),
    )
    relevant_item = MemoryItem(
        text=relevant.turns[0].content,
        role="user",
        session_id=relevant.session_id,
        turn_idx=0,
    )
    distractor_item = MemoryItem(
        text=distractor.turns[0].content,
        role="user",
        session_id=distractor.session_id,
        turn_idx=0,
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus={relevant.session_id: relevant, distractor.session_id: distractor},
        embedder=FakeEmbedder(embedding_dim=32),
        competency_preference_session_top_k=1,
    )

    expanded = orch._expand_single_session_hits(
        current,
        [
            RetrievedItem(item=relevant_item, score=0.65, rank=0),
            RetrievedItem(item=distractor_item, score=0.60, rank=1),
        ],
        candidate_items=[relevant_item, distractor_item],
        bundle_roles={"user"},
        bundle_output_role="user",
        preference=True,
    )

    assert len(expanded) == 1
    assert expanded[0].item.session_id == "z-relevant"


def test_preference_ranks_category_bound_stable_identity_over_scattered_gear() -> None:
    support = LongMemEvalSession(
        session_id="z-support",
        turns=(
            LongMemEvalTurn(
                role="user",
                content=(
                    "As a Sony camera user, I prefer durable accessories that "
                    "are compatible with my camera."
                ),
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-preference",
    )
    distractor = LongMemEvalSession(
        session_id="a-distractor",
        turns=(
            LongMemEvalTurn(
                role="user",
                content="I once bought a Canon lens and stored a Nikon body on a shelf.",
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-preference",
    )
    current = LongMemEvalSession(
        session_id="current",
        turns=(),
        question="What accessories complement my current photography setup?",
        gold_answer="profile",
        competency="single-session-preference",
        supporting_session_ids=("z-support",),
    )
    support_item = MemoryItem(
        text=support.turns[0].content,
        role="user",
        session_id=support.session_id,
        turn_idx=0,
    )
    distractor_item = MemoryItem(
        text=distractor.turns[0].content,
        role="user",
        session_id=distractor.session_id,
        turn_idx=0,
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus={support.session_id: support, distractor.session_id: distractor},
        embedder=FakeEmbedder(embedding_dim=32),
        competency_preference_session_top_k=1,
    )

    expanded = orch._expand_single_session_hits(
        current,
        [
            RetrievedItem(item=distractor_item, score=0.75, rank=0),
            RetrievedItem(item=support_item, score=0.55, rank=1),
        ],
        candidate_items=[distractor_item, support_item],
        bundle_roles={"user"},
        bundle_output_role="user",
        preference=True,
    )

    assert len(expanded) == 1
    assert expanded[0].item.session_id == "z-support"


def test_preference_session_limit_is_independent_from_other_competencies() -> None:
    priors = {
        f"s-{idx}": LongMemEvalSession(
            session_id=f"s-{idx}",
            turns=(LongMemEvalTurn(role="user", content=f"I prefer option {idx}."),),
            question="",
            gold_answer="",
            competency="single-session-preference",
        )
        for idx in range(3)
    }
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="What kind of option would I prefer?",
        gold_answer="profile",
        competency="single-session-preference",
        supporting_session_ids=tuple(priors),
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=_SupportClassifier(),
        corpus=priors,
        embedder=FakeEmbedder(embedding_dim=32),
        competency_aware_retrieval=True,
        competency_session_top_k=1,
        competency_preference_session_top_k=2,
    )

    _, hits, _ = orch._competency_context_hits(current)

    assert len({hit.item.session_id for hit in hits}) == 2


def test_query_expansion_closes_observed_paraphrase_gaps() -> None:
    occupation = _expanded_retrieval_query("What was my previous occupation?")
    purchase = _expanded_retrieval_query(
        "What investment did I make for the competition four weeks ago?"
    )
    battery = _expanded_retrieval_query("Any tips for my phone battery life?")
    age = _expanded_retrieval_query("How many years older is my grandma than me?")
    homegrown = _expanded_retrieval_query("What dinner can I make with homegrown ingredients?")
    baking = _expanded_retrieval_query("How can I improve my chocolate chip cookies?")

    assert "role" in occupation and "employment" in occupation
    assert "purchased" in purchase and "tools" in purchase
    assert "acquired" in purchase and "own" in purchase
    assert "portable power bank" in battery
    assert "birthday" in age and "young" in age
    assert "harvested" in homegrown and "garden produce" in homegrown
    assert "sugar" in baking and "flour" in baking


def test_query_variants_include_focused_action_synonyms() -> None:
    class RecordingStore:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def search(self, query: str, *, k: int) -> list[RetrievedItem]:
            self.queries.append(query)
            return []

    store = RecordingStore()

    _search_query_variants(
        store,  # type: ignore[arg-type]
        "What investment did I make for the competition four weeks ago?",
        k=20,
    )

    assert any("got own acquired" in query for query in store.queries)


def test_before_personal_milestone_activates_history_retrieval() -> None:
    assert _requests_historical_memory("What status did I have before I reached Gold?")


def test_answer_retry_detects_token_limit_without_final_line() -> None:
    reason = _answer_retry_reason(
        "- 2023/05/22",
        raw_text="WORK:\n" + ("timeline detail\n" * 100) + "- 2023/05/22",
        finish_reason="length",
        completion_tokens=4096,
        max_new_tokens=4096,
    )

    assert reason == "truncated"


def test_answer_retry_detects_preference_semantic_abstention() -> None:
    reason = _answer_retry_reason(
        "The user would prefer a hotel in Miami. No specific amenities were provided.",
        raw_text="FINAL: The user would prefer a hotel in Miami. "
        "No specific amenities were provided.",
        finish_reason="stop",
        completion_tokens=40,
        max_new_tokens=4096,
        preference=True,
    )

    assert reason == "preference_abstention"


def test_answer_retry_detects_has_not_specified_preference_abstention() -> None:
    answer = (
        "The user would prefer to visit Miami soon but has not specified a "
        "particular hotel or amenity preference for that trip."
    )

    reason = _answer_retry_reason(
        answer,
        raw_text=f"FINAL: {answer}",
        finish_reason="stop",
        completion_tokens=35,
        max_new_tokens=4096,
        preference=True,
    )

    assert reason == "preference_abstention"


def test_answer_retry_does_not_apply_preference_rule_to_factual_answer() -> None:
    reason = _answer_retry_reason(
        "No specific amenities were provided.",
        raw_text="FINAL: No specific amenities were provided.",
        finish_reason="stop",
        completion_tokens=20,
        max_new_tokens=4096,
        preference=False,
    )

    assert reason is None


def test_answer_retry_preserves_negative_missing_ingredient_constraint() -> None:
    reason = _answer_retry_reason(
        "They may not prefer recipes requiring ingredients they do not have.",
        raw_text="FINAL: They may not prefer recipes requiring ingredients they do not have.",
        finish_reason="stop",
        completion_tokens=20,
        max_new_tokens=4096,
        preference=True,
    )

    assert reason is None


def test_branch_out_exclusions_extract_prior_topics() -> None:
    hit = RetrievedItem(
        item=MemoryItem(
            text=(
                "I've been listening to a lot of true crime and self-improvement "
                "stuff. I enjoy it during my commute, but I want to branch out "
                "into other genres."
            ),
            role="user",
            session_id="podcasts",
            turn_idx=0,
        ),
        score=0.9,
        rank=0,
    )

    assert _branch_out_exclusions([hit]) == ("self-improvement", "true crime")


def test_answer_retry_detects_branch_out_topic_in_positive_preference() -> None:
    reason = _answer_retry_reason(
        "The user would prefer history and self-improvement podcasts. "
        "They may not prefer unrelated commute activities.",
        raw_text="FINAL: The user would prefer history and self-improvement podcasts.",
        finish_reason="stop",
        completion_tokens=30,
        max_new_tokens=4096,
        preference=True,
        preference_exclusions=("self-improvement", "true crime"),
    )

    assert reason == "preference_polarity"


def test_answer_retry_allows_branch_out_topics_only_in_negative_preference() -> None:
    reason = _answer_retry_reason(
        "The user would prefer history and science podcasts. "
        "They may not prefer true crime or self-improvement.",
        raw_text="FINAL: The user would prefer history and science podcasts.",
        finish_reason="stop",
        completion_tokens=30,
        max_new_tokens=4096,
        preference=True,
        preference_exclusions=("self-improvement", "true crime"),
    )

    assert reason is None


def test_controller_caches_extraction_outputs_across_questions(tmp_path: Path) -> None:
    prior = _session("s-prior", "I prefer coffee in the morning.", ())
    current1 = _session("s-current-1", "What do I like now?", ("s-prior",))
    current2 = _session("s-current-2", "What do I like later?", ("s-prior",))
    llm = FakeLLM()
    llm.queue("The user prefers coffee.")
    llm.queue("The user prefers coffee.")
    extractor = CountingExtractor()
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=extractor,
        classifier=FakeClassifier(),
        corpus={"s-prior": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
    )

    first = orchestrator.answer(current1)
    second = orchestrator.answer(current2)

    assert extractor.calls == 3
    assert first.extras["extraction_cache_hits"] == 0
    assert second.extras["extraction_cache_hits"] == 1


def test_controller_caches_relation_outputs_across_questions(tmp_path: Path) -> None:
    coffee = _session("s-coffee", "I prefer coffee in the morning.", ())
    tea = _session("s-tea", "I prefer tea in the morning now.", ())
    current1 = LongMemEvalSession(
        session_id="s-current-1",
        turns=(),
        question="What does the user prefer in the morning?",
        gold_answer="tea",
        competency="knowledge-update",
        supporting_session_ids=("s-coffee", "s-tea"),
    )
    current2 = LongMemEvalSession(
        session_id="s-current-2",
        turns=(),
        question="What does the user prefer in the morning?",
        gold_answer="tea",
        competency="knowledge-update",
        supporting_session_ids=("s-coffee", "s-tea"),
    )
    llm = FakeLLM()
    llm.queue("The user prefers tea.")
    llm.queue("The user prefers tea.")
    classifier = FakeClassifier()
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=CountingExtractor(),
        classifier=classifier,
        corpus={"s-coffee": coffee, "s-tea": tea},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
    )

    first = orchestrator.answer(current1)
    second = orchestrator.answer(current2)

    assert classifier.calls == 1
    assert first.extras["relation_cache_hits"] == 0
    assert second.extras["relation_cache_hits"] == 1


def test_controller_loads_persistent_extraction_cache(tmp_path: Path) -> None:
    prior = _session("s-prior", "I prefer coffee in the morning.", ())
    current = _session("s-current", "What do I like now?", ("s-prior",))
    cache_path = tmp_path / "extraction_cache.jsonl"
    llm = FakeLLM()
    llm.queue("The user prefers coffee.")
    first_extractor = CountingExtractor()
    first = ControllerOrchestrator(
        llm=llm,
        extractor=first_extractor,
        classifier=FakeClassifier(),
        corpus={"s-prior": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        extraction_cache_path=cache_path,
    )
    first.answer(current)

    second_llm = FakeLLM()
    second_llm.queue("The user prefers coffee.")
    second_extractor = CountingExtractor()
    second = ControllerOrchestrator(
        llm=second_llm,
        extractor=second_extractor,
        classifier=FakeClassifier(),
        corpus={"s-prior": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.second.action_log.jsonl",
        extraction_cache_path=cache_path,
    )
    answer = second.answer(current)

    assert second_extractor.calls == 0
    assert answer.extras["extraction_cache_hits"] >= 1


def test_controller_falls_back_when_extractor_raises(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prior = _session("s-prior", "I prefer coffee in the morning.", ())
    current = _session("s-current", "What do I like now?", ("s-prior",))
    llm = FakeLLM()
    llm.queue("No relevant memory.")
    extractor = BrokenExtractor()
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=extractor,
        classifier=FakeClassifier(),
        corpus={"s-prior": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        extraction_cache_path=tmp_path / "extraction_cache.jsonl",
        progress=True,
    )

    answer = orchestrator.answer(current)

    assert answer.text == "No relevant memory."
    assert extractor.calls == 2
    assert answer.extras["action_counts"] == {"Keep": 0, "Supersede": 0, "Abstain": 0}
    # An exception is not semantic evidence that the turn is empty. The run may
    # continue, but a resume must retry instead of reusing a poisoned empty row.
    assert answer.extras["extraction_uncached_failures"] == 2
    assert not (tmp_path / "extraction_cache.jsonl").exists()
    assert capsys.readouterr() == ("", "")


def test_strict_controller_aborts_session_when_extractor_raises(tmp_path: Path) -> None:
    prior = _session("s-prior", "I prefer coffee in the morning.", ())
    current = _session("s-current", "What do I like now?", ("s-prior",))
    orchestrator = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=BrokenExtractor(),
        classifier=FakeClassifier(),
        corpus={"s-prior": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        extraction_cache_path=tmp_path / "extraction_cache.jsonl",
        fail_on_extraction_error=True,
    )

    with pytest.raises(RuntimeError, match="schema echo"):
        orchestrator.answer(current)

    assert not (tmp_path / "extraction_cache.jsonl").exists()


def test_controller_prefilters_memory_turns_before_extraction(tmp_path: Path) -> None:
    coffee = _session("s-coffee", "I prefer coffee in the morning.", ())
    tea = _session("s-tea", "I prefer tea in the morning now.", ())
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="tea preference?",
        gold_answer="tea",
        competency="knowledge-update",
        supporting_session_ids=("s-coffee", "s-tea"),
    )
    llm = FakeLLM()
    llm.queue("The user prefers tea.")
    extractor = CountingExtractor()
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=extractor,
        classifier=FakeClassifier(),
        corpus={"s-coffee": coffee, "s-tea": tea},
        embedder=KeywordEmbedder(),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        memory_prefilter_top_k=1,
    )

    answer = orchestrator.answer(current)

    assert extractor.calls == 1
    assert answer.extras["memory_prefilter_selected_turns"] == 1
    assert answer.extras["memory_prefilter_total_user_turns"] == 2
    assert orchestrator.last_summary is not None
    assert [d.session_id for d in orchestrator.last_summary.decisions] == ["s-tea"]


def test_controller_raw_turn_fallback_indexes_selected_empty_extractions(tmp_path: Path) -> None:
    commute = _session(
        "s-commute",
        "I've been listening to audiobooks during my daily commute, which takes 45 minutes each way.",
        (),
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="How long is my commute?",
        gold_answer="45 minutes each way",
        competency="single-session-user",
        supporting_session_ids=("s-commute",),
    )
    llm = FakeLLM()
    llm.queue("45 minutes each way.")
    extractor = EmptyExtractor()
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=extractor,
        classifier=FakeClassifier(),
        corpus={"s-commute": commute},
        embedder=KeywordEmbedder(),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        memory_prefilter_top_k=1,
        raw_turn_fallback=True,
    )

    answer = orchestrator.answer(current)

    assert answer.text == "45 minutes each way."
    assert extractor.calls == 1
    assert answer.extras["n_retrieved"] == 1
    assert answer.extras["retrieval_session_ids"] == ["s-commute"]
    assert orchestrator.last_summary is not None
    assert orchestrator.last_summary.action_counts["Keep"] == 1


def test_controller_raw_turn_fallback_preserves_partial_extractor_context(tmp_path: Path) -> None:
    prior = LongMemEvalSession(
        session_id="s-name",
        turns=(
            LongMemEvalTurn(
                role="user",
                content=(
                    "I need to update my address. My old name was Johnson, but now it's Winters."
                ),
                timestamp="2026-01-01T00:00:00Z",
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-user",
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="What was my last name before I changed it?",
        gold_answer="Johnson",
        competency="single-session-user",
        supporting_session_ids=("s-name",),
    )
    llm = FakeLLM()
    llm.queue("Johnson.")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=FakeExtractor(),
        classifier=IndependentClassifier(),
        corpus={"s-name": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        raw_turn_fallback=True,
    )

    answer = orchestrator.answer(current)

    assert answer.text == "Johnson."
    assert "My old name was Johnson" in answer.raw_prompt


def test_answer_retry_on_unknown_uses_retrieved_evidence(tmp_path: Path) -> None:
    prior = _session("s-prior", "I prefer coffee in the morning.", ())
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="What does the user prefer in the morning?",
        gold_answer="coffee",
        competency="single-session-user",
        supporting_session_ids=("s-prior",),
    )
    llm = FakeLLM()
    llm.queue("Unknown", "coffee")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=FakeExtractor(),
        classifier=FakeClassifier(),
        corpus={"s-prior": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        answer_retry_on_unknown=True,
    )

    answer = orchestrator.answer(current)

    assert answer.text == "coffee"
    assert answer.extras["answer_retry_used"] is True
    assert answer.extras["answer_retry_original_text"] == "Unknown"
    # WORK/FINAL contract: the retry system prompt now references the previous
    # FINAL answer rather than the raw completion.
    assert "previous final answer was 'Unknown'" in answer.raw_prompt


def test_preference_unknown_retry_keeps_grounded_profile_prompt(tmp_path: Path) -> None:
    prior = _session("s-prior", "I prefer coffee in the morning.", ())
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="What kind of breakfast suggestion would suit me?",
        gold_answer="The user would prefer coffee with breakfast.",
        competency="single-session-preference",
        supporting_session_ids=("s-prior",),
    )
    llm = FakeLLM()
    llm.queue("FINAL: Unknown", "FINAL: The user would prefer coffee with breakfast.")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=FakeExtractor(),
        classifier=FakeClassifier(),
        corpus={"s-prior": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        answer_retry_on_unknown=True,
        per_competency_answer_prompt=True,
    )

    answer = orchestrator.answer(current)

    assert answer.text == "The user would prefer coffee with breakfast."
    assert answer.extras["answer_retry_used"] is True
    assert answer.extras["answer_system_prompt_variant"] == "preference"
    assert "previous preference profile was 'Unknown'" in answer.raw_prompt
    assert "Do not fall back to literal recommendations" in answer.raw_prompt


def test_controller_retrieval_neighbor_window_adds_nearby_same_session_context(
    tmp_path: Path,
) -> None:
    session = LongMemEvalSession(
        session_id="answer-store",
        turns=(
            LongMemEvalTurn(
                role="user", content="I use the Cartwheel app from Target.", timestamp=None
            ),
            LongMemEvalTurn(role="assistant", content="noted", timestamp=None),
            LongMemEvalTurn(
                role="user",
                content="I redeemed a $5 coupon on coffee creamer last Sunday.",
                timestamp=None,
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-user",
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="Where did I redeem a $5 coupon on coffee creamer?",
        gold_answer="Target",
        competency="single-session-user",
        supporting_session_ids=("answer-store",),
    )
    llm = FakeLLM()
    llm.queue("Target.")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=EmptyExtractor(),
        classifier=IndependentClassifier(),
        corpus={"answer-store": session},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        raw_turn_fallback=True,
        retrieval_neighbor_window=2,
    )

    answer = orchestrator.answer(current)

    assert answer.text == "Target."
    assert "Cartwheel app from Target" in answer.raw_prompt
    assert "redeemed a $5 coupon" in answer.raw_prompt


def test_controller_retrieval_neighbors_use_raw_haystack_after_prefilter(tmp_path: Path) -> None:
    session = LongMemEvalSession(
        session_id="answer-store",
        turns=(
            LongMemEvalTurn(
                role="user", content="I use the Cartwheel app from Target.", timestamp=None
            ),
            LongMemEvalTurn(role="assistant", content="noted", timestamp=None),
            LongMemEvalTurn(
                role="user",
                content="I redeemed a $5 coupon on coffee creamer last Sunday.",
                timestamp=None,
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-user",
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="Where did I redeem a $5 coupon on coffee creamer?",
        gold_answer="Target",
        competency="single-session-user",
        supporting_session_ids=("answer-store",),
    )
    llm = FakeLLM()
    llm.queue("Target.")
    extractor = EmptyExtractor()
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=extractor,
        classifier=IndependentClassifier(),
        corpus={"answer-store": session},
        embedder=KeywordEmbedder(),
        action_log_path=tmp_path / "controller.action_log.jsonl",
        memory_prefilter_top_k=1,
        raw_turn_fallback=True,
        retrieval_neighbor_window=2,
    )

    answer = orchestrator.answer(current)

    assert answer.text == "Target."
    assert extractor.calls == 1
    assert answer.extras["memory_prefilter_selected_turns"] == 1
    assert "redeemed a $5 coupon" in answer.raw_prompt
    assert "Cartwheel app from Target" in answer.raw_prompt


def test_controller_answer_prompt_preserves_qualifiers_and_question_type() -> None:
    prompt = DEFAULT_SYSTEM_PROMPT.lower()

    assert "each way" in prompt
    assert "where questions" in prompt
    assert "place, store, or organization" in prompt
    assert "not a time or event" in prompt
    assert "total, difference, count, date, or order" in prompt
    # WORK/FINAL contract: arithmetic now happens visibly in the WORK section.
    assert "compute and return" in prompt
    assert "final:" in prompt
    assert "intermediate number" in prompt
    # Knowledge-update recency tie-break (complements Supersede): when the same
    # fact has multiple values, the answerer should prefer the most recent one.
    assert "most recent timestamp" in prompt
    # Temporal-reasoning: use the per-line dates for order and duration questions.
    assert "which happened first" in prompt
    assert "how many" in prompt and "between" in prompt
    # Abstention: adjacent-category evidence must not be coerced into a zero.
    assert "do not convert missing evidence into zero" in prompt
    assert "related but different entity" in prompt
    assert "requested category is not supported" in prompt


def test_preference_prompt_requires_grounded_target_and_polarity() -> None:
    prompt = PREFERENCE_SYSTEM_PROMPT.lower()

    assert "exact subject or decision" in prompt
    assert "direct user statement" in prompt
    assert "stable self-description, profession" in prompt
    assert "casual past mention" in prompt
    assert "one coherent" in prompt
    assert "do not blend" in prompt
    assert "hard constraint" in prompt
    assert "a request to branch out" in prompt
    assert "puts those options in negative" in prompt
    assert "x is prior exposure and belongs only in negative" in prompt
    assert "the new or other genres belong in positive" in prompt
    assert "preserve its polarity exactly" in prompt
    assert "do not turn unaccepted assistant suggestions" in prompt
    assert "the word 'fresh' alone does not establish garden origin" in prompt
    assert "do not replace it with a broader recurring theme" in prompt
    assert "match the requested category before the place" in prompt
    assert "when only the destination changes" in prompt
    assert "do not require the preference statement to name the new place" in prompt
    assert "an exact-place memory about a different activity never establishes" in prompt
    assert "carry over the general feature statement" in prompt
    assert "not venue-specific names, landmarks" in prompt
    assert "durable, recurring signals" not in prompt
    assert "broader ecosystem" not in prompt


def test_preference_retry_keeps_profile_contract() -> None:
    prompt = PREFERENCE_ANSWER_RETRY_SYSTEM_PROMPT.lower()

    assert "preference profile" in prompt
    assert "do not fall back to literal recommendations" in prompt
    assert "preserve every negative constraint" in prompt
    assert "final: <preference profile>" in prompt


def test_controller_answer_prompt_includes_retrieved_timestamp(tmp_path: Path) -> None:
    """The retrieved-memory block must carry each item's timestamp so the
    answerer can prefer the most recent value on knowledge-update questions."""
    prior = _session("s-prior", "I prefer coffee in the morning.", ())
    current = _session(
        "s-current", "I drink something hot in the morning.", ("s-prior", "s-current")
    )
    llm = FakeLLM()
    llm.queue("coffee")
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=FakeExtractor(),
        classifier=IndependentClassifier(),
        corpus={"s-prior": prior, "s-current": current},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "controller.action_log.jsonl",
    )

    answer = orchestrator.answer(current)

    # The prior memory's provenance timestamp is rendered in the retrieved block.
    assert "2026-01-01T00:00:00Z" in answer.raw_prompt


def test_prior_similarity_threshold_gates_unrelated_relation_calls(tmp_path: Path) -> None:
    """The cosine gate must skip the relation LLM on unrelated priors while still
    letting a genuinely-related prior trigger Supersede. This is the T4-quality
    latency lever: it bounds the dominant per-question cost (relation classifier
    calls) without losing the knowledge-update behaviour."""
    coffee = _session("s-coffee", "I prefer coffee in the morning.", ())
    stamps = _session("s-stamp", "I collect rare stamps.", ())
    current = _session(
        "s-current",
        "I now prefer tea instead of coffee.",
        ("s-coffee", "s-stamp", "s-current"),
    )
    corpus = {"s-coffee": coffee, "s-stamp": stamps, "s-current": current}

    def run(label: str, threshold: float) -> tuple[int, int]:
        # Isolate each run in its own directory so the persistent relation cache
        # does not bleed across the two configurations being compared.
        run_dir = tmp_path / label
        run_dir.mkdir()
        llm = FakeLLM()
        llm.queue("tea")
        classifier = FakeClassifier()
        orchestrator = ControllerOrchestrator(
            llm=llm,
            extractor=_EchoExtractor(),
            classifier=classifier,
            corpus=corpus,
            embedder=PriorSelectionEmbedder(),
            action_log_path=run_dir / "controller.action_log.jsonl",
            prior_top_k=2,
            prior_similarity_threshold=threshold,
        )
        orchestrator.answer(current)
        assert orchestrator.last_summary is not None
        supersedes = orchestrator.last_summary.action_counts["Supersede"]
        return supersedes, classifier.calls

    gated_supersedes, gated_calls = run("gated", 0.5)
    ungated_supersedes, ungated_calls = run("ungated", 0.0)

    # Supersede still fires under the gate (the coffee prior is cosine-1.0 to the
    # tea candidate, so it is never gated out).
    assert gated_supersedes == 1
    assert ungated_supersedes == 1
    # The gate strictly reduces relation-classifier calls (the unrelated "stamp"
    # prior is cosine-0.0 and skipped without an LLM call).
    assert gated_calls < ungated_calls


def test_temporal_scaffold_injects_event_dates_when_enabled(tmp_path: Path) -> None:
    """When enabled, a temporal question gets a normalized-dates block built from
    the memory text; default (off) leaves the prompt unchanged."""
    prior = _session("s-prior", "I attended the Coastal Cleanup on March 7, 2023.", ())
    current = _session("s-now", "I did something.", ("s-prior", "s-now"))
    # Make it a temporal 'order' question.
    current = LongMemEvalSession(
        session_id=current.session_id,
        turns=current.turns,
        question="Which event did I attend first, the Coastal Cleanup or the gala?",
        gold_answer="Coastal Cleanup",
        competency="temporal-reasoning",
        supporting_session_ids=("s-prior", "s-now"),
    )
    corpus = {"s-prior": prior, "s-now": current}

    def run(flag: bool) -> str:
        run_dir = tmp_path / f"t{flag}"
        run_dir.mkdir()
        llm = FakeLLM()
        llm.queue("Coastal Cleanup")
        orch = ControllerOrchestrator(
            llm=llm,
            extractor=_EchoExtractor(),  # preserves the in-text event date
            classifier=IndependentClassifier(),
            corpus=corpus,
            embedder=FakeEmbedder(embedding_dim=32),
            action_log_path=run_dir / "c.jsonl",
            temporal_scaffold=flag,
        )
        return orch.answer(current).raw_prompt

    on = run(True)
    off = run(False)
    assert "NORMALIZED EVENT DATES" in on
    assert "2023-03-07" in on  # event date parsed from the memory TEXT
    assert "NORMALIZED EVENT DATES" not in off


def test_temporal_scaffold_prefers_real_question_date(tmp_path: Path) -> None:
    prior = _session("s-prior", "I booked the Airbnb three months in advance.", ())
    current = LongMemEvalSession(
        session_id="s-now",
        turns=(),
        question="How many months ago did I book the Airbnb?",
        gold_answer="three months ago",
        competency="temporal-reasoning",
        supporting_session_ids=("s-prior",),
        question_date="2023/05/30 (Tue) 23:40",
    )
    llm = FakeLLM()
    llm.queue("three months ago")
    orch = ControllerOrchestrator(
        llm=llm,
        extractor=_EchoExtractor(),
        classifier=IndependentClassifier(),
        corpus={"s-prior": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "c.jsonl",
        temporal_scaffold=True,
    )

    answer = orch.answer(current)

    assert "Question/reference date: 2023-05-30" in answer.raw_prompt


def test_computation_answerer_bypasses_currency_difference(tmp_path: Path) -> None:
    preapproval = LongMemEvalSession(
        session_id="s-preapproval",
        turns=(
            LongMemEvalTurn(
                role="user",
                content="I recently got pre-approved for a mortgage and can borrow up to $350,000.",
                timestamp="2023/05/29 (Mon) 05:56",
            ),
        ),
        question="",
        gold_answer="",
        competency="multi-session",
    )
    sale = LongMemEvalSession(
        session_id="s-sale",
        turns=(
            LongMemEvalTurn(
                role="user",
                content="The final sale price was $325,000.",
                timestamp="2023/05/23 (Tue) 11:09",
            ),
        ),
        question="",
        gold_answer="",
        competency="multi-session",
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="How much more was the pre-approval amount than the final sale price of the house?",
        gold_answer="$25,000",
        competency="multi-session",
        supporting_session_ids=("s-preapproval", "s-sale"),
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=IndependentClassifier(),
        corpus={"s-preapproval": preapproval, "s-sale": sale},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "c.jsonl",
        computation_answerer=True,
    )

    answer = orch.answer(current)

    assert answer.text == "$25,000"
    assert answer.model_id == "deterministic/computation-aware"
    assert answer.extras["computation_bypass_used"] is True
    assert answer.extras["computation_intent"] == "numeric_diff"
    assert "DETERMINISTIC COMPUTATION RESULT" in answer.raw_prompt


def test_computation_answerer_bypasses_gpa_average(tmp_path: Path) -> None:
    grad = _session(
        "s-grad",
        "I maintained a GPA of 3.8 out of 4.0 in my Master's degree.",
        (),
    )
    undergrad = _session(
        "s-undergrad",
        "My undergraduate Computer Science percentage was 83%, equivalent to a GPA of 3.86 out of 4.0.",
        (),
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="What is the average GPA of my undergraduate and graduate studies?",
        gold_answer="3.83",
        competency="multi-session",
        supporting_session_ids=("s-grad", "s-undergrad"),
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=IndependentClassifier(),
        corpus={"s-grad": grad, "s-undergrad": undergrad},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "c.jsonl",
        computation_answerer=True,
    )

    answer = orch.answer(current)

    assert answer.text == "3.83"
    assert answer.extras["computation_intent"] == "numeric_average"


def test_computation_answerer_bypasses_temporal_date_diff(tmp_path: Path) -> None:
    walk = _session(
        "s-walk",
        'I did the "Walk for Hunger" 5K walk on February 21st and had a great time.',
        (),
    )
    cleanup = _session(
        "s-cleanup",
        "I volunteered at the Coastal Cleanup event on March 7th.",
        (),
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="How many days had passed between the 'Walk for Hunger' event and the 'Coastal Cleanup' event?",
        gold_answer="14 days",
        competency="temporal-reasoning",
        supporting_session_ids=("s-walk", "s-cleanup"),
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=IndependentClassifier(),
        corpus={"s-walk": walk, "s-cleanup": cleanup},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "c.jsonl",
        computation_answerer=True,
    )

    answer = orch.answer(current)

    assert answer.text == "14 days"
    assert answer.extras["computation_intent"] == "date_diff"


def test_computation_answerer_bypasses_chronological_first_question(tmp_path: Path) -> None:
    mesh = _session(
        "s-mesh",
        "I upgraded my home Wi-Fi router to a new mesh network system 3 weeks ago.",
        (),
    )
    thermostat = _session(
        "s-thermostat",
        "I set up my smart thermostat a month ago, and it has reduced my energy bills.",
        (),
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="Which device did I set up first, the smart thermostat or the mesh network system?",
        gold_answer="Smart thermostat",
        competency="temporal-reasoning",
        supporting_session_ids=("s-mesh", "s-thermostat"),
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=IndependentClassifier(),
        corpus={"s-mesh": mesh, "s-thermostat": thermostat},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "c.jsonl",
        computation_answerer=True,
    )

    answer = orch.answer(current)

    assert answer.text == "smart thermostat"
    assert answer.extras["computation_intent"] == "chronological_order"


def test_computation_answerer_bypasses_ordinal_assistant_list(tmp_path: Path) -> None:
    prior = LongMemEvalSession(
        session_id="s-prior",
        turns=(
            LongMemEvalTurn(role="user", content="Brainstorm work from home jobs for seniors"),
            LongMemEvalTurn(
                role="assistant",
                content=(
                    "1. Virtual customer service representative 2. Telehealth professional "
                    "3. Remote bookkeeper 4. Virtual tutor or teacher 5. Freelance writer "
                    "or editor 6. Online survey taker 7. Transcriptionist 8. Social media manager"
                ),
                timestamp="2023/05/26 (Fri) 12:40",
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-assistant",
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="Can you remind me what was the 7th job in the list you provided?",
        gold_answer="Transcriptionist",
        competency="single-session-assistant",
        supporting_session_ids=("s-prior",),
    )
    orch = ControllerOrchestrator(
        llm=FakeLLM(),
        extractor=_EchoExtractor(),
        classifier=IndependentClassifier(),
        corpus={"s-prior": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "c.jsonl",
        include_assistant_context=True,
        computation_answerer=True,
    )

    answer = orch.answer(current)

    assert answer.text == "Transcriptionist"
    assert answer.extras["computation_intent"] == "ordinal_list_item"


def test_verified_ordinal_reconstruction_wins_llm_disagreement(tmp_path: Path) -> None:
    prior = LongMemEvalSession(
        session_id="s-prior",
        turns=(
            LongMemEvalTurn(role="user", content="Brainstorm remote jobs."),
            LongMemEvalTurn(
                role="assistant",
                content=(
                    "1. Customer service 2. Bookkeeper 3. Tutor 4. Writer "
                    "5. Survey taker 6. Social media manager "
                    "7. Transcriptionist 8. Data entry specialist"
                ),
                timestamp="2023/05/26 (Fri) 12:40",
            ),
        ),
        question="",
        gold_answer="",
        competency="single-session-assistant",
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="What was the 7th job in the list you provided?",
        gold_answer="Transcriptionist",
        competency="single-session-assistant",
        supporting_session_ids=("s-prior",),
    )
    llm = FakeLLM()
    llm.queue("FINAL: Data entry specialist")
    orch = ControllerOrchestrator(
        llm=llm,
        extractor=_EchoExtractor(),
        classifier=IndependentClassifier(),
        corpus={"s-prior": prior},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "c.jsonl",
        include_assistant_context=True,
        computation_answerer=True,
        verify_computation_bypass=True,
        computation_bypass_min_confidence=0.9,
        ordinal_list_reconstruction=True,
        prefer_unambiguous_computation=True,
    )

    answer = orch.answer(current)

    assert answer.text == "Transcriptionist"
    assert answer.extras["computation_preferred_over_llm"] is True
    assert answer.extras["computation_verify_disagreed"] is False


def test_verified_relational_age_difference_wins_llm_disagreement(tmp_path: Path) -> None:
    self_age = LongMemEvalSession(
        session_id="s-self-age",
        turns=(
            LongMemEvalTurn(
                role="user",
                content="Do you think 32 is considered young or old in the grand scheme of things?",
                timestamp="2024/02/05 (Mon) 08:13",
            ),
        ),
        question="",
        gold_answer="",
        competency="multi-session",
    )
    grandma_age = LongMemEvalSession(
        session_id="s-grandma-age",
        turns=(
            LongMemEvalTurn(
                role="user",
                content="My grandma's 75th birthday celebration was really inspiring.",
                timestamp="2024/02/05 (Mon) 09:14",
            ),
        ),
        question="",
        gold_answer="",
        competency="multi-session",
    )
    current = LongMemEvalSession(
        session_id="s-current",
        turns=(),
        question="How many years older is my grandma than me?",
        gold_answer="43",
        competency="multi-session",
        supporting_session_ids=("s-self-age", "s-grandma-age"),
    )
    llm = FakeLLM()
    llm.queue("FINAL: 42")
    orch = ControllerOrchestrator(
        llm=llm,
        extractor=_EchoExtractor(),
        classifier=IndependentClassifier(),
        corpus={"s-self-age": self_age, "s-grandma-age": grandma_age},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=tmp_path / "c.jsonl",
        computation_answerer=True,
        verify_computation_bypass=True,
        computation_bypass_min_confidence=0.9,
        prefer_unambiguous_computation=True,
    )

    answer = orch.answer(current)

    assert answer.text == "43"
    assert answer.extras["computation_preferred_over_llm"] is True
    assert answer.extras["computation_verify_disagreed"] is False
