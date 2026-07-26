"""HTTP header helpers for OpenAI-compatible providers."""

from __future__ import annotations

import os
from collections.abc import Mapping


def _redacted_env_label(api_key_env: str) -> str:
    return (
        "<redacted api key value>"
        if api_key_env.lower().startswith(("sk-", "sk_"))
        else api_key_env
    )


def openai_compatible_headers(
    *,
    api_key: str | None,
    api_key_env: str,
    extra_headers: Mapping[str, str] | None = None,
    modal_key_env: str = "MODAL_KEY",
    modal_secret_env: str = "MODAL_SECRET",
) -> dict[str, str]:
    """Build JSON request headers for OpenAI-compatible HTTP endpoints.

    Modal's OpenAI-compatible endpoints authenticate with `Modal-Key` and
    `Modal-Secret` headers, while most clients still require a non-empty bearer
    token. If both Modal headers are available, use a dummy bearer token unless
    the caller provided one explicitly.
    """

    headers: dict[str, str] = {"Content-Type": "application/json"}

    modal_key = os.getenv(modal_key_env) if modal_key_env else None
    modal_secret = os.getenv(modal_secret_env) if modal_secret_env else None
    if modal_key:
        headers["Modal-Key"] = modal_key
    if modal_secret:
        headers["Modal-Secret"] = modal_secret

    if extra_headers:
        headers.update({str(key): str(value) for key, value in extra_headers.items()})

    resolved_api_key = api_key or os.getenv(api_key_env)
    has_modal_auth = bool(headers.get("Modal-Key") and headers.get("Modal-Secret"))
    if not resolved_api_key:
        if has_modal_auth:
            resolved_api_key = "dummy"
        else:
            raise RuntimeError(
                f"OpenAI-compatible API key not provided; set {_redacted_env_label(api_key_env)} "
                "or pass api_key explicitly"
            )
    headers.setdefault("Authorization", f"Bearer {resolved_api_key}")
    return headers
