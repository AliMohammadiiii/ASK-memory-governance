from __future__ import annotations

import pytest

from ask.inference.openai_headers import openai_compatible_headers


def test_missing_api_key_error_redacts_secret_like_env_name(monkeypatch) -> None:
    monkeypatch.delenv("MODAL_KEY", raising=False)
    monkeypatch.delenv("MODAL_SECRET", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        openai_compatible_headers(api_key=None, api_key_env="sk-test-secret")

    message = str(exc_info.value)
    assert "sk-test-secret" not in message
    assert "<redacted api key value>" in message
