"""Prompt-budget guard contracts (M4W13 context-saturation fix).

These tests pin the behavior added to stop the answer prompt from filling the
whole Ollama context window (the failure that made session 852ce960 answer "$"
instead of "$400,000"): the prompt must be trimmed to leave room for the
answer, the question must never be trimmed, and a floor of the highest-scoring
retrieved items must survive.
"""

from __future__ import annotations

from ask.baselines.embeddings import FakeEmbedder
from ask.baselines.flat_vector_store import MemoryItem, RetrievedItem
from ask.data.longmemeval import LongMemEvalSession
from ask.inference.fake import FakeLLM
from ask.pipeline import ControllerOrchestrator
from ask.pipeline.orchestrator import _BUDGET_FLOOR_ITEMS, _estimate_prompt_tokens
from tests.test_pipeline_orchestrator import FakeClassifier, FakeExtractor


def _orchestrator(num_ctx: int | None) -> ControllerOrchestrator:
    llm = FakeLLM()
    if num_ctx is not None:
        llm.num_ctx = num_ctx  # type: ignore[attr-defined]
    return ControllerOrchestrator(
        llm=llm,
        extractor=FakeExtractor(),
        classifier=FakeClassifier(),
        corpus={},
        embedder=FakeEmbedder(embedding_dim=32),
        max_new_tokens=256,
    )


def _question_session() -> LongMemEvalSession:
    return LongMemEvalSession(
        session_id="s-budget",
        turns=(),
        question="What is the capital of France?",
        gold_answer="Paris",
        competency="multi-session",
    )


def _retrieved(n: int) -> list[RetrievedItem]:
    items: list[RetrievedItem] = []
    for i in range(n):
        role = "assistant" if i % 2 == 0 else "user"
        items.append(
            RetrievedItem(
                item=MemoryItem(
                    text=("lorem ipsum dolor sit amet " * 24) + f" marker{i}",
                    role=role,
                    session_id=f"m{i}",
                    turn_idx=i,
                    timestamp="2024-01-01",
                ),
                score=1.0 - i * 0.01,
                rank=i,
            )
        )
    return items


def test_budget_disabled_when_backend_has_no_num_ctx() -> None:
    orch = _orchestrator(num_ctx=None)
    num_ctx, _reserved, budget = orch._answer_token_budget()
    assert num_ctx is None
    assert budget == 0
    retrieved = _retrieved(20)
    trimmed, debug = orch._budget_trim_for_answer(_question_session(), retrieved, None, budget)
    # No window exposed -> never trim, byte-stable behavior.
    assert trimmed is retrieved
    assert debug["prompt_trimmed"] is False


def test_budget_trim_fits_keeps_floor_and_preserves_question() -> None:
    orch = _orchestrator(num_ctx=1200)
    num_ctx, reserved, budget = orch._answer_token_budget()
    assert (num_ctx, reserved) == (1200, 256)
    assert budget == 1200 - 256 - 256  # num_ctx - reserved_output - margin

    session = _question_session()
    retrieved = _retrieved(40)
    trimmed, debug = orch._budget_trim_for_answer(session, retrieved, None, budget)

    assert debug["prompt_trimmed"] is True
    assert len(trimmed) < len(retrieved)
    assert len(trimmed) >= _BUDGET_FLOOR_ITEMS
    # Either the trimmed prompt fits, or we are pinned at the protected floor.
    rendered = orch._render_prompt(session, trimmed, computed_answer=None)
    assert _estimate_prompt_tokens(rendered) <= budget or len(trimmed) == _BUDGET_FLOOR_ITEMS
    # The question is never trimmed.
    assert "capital of France" in rendered
    # Assistant context is dropped before user-asserted facts.
    assert all(item.item.role == "user" for item in trimmed)
    # Surviving items stay in their original retrieval order.
    ranks = [item.rank for item in trimmed]
    assert ranks == sorted(ranks)


def test_budget_no_trim_when_prompt_already_fits() -> None:
    orch = _orchestrator(num_ctx=32768)
    _, _, budget = orch._answer_token_budget()
    session = _question_session()
    retrieved = _retrieved(3)
    trimmed, debug = orch._budget_trim_for_answer(session, retrieved, None, budget)
    assert debug["prompt_trimmed"] is False
    assert len(trimmed) == 3


def test_answer_records_budget_extras() -> None:
    orch = _orchestrator(num_ctx=8192)
    session = _question_session()
    answer = orch.answer(session)
    for key in (
        "prompt_num_ctx",
        "prompt_reserved_output_tokens",
        "prompt_generation_budget_tokens",
        "prompt_memory_items_before_trim",
        "prompt_memory_items_after_trim",
        "prompt_trimmed",
        "prompt_assistant_context_included",
        "prompt_neighbor_window",
        "answer_text_length",
        "answer_looks_truncated",
        "prompt_token_estimate_is_approximate",
    ):
        assert key in answer.extras
    assert answer.extras["prompt_num_ctx"] == 8192
    assert answer.extras["prompt_token_estimate_is_approximate"] is True
