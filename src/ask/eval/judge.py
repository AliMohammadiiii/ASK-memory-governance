"""Config-toggleable LongMemEval judge backends for M4-W13.

The evaluator itself only needs an object satisfying the LLM Protocol. This
module keeps the Month-4 judge choice explicit and auditable instead of hiding
it in the generic answerer flags.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from ask.inference.llm import LLM, InferenceConfig

JudgeBackend = Literal[
    "same_as_answerer",
    "ollama",
    "huggingface",
    "hf",
    "fake",
    "openai_compatible",
]


@dataclass(frozen=True)
class JudgeBackendConfig:
    """Backend selection for LongMemEval grading."""

    backend: JudgeBackend = "same_as_answerer"
    model_id: str | None = None
    ollama_host: str = "http://localhost:11434"
    num_ctx: int | None = 2048
    timeout_s: float = 900.0
    response_format: str | dict[str, Any] | None = "json"
    think: bool | str | None = False
    hf_dtype: str = "float16"
    hf_device_map: str = "auto"
    hf_load_in_4bit: bool = False
    hf_trust_remote_code: bool = False
    hf_max_seq_len: int = 4096
    openai_base_url: str = "http://localhost:3001/v1"
    openai_api_key: str | None = None
    openai_api_key_env: str = "FREELLMAPI_KEY"
    openai_timeout_s: float = 120.0
    openai_log_path: str | None = None
    openai_include_raw_responses: bool = False

    @classmethod
    def from_yaml(cls, path: str | Path) -> JudgeBackendConfig:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        judge = raw.get("judge", raw)
        response_format = judge.get("response_format", "json")
        if response_format in ("", "none", "None", None):
            response_format = None
        return cls(
            backend=str(judge.get("backend", "same_as_answerer")),  # type: ignore[arg-type]
            model_id=judge.get("model_id"),
            ollama_host=str(judge.get("ollama_host", "http://localhost:11434")),
            num_ctx=judge.get("num_ctx", 2048),
            timeout_s=float(judge.get("timeout_s", 900.0)),
            response_format=response_format,
            think=judge.get("think", False),
            hf_dtype=str(judge.get("hf_dtype", "float16")),
            hf_device_map=str(judge.get("hf_device_map", "auto")),
            hf_load_in_4bit=bool(judge.get("hf_load_in_4bit", False)),
            hf_trust_remote_code=bool(judge.get("hf_trust_remote_code", False)),
            hf_max_seq_len=int(judge.get("hf_max_seq_len", 4096)),
            openai_base_url=str(judge.get("openai_base_url", "http://localhost:3001/v1")),
            openai_api_key=judge.get("openai_api_key"),
            openai_api_key_env=str(judge.get("openai_api_key_env", "FREELLMAPI_KEY")),
            openai_timeout_s=float(judge.get("openai_timeout_s", 120.0)),
            openai_log_path=judge.get("openai_log_path"),
            openai_include_raw_responses=bool(judge.get("openai_include_raw_responses", False)),
        )


def build_judge_backend(
    config: JudgeBackendConfig,
    *,
    answerer: LLM | None = None,
) -> LLM:
    """Build the selected judge LLM.

    `same_as_answerer` is preserved for old development runs. M4-W13 should
    use `backend="ollama"` with an explicit `model_id` so the judge is a
    substitute backend rather than a silent self-judge.
    """
    if config.backend == "same_as_answerer":
        if answerer is None:
            raise ValueError("same_as_answerer judge backend requires answerer")
        return answerer

    if config.backend == "fake":
        from ask.inference.fake import FakeLLM

        return FakeLLM(model_id=config.model_id or "fake/judge")

    if config.backend == "ollama":
        if not config.model_id:
            raise ValueError("ollama judge backend requires model_id")
        from ask.inference.ollama import OllamaLLM

        return OllamaLLM(
            model_id=config.model_id,
            host=config.ollama_host,
            num_ctx=config.num_ctx,
            timeout_s=config.timeout_s,
            response_format=config.response_format,
            think=config.think,
        )

    if config.backend == "openai_compatible":
        if not config.model_id:
            raise ValueError("openai_compatible judge backend requires model_id")
        from ask.inference.openai_compatible import OpenAICompatibleLLM

        return OpenAICompatibleLLM(
            model_id=config.model_id,
            base_url=config.openai_base_url,
            api_key=config.openai_api_key,
            api_key_env=config.openai_api_key_env,
            timeout_s=config.openai_timeout_s,
            response_format={"type": "json_object"} if config.response_format else None,
            require_json=bool(config.response_format),
            log_path=Path(config.openai_log_path) if config.openai_log_path else None,
            include_raw_response=config.openai_include_raw_responses,
        )

    if config.backend in {"huggingface", "hf"}:
        if not config.model_id:
            raise ValueError("huggingface judge backend requires model_id")
        from ask.inference.llm import HuggingFaceLLM

        return HuggingFaceLLM(
            InferenceConfig(
                model_id=config.model_id,
                dtype=config.hf_dtype,
                device_map=config.hf_device_map,
                load_in_4bit=config.hf_load_in_4bit,
                trust_remote_code=config.hf_trust_remote_code,
                max_seq_len=config.hf_max_seq_len,
                backend="huggingface",
            )
        )

    raise ValueError(f"unknown judge backend {config.backend!r}")
