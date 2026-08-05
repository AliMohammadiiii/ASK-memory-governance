"""Tests for the turn-level embedder (M1-W3 §3.1).

Three contracts:
  1. Output shape and dtype — `(n, dim)` float32, regardless of how the
     underlying model returns its tensors.
  2. L2-normalization — every row's norm equals 1.0 within float32
     tolerance. This is what makes FAISS inner-product = cosine similarity
     in `FlatVectorStore`.
  3. Determinism — same input → identical embedding vectors across calls
     within one process.

The test suite uses `FakeEmbedder` (sha256-based hashing) so it does not
pull torch / sentence-transformers. The `TurnEmbedder` is exercised only
by smoke tests that skip if `sentence_transformers` is not importable —
mirroring how Week 2 tests handle the optional `[ml]` deps.
"""

from __future__ import annotations

import importlib.util
import json
import os
import urllib.request

import numpy as np
import pytest

from ask.baselines.embeddings import (
    Embedder,
    FakeEmbedder,
    OllamaEmbedder,
    OpenAICompatibleEmbedder,
    TurnEmbedder,
    _resolve_sentence_transformer_device,
    role_tag,
)

# --------------------------------------------------------------------- #
# §3.1 contract tests, run against FakeEmbedder (hermetic)               #
# --------------------------------------------------------------------- #


def test_fake_embedder_output_shape_and_dtype() -> None:
    e = FakeEmbedder(embedding_dim=64)
    out = e.embed(["alpha", "beta", "gamma"])
    assert out.shape == (3, 64)
    assert out.dtype == np.float32


def test_fake_embedder_rows_are_l2_normalized() -> None:
    """Cosine via IP requires unit-norm rows. Any drift here breaks retrieval."""
    e = FakeEmbedder(embedding_dim=32)
    out = e.embed(["hello world", "the quick brown fox", "a"])
    norms = np.linalg.norm(out, axis=1)
    # float32 tolerance.
    assert np.allclose(norms, 1.0, atol=1e-6), f"got norms {norms}"


def test_fake_embedder_empty_input_returns_empty_array() -> None:
    """Empty input is a degenerate path the FlatVectorBaseline relies on."""
    e = FakeEmbedder(embedding_dim=16)
    out = e.embed([])
    assert out.shape == (0, 16)
    assert out.dtype == np.float32


def test_fake_embedder_determinism() -> None:
    """Same string → identical vector on repeat calls."""
    e = FakeEmbedder(embedding_dim=32)
    a = e.embed(["I prefer coffee in the morning."])
    b = e.embed(["I prefer coffee in the morning."])
    assert np.array_equal(a, b)


def test_fake_embedder_different_strings_yield_different_vectors() -> None:
    """Sufficient discrimination for 'search for own text returns self' tests."""
    e = FakeEmbedder(embedding_dim=32)
    out = e.embed(["I prefer coffee", "I prefer tea"])
    # Cosine similarity between two essentially-random unit vectors should
    # be far from 1.0; we use 0.99 as an extremely permissive ceiling.
    sim = float(out[0] @ out[1])
    assert abs(sim) < 0.99


def test_fake_embedder_satisfies_embedder_protocol() -> None:
    """Runtime-check the Protocol contract on the test stub."""
    assert isinstance(FakeEmbedder(), Embedder)


def test_ollama_embedder_uses_api_embed_and_normalizes(monkeypatch) -> None:
    calls = []

    class _Response:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(req, timeout):  # noqa: ANN001
        payload = json.loads(req.data.decode("utf-8"))
        calls.append((req.full_url, timeout, payload))
        rows = len(payload["input"])
        return _Response({"embeddings": [[float(i + 1), 0.0, 0.0] for i in range(rows)]})

    monkeypatch.setattr("ask.baselines.embeddings.urllib.request.urlopen", fake_urlopen)

    e = OllamaEmbedder(
        model_id="llama3.2:3b",
        host="http://ollama.test",
        allow_insecure_http=True,
        timeout_s=12.0,
        batch_size=2,
    )
    out = e.embed(["alpha", "beta", "gamma"])

    assert out.shape == (3, 3)
    assert out.dtype == np.float32
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-6)
    assert e.embedding_dim == 3
    assert [call[0] for call in calls] == [
        "http://ollama.test/api/embed",
        "http://ollama.test/api/embed",
    ]
    assert calls[0][1] == 12.0
    assert calls[0][2]["model"] == "llama3.2:3b"
    assert calls[0][2]["input"] == ["alpha", "beta"]


