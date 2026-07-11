"""Tests for the no-memory baseline (M1-W2 §3.1).

Three contracts:
  1. Prompt isolation — the rendered prompt contains exactly the current
     session's turns + question; no other sessions' content leaks in.
  2. Determinism — same session, same seed → identical answer text and
     token-account fields.
  3. Token-count fidelity — the BaselineAnswer's prompt/completion token
     counts equal what the underlying LLM reports (no off-by-one or accidental
     re-tokenization).
"""

from __future__ import annotations

import dataclasses

import pytest

from ksa.baselines.base import BaselineAnswer
from ksa.baselines.no_memory import (
    DEFAULT_SYSTEM_PROMPT,
    NoMemoryBaseline,
)
from ksa.data.longmemeval import LongMemEvalSession, LongMemEvalTurn
from ksa.inference.llm import LLMResponse

# --------------------------------------------------------------------- #
# Helpers / fixtures                                                     #
# --------------------------------------------------------------------- #


def _session(
    sid: str,
    turns: list[tuple[str, str]],
    question: str,
    competency: str = "single-session-user",
    gold: str = "the gold answer",
) -> LongMemEvalSession:
    return LongMemEvalSession(
        session_id=sid,
        turns=tuple(LongMemEvalTurn(role=r, content=c) for r, c in turns),
        question=question,
        gold_answer=gold,
        competency=competency,
    )


class _RecordingLLM:
    """Minimal LLM Protocol impl that echoes back a deterministic response.

    Records the most recent prompt for assertion. Not the same as `FakeLLM` —
    we want to control the response text precisely from the test.
    """

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
        # Deterministic: token counts derive from the prompt + response only.
        return LLMResponse(
            text=self.response_text,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(self.response_text.split()),
            latency_ms=0.0,
            seed=seed,
            temperature=temperature,
            model_id=self.model_id,
        )


# --------------------------------------------------------------------- #
# §3.1 exit-criterion tests                                              #
# --------------------------------------------------------------------- #


def test_render_prompt_includes_required_slots() -> None:
    """The Jinja template fills system_prompt, turns, and question slots."""
    llm = _RecordingLLM()
    bl = NoMemoryBaseline(llm=llm, system_prompt="SYSTEM_MARKER")
    sess = _session(
        "sess-001",
        [("user", "USER_TURN_MARKER"), ("assistant", "ASSISTANT_TURN_MARKER")],
        "QUESTION_MARKER",
    )
    rendered = bl.render_prompt(sess)
    assert "SYSTEM_MARKER" in rendered
    assert "USER_TURN_MARKER" in rendered
    assert "ASSISTANT_TURN_MARKER" in rendered
    assert "QUESTION_MARKER" in rendered
    # role-tagged dialogue
    assert "USER:" in rendered
    assert "ASSISTANT:" in rendered


def test_default_system_prompt_is_minimal_and_no_memory_framing() -> None:
    """Catch accidental drift toward a 'use your memory' system prompt.

    The whole point of the no-memory baseline is unaided performance.
    """
    s = DEFAULT_SYSTEM_PROMPT.lower()
    assert "memory" not in s
    assert "remember" not in s
    assert "step by step" not in s  # no CoT hint
    assert "let's think" not in s
    assert "chain of thought" not in s
    assert "surrounding sentence" in s


def test_prompt_answer_marker_requests_short_answer_only() -> None:
    llm = _RecordingLLM()
    bl = NoMemoryBaseline(llm=llm)
    rendered = bl.render_prompt(_session("sess-001", [("user", "hi")], "QUESTION_MARKER"))

    assert "ANSWER (short answer only)" in rendered
    assert "ANSWER (one short sentence)" not in rendered


def test_prompt_contains_only_current_session() -> None:
    """Critical: the no-memory baseline must NOT see any prior session's content.

    If this test ever passes-when-it-shouldn't, every later baseline's
    accuracy delta is meaningless because Baseline 1 silently has memory.
    """
    llm = _RecordingLLM()
    bl = NoMemoryBaseline(llm=llm)
    sess_now = _session(
        "sess-now",
        [("user", "TURN_FROM_CURRENT_SESSION")],
        "What did I just say?",
    )
    # Construct an unrelated session whose content must NOT leak in.
    _other = _session(
        "sess-other",
        [("user", "LEAK_CANARY_FROM_OTHER_SESSION")],
        "different question",
    )
    rendered = bl.render_prompt(sess_now)
    assert "TURN_FROM_CURRENT_SESSION" in rendered
    assert "LEAK_CANARY_FROM_OTHER_SESSION" not in rendered
    # Also: nothing from the gold answer or competency is leaking.
    assert sess_now.gold_answer not in rendered
    assert sess_now.competency not in rendered


def test_prompt_does_not_leak_supporting_session_ids() -> None:
    """Multi-session questions ship `supporting_session_ids` — must not leak."""
    sess = LongMemEvalSession(
        session_id="sess-ms-1",
        turns=(LongMemEvalTurn(role="user", content="hi"),),
        question="aggregate question",
        gold_answer="answer",
        competency="multi-session",
        supporting_session_ids=("sess-ms-1", "sess-ms-7"),
    )
    bl = NoMemoryBaseline(llm=_RecordingLLM())
    rendered = bl.render_prompt(sess)
    assert "sess-ms-7" not in rendered


def test_determinism_same_session_same_seed() -> None:
    """Same input → identical answer text and token accounting."""
    llm = _RecordingLLM(response_text="deterministic answer.")
    bl = NoMemoryBaseline(llm=llm, seed=42)
    sess = _session("sess-x", [("user", "hello")], "Q?")
    a = bl.answer(sess)
    b = bl.answer(sess)
    # Note: dataclasses.replace would let us compare ignoring latency, but we
    # mocked latency to 0.0 above so a direct equality holds.
    assert a == b
    assert a.text == "deterministic answer."
    assert a.session_id == "sess-x"
    assert a.baseline == "no_memory"
    assert a.seed == 42
    assert a.model_id == "recording-llm-v0"


def test_token_counts_match_llm_response() -> None:
    """BaselineAnswer mirrors the LLM's reported token counts exactly."""
    llm = _RecordingLLM(response_text="word1 word2 word3.")
    bl = NoMemoryBaseline(llm=llm)
    sess = _session("sess-t", [("user", "hi there")], "Q?")
    ans = bl.answer(sess)
    # _RecordingLLM uses .split() to compute counts; we replicate the same.
    expected_prompt_tokens = len(llm.last_prompt.split())  # type: ignore[union-attr]
    assert ans.prompt_tokens == expected_prompt_tokens
    assert ans.completion_tokens == 3  # "word1 word2 word3."


def test_baseline_answer_is_serializable() -> None:
    """to_dict() returns a JSON-friendly dict (round-trips through dataclasses.asdict)."""
    llm = _RecordingLLM()
    bl = NoMemoryBaseline(llm=llm)
    sess = _session("sess-s", [("user", "hi")], "Q?")
    ans = bl.answer(sess)
    d = ans.to_dict()
    # the dataclasses.asdict path covers nested dataclasses → dict.
    assert isinstance(d, dict)
    assert d["baseline"] == "no_memory"
    assert d["session_id"] == "sess-s"
    assert "extras" in d


def test_baseline_answer_is_frozen() -> None:
    """BaselineAnswer is immutable; mutation attempts must raise.

    Frozen-ness matters for the cache key in the evaluator.
    """
    a = BaselineAnswer(
        session_id="x",
        text="t",
        prompt_tokens=1,
        completion_tokens=1,
        latency_ms=0.0,
        raw_prompt="p",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.text = "mutated"  # type: ignore[misc]
