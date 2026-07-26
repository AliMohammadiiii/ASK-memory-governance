"""OllamaLLM contract tests (no network).

Verifies that:
  - OllamaLLM satisfies the LLM Protocol,
  - the request payload it would send matches the Ollama /api/generate spec,
  - failures surface as RuntimeError with a helpful hint.

Live integration is exercised by the smoke script with `--ollama` against the
user's local daemon (e.g. `gemma3:4b`).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from ask.inference.llm import LLM, InferenceConfig, build_llm
from ask.inference.ollama import OllamaLLM


def test_ollama_satisfies_llm_protocol() -> None:
    o = OllamaLLM(model_id="gemma3:4b")
    assert isinstance(o, LLM)
    assert o.model_id == "gemma3:4b"


def test_build_llm_dispatches_to_ollama_backend() -> None:
    cfg = InferenceConfig(
        model_id="gemma3:4b",
        backend="ollama",
        ollama_host="http://localhost:11434",
    )
    llm = build_llm(cfg)
    assert isinstance(llm, OllamaLLM)
    assert llm.model_id == "gemma3:4b"
    assert llm.host == "http://localhost:11434"


def test_build_llm_rejects_unknown_backend() -> None:
    cfg = InferenceConfig(model_id="x", backend="not-a-real-backend")
    with pytest.raises(ValueError):
        build_llm(cfg)


def test_ollama_chat_mode_sends_messages_and_parses_response() -> None:
    """Default chat=True: /api/chat with messages list, parses message.content."""
    o = OllamaLLM(model_id="gemma3:4b", system="You are precise.")

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(
        {
            "message": {"role": "assistant", "content": "coffee"},
            "prompt_eval_count": 12,
            "eval_count": 1,
        }
    ).encode("utf-8")
    fake_response.__enter__ = lambda self: self
    fake_response.__exit__ = lambda self, *a: None

    with patch("urllib.request.urlopen", return_value=fake_response) as mock_urlopen:
        resp = o.generate(
            "What does the user like?",
            max_new_tokens=64,
            temperature=0.0,
            seed=42,
            stop=["\n\n"],
        )

    req = mock_urlopen.call_args.args[0]
    assert req.full_url == "http://localhost:11434/api/chat"
    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "gemma3:4b"
    assert body["stream"] is False
    assert body["messages"] == [
        {"role": "system", "content": "You are precise."},
        {"role": "user", "content": "What does the user like?"},
    ]
    assert body["options"]["temperature"] == 0.0
    assert body["options"]["seed"] == 42
    assert body["options"]["num_predict"] == 64
    assert body["options"]["stop"] == ["\n\n"]
    # M1-W2 hotfix: num_ctx halved from Ollama's 4096 default to ease KV-cache
    # memory pressure on 8 GB Macs. The no-memory baseline never approaches
    # 2048 prompt tokens.
    assert body["options"]["num_ctx"] == 2048
    # M1-W2 hotfix: keep_alive bumped to 30m so the model stays resident
    # across the 50-session loop instead of being re-loaded between calls.
    assert body["keep_alive"] == "30m"

    assert resp.text == "coffee"
    assert resp.prompt_tokens == 12
    assert resp.completion_tokens == 1
    assert resp.model_id == "gemma3:4b"


def test_ollama_chat_mode_can_disable_thinking() -> None:
    """Reasoning-capable Ollama models should support think=false."""
    o = OllamaLLM(model_id="qwen3.5:9b", think=False)

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(
        {"message": {"role": "assistant", "content": "final"}, "eval_count": 1}
    ).encode("utf-8")
    fake_response.__enter__ = lambda self: self
    fake_response.__exit__ = lambda self, *a: None

    with patch("urllib.request.urlopen", return_value=fake_response) as mock_urlopen:
        resp = o.generate("Answer briefly.", max_new_tokens=8)

    body = json.loads(mock_urlopen.call_args.args[0].data.decode("utf-8"))
    assert body["think"] is False
    assert resp.text == "final"


def test_ollama_completion_mode_sends_to_generate_endpoint() -> None:
    """chat=False: /api/generate with raw prompt, parses response field."""
    o = OllamaLLM(model_id="gemma3:4b", chat=False)

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(
        {"response": "coffee", "prompt_eval_count": 12, "eval_count": 1}
    ).encode("utf-8")
    fake_response.__enter__ = lambda self: self
    fake_response.__exit__ = lambda self, *a: None

    with patch("urllib.request.urlopen", return_value=fake_response) as mock_urlopen:
        resp = o.generate("p", max_new_tokens=8, seed=0)

    req = mock_urlopen.call_args.args[0]
    assert req.full_url == "http://localhost:11434/api/generate"
    body = json.loads(req.data.decode("utf-8"))
    assert "prompt" in body and "messages" not in body
    assert resp.text == "coffee"


def test_ollama_unreachable_raises_helpful_message() -> None:
    """Pointing at a closed port should raise RuntimeError with `ollama serve` hint."""
    # Port 1 is reserved + nothing listens there; a connect() will fail fast.
    # max_retries=0 so the test isn't slowed by the retry backoff.
    o = OllamaLLM(model_id="gemma3:4b", host="http://127.0.0.1:1", timeout_s=2.0, max_retries=0)
    with pytest.raises(RuntimeError) as excinfo:
        o.generate("hi", max_new_tokens=4)
    assert "ollama" in str(excinfo.value).lower()


def test_ollama_retries_on_transient_502_then_succeeds() -> None:
    """Cold-start /api/chat 502 → retry → 200 should not bubble an error.

    Regression for the M1-W2 finalize 502 (Ollama runner cold-start window).
    """
    import urllib.error

    o = OllamaLLM(model_id="gemma4:e4b", max_retries=2, backoff_s=0.0)

    # First call: 502. Second call: 200.
    success = MagicMock()
    success.read.return_value = json.dumps(
        {
            "message": {"role": "assistant", "content": "ok"},
            "prompt_eval_count": 3,
            "eval_count": 1,
        }
    ).encode("utf-8")
    success.__enter__ = lambda self: self
    success.__exit__ = lambda self, *a: None

    err = urllib.error.HTTPError(
        url="http://localhost:11434/api/chat",
        code=502,
        msg="Bad Gateway",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=[err, success]) as mock_urlopen:
        resp = o.generate("hi", max_new_tokens=8)

    assert mock_urlopen.call_count == 2
    assert resp.text == "ok"


def test_ollama_does_not_retry_on_4xx() -> None:
    """A 404 (e.g. unknown model tag) is a user error — fail fast, do not retry."""
    import urllib.error

    o = OllamaLLM(model_id="not-a-real-model", max_retries=3, backoff_s=0.0)
    err = urllib.error.HTTPError(
        url="http://localhost:11434/api/chat",
        code=404,
        msg="Not Found",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=err) as mock_urlopen:
        with pytest.raises(RuntimeError):
            o.generate("hi", max_new_tokens=8)
    # Exactly one call — no retries on 4xx.
    assert mock_urlopen.call_count == 1


def test_ollama_gives_up_after_max_retries_on_persistent_502() -> None:
    """If 502 never clears, surface a single useful RuntimeError."""
    import urllib.error

    o = OllamaLLM(model_id="gemma4:e4b", max_retries=2, backoff_s=0.0)
    err = urllib.error.HTTPError(
        url="http://localhost:11434/api/chat",
        code=502,
        msg="Bad Gateway",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=err) as mock_urlopen:
        with pytest.raises(RuntimeError) as excinfo:
            o.generate("hi", max_new_tokens=8)

    # 1 initial + 2 retries = 3 total.
    assert mock_urlopen.call_count == 3
    msg = str(excinfo.value).lower()
    assert "ollama" in msg
    # The error message must include the curl ping suggestion so the user
    # has a self-service diagnostic.
    assert "curl" in msg or "api/chat" in msg


def test_ollama_default_retry_budget_survives_runner_restart() -> None:
    """M1-W2 hotfix: default budget (5 retries × backoff 2s) ≥ 60s.

    A cold-start runner restart on a memory-constrained Mac can take 30-60s.
    The retry budget must cover that without bubbling an error.
    """
    o = OllamaLLM(model_id="gemma4:e4b")
    # 5 retries with backoff_s=2 → 2 + 4 + 8 + 16 + 32 = 62s budget.
    assert o.max_retries >= 5
    # Compute the worst-case wait this contract promises.
    worst_case = sum(o.backoff_s * (2**i) for i in range(o.max_retries))
    assert worst_case >= 60.0, (
        f"retry budget {worst_case:.1f}s < 60s; "
        "Ollama runner restarts can take that long on memory-constrained Macs."
    )


def test_ollama_num_ctx_can_be_disabled_to_use_server_default() -> None:
    """num_ctx=None opts out — useful if a future baseline needs the full 4096."""
    o = OllamaLLM(model_id="gemma3:4b", num_ctx=None)

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(
        {"message": {"role": "assistant", "content": "ok"}, "prompt_eval_count": 1, "eval_count": 1}
    ).encode("utf-8")
    fake_response.__enter__ = lambda self: self
    fake_response.__exit__ = lambda self, *a: None

    with patch("urllib.request.urlopen", return_value=fake_response) as mock_urlopen:
        o.generate("hi", max_new_tokens=8)

    body = json.loads(mock_urlopen.call_args.args[0].data.decode("utf-8"))
    assert "num_ctx" not in body["options"]


def test_ollama_warns_when_prompt_fills_context(capsys) -> None:
    """Regression: a prompt that fills num_ctx leaves no room to generate and
    Ollama returns a single token. The wrapper must warn loudly so this silent
    failure (every answer truncated to one token) is caught immediately."""
    o = OllamaLLM(model_id="qwen3.5:9b", num_ctx=2048)

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(
        {
            "message": {"role": "assistant", "content": "9"},
            "prompt_eval_count": 2047,
            "eval_count": 1,
        }
    ).encode("utf-8")
    fake_response.__enter__ = lambda self: self
    fake_response.__exit__ = lambda self, *a: None

    with patch("urllib.request.urlopen", return_value=fake_response):
        resp = o.generate("huge prompt", max_new_tokens=512, temperature=0.0, seed=0)

    assert resp.completion_tokens == 1
    out = capsys.readouterr().out
    assert "num_ctx" in out and "truncated" in out


def test_ollama_no_truncation_warning_on_healthy_generation(capsys) -> None:
    o = OllamaLLM(model_id="qwen3.5:9b", num_ctx=8192)

    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(
        {
            "message": {"role": "assistant", "content": "9 months"},
            "prompt_eval_count": 2100,
            "eval_count": 3,
        }
    ).encode("utf-8")
    fake_response.__enter__ = lambda self: self
    fake_response.__exit__ = lambda self, *a: None

    with patch("urllib.request.urlopen", return_value=fake_response):
        o.generate("normal prompt", max_new_tokens=512, temperature=0.0, seed=0)

    assert "WARNING" not in capsys.readouterr().out
