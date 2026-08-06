"""Fallback composition for LLM backends."""

from __future__ import annotations

from dataclasses import dataclass

from .llm import LLM, LLMResponse


@dataclass
class FallbackLLM:
    """Try LLMs in order until one returns a passing response."""

    candidates: tuple[LLM, ...]

    def __post_init__(self) -> None:
        if not self.candidates:
            raise ValueError("FallbackLLM requires at least one candidate")
        self.model_id = " -> ".join(getattr(c, "model_id", "?") for c in self.candidates)

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        seed: int = 0,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        errors: list[str] = []
        last_response: LLMResponse | None = None
        for index, llm in enumerate(self.candidates):
            try:
                response = llm.generate(
                    prompt,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    seed=seed,
                    stop=stop,
                )
            except (OSError, TimeoutError, RuntimeError) as exc:
                errors.append(f"{getattr(llm, 'model_id', '?')}: {type(exc).__name__}: {exc}")
                continue
            meta = dict(response.metadata)
            meta["fallback_candidate_index"] = index
            meta["fallback_chain"] = self.model_id
            response = LLMResponse(
                text=response.text,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                latency_ms=response.latency_ms,
                seed=response.seed,
                temperature=response.temperature,
                model_id=response.model_id,
                metadata=meta,
            )
            last_response = response
            if meta.get("gate_pass", True):
                return response
            errors.append(
                f"{getattr(llm, 'model_id', '?')}: gate failed {meta.get('validation_errors', '')}"
            )
        if last_response is not None:
            return last_response
        raise RuntimeError("all fallback LLMs failed: " + " | ".join(errors))
