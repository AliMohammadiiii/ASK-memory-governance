from __future__ import annotations

import io
import json
import urllib.error

from ask.inference.fallback import FallbackLLM
from ask.inference.llm import LLMResponse
from ask.inference.openmodel_messages import OpenModelMessagesLLM


class _Resp:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):  # noqa: ANN001
        return io.BytesIO(json.dumps(self.payload).encode("utf-8"))

    def __exit__(self, *_args):  # noqa: ANN002
        return False


def test_openmodel_messages_posts_anthropic_messages(monkeypatch) -> None:  # noqa: ANN001
    seen = {}

    def fake_urlopen(req, timeout):  # noqa: ANN001
        seen["url"] = req.full_url
        seen["timeout"] = timeout
        seen["headers"] = dict(req.header_items())
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp(
            {
                "model": "deepseek-v4-flash-202605",
                "content": [{"type": "thinking", "thinking": "x"}, {"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 3, "output_tokens": 1},
            }
        )

    monkeypatch.setenv("OPENMODEL_API_KEY", "key")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    llm = OpenModelMessagesLLM(model_id="deepseek-v4-flash", timeout_s=7)
    resp = llm.generate("hello", max_new_tokens=12, temperature=0.2)

    assert seen["url"] == "https://api.openmodel.ai/v1/messages"
    assert seen["timeout"] == 7
    assert seen["headers"]["X-api-key"] == "key"
    assert seen["body"]["model"] == "deepseek-v4-flash"
    assert seen["body"]["messages"] == [{"role": "user", "content": "hello"}]
    assert seen["body"]["max_tokens"] == 12
    assert resp.text == "ok"
    assert resp.model_id == "deepseek-v4-flash-202605"


def test_openmodel_messages_round_robins_key_envs(monkeypatch) -> None:  # noqa: ANN001
    seen_keys = []

    def fake_urlopen(req, timeout):  # noqa: ANN001
        seen_keys.append(dict(req.header_items())["X-api-key"])
        return _Resp(
            {
                "model": "deepseek-v4-flash-202605",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )

    monkeypatch.setenv("OPENMODEL_KEY1", "key-1")
    monkeypatch.setenv("OPENMODEL_KEY2", "key-2")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    llm = OpenModelMessagesLLM(
        model_id="deepseek-v4-flash",
        api_key_envs=("OPENMODEL_KEY1", "OPENMODEL_KEY2"),
    )

    llm.generate("a")
    llm.generate("b")
    llm.generate("c")

    assert seen_keys == ["key-1", "key-2", "key-1"]


def test_openmodel_messages_tries_next_key_on_http_error(monkeypatch) -> None:  # noqa: ANN001
    seen_keys = []

    def fake_urlopen(req, timeout):  # noqa: ANN001
        key = dict(req.header_items())["X-api-key"]
        seen_keys.append(key)
        if key == "bad":
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b"disabled"))
        return _Resp(
            {
                "model": "deepseek-v4-flash-202605",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )

    monkeypatch.setenv("OPENMODEL_KEY1", "bad")
    monkeypatch.setenv("OPENMODEL_KEY2", "good")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    llm = OpenModelMessagesLLM(
        model_id="deepseek-v4-flash",
        api_key_envs=("OPENMODEL_KEY1", "OPENMODEL_KEY2"),
    )
    resp = llm.generate("hello")

    assert resp.text == "ok"
    assert seen_keys == ["bad", "good"]


def test_fallback_llm_tries_second_when_gate_fails() -> None:
    class BadJson:
        model_id = "bad-json"

        def generate(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
            return LLMResponse(
                text="not json",
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=1,
                model_id="bad-json",
                metadata={"gate_pass": False, "validation_errors": ["invalid JSON"]},
            )

    class Good:
        model_id = "good"

        def generate(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
            return LLMResponse(
                text='{"correct": true, "rationale": "ok"}',
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=1,
                model_id="good",
                metadata={"gate_pass": True},
            )

    good = Good()
    resp = FallbackLLM((BadJson(), good)).generate("judge")

    assert resp.model_id == "good"
    assert resp.metadata["fallback_candidate_index"] == 1
