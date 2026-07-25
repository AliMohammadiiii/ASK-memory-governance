"""§5 fix 1 — concurrent intra-question extraction must match the serial path.

The Keep/Supersede/Abstain decision loop stays sequential; only the independent
per-turn extraction is parallelized. This test proves that turning concurrency
on changes nothing observable (same memory, same decisions, same answer) and
that concurrent calls actually overlap in wall-clock time.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from ask.classifier.schema import RelationOutput
from ask.data.longmemeval import LongMemEvalSession, LongMemEvalTurn
from ask.extraction import EvidenceSpan, ExtractedItem, ExtractionOutput
from ask.inference.fake import FakeLLM
from ask.pipeline.orchestrator import ControllerOrchestrator


class _SlowEchoExtractor:
    """Identity extractor with a small sleep so overlap is measurable."""

    def __init__(self, delay: float = 0.05) -> None:
        self.delay = delay
        self.calls = 0

    def extract(self, turn, window, *, max_new_tokens=512, temperature=0.0, seed=0):
        time.sleep(self.delay)
        self.calls += 1
        return ExtractionOutput(
            items=[
                ExtractedItem(
                    text=turn["content"],
                    type_guess="episodic_fact",
                    evidence_span=EvidenceSpan(
                        session_id=turn["session_id"],
                        turn_idx=turn["turn_idx"],
                        char_start=0,
                        char_end=len(turn["content"]),
                    ),
                    extraction_confidence=0.95,
                    negation_marker=False,
                    hedge_marker=False,
                )
            ],
            no_extractable_content=False,
        )


class _IndependentClassifier:
    def classify(self, candidate, prior, *, max_new_tokens=128, temperature=0.0, seed=0):
        return RelationOutput(
            logical_relation="independent",
            temporal="unknown",
            same_subject=False,
            relation_to_prior_state="unclear",
            stage1_rationale="fake",
            stage2_rationale="fake",
        )


class _ConstantEmbedder:
    embedding_dim = 2
    model_id = "fake/constant"

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.tile(np.asarray([[1.0, 0.0]], dtype=np.float32), (len(texts), 1))


def _many_turn_session(n_user_turns: int) -> LongMemEvalSession:
    turns: list[LongMemEvalTurn] = []
    for i in range(n_user_turns):
        turns.append(
            LongMemEvalTurn(
                role="user",
                content=f"Fact number {i}: I bought item {i}.",
                timestamp=f"2026/01/{i + 1:02d} (Mon) 10:00",
            )
        )
        turns.append(LongMemEvalTurn(role="assistant", content="noted"))
    return LongMemEvalSession(
        session_id="mem-A",
        turns=tuple(turns),
        question="What facts did I mention?",
        gold_answer="various",
        competency="multi-session",
        supporting_session_ids=("mem-A",),
    )


def _run(concurrency: int, tmp_path: Path, delay: float = 0.05):
    memory = _many_turn_session(8)
    current = LongMemEvalSession(
        session_id="cur",
        turns=(LongMemEvalTurn(role="user", content="Checking in."),),
        question="What facts did I mention?",
        gold_answer="various",
        competency="multi-session",
        supporting_session_ids=("mem-A",),
    )
    llm = FakeLLM()
    llm.queue("FINAL: various")
    extractor = _SlowEchoExtractor(delay=delay)
    orch = ControllerOrchestrator(
        llm=llm,
        extractor=extractor,
        classifier=_IndependentClassifier(),
        corpus={"mem-A": memory, "cur": current},
        embedder=_ConstantEmbedder(),
        k=8,
        action_log_path=tmp_path / f"log_{concurrency}.jsonl",
        extraction_concurrency=concurrency,
    )
    t0 = time.perf_counter()
    answer = orch.answer(current)
    elapsed = time.perf_counter() - t0
    return answer, extractor.calls, elapsed


def test_concurrent_extraction_matches_serial(tmp_path: Path) -> None:
    serial, serial_calls, serial_time = _run(1, tmp_path / "s")
    (tmp_path / "s").mkdir(exist_ok=True)
    (tmp_path / "c").mkdir(exist_ok=True)
    concurrent, conc_calls, conc_time = _run(8, tmp_path / "c")

    # Identical observable outcome.
    assert serial.text == concurrent.text
    assert serial.extras["action_counts"] == concurrent.extras["action_counts"]
    assert serial.extras["memory_session_ids"] == concurrent.extras["memory_session_ids"]
    # 8 memory turns + the current session's 1 user turn, both paths equal.
    assert serial_calls == conc_calls == 9

    # Concurrency actually overlapped: 8 serial 50ms sleeps ~= 0.4s; the
    # concurrent run should be well under the serial sum.
    assert conc_time < serial_time
