"""Baseline 4 destructive-overwrite behavior."""

from __future__ import annotations

import json
from pathlib import Path

from ask.baselines.embeddings import FakeEmbedder
from ask.baselines.naive_overwrite import NaiveOverwriteBaseline
from ask.data.longmemeval import LongMemEvalSession, LongMemEvalTurn
from ask.inference.fake import FakeLLM
from tests.test_pipeline_orchestrator import FakeClassifier, FakeExtractor


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


def test_naive_overwrite_deletes_prior_without_lineage(tmp_path: Path) -> None:
    prior = _session("s-prior", "I prefer coffee in the morning.", ())
    current = _session("s-current", "I prefer tea in the morning now.", ("s-prior", "s-current"))
    llm = FakeLLM()
    llm.queue("The user prefers tea.")
    log_path = tmp_path / "naive.action_log.jsonl"

    baseline = NaiveOverwriteBaseline(
        llm=llm,
        extractor=FakeExtractor(),
        classifier=FakeClassifier(),
        corpus={"s-prior": prior, "s-current": current},
        embedder=FakeEmbedder(embedding_dim=32),
        action_log_path=log_path,
    )

    answer = baseline.answer(current)

    assert answer.baseline == "naive_overwrite"
    assert answer.extras["current_session_leakage_count"] == 0
    assert answer.extras["action_counts"]["Supersede"] == 1

    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    overwrite = next(row for row in rows if row["action"] == "Supersede")
    assert overwrite["feature_c"] is None
    assert overwrite["s_rev"] is None
    assert "deleted prior" in overwrite["rationale"]
    assert "no supersession lineage" in overwrite["rationale"]
