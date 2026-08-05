"""Regression tests for the Qwen3.5 (thinking-off) + Jina-v5 embedder support.

These are hermetic: they exercise the pure helpers, the config flag, and the
embedder field plumbing without loading any model weights.
"""

from __future__ import annotations

import ask.baselines.embeddings as embeddings_module
from ask.baselines.embeddings import Embedder, FakeEmbedder, TurnEmbedder
from ask.inference.llm import InferenceConfig, _strip_think_blocks


def test_strip_think_block_removes_reasoning_keeps_answer() -> None:
    assert _strip_think_blocks("<think>chain of thought</think>Paris") == "Paris"
    assert _strip_think_blocks("<think>a</think>  $400,000 ") == "$400,000"


def test_strip_think_is_noop_without_tags() -> None:
    assert _strip_think_blocks("no tags here") == "no tags here"
    assert _strip_think_blocks("3") == "3"  # a real one-char answer survives


def test_strip_think_handles_unbalanced_tags() -> None:
    # Budget ran out inside the think block -> nothing usable remains.
    assert _strip_think_blocks("<think>still reasoning, cut off") == ""
    # Stray closing tag -> keep only what follows it.
    assert _strip_think_blocks("leftover</think>Final Answer") == "Final Answer"


def test_inference_config_enable_thinking_default_and_set() -> None:
    assert InferenceConfig(model_id="x").enable_thinking is None
    assert InferenceConfig(model_id="x", enable_thinking=False).enable_thinking is False
    assert InferenceConfig(model_id="x", enable_thinking=True).enable_thinking is True


def test_turn_embedder_accepts_jina_fields_without_loading() -> None:
    emb = TurnEmbedder(
        model_id="jinaai/jina-embeddings-v5-text-small",
        revision="a" * 40,
        device="cpu",
        trust_remote_code=True,
        task="retrieval",
        prompt_name="document",
    )
    assert emb.trust_remote_code is True
    assert emb.revision == "a" * 40
    assert emb.task == "retrieval"
    assert emb.prompt_name == "document"
    # Default still satisfies the Embedder protocol contract.
    assert isinstance(FakeEmbedder(), Embedder)


def test_turn_embedder_defaults_are_backward_compatible() -> None:
    emb = TurnEmbedder()
    assert emb.trust_remote_code is False
    assert emb.revision is None
    assert emb.task is None
    assert emb.prompt_name is None


def test_turn_embedder_forwards_immutable_revision(monkeypatch) -> None:
    captured = {}

    def fake_loader(model_id, device, revision, trust_remote_code):  # noqa: ANN001
        captured.update(
            model_id=model_id,
            device=device,
            revision=revision,
            trust_remote_code=trust_remote_code,
        )
        return object()

    monkeypatch.setattr(embeddings_module, "_get_or_load_model", fake_loader)
    revision = "b" * 40
    emb = TurnEmbedder(model_id="example/embedder", revision=revision, device="cpu")

    emb._ensure_loaded()

    assert captured == {
        "model_id": "example/embedder",
        "device": "cpu",
        "revision": revision,
        "trust_remote_code": False,
    }


def test_embedding_dim_probes_when_accessor_unusable() -> None:
    """jina-v5 returns None from get_sentence_embedding_dimension and requires
    `task` at encode time; the dim must be recovered by a task-aware probe."""
    import numpy as np

    class _FakeJina:
        def get_sentence_embedding_dimension(self):  # unusable, like jina v5
            return None

        def encode(self, texts, **kw):
            if "task" not in kw:
                raise ValueError("Task must be specified before encoding data.")
            return np.random.rand(len(texts), 1024).astype("float32")

    emb = TurnEmbedder(
        model_id="jinaai/jina-embeddings-v5-text-small",
        device="cpu",
        trust_remote_code=True,
        task="retrieval",
    )
    emb._model = _FakeJina()  # inject, skip real load
    assert emb.embedding_dim == 1024
    out = emb.embed(["hello world"])
    assert out.shape == (1, 1024)
    assert abs(float(np.linalg.norm(out[0])) - 1.0) < 1e-4