def test_openai_compatible_embedder_uses_v1_embeddings_and_normalizes(
    monkeypatch, tmp_path
) -> None:
    calls = []

    class _Response:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(req, timeout):  # noqa: ANN001
        payload = json.loads(req.data.decode("utf-8"))
        calls.append((req.full_url, timeout, req.headers, payload))
        data = [
            {"index": i, "embedding": [float(i + 1), 0.0, 0.0]}
            for i in range(len(payload["input"]))
        ]
        return _Response({"model": "auto", "data": data})

    monkeypatch.setattr("ask.baselines.embeddings.urllib.request.urlopen", fake_urlopen)

    e = OpenAICompatibleEmbedder(
        model_id="auto",
        base_url="http://freellmapi.test/v1",
        allow_insecure_http=True,
        api_key="key",
        timeout_s=9.0,
        batch_size=2,
        log_path=str(tmp_path / "embedding_calls.jsonl"),
    )
    out = e.embed(["alpha", "beta", "gamma"])

    assert out.shape == (3, 3)
    assert out.dtype == np.float32
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-6)
    assert e.embedding_dim == 3
    assert [call[0] for call in calls] == [
        "http://freellmapi.test/v1/embeddings",
        "http://freellmapi.test/v1/embeddings",
    ]
    assert calls[0][1] == 9.0
    assert calls[0][2]["Authorization"] == "Bearer key"
    assert calls[0][3]["model"] == "auto"
    assert calls[0][3]["input"] == ["alpha", "beta"]

    rows = [
        json.loads(line) for line in (tmp_path / "embedding_calls.jsonl").read_text().splitlines()
    ]
    assert rows[0]["n_texts"] == 2
    assert rows[0]["embedding_dim"] == 3


def test_openai_compatible_embedder_uses_modal_headers_from_env(monkeypatch) -> None:
    monkeypatch.setenv("MODAL_KEY", "modal-key")
    monkeypatch.setenv("MODAL_SECRET", "modal-secret")
    monkeypatch.delenv("FREELLMAPI_KEY", raising=False)
    calls = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> None:
            return None

        def read(self) -> bytes:
            payload = {"model": "auto", "data": [{"index": 0, "embedding": [1.0, 0.0]}]}
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(req, timeout):  # noqa: ANN001, ARG001
        calls.append(req.headers)
        return _Response()

    monkeypatch.setattr("ask.baselines.embeddings.urllib.request.urlopen", fake_urlopen)

    e = OpenAICompatibleEmbedder(
        model_id="auto",
        base_url="https://example.modal.direct/v1",
    )
    out = e.embed(["alpha"])

    assert out.shape == (1, 2)
    assert calls[0]["Modal-key"] == "modal-key"
    assert calls[0]["Modal-secret"] == "modal-secret"
    assert calls[0]["Authorization"] == "Bearer dummy"


def test_openai_compatible_embedder_splits_by_batch_chars(monkeypatch) -> None:
    calls = []

    class _Response:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(req, timeout):  # noqa: ANN001, ARG001
        payload = json.loads(req.data.decode("utf-8"))
        calls.append(payload["input"])
        data = [
            {"index": i, "embedding": [float(i + 1), 0.0, 0.0]}
            for i in range(len(payload["input"]))
        ]
        return _Response({"model": "bge-m3", "data": data})

    monkeypatch.setattr("ask.baselines.embeddings.urllib.request.urlopen", fake_urlopen)

    e = OpenAICompatibleEmbedder(
        model_id="bge-m3",
        base_url="http://freellmapi.test/v1",
        allow_insecure_http=True,
        api_key="key",
        batch_size=10,
        max_batch_chars=4,
    )
    e.embed(["aa", "bbbb", "cc"])

    assert calls == [["aa"], ["bbbb"], ["cc"]]


