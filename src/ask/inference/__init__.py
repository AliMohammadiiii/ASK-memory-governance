"""Model inference harness (M1-W1 §3.2).

Abstracts over Llama-3-8B-Instruct (primary) and Qwen2.5-7B-Instruct (fallback)
so the Month-2 classifier-gate fallback is a config flip, not a rewrite.
"""

from .llm import (
    LLM,
    LLMResponse,
    StructuredLLM,
    StructuredLLMError,
    build_llm,
    load_inference_config,
)
from .openai_compatible import OpenAICompatibleLLM

__all__ = [
    "LLM",
    "LLMResponse",
    "OpenAICompatibleLLM",
    "StructuredLLM",
    "StructuredLLMError",
    "build_llm",
    "load_inference_config",
]
