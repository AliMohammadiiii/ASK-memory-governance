"""Baseline 1 — No external memory.

The simplest possible system: an LLM that sees only the *current* session's
turns and the question. No retrieval, no memory store, no cross-session
context. This baseline is the floor against which every later result is
implicitly a delta (M1-W2 §1).

Implementation discipline:
  * The rendered prompt MUST contain ONLY the current session's turns. Test
    `tests/test_no_memory.py::test_prompt_contains_only_current_session`
    verifies this. Do not add cross-session leakage in the name of "helpful
    context" — that defeats the experimental design.
  * The system prompt is deliberately minimal: no chain-of-thought hint, no
    "use your memory" framing, no role-play preamble. Anything more turns
    Baseline 1 into "Baseline 1 + prompt eng," which is a different
    experiment.
  * The same `BaselineAnswer` shape is used by Baselines 2-4 and the
    controller; the evaluator does not know which baseline produced it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ask.data.longmemeval import LongMemEvalSession
from ask.inference.llm import LLM

from .base import BaselineAnswer

# Minimal system prompt. Reads as plain instruction, no memory framing, no
# chain-of-thought hint. Match the smoke-prompt vocabulary in scripts/smoke_e2e
# so cross-baseline differences in §3.4 sanity numbers are not artifacts of
# prompt re-wording.
DEFAULT_SYSTEM_PROMPT = (
    "Read the provided context and answer the question with only the requested "
    "value, name, date, number, or short phrase. Do not explain. Do not add "
    "surrounding sentence text. If the context is insufficient, answer Unknown."
)

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _build_jinja_env() -> Environment:
    """Module-level Jinja env. autoescape off (we render plain text, not HTML)."""
    return Environment(
        loader=FileSystemLoader(str(_PROMPT_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )


@dataclass
class NoMemoryBaseline:
    """LLM + a single Jinja2 template, nothing else.

    Args:
        llm: any object satisfying the `ask.inference.llm.LLM` Protocol.
        prompt_template: name of a `.j2` file in `prompts/`. Defaults to
            `no_memory.j2`. Override only for ablations — the canonical Week-2
            run uses the default.
        system_prompt: top of the rendered prompt. Defaults to
            `DEFAULT_SYSTEM_PROMPT`. Tests inject custom values to verify
            slot rendering.
        max_new_tokens: cap for the completion. 512 is generous for a
            "single short sentence" answer; the task spec sets this default.
        seed: passed through to the LLM. Determinism contract: same session
            + same seed → same answer text.
    """

    llm: LLM
    prompt_template: str = "no_memory.j2"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_new_tokens: int = 512
    seed: int = 0

    BASELINE_NAME: str = "no_memory"

    def __post_init__(self) -> None:
        self._env = _build_jinja_env()
        # Touch the template at __init__ so a missing file fails fast, not on
        # the first answer.
        self._template = self._env.get_template(self.prompt_template)

    # --- prompt rendering -------------------------------------------- #

    def render_prompt(self, session: LongMemEvalSession) -> str:
        """Return the exact text we will hand to `llm.generate`.

        Crucially: we pass *only* `session.turns` and `session.question`.
        We do not pass `session.competency` (would leak the answer category),
        `session.gold_answer` (would leak the answer), or
        `session.supporting_session_ids` (would leak that this is a
        multi-session question and which sessions to look at).
        """
        turn_dicts = [{"role": t.role, "content": t.content} for t in session.turns]
        return self._template.render(
            system_prompt=self.system_prompt,
            turns=turn_dicts,
            question=session.question,
        )

    # --- generation -------------------------------------------------- #

    def answer(self, session: LongMemEvalSession) -> BaselineAnswer:
        """Generate one answer for one session. Synchronous, blocking."""
        prompt = self.render_prompt(session)
        resp = self.llm.generate(
            prompt,
            max_new_tokens=self.max_new_tokens,
            temperature=0.0,
            seed=self.seed,
        )
        # Strip leading/trailing whitespace; some chat models emit a leading
        # newline. Do not normalize internally — the judge sees what we got.
        text = resp.text.strip()
        return BaselineAnswer(
            session_id=session.session_id,
            text=text,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            latency_ms=resp.latency_ms,
            raw_prompt=prompt,
            seed=self.seed,
            model_id=resp.model_id,
            baseline=self.BASELINE_NAME,
            extras={"llm_call": dict(resp.metadata)},
        )