def test_openai_compatible_embedder_bypasses_proxy_for_loopback(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> None:
            return None

        def read(self) -> bytes:
            payload = {
                "model": "minilm",
                "data": [{"index": 0, "embedding": [1.0, 0.0]}],
            }
            return json.dumps(payload).encode("utf-8")

    class _ProxylessOpener:
        def open(self, req, timeout):  # noqa: ANN001
            calls["url"] = req.full_url
            calls["timeout"] = timeout
            return _Response()

    def fake_build_opener(handler):  # noqa: ANN001
        calls["handler"] = handler
        return _ProxylessOpener()

    def forbidden_urlopen(*_args, **_kwargs):
        raise AssertionError("loopback request used the system-proxy opener")

    monkeypatch.setattr("ask.baselines.embeddings.urllib.request.build_opener", fake_build_opener)
    monkeypatch.setattr("ask.baselines.embeddings.urllib.request.urlopen", forbidden_urlopen)

    e = OpenAICompatibleEmbedder(
        model_id="minilm",
        base_url="http://127.0.0.1:8100/v1",
        timeout_s=7.0,
    )
    out = e.embed(["alpha"])

    assert out.shape == (1, 2)
    assert calls["url"] == "http://127.0.0.1:8100/v1/embeddings"
    assert calls["timeout"] == 7.0
    handler = calls["handler"]
    assert isinstance(handler, urllib.request.ProxyHandler)
    assert handler.proxies == {}


# --------------------------------------------------------------------- #
# Role-tag helper                                                        #
# --------------------------------------------------------------------- #


def test_role_tag_user_and_assistant_have_distinct_prefixes() -> None:
    u = role_tag("user", "I like coffee.")
    a = role_tag("assistant", "Noted.")
    assert u.startswith("[USER] ")
    assert a.startswith("[ASSISTANT] ")
    assert "I like coffee." in u
    assert "Noted." in a


def test_role_tag_is_case_insensitive_on_role() -> None:
    """The data loader normalizes to lower-case but defensive to be safe."""
    a = role_tag("USER", "x")
    b = role_tag("user", "x")
    assert a == b


def test_role_tag_unknown_role_uppercases_defensively() -> None:
    out = role_tag("system", "hi")
    assert out.startswith("[SYSTEM] ")


# --------------------------------------------------------------------- #
# TurnEmbedder — smoke tests (skip if sentence-transformers absent)      #
# --------------------------------------------------------------------- #


_HAS_ST = importlib.util.find_spec("sentence_transformers") is not None

# Gate the MiniLM smoke tests behind an env var. They are valuable but
# fragile: on Apple Silicon, running BERT forward passes inside pytest's
# threaded harness can segfault due to libomp double-loading (torch +
# faiss-cpu each bring their own OpenMP). The hermetic FakeEmbedder
# tests above already cover the L2-norm / shape / determinism / Protocol
# contract; the smoke tests below verify the contract holds with the
# REAL MiniLM weights.
#
# To run them on the host:
#   ASK_RUN_MINILM_SMOKE=1 OMP_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
#       PYTHONPATH=src pytest tests/test_embeddings.py -k minilm
_RUN_MINILM_SMOKE = os.environ.get("ASK_RUN_MINILM_SMOKE", "0") == "1"
_SKIP_REASON_MINILM = (
    "MiniLM smoke tests are gated by ASK_RUN_MINILM_SMOKE=1 "
    "(default off — Apple-Silicon libomp segfault risk; see test_embeddings.py)"
)


def test_turn_embedder_known_dim_resolves_without_load() -> None:
    """The 384-dim of all-MiniLM-L6-v2 is queryable without paying the load.

    This is what lets `FlatVectorStore.__init__` pre-size the FAISS index.
    """
    e = TurnEmbedder(model_id="sentence-transformers/all-MiniLM-L6-v2")
    assert e.embedding_dim == 384
    # Crucially: no model has been loaded yet (we did not call .embed()).
    assert e._model is None  # noqa: SLF001 — explicit invariant


def test_turn_embedder_default_model_is_minilm() -> None:
    """Pinning the default. A bump must come with a tag bump per pyproject."""
    e = TurnEmbedder()
    assert e.model_id == "sentence-transformers/all-MiniLM-L6-v2"
    assert e.embedding_dim == 384


def test_sentence_transformer_auto_device_uses_cuda_when_available(monkeypatch) -> None:
    monkeypatch.setattr("ask.baselines.embeddings._torch_cuda_is_available", lambda: True)

    assert _resolve_sentence_transformer_device("auto") == "cuda"


def test_sentence_transformer_cuda_device_falls_back_to_cpu(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("ask.baselines.embeddings._torch_cuda_is_available", lambda: False)

    assert _resolve_sentence_transformer_device("cuda") == "cpu"
    assert "falling back to CPU" in capsys.readouterr().out


@pytest.mark.skipif(not _HAS_ST, reason="sentence-transformers not installed")
@pytest.mark.skipif(not _RUN_MINILM_SMOKE, reason=_SKIP_REASON_MINILM)
def test_turn_embedder_real_minilm_smoke() -> None:
    """Smoke test against the actual MiniLM weights when available.

    Verifies the contract is honored end-to-end:
      * shape (n, 384), dtype float32
      * row norms ≈ 1.0
      * deterministic across two embed() calls in one process
    """
    e = TurnEmbedder(device="cpu", batch_size=4)
    texts = [
        role_tag("user", "I prefer coffee in the morning."),
        role_tag("assistant", "Noted — I will remember that."),
    ]
    out1 = e.embed(texts)
    assert out1.shape == (2, 384)
    assert out1.dtype == np.float32
    norms = np.linalg.norm(out1, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-6)
    # Determinism across calls.
    out2 = e.embed(texts)
    assert np.allclose(out1, out2, atol=1e-6)


@pytest.mark.skipif(not _HAS_ST, reason="sentence-transformers not installed")
@pytest.mark.skipif(not _RUN_MINILM_SMOKE, reason=_SKIP_REASON_MINILM)
def test_turn_embedder_satisfies_protocol_after_load() -> None:
    e = TurnEmbedder(device="cpu", batch_size=4)
    # touch the model so embedding_dim is fully resolved
    _ = e.embed([role_tag("user", "hi")])
    assert isinstance(e, Embedder)
