"""pydantic-ai-backed structured-output wrapper (optional).

The hand-rolled `StructuredLLM` in `llm.py` does the job for the Master's
extractor + relation classifier, but pydantic-ai gives a more robust path
(grammar-constrained sampling for OpenAI-compatible servers, native repair
loops, observability hooks) that may be useful in Month 2 when the relation
classifier ships.

This module is imported lazily so pydantic-ai is **not** a hard dependency
of the harness. Install with:

    pip install pydantic-ai pydantic-ai-slim[ollama]

Usage:

    from ask.inference.structured_pai import structured_via_pydantic_ai
    obj = structured_via_pydantic_ai(
        model="ollama:gemma3:4b",
        prompt=prompt,
        schema=ExtractionModel,
    )

For OpenAI-compatible Ollama bridges:

    obj = structured_via_pydantic_ai(
        model="openai:gemma3:4b",                 # via Ollama's OpenAI shim
        prompt=prompt,
        schema=ExtractionModel,
        base_url="http://localhost:11434/v1",
    )
"""

from __future__ import annotations

from typing import Any

from ask.endpoints import validate_http_endpoint


def structured_via_pydantic_ai(
    *,
    model: str,
    prompt: str,
    schema: type,
    system: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    seed: int = 0,
    temperature: float = 0.0,
    allow_insecure_http: bool = False,
) -> Any:
    """Run one structured extraction via pydantic-ai. Returns an instance of `schema`.

    Raises:
        RuntimeError: if pydantic-ai is not installed.
        pydantic_ai.exceptions.UnexpectedModelBehavior: if the model fails the
            schema after pydantic-ai's own retry budget.
    """
    try:
        from pydantic_ai import Agent  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "pydantic-ai not installed. Install with:\n"
            "    pip install pydantic-ai pydantic-ai-slim[ollama]"
        ) from exc

    model_obj: Any = model
    if base_url:
        validate_http_endpoint(base_url, allow_insecure_http=allow_insecure_http)
        try:
            from pydantic_ai.models.openai import OpenAIModel  # type: ignore[import-not-found]
            from pydantic_ai.providers.openai import (
                OpenAIProvider,  # type: ignore[import-not-found]
            )
        except ImportError as exc:
            raise RuntimeError(
                "pydantic-ai OpenAI provider is not available in this environment"
            ) from exc
        model_obj = OpenAIModel(
            model,
            provider=OpenAIProvider(base_url=base_url, api_key=api_key or "api-key-not-set"),
        )

    # pydantic-ai 1.x uses `output_type`; older project notes used
    # `result_type`. Keep this wrapper as the compatibility boundary.
    agent_kwargs: dict[str, Any] = {
        "output_type": schema,
        "model_settings": {"temperature": temperature, "seed": seed},
    }
    if system:
        agent_kwargs["system_prompt"] = system

    agent = Agent(model_obj, **agent_kwargs)
    result = agent.run_sync(prompt)
    return result.output
