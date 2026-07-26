"""OpenModel Anthropic-compatible `/v1/messages` backend."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .llm import LLMResponse
from .openai_compatible import _parse_strict_json_object


@dataclass
class OpenModelMessagesLLM:
    """LLM Protocol implementation for OpenModel's Messages API."""

    model_id: str = "deepseek-v4-flash"
    base_url: str = "https://api.openmodel.ai/v1"
    api_key: str | None = None
    api_key_env: str = "OPENMODEL_API_KEY"
    api_key_envs: tuple[str, ...] = ()
    timeout_s: float = 120.0
    system: str | None = None
    require_json: bool = False
    log_path: Path | None = None
    include_raw_response: bool = False
    extra_headers: dict[str, str] = field(default_factory=dict)
    _next_key_index: int = field(default=0, init=False, repr=False)

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        seed: int = 0,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": int(max_new_tokens),
            "temperature": float(temperature),
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.system:
            payload["system"] = self.system
        if stop:
            payload["stop_sequences"] = list(stop)

        print(
            f"[api-call:start] provider=openmodel base_url={self.base_url} "
            f"path=/messages model={self.model_id} require_json={self.require_json} "
            f"max_tokens={max_new_tokens} prompt_chars={len(prompt)}",
            flush=True,
        )
        t0 = time.perf_counter()
        raw, key_env = self._post_json("/messages", payload)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        parsed = json.loads(raw)
        text = "".join(
            str(part.get("text", ""))
            for part in parsed.get("content", [])
            if part.get("type") == "text"
        )
        if stop:
            for s in stop:
                idx = text.find(s)
                if idx >= 0:
                    text = text[:idx]
        usage = parsed.get("usage") or {}
        parsed_json, json_error = _parse_strict_json_object(text)
        valid_json = parsed_json is not None
        gate_pass = bool(text.strip()) and (valid_json if self.require_json else True)
        validation_errors = [json_error] if self.require_json and json_error else []
        metadata = {
            "gate_pass": gate_pass,
            "valid_json": valid_json,
            "schema_pass": valid_json if self.require_json else True,
            "validation_errors": validation_errors,
            "base_url": self.base_url,
            "requested_model": self.model_id,
            "model": parsed.get("model") or self.model_id,
            "api_key_env": key_env,
            "raw_response_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "raw_response_chars": len(text),
        }
        if self.include_raw_response:
            metadata["raw_response"] = text
        self._write_log(metadata)
        print(
            f"[api-call:done] provider=openmodel base_url={self.base_url} "
            f"model={metadata['model']} key_env={key_env} latency_ms={latency_ms:.1f} "
            f"prompt_tokens={usage.get('input_tokens') or 0} "
            f"completion_tokens={usage.get('output_tokens') or 0} "
            f"gate_pass={gate_pass} valid_json={valid_json}",
            flush=True,
        )
        return LLMResponse(
            text=text,
            prompt_tokens=int(usage.get("input_tokens") or 0),
            completion_tokens=int(usage.get("output_tokens") or 0),
            latency_ms=latency_ms,
            seed=seed,
            temperature=temperature,
            model_id=str(parsed.get("model") or self.model_id),
            metadata=metadata,
        )

    def _post_json(self, path: str, payload: dict[str, Any]) -> tuple[str, str]:
        key_candidates = self._ordered_key_candidates()
        if not key_candidates:
            raise RuntimeError("OpenModel API key not provided; set api_key or api_key_envs")
        url = f"{self.base_url.rstrip('/')}{path}"
        errors: list[str] = []
        for key_env, api_key in key_candidates:
            if not api_key:
                print(
                    f"[api-call:key-skip] provider=openmodel key_env={key_env} reason=missing",
                    flush=True,
                )
                errors.append(f"{key_env}: missing")
                continue
            headers = {
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
                **self.extra_headers,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                print(
                    f"[api-call:key-try] provider=openmodel key_env={key_env} "
                    f"url={url} model={payload.get('model')}",
                    flush=True,
                )
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return resp.read().decode("utf-8"), key_env
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8")[:500]
                except Exception:
                    pass
                print(
                    f"[api-call:key-error] provider=openmodel key_env={key_env} "
                    f"HTTP {exc.code}: {body}",
                    flush=True,
                )
                errors.append(f"{key_env}: HTTP {exc.code} {body}")
            except urllib.error.URLError as exc:
                print(
                    f"[api-call:key-error] provider=openmodel key_env={key_env} error={exc}",
                    flush=True,
                )
                errors.append(f"{key_env}: request failed {exc}")
        raise RuntimeError(
            f"OpenModel request failed for all API keys at {url}: {' | '.join(errors)}"
        )

    def _ordered_key_candidates(self) -> list[tuple[str, str | None]]:
        if self.api_key:
            return [("<explicit>", self.api_key)]
        envs = list(self.api_key_envs)
        if not envs:
            envs = [part.strip() for part in self.api_key_env.split(",") if part.strip()]
        envs = [env for env in envs if env]
        if not envs:
            return []
        start = self._next_key_index % len(envs)
        self._next_key_index = (self._next_key_index + 1) % len(envs)
        ordered = envs[start:] + envs[:start]
        return [(env, os.getenv(env)) for env in ordered]

    def _write_log(self, row: dict[str, Any]) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
