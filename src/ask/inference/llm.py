"""LLM inference harness with Protocol + HuggingFace + structured-output wrapper.

Design goals (M1-W1 §3.2):
  1. Model-agnostic: swapping Llama-3-8B → Qwen2.5-7B is a config flip.
  2. Deterministic mode: temperature=0.0 + fixed seed → bit-identical text on a
     given hardware/transformers version.
  3. Optional heavy deps: `transformers`, `torch`, `flash_attn`, `bitsandbytes`
     are imported lazily so `pytest` on the skeleton does not pull GPU stacks.
  4. Structured output: validate JSON outputs against pydantic models; one
     auto-repair retry on parse failure.

Public surface:

    response = llm.generate("hello", max_new_tokens=64, temperature=0.0, seed=0)
    obj      = StructuredLLM(llm).generate_json(prompt, MyPydanticModel)
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# Pydantic is a declared hard dependency. Import it directly so the runtime and
# type contract agree: structured schemas are subclasses of ``BaseModel``.
import pydantic
import yaml
from pydantic import BaseModel

from ask.endpoints import validate_http_endpoint

_PYDANTIC_AVAILABLE = True

logger = logging.getLogger(__name__)


_DEFAULT_INFERENCE_CONFIG = (
    Path(__file__).resolve().parents[1] / "resources" / "configs" / "inference.yaml"
)


# --------------------------------------------------------------------- #
# Response and config dataclasses                                        #
# --------------------------------------------------------------------- #


@dataclass(frozen=True)
class LLMResponse:
    """One generation, with token accounting for the compute section."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    seed: int | None = None
    temperature: float = 0.0
    model_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class InferenceConfig:
    model_id: str
    fallback_model_id: str | None = None
    dtype: str = "bfloat16"  # bfloat16 | float16 | float32
    device_map: str = "auto"
    use_flash_attn_2: bool = False
    load_in_4bit: bool = False
    trust_remote_code: bool = False
    max_seq_len: int = 8192
    chat: bool = True
    # Reasoning ("thinking") models such as Qwen3 / Qwen3.5 emit a
    # <think>...</think> block by default. For short-answer + structured-JSON
    # eval that block wastes the (small) generation budget and pollutes the
    # answer, so the harness disables it via the chat template when this is set
    # to False. None = leave the template default untouched (Qwen2.5 etc.).
    enable_thinking: bool | None = None
    backend: str = "huggingface"  # huggingface | ollama | openai_compatible
    ollama_host: str = "http://localhost:11434"
    openai_base_url: str = "http://localhost:3001/v1"
    openai_api_key_env: str = "FREELLMAPI_KEY"
    openai_timeout_s: float = 120.0
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        validate_http_endpoint(
            self.ollama_host,
            allow_insecure_http=self.allow_insecure_http,
        )
        validate_http_endpoint(
            self.openai_base_url,
            allow_insecure_http=self.allow_insecure_http,
        )


def load_inference_config(path: str | Path | None = None) -> InferenceConfig:
    p = Path(path) if path else _DEFAULT_INFERENCE_CONFIG
    if not p.exists():
        # Sensible defaults: Llama-3-8B primary, Qwen2.5-7B fallback. The
        # config file is optional in Week 1; the test suite injects models
        # directly and the smoke script accepts overrides.
        return InferenceConfig(
            model_id="meta-llama/Meta-Llama-3-8B-Instruct",
            fallback_model_id="Qwen/Qwen2.5-7B-Instruct",
            dtype="bfloat16",
            device_map="auto",
            use_flash_attn_2=False,
            load_in_4bit=False,
            trust_remote_code=False,
            max_seq_len=8192,
        )
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    return InferenceConfig(
        model_id=str(raw["model_id"]),
        fallback_model_id=raw.get("fallback_model_id"),
        dtype=str(raw.get("dtype", "bfloat16")),
        device_map=str(raw.get("device_map", "auto")),
        use_flash_attn_2=bool(raw.get("use_flash_attn_2", False)),
        load_in_4bit=bool(raw.get("load_in_4bit", False)),
        trust_remote_code=bool(raw.get("trust_remote_code", False)),
        max_seq_len=int(raw.get("max_seq_len", 8192)),
        chat=bool(raw.get("chat", True)),
        enable_thinking=(
            None if raw.get("enable_thinking") is None else bool(raw.get("enable_thinking"))
        ),
        backend=str(raw.get("backend", "huggingface")),
        ollama_host=str(raw.get("ollama_host", "http://localhost:11434")),
        openai_base_url=str(raw.get("openai_base_url", "http://localhost:3001/v1")),
        openai_api_key_env=str(raw.get("openai_api_key_env", "FREELLMAPI_KEY")),
        openai_timeout_s=float(raw.get("openai_timeout_s", 120.0)),
        allow_insecure_http=bool(raw.get("allow_insecure_http", False)),
    )


