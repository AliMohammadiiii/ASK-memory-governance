"""Deterministic non-GPU LLM stub for tests and the e2e smoke script.

The Master's harness needs to be exercisable on CI / dev machines without
multi-GB downloads. `FakeLLM` implements the `LLM` Protocol with a seedable
deterministic answer-generator and a programmable scripted-response queue.
It is **not** a model — it exists purely to drive integration tests.
"""

from __future__ import annotations

import hashlib
import time
from collections import deque
from dataclasses import dataclass

from .llm import LLM, LLMResponse


@dataclass
class FakeLLM:
    """Deterministic stand-in for a real LLM.

    Two response modes:
      - If `scripted` is non-empty: pop and return scripted strings in order.
        Once exhausted, falls back to seeded deterministic answers.
      - Otherwise: returns `f"<deterministic({hash(prompt+seed)})>"`.

    Token counts are approximated as word counts (good enough for smoke tests).
    """

    model_id: str = "fake/deterministic-1"
    scripted: deque[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.scripted is None:
            self.scripted = deque()

    def queue(self, *texts: str) -> None:
        """Push scripted responses to the back of the queue."""
        for t in texts:
            self.scripted.append(t)

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        seed: int = 0,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        t0 = time.perf_counter()
        if self.scripted:
            text = self.scripted.popleft()
        else:
            digest = hashlib.blake2b(
                f"{prompt}|{seed}|{temperature}".encode(),
                digest_size=8,
            ).hexdigest()
            text = f"<deterministic:{digest}>"
        if stop:
            for s in stop:
                idx = text.find(s)
                if idx >= 0:
                    text = text[:idx]
        latency_ms = (time.perf_counter() - t0) * 1000.0
        prompt_tokens = max(1, len(prompt.split()))
        completion_tokens = max(1, len(text.split()))
        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            seed=seed,
            temperature=temperature,
            model_id=self.model_id,
        )


# Sanity check at import time: FakeLLM must satisfy the LLM Protocol.
assert isinstance(FakeLLM(), LLM)  # noqa: S101 — module-level invariant
