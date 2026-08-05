"""Inference harness tests (M1-W1 §3.2).

The Llama-3-8B model itself is exercised by `scripts/bench_inference.py` on
the GPU runner; this file tests the harness contract (Protocol satisfaction,
determinism, JSON validation + repair, fallback config flip) using the
deterministic FakeLLM. The contract is what subsequent weeks depend on; the
weights are not.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from ask.inference.fake import FakeLLM
from ask.inference.llm import (
    LLM,
    InferenceConfig,
    LLMResponse,
    StructuredLLM,
    StructuredLLMError,
    _extract_first_json_object,
    build_llm,
    load_inference_config,
)

# pydantic v2 is the structured contract. v1 stubs would also work but we
# require v2 in pyproject — fail loudly here if it is missing.
pydantic = pytest.importorskip("pydantic", minversion="2.0")
from pydantic import BaseModel, Field  # noqa: E402

# ----------------- Protocol satisfaction ---------------- #


def test_fake_llm_satisfies_llm_protocol() -> None:
    f = FakeLLM()
    assert isinstance(f, LLM)
    assert hasattr(f, "model_id")


def test_response_dataclass_round_trip() -> None:
    f = FakeLLM()
    r = f.generate("hello", seed=1, temperature=0.0, max_new_tokens=8)
    assert isinstance(r, LLMResponse)
    d = r.to_dict()
    assert {
        "text",
        "prompt_tokens",
        "completion_tokens",
        "latency_ms",
        "seed",
        "temperature",
        "model_id",
    } <= set(d)


# ----------------- Determinism -------------------------- #


def test_determinism_same_prompt_seed_temp_zero() -> None:
    f = FakeLLM()
    a = f.generate("the user said X", temperature=0.0, seed=0)
    b = f.generate("the user said X", temperature=0.0, seed=0)
    assert a.text == b.text


def test_seed_change_alters_output() -> None:
    f = FakeLLM()
    a = f.generate("the user said X", temperature=0.0, seed=0)
    b = f.generate("the user said X", temperature=0.0, seed=1)
    assert a.text != b.text


# ----------------- Structured-output wrapper ------------ #


class Extraction(BaseModel):
    text: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)


def test_generate_json_parses_clean_output() -> None:
    inner = FakeLLM()
    inner.queue('{"text": "User likes coffee", "confidence": 0.9}')
    s = StructuredLLM(inner)
    obj = s.generate_json("extract", Extraction, seed=0)
    assert isinstance(obj, Extraction)
    assert obj.text == "User likes coffee"
    assert obj.confidence == 0.9


def test_generate_json_retries_once_on_malformed_then_succeeds() -> None:
    inner = FakeLLM()
    # First attempt: not valid JSON. Second attempt: valid.
    inner.queue("here is some prose without braces — totally not JSON")
    inner.queue('{"text": "User drinks tea", "confidence": 0.85}')
    s = StructuredLLM(inner)
    obj = s.generate_json("extract", Extraction, seed=0)
    assert obj.text == "User drinks tea"
    # Both responses were consumed → exactly one retry happened.
    assert len(inner.scripted) == 0


def test_generate_json_raises_after_two_failures() -> None:
    inner = FakeLLM()
    inner.queue("not json")
    inner.queue("still not json")
    s = StructuredLLM(inner)
    with pytest.raises(StructuredLLMError):
        s.generate_json("extract", Extraction, seed=0)


def test_generate_json_validation_failure_triggers_repair() -> None:
    inner = FakeLLM()
    # First: parsable JSON but fails pydantic validation (confidence > 1).
    inner.queue('{"text": "X", "confidence": 5.0}')
    inner.queue('{"text": "X", "confidence": 0.5}')
    s = StructuredLLM(inner)
    obj = s.generate_json("extract", Extraction, seed=0)
    assert obj.confidence == 0.5
    assert len(inner.scripted) == 0


def test_json_extractor_uses_first_balanced_object() -> None:
    text = '{"text": "A", "confidence": 0.9}\n{"text": "B", "confidence": 0.1}'

    assert _extract_first_json_object(text) == '{"text": "A", "confidence": 0.9}'


def test_generate_json_skips_schema_echo_and_uses_later_valid_object() -> None:
    inner = FakeLLM()
    inner.queue(
        '{"title":"Extraction","type":"object"}\n{"text": "User likes coffee", "confidence": 0.9}'
    )
    s = StructuredLLM(inner)

    obj = s.generate_json("extract", Extraction, seed=0)

    assert obj.text == "User likes coffee"


# ----------------- Fallback config flip ----------------- #


def test_config_loads_primary_and_fallback_revisions(tmp_path: Path) -> None:
    config_path = tmp_path / "inference.yaml"
    config_path.write_text(
        "\n".join(
            [
                "model_id: primary",
                "model_revision: primary-sha",
                "fallback_model_id: fallback",
                "fallback_model_revision: fallback-sha",
            ]
        ),
        encoding="utf-8",
    )

    config = load_inference_config(config_path)

    assert config.model_revision == "primary-sha"
    assert config.fallback_model_revision == "fallback-sha"


def test_fallback_flag_swaps_model_id_and_nothing_else() -> None:
    cfg = InferenceConfig(
        model_id="meta-llama/Meta-Llama-3-8B-Instruct",
        fallback_model_id="Qwen/Qwen2.5-7B-Instruct",
        dtype="bfloat16",
        device_map="auto",
    )
    primary = build_llm(cfg)
    fallback = build_llm(cfg, use_fallback=True)
    assert primary.model_id == "meta-llama/Meta-Llama-3-8B-Instruct"
    assert fallback.model_id == "Qwen/Qwen2.5-7B-Instruct"
    # All other config fields preserved.
    assert primary.config.dtype == fallback.config.dtype  # type: ignore[attr-defined]
    assert primary.config.device_map == fallback.config.device_map  # type: ignore[attr-defined]


def test_fallback_propagates_its_own_revision() -> None:
    cfg = InferenceConfig(
        model_id="primary",
        model_revision="primary-sha",
        fallback_model_id="fallback",
        fallback_model_revision="fallback-sha",
    )
    fallback = build_llm(cfg, use_fallback=True)
    assert fallback.config.model_revision == "fallback-sha"  # type: ignore[attr-defined]


def test_build_llm_raises_on_missing_fallback() -> None:
    cfg = InferenceConfig(model_id="x/y", fallback_model_id=None)
    with pytest.raises(ValueError):
        build_llm(cfg, use_fallback=True)


# ----------------- HuggingFaceLLM (smoke; no model download) -------- #


def test_huggingface_llm_construction_does_not_load_weights() -> None:
    """Construction is cheap; weights are loaded only on first generate()."""
    from ask.inference.llm import HuggingFaceLLM

    cfg = InferenceConfig(model_id="meta-llama/Meta-Llama-3-8B-Instruct", max_seq_len=6144)
    h = HuggingFaceLLM(cfg)
    assert h.model_id == "meta-llama/Meta-Llama-3-8B-Instruct"
    assert h.num_ctx == 6144
    # Internal handles must be None until generate() runs.
    assert h._tokenizer is None
    assert h._model is None


def test_huggingface_loader_propagates_exact_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ask.inference import llm as llm_module
    from ask.inference.llm import HuggingFaceLLM

    observed: dict[str, dict[str, object]] = {}

    class _Tokenizer:
        pad_token_id = 1

    class _Model:
        def eval(self) -> None:
            return None

    class _TokenizerFactory:
        @staticmethod
        def from_pretrained(model_id: str, **kwargs: object) -> _Tokenizer:
            observed["tokenizer"] = {"model_id": model_id, **kwargs}
            return _Tokenizer()

    class _ModelFactory:
        @staticmethod
        def from_pretrained(model_id: str, **kwargs: object) -> _Model:
            observed["model"] = {"model_id": model_id, **kwargs}
            return _Model()

    torch_module = ModuleType("torch")
    torch_module.bfloat16 = SimpleNamespace()  # type: ignore[attr-defined]
    torch_module.float16 = SimpleNamespace()  # type: ignore[attr-defined]
    torch_module.float32 = SimpleNamespace()  # type: ignore[attr-defined]
    transformers_module = ModuleType("transformers")
    transformers_module.AutoTokenizer = _TokenizerFactory  # type: ignore[attr-defined]
    transformers_module.AutoModelForCausalLM = _ModelFactory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", torch_module)
    monkeypatch.setitem(sys.modules, "transformers", transformers_module)
    llm_module._HF_MODEL_CACHE.clear()

    llm = HuggingFaceLLM(
        InferenceConfig(model_id="model", model_revision="commit-sha", dtype="float32")
    )
    llm._ensure_loaded()

    assert observed["tokenizer"]["revision"] == "commit-sha"
    assert observed["model"]["revision"] == "commit-sha"