# --------------------------------------------------------------------- #
# Protocol                                                               #
# --------------------------------------------------------------------- #


@runtime_checkable
class LLM(Protocol):
    """Anything that turns a prompt into an LLMResponse.

    Implementations are responsible for:
      - their own tokenization,
      - honoring `temperature=0.0` as deterministic-greedy with a fixed seed,
      - reporting latency in milliseconds wall-clock.
    """

    model_id: str

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        seed: int = 0,
        stop: list[str] | None = None,
    ) -> LLMResponse: ...


# --------------------------------------------------------------------- #
# HuggingFace concrete implementation (heavy import deferred)            #
# --------------------------------------------------------------------- #


_HF_MODEL_CACHE: dict[tuple[Any, ...], tuple[Any, Any, Any]] = {}

# Reasoning models (Qwen3/Qwen3.5, etc.) may emit a <think>...</think> block
# before the answer. With enable_thinking=False the template suppresses it, but
# we strip defensively so a stray block never reaches the grader or the JSON
# parser. Also drops an unclosed leading "<think> ..." (budget ran out mid-think)
# and a dangling closing "</think>" with the visible answer after it.
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think>.*\Z", re.DOTALL | re.IGNORECASE)


def _strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> reasoning spans from model output."""
    if "<think" not in text.lower() and "</think>" not in text.lower():
        return text
    cleaned = _THINK_BLOCK_RE.sub("", text)
    # A closing tag with no opening one = the opening was before the visible
    # completion (rare with some templates); keep only what follows it.
    lower = cleaned.lower()
    if "</think>" in lower:
        cleaned = cleaned[lower.rindex("</think>") + len("</think>") :]
    # An opening tag with no close = generation budget ran out inside the
    # think block; nothing usable remains, so drop it.
    cleaned = _THINK_OPEN_RE.sub("", cleaned)
    return cleaned.strip()


class HuggingFaceLLM:
    """Concrete LLM backed by `transformers.AutoModelForCausalLM`.

    Loaded lazily: the model is instantiated on first `generate()` call so the
    test suite (and the rest of Week 1) can construct the harness without
    paying multi-GB download / VRAM costs.

    KV cache is reused across calls implicitly via the `model` handle held on
    `self`. This is a single-process design — multi-tenant batching is
    explicitly out of scope for the Master's.
    """

    def __init__(self, config: InferenceConfig | None = None) -> None:
        self.config = config or load_inference_config()
        self.model_id = self.config.model_id
        # Expose the HF context window through the same attribute used by the
        # controller prompt-budget guard. Without this, long HF prompts are only
        # truncated inside the tokenizer, after the retriever has already built
        # an over-sized answer prompt.
        self.num_ctx = int(self.config.max_seq_len)
        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self._torch: Any | None = None  # cached torch module reference

    # --- lazy init helpers ------------------------------------------- #

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        cache_key = (
            self.config.model_id,
            self.config.dtype,
            self.config.device_map,
            self.config.use_flash_attn_2,
            self.config.load_in_4bit,
            self.config.trust_remote_code,
        )
        cached = _HF_MODEL_CACHE.get(cache_key)
        if cached is not None:
            self._tokenizer, self._model, self._torch = cached
            return
        try:
            import torch  # type: ignore[import-not-found]
            from transformers import (  # type: ignore[import-not-found]
                AutoModelForCausalLM,
                AutoTokenizer,
            )
        except ImportError as exc:
            raise RuntimeError(
                "transformers / torch are required for HuggingFaceLLM. "
                "Install with: pip install -e .[ml]"
            ) from exc

        self._torch = torch
        dtype = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }[self.config.dtype]

        load_kwargs: dict[str, Any] = {
            "torch_dtype": dtype,
            "device_map": self.config.device_map,
            "trust_remote_code": self.config.trust_remote_code,
            "low_cpu_mem_usage": True,
        }
        if self.config.use_flash_attn_2:
            load_kwargs["attn_implementation"] = "flash_attention_2"
        if self.config.load_in_4bit:
            try:
                from transformers import BitsAndBytesConfig  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError(
                    "load_in_4bit=True requires bitsandbytes; pip install bitsandbytes"
                ) from exc
            load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)

        logger.info(
            "loading model=%s dtype=%s 4bit=%s",
            self.model_id,
            self.config.dtype,
            self.config.load_in_4bit,
        )
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id, trust_remote_code=self.config.trust_remote_code
        )
        # Make sure pad_token is defined for batched generation paths.
        if self._tokenizer.pad_token_id is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        # Most checkpoints are plain causal LMs. A few newer Qwen releases
        # (e.g. the `qwen3_5` image-text-to-text family) only register an
        # image-text-to-text / vision2seq auto-class, so AutoModelForCausalLM
        # raises ValueError on them. Text-only generation still works through
        # those classes (they accept input_ids), so fall back rather than fail.
        try:
            self._model = AutoModelForCausalLM.from_pretrained(self.model_id, **load_kwargs)
        except (ValueError, KeyError) as causal_exc:
            self._model = self._load_non_causal_fallback(load_kwargs, causal_exc)
        self._model.eval()
        _HF_MODEL_CACHE[cache_key] = (self._tokenizer, self._model, self._torch)

    def _load_non_causal_fallback(self, load_kwargs: dict[str, Any], causal_exc: Exception) -> Any:
        """Load checkpoints that only register a non-causal auto-class.

        Tries the image-text-to-text and vision2seq auto-classes in turn for
        models like `qwen3_5` whose text decoder is reachable but not exposed
        through AutoModelForCausalLM. Re-raises the original causal-LM error if
        none apply, so a genuinely unsupported model still fails loudly.
        """
        candidates: list[str] = ["AutoModelForImageTextToText", "AutoModelForVision2Seq"]
        last_exc: Exception = causal_exc
        for name in candidates:
            try:
                import transformers  # type: ignore[import-not-found]

                cls = getattr(transformers, name, None)
                if cls is None:
                    continue
                logger.info("model=%s primary loader failed; trying %s", self.model_id, name)
                return cls.from_pretrained(self.model_id, **load_kwargs)
            except (ValueError, KeyError, OSError) as exc:  # pragma: no cover - depends on model
                last_exc = exc
                continue
        raise RuntimeError(
            f"could not load {self.model_id!r} as a causal LM or an "
            f"image-text-to-text/vision2seq model. transformers may be too old "
            f"for this architecture (upgrade it), or the checkpoint is "
            f"unsupported. Original error: {causal_exc}"
        ) from last_exc

    # --- generation -------------------------------------------------- #

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        seed: int = 0,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        self._ensure_loaded()
        assert self._model is not None
        assert self._tokenizer is not None
        assert self._torch is not None
        torch = self._torch

        # Determinism: greedy decode + manual seeds. transformers honors
        # the global seed for sampling paths; for greedy decode this is
        # belt-and-suspenders.
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        inputs = self._encode_prompt(prompt)
        input_truncated = bool(inputs.pop("_input_truncated", False))
        target_device = getattr(self._model, "device", None)
        if target_device is None and torch.cuda.is_available():
            target_device = "cuda"
        if target_device is not None:
            inputs = {k: v.to(target_device) for k, v in inputs.items()}
        prompt_tokens = int(inputs["input_ids"].shape[-1])

        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": int(max_new_tokens),
            "do_sample": temperature > 0.0,
            "pad_token_id": self._tokenizer.pad_token_id,
        }
        if temperature > 0.0:
            gen_kwargs["temperature"] = float(temperature)

        t0 = time.perf_counter()
        with torch.inference_mode():
            out = self._model.generate(**inputs, **gen_kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        completion_ids = out[0, prompt_tokens:]
        text = self._tokenizer.decode(completion_ids, skip_special_tokens=True)
        text = _strip_think_blocks(text)
        if stop:
            for s in stop:
                idx = text.find(s)
                if idx >= 0:
                    text = text[:idx]

        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=int(completion_ids.shape[-1]),
            latency_ms=latency_ms,
            seed=seed,
            temperature=temperature,
            model_id=self.model_id,
            metadata={
                "max_seq_len": int(self.config.max_seq_len),
                "input_truncated": input_truncated,
            },
        )

    def _encode_prompt(self, prompt: str) -> dict[str, Any]:
        assert self._tokenizer is not None
        assert self._torch is not None
        torch = self._torch
        if self.config.chat and getattr(self._tokenizer, "chat_template", None):
            messages = [{"role": "user", "content": prompt}]
            # Pass enable_thinking only when explicitly configured AND the
            # template accepts it; Qwen2.5 templates reject the kwarg.
            thinking_kwargs: dict[str, Any] = {}
            if self.config.enable_thinking is not None:
                thinking_kwargs["enable_thinking"] = bool(self.config.enable_thinking)
            try:
                input_ids = self._tokenizer.apply_chat_template(
                    messages,
                    tokenize=True,
                    add_generation_prompt=True,
                    return_tensors="pt",
                    truncation=True,
                    max_length=self.config.max_seq_len,
                    **thinking_kwargs,
                )
                input_truncated = int(input_ids.shape[-1]) >= int(self.config.max_seq_len)
            except TypeError:
                # Oldest-compatible call: drop truncation/max_length AND the
                # thinking kwarg, since either may be what the template rejected.
                input_ids = self._tokenizer.apply_chat_template(
                    messages,
                    tokenize=True,
                    add_generation_prompt=True,
                    return_tensors="pt",
                )
                input_truncated = bool(input_ids.shape[-1] > self.config.max_seq_len)
                if input_ids.shape[-1] > self.config.max_seq_len:
                    input_ids = input_ids[:, -self.config.max_seq_len :]
            return {
                "input_ids": input_ids,
                "attention_mask": torch.ones_like(input_ids),
                "_input_truncated": input_truncated,
            }
        encoded = self._tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.config.max_seq_len,
        )
        encoded["_input_truncated"] = int(encoded["input_ids"].shape[-1]) >= int(
            self.config.max_seq_len
        )
        return encoded


# --------------------------------------------------------------------- #
# Structured (JSON) wrapper                                              #
# --------------------------------------------------------------------- #


class StructuredLLMError(RuntimeError):
    """Raised when generate_json fails after its single repair retry."""


def _extract_first_json_object(text: str) -> str:
    """Best-effort JSON-object extraction.

    Pulls the first balanced JSON object instead of a greedy `{...}` span. This
    matters for local Ollama runs at nonzero temperature, where models sometimes
    emit a valid JSON object followed by a second example or explanatory text
    with braces. The parser respects JSON strings and escaped quotes.
    """
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found in model output")
    end = _balanced_json_object_end(text, start)
    if end is None:
        raise ValueError("unterminated JSON object in model output")
    return text[start:end]


def _balanced_json_object_end(text: str, start: int) -> int | None:
    """Return the exclusive end of a balanced object starting at ``start``."""
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return idx + 1
    return None


def _iter_json_objects(text: str) -> list[str]:
    """Return every balanced JSON object substring in text, left to right."""
    objects: list[str] = []
    idx = 0
    while idx < len(text):
        start = text.find("{", idx)
        if start < 0:
            break
        end = _balanced_json_object_end(text, start)
        if end is None:
            break
        objects.append(text[start:end])
        idx = end
    return objects


def _validate_any_json_object(text: str, schema: type[BaseModel]) -> BaseModel:
    """Validate the first object in text that matches the target schema."""
    last_err: Exception | None = None
    for obj_str in _iter_json_objects(text):
        try:
            data = json.loads(obj_str)
            return schema.model_validate(data)
        except (json.JSONDecodeError, pydantic.ValidationError) as exc:  # type: ignore[union-attr]
            last_err = exc
    if last_err is not None:
        raise last_err
    raise ValueError("no JSON object found in model output")


class StructuredLLM:
    """Wraps an LLM with `generate_json(prompt, schema)`.

    Behavior:
      1. Calls the wrapped LLM with `prompt`.
      2. Extracts the first JSON object substring.
      3. Parses + validates against the pydantic schema.
      4. On failure: ONE repair retry, asking the model to emit valid JSON
         given the schema's JSON-Schema dump.
      5. On second failure: raises StructuredLLMError.
    """

    def __init__(self, inner: LLM, *, max_repair_tokens: int = 512) -> None:
        if not _PYDANTIC_AVAILABLE:
            raise RuntimeError("pydantic>=2 is required for StructuredLLM. pip install pydantic")
        self.inner = inner
        self.max_repair_tokens = max_repair_tokens

    def generate_json(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        max_new_tokens: int = 512,
        temperature: float = 0.0,
        seed: int = 0,
        trace: dict[str, Any] | None = None,
    ) -> Any:
        """Parse one schema object from the model, repairing at most once.

        The first response is validated as-is. Schema-level ``mode="before"``
        validators (e.g. inferring a missing ``no_extractable_content`` flag)
        run inside this validation, so an output that is *recoverable by
        normalization* succeeds here and the repair call is skipped entirely.
        Repair therefore only fires on genuinely unparseable output, which
        prevents a successful-but-emptier repair from silently overwriting a
        good first-pass extraction.

        When ``trace`` is provided it is populated with ``parse_path``
        (``first`` | ``repair``), ``repair_used``, ``first_error``, and (on
        repair) ``repair_error`` so callers can log the full decision.
        """
        if trace is not None:
            trace.setdefault("repair_used", False)
            trace.setdefault("first_error", None)
            trace.setdefault("repair_error", None)
            trace.setdefault("parse_path", None)
        first = self.inner.generate(
            prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            seed=seed,
        )
        try:
            result = _validate_any_json_object(first.text, schema)
            if trace is not None:
                trace["parse_path"] = "first"
            return result
        except (ValueError, json.JSONDecodeError, pydantic.ValidationError) as first_err:  # type: ignore[union-attr]
            if trace is not None:
                trace["repair_used"] = True
                trace["first_error"] = str(first_err)
            repair_prompt = self._build_repair_prompt(prompt, first.text, schema, first_err)
            second = self.inner.generate(
                repair_prompt,
                max_new_tokens=self.max_repair_tokens,
                temperature=0.0,
                seed=seed,
            )
            try:
                result = _validate_any_json_object(second.text, schema)
                if trace is not None:
                    trace["parse_path"] = "repair"
                return result
            except (ValueError, json.JSONDecodeError, pydantic.ValidationError) as second_err:  # type: ignore[union-attr]
                if trace is not None:
                    trace["repair_error"] = str(second_err)
                raise StructuredLLMError(
                    f"failed to parse JSON after one repair retry: {second_err}"
                ) from second_err

    @staticmethod
    def _build_repair_prompt(
        original: str, bad_output: str, schema: type[BaseModel], err: Exception
    ) -> str:
        try:
            schema_dump = json.dumps(schema.model_json_schema(), indent=2)
        except (AttributeError, TypeError, ValueError):
            schema_dump = str(schema)
        return (
            "Your previous response could not be parsed. "
            "Re-emit ONLY the requested answer JSON object. Do not repeat, quote, "
            "or summarize the schema. Do not include markdown or explanations.\n\n"
            "----- ORIGINAL PROMPT -----\n"
            f"{original}\n"
            "----- YOUR PREVIOUS OUTPUT (invalid) -----\n"
            f"{bad_output}\n"
            "----- PARSE ERROR -----\n"
            f"{err}\n"
            "----- REQUIRED JSON SCHEMA (reference only; do not output this) -----\n"
            f"{schema_dump}\n"
            "----- REQUESTED ANSWER JSON ONLY -----\n"
        )


# --------------------------------------------------------------------- #
# Factory                                                                #
# --------------------------------------------------------------------- #


def build_llm(
    config: InferenceConfig | None = None,
    *,
    use_fallback: bool = False,
) -> LLM:
    """Build the harness, optionally using the configured fallback model.

    Backend dispatch:
        backend="huggingface" → HuggingFaceLLM (GPU; primary for the bench)
        backend="ollama"      → OllamaLLM (local daemon; dev/laptop path)
        backend="openai_compatible" → OpenAICompatibleLLM (FreeLLMAPI, etc.)
    """
    cfg = config or load_inference_config()
    if use_fallback:
        if cfg.fallback_model_id is None:
            raise ValueError("no fallback_model_id configured")
        cfg = dataclasses.replace(cfg, model_id=cfg.fallback_model_id)
    if cfg.backend == "ollama":
        from .ollama import OllamaLLM

        return OllamaLLM(
            model_id=cfg.model_id,
            host=cfg.ollama_host,
            allow_insecure_http=cfg.allow_insecure_http,
        )
    if cfg.backend in {"openai_compatible", "openai-compatible", "openai"}:
        from .openai_compatible import OpenAICompatibleLLM

        return OpenAICompatibleLLM(
            model_id=cfg.model_id,
            base_url=cfg.openai_base_url,
            api_key_env=cfg.openai_api_key_env,
            timeout_s=cfg.openai_timeout_s,
            allow_insecure_http=cfg.allow_insecure_http,
        )
    if cfg.backend == "huggingface":
        return HuggingFaceLLM(cfg)
    raise ValueError(f"unknown backend: {cfg.backend!r}")
