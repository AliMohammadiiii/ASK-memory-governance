"""OpenAI-compatible LLM backend contract tests."""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from ask.inference.llm import InferenceConfig, build_llm
from ask.inference.openai_compatible import (
    OpenAICompatibleFatalError,
    OpenAICompatibleLLM,
    _retry_after_from_body,
)


def _response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *a: None
    return resp


def _chat(text: str, *, model: str = "cogito-2.1:671b") -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        "_routed_via": {"platform": "ollama", "model": model},
    }


def _http_error(code: int, body: str = "temporary failure") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="http://localhost:3001/v1/chat/completions",
        code=code,
        msg="error",
        hdrs={},
        fp=io.BytesIO(body.encode("utf-8")),
    )


def test_openai_compatible_sends_chat_completion_and_logs_metadata(tmp_path, capsys) -> None:
    llm = OpenAICompatibleLLM(
        model_id="cogito-2.1:671b",
        base_url="http://localhost:3001/v1",
        api_key="key",
        require_json=True,
        response_format={"type": "json_object"},
        log_path=tmp_path / "calls.jsonl",
    )

    with patch("urllib.request.urlopen", return_value=_response(_chat('{"answer": "ok"}'))) as mock:
        resp = llm.generate("Return JSON.", max_new_tokens=32, seed=4)

    req = mock.call_args.args[0]
    assert req.full_url == "http://localhost:3001/v1/chat/completions"
    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "cogito-2.1:671b"
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == 32
    assert body["seed"] == 4

    assert resp.text == '{"answer": "ok"}'
    assert resp.model_id == "cogito-2.1:671b"
    assert resp.metadata["valid_json"] is True
    assert resp.metadata["schema_pass"] is True
    assert resp.metadata["task_pass"] is True
    assert "raw_response_hash" in resp.metadata
    assert "raw_response" not in resp.metadata

    rows = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["valid_json"] is True
    assert rows[0]["fallback_used"] is False
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_openai_compatible_uses_modal_headers_from_env(monkeypatch) -> None:
    monkeypatch.setenv("MODAL_KEY", "modal-key")
    monkeypatch.setenv("MODAL_SECRET", "modal-secret")
    monkeypatch.delenv("FREELLMAPI_KEY", raising=False)
    llm = OpenAICompatibleLLM(
        model_id="Qwen/Qwen3.5-9B",
        base_url="https://example.modal.direct/v1",
        chat_template_kwargs={"enable_thinking": False},
    )

    with patch("urllib.request.urlopen", return_value=_response(_chat("modal ok"))) as mock:
        resp = llm.generate("Say only: modal ok", max_new_tokens=64, temperature=0)

    req = mock.call_args.args[0]
    body = json.loads(req.data.decode("utf-8"))
    assert req.full_url == "https://example.modal.direct/v1/chat/completions"
    assert req.headers["Modal-key"] == "modal-key"
    assert req.headers["Modal-secret"] == "modal-secret"
    assert req.headers["Authorization"] == "Bearer dummy"
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert resp.text == "modal ok"


def test_openai_compatible_retries_transient_429() -> None:
    llm = OpenAICompatibleLLM(
        model_id="busy-model",
        base_url="http://localhost:3001/v1",
        api_key="key",
        retry_max_attempts=2,
        retry_initial_delay_s=0,
    )

    with patch(
        "urllib.request.urlopen",
        side_effect=[
            _http_error(429),
            _response(_chat("ok", model="busy-model")),
        ],
    ) as mock:
        resp = llm.generate("Say ok.")

    assert mock.call_count == 2
    assert resp.text == "ok"
    assert resp.metadata["requested_model"] == "busy-model"
    assert resp.metadata["fallback_used"] is False


def test_openai_compatible_retries_error_envelope_returned_with_http_200() -> None:
    """OpenRouter can tunnel a provider 504 inside an HTTP-200 JSON body."""
    llm = OpenAICompatibleLLM(
        model_id="busy-model",
        base_url="http://localhost:3001/v1",
        api_key="key",
        retry_max_attempts=2,
        retry_initial_delay_s=0,
    )
    embedded_error = {
        "error": {
            "code": 504,
            "message": "Provider returned an error",
            "metadata": {"provider_name": "upstream"},
        }
    }

    with patch(
        "urllib.request.urlopen",
        side_effect=[
            _response(embedded_error),
            _response(_chat("ok", model="busy-model")),
        ],
    ) as mock:
        resp = llm.generate("Say ok.")

    assert mock.call_count == 2
    assert resp.text == "ok"
    assert resp.metadata["fallback_used"] is False


def test_openai_compatible_reads_retry_after_from_openrouter_error_body() -> None:
    body = json.dumps(
        {
            "error": {
                "metadata": {
                    "provider_name": "Venice",
                    "retry_after_seconds": 7,
                    "retry_after_seconds_raw": 6.756,
                }
            }
        }
    )

    assert _retry_after_from_body(body) == "7"


def test_openai_compatible_falls_back_after_transient_retries_exhausted() -> None:
    llm = OpenAICompatibleLLM(
        model_id="busy-model",
        fallback_model_ids=("backup-model",),
        base_url="http://localhost:3001/v1",
        api_key="key",
        retry_max_attempts=2,
        retry_initial_delay_s=0,
    )

    with patch(
        "urllib.request.urlopen",
        side_effect=[
            _http_error(429),
            _http_error(429),
            _response(_chat("backup ok", model="backup-model")),
        ],
    ) as mock:
        resp = llm.generate("Say ok.")

    assert mock.call_count == 3
    assert resp.text == "backup ok"
    assert resp.metadata["requested_model"] == "backup-model"
    assert resp.metadata["fallback_used"] is True


def test_openai_compatible_does_not_retry_or_fallback_after_credit_402() -> None:
    llm = OpenAICompatibleLLM(
        model_id="primary-model",
        fallback_model_ids=("backup-model",),
        base_url="http://localhost:3001/v1",
        api_key="key",
        retry_max_attempts=5,
        retry_initial_delay_s=0,
    )

    with patch(
        "urllib.request.urlopen", side_effect=_http_error(402, "Insufficient credits")
    ) as mock:
        with pytest.raises(OpenAICompatibleFatalError, match="HTTP 402"):
            llm.generate("Say ok.")

    assert mock.call_count == 1


def test_openai_compatible_falls_back_when_json_gate_fails() -> None:
    llm = OpenAICompatibleLLM(
        model_id="bad-json",
        fallback_model_ids=("good-json",),
        base_url="http://localhost:3001/v1",
        api_key="key",
        require_json=True,
        response_format="json",
    )

    with patch(
        "urllib.request.urlopen",
        side_effect=[
            _response(_chat("prose only", model="bad-json")),
            _response(_chat('{"answer": "ok"}', model="good-json")),
        ],
    ):
        resp = llm.generate("Return JSON.")

    assert resp.text == '{"answer": "ok"}'
    assert resp.metadata["requested_model"] == "good-json"
    assert resp.metadata["fallback_used"] is True
    assert resp.metadata["gate_pass"] is True


def test_build_llm_dispatches_to_openai_compatible_backend() -> None:
    cfg = InferenceConfig(
        model_id="cogito-2.1:671b",
        backend="openai_compatible",
        openai_base_url="http://localhost:3001/v1",
        openai_api_key_env="FREELLMAPI_KEY",
    )

    llm = build_llm(cfg)

    assert isinstance(llm, OpenAICompatibleLLM)
    assert llm.model_id == "cogito-2.1:671b"
    assert llm.base_url == "http://localhost:3001/v1"
