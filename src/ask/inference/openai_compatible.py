"""OpenAI-compatible chat-completions backend with auditable call metadata.

This is the FreeLLMAPI path used for thesis runs. It deliberately talks to the
OpenAI-compatible HTTP surface directly instead of hiding behind an SDK so each
attempt can be logged with routing, latency, validation, and response hashes.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ask.endpoints import validate_http_endpoint

from .llm import LLMResponse, _strip_think_blocks
from .openai_headers import openai_compatible_headers

TaskValidator = Callable[[str, dict[str, Any] | None], tuple[bool, str | None]]


class OpenAIUsage(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAIMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str = "assistant"
    content: str | None = ""


class OpenAIChoice(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int = 0
    message: OpenAIMessage
    finish_reason: str | None = None


class OpenAIChatCompletion(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str | None = None
    object: str | None = None
    model: str | None = None
    choices: list[OpenAIChoice]
    usage: OpenAIUsage | None = None
    routed_via: dict[str, Any] | None = Field(default=None, alias="_routed_via")


class LLMCallLogRow(BaseModel):
    """Metadata row safe to keep for thesis analysis."""

    model_config = ConfigDict(extra="allow")

    model: str
    requested_model: str
    latency_ms: float
    valid_json: bool
    schema_pass: bool
    task_pass: bool
    fallback_used: bool
    raw_response_hash: str
    raw_response_chars: int
    attempt_index: int
    provider: str | None = None
    routed_model: str | None = None
    finish_reason: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    base_url: str
    validation_errors: list[str] = Field(default_factory=list)
    error: str | None = None
    raw_response: str | None = None
    provider_preferences: dict[str, Any] | None = None


class OpenAICompatibleFatalError(RuntimeError):
    """Account/auth failure that another model retry cannot recover from."""


@dataclass
class OpenAICompatibleLLM:
    """LLM Protocol implementation for `/v1/chat/completions`.

    Validation gate behavior:
      - Plain answer calls accept any non-empty text.
      - JSON-required calls must contain exactly one JSON object and no prose.
      - Optional task validators can enforce numeric/supersession checks.
      - Failed attempts fall through to the configured fallback model list.
    """

    model_id: str = "cogito-2.1:671b"
    base_url: str = "http://localhost:3001/v1"
    api_key: str | None = None
    api_key_env: str = "FREELLMAPI_KEY"
    timeout_s: float = 120.0
    system: str | None = None
    response_format: str | dict[str, Any] | None = None
    require_json: bool = False
    fallback_model_ids: tuple[str, ...] = ()
    log_path: Path | None = None
    include_raw_response: bool = False
    task_validator: TaskValidator | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    # vLLM (and other OpenAI-compatible servers) extend the request body. These
    # are merged into the JSON payload when set:
    #   chat_template_kwargs={"enable_thinking": False} disables Qwen3/3.5
    #     <think> blocks server-side (the recommended non-thinking switch).
    #   guided_json={...} constrains output to a JSON Schema (vLLM guided
    #     decoding) for reliable extraction / relation JSON.
    #   extra_body is a generic escape hatch for any other server field.
    chat_template_kwargs: dict[str, Any] | None = None
    guided_json: dict[str, Any] | None = None
    extra_body: dict[str, Any] | None = None
    strip_think: bool = True
    retry_max_attempts: int = 3
    retry_initial_delay_s: float = 1.0
    retry_max_delay_s: float = 10.0
    retry_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504, 520, 522, 524)
    # Server context window (vLLM --max-model-len). Exposed under the same
    # attribute the controller prompt-budget guard reads on the HF backend, so
    # the answer prompt is trimmed to leave room for generation. Without it the
    # guard is OFF and an oversized prompt is rejected by vLLM with HTTP 400
    # ("maximum context length is N tokens").
    num_ctx: int | None = None
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        validate_http_endpoint(
            self.base_url,
            allow_insecure_http=self.allow_insecure_http,
        )

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        seed: int = 0,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        models = (self.model_id, *self.fallback_model_ids)
        last_response: LLMResponse | None = None
        last_error: BaseException | None = None

        for attempt_index, model in enumerate(models):
            try:
                response = self._generate_once(
                    model=model,
                    prompt=prompt,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    seed=seed,
                    stop=stop,
                    attempt_index=attempt_index,
                )
            except OpenAICompatibleFatalError as exc:
                self._write_log(
                    LLMCallLogRow(
                        model=model,
                        requested_model=self.model_id,
                        latency_ms=0.0,
                        valid_json=False,
                        schema_pass=False,
                        task_pass=False,
                        fallback_used=attempt_index > 0,
                        raw_response_hash="",
                        raw_response_chars=0,
                        attempt_index=attempt_index,
                        base_url=self.base_url,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                # Credit exhaustion is account-wide. Trying every fallback model
                # only repeats paid requests and then causes every shard restart
                # to do the same work again.
                raise
            except Exception as exc:
                last_error = exc
                self._write_log(
                    LLMCallLogRow(
                        model=model,
                        requested_model=self.model_id,
                        latency_ms=0.0,
                        valid_json=False,
                        schema_pass=False,
                        task_pass=False,
                        fallback_used=attempt_index > 0,
                        raw_response_hash="",
                        raw_response_chars=0,
                        attempt_index=attempt_index,
                        base_url=self.base_url,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue

            last_response = response
            meta = response.metadata
            if meta.get("gate_pass", False):
                return response

        if last_response is not None:
            # Preserve existing pipeline behavior when every candidate produced
            # text but failed a strict gate. Downstream structured wrappers can
            # still repair or report the parse failure.
            return last_response
        raise RuntimeError(f"OpenAI-compatible request failed for all models: {last_error}")

    def _generate_once(
        self,
        *,
        model: str,
        prompt: str,
        max_new_tokens: int,
        temperature: float,
        seed: int,
        stop: list[str] | None,
        attempt_index: int,
    ) -> LLMResponse:
        messages: list[dict[str, str]] = []
        if self.system:
            messages.append({"role": "system", "content": self.system})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_new_tokens),
        }
        if stop:
            payload["stop"] = list(stop)
        if seed is not None:
            payload["seed"] = int(seed)
        if self.response_format is not None:
            payload["response_format"] = _normalize_response_format(self.response_format)
        # vLLM server-side extensions.
        if self.chat_template_kwargs:
            payload["chat_template_kwargs"] = dict(self.chat_template_kwargs)
        if self.guided_json is not None:
            payload["guided_json"] = self.guided_json
        if self.extra_body:
            for key, value in self.extra_body.items():
                payload.setdefault(key, value)

        provider_preferences = payload.get("provider")
        provider_preferences_json = (
            json.dumps(provider_preferences, sort_keys=True, separators=(",", ":"))
            if provider_preferences is not None
            else None
        )
        provider_part = (
            f" provider_preferences={provider_preferences_json}"
            if provider_preferences_json is not None
            else ""
        )
        print(
            f"[api-call:start] provider=openai-compatible base_url={self.base_url} "
            f"path=/chat/completions model={model} require_json={self.require_json} "
            f"max_tokens={max_new_tokens} prompt_chars={len(prompt)} attempt={attempt_index}"
            f"{provider_part}",
            flush=True,
        )
        t0 = time.perf_counter()
        raw = self._post_json("/chat/completions", payload)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        parsed_response = OpenAIChatCompletion.model_validate_json(raw)
        choice = parsed_response.choices[0]
        text = choice.message.content or ""
        if self.strip_think:
            text = _strip_think_blocks(text)
        if stop:
            for s in stop:
                idx = text.find(s)
                if idx >= 0:
                    text = text[:idx]
        usage = parsed_response.usage or OpenAIUsage()
        parsed_json, json_error = _parse_strict_json_object(text)
        valid_json = parsed_json is not None
        schema_pass = valid_json if self.require_json else True
        task_pass, task_error = self._task_pass(text, parsed_json)
        gate_pass = bool(text.strip()) and schema_pass and task_pass
        route = parsed_response.routed_via or {}
        routed_model = str(route.get("model") or parsed_response.model or model)
        provider = route.get("platform") or route.get("provider")
        validation_errors = [
            err
            for err in (json_error if self.require_json and json_error else None, task_error)
            if err
        ]

        log_row = LLMCallLogRow(
            model=routed_model,
            requested_model=model,
            provider=str(provider) if provider is not None else None,
            routed_model=routed_model,
            latency_ms=latency_ms,
            valid_json=valid_json,
            schema_pass=schema_pass,
            task_pass=task_pass,
            fallback_used=attempt_index > 0,
            raw_response_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            raw_response_chars=len(text),
            attempt_index=attempt_index,
            finish_reason=choice.finish_reason,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            base_url=self.base_url,
            validation_errors=validation_errors,
            raw_response=text if self.include_raw_response else None,
            provider_preferences=provider_preferences,
        )
        self._write_log(log_row)
        metadata = log_row.model_dump(exclude_none=True)
        metadata["gate_pass"] = gate_pass
        metadata["route"] = route
        routed_provider = str(provider) if provider is not None else "unreported"
        print(
            f"[api-call:done] provider=openai-compatible base_url={self.base_url} "
            f"routed_provider={routed_provider} model={routed_model} "
            f"requested_model={model} latency_ms={latency_ms:.1f} "
            f"prompt_tokens={usage.prompt_tokens} completion_tokens={usage.completion_tokens} "
            f"gate_pass={gate_pass} valid_json={valid_json}",
            flush=True,
        )
        return LLMResponse(
            text=text,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            latency_ms=latency_ms,
            seed=seed,
            temperature=temperature,
            model_id=routed_model,
            metadata=metadata,
        )

    def _post_json(self, path: str, payload: dict[str, Any]) -> str:
        url = f"{self.base_url.rstrip('/')}{path}"
        headers = openai_compatible_headers(
            api_key=self.api_key,
            api_key_env=self.api_key_env,
            extra_headers=self.extra_headers,
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        attempts = max(1, int(self.retry_max_attempts))
        for attempt in range(1, attempts + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    body = resp.read().decode("utf-8")
                # Some OpenRouter upstreams return an OpenAI error envelope in
                # a successful HTTP response (observed with provider code 504).
                # Passing that envelope to OpenAIChatCompletion produces a
                # misleading Pydantic "choices missing" traceback and skips the
                # transport retry policy. Treat a top-level error object exactly
                # like the equivalent HTTP failure instead.
                error_payload: Any = None
                try:
                    decoded = json.loads(body)
                    if isinstance(decoded, dict):
                        error_payload = decoded.get("error")
                except (TypeError, ValueError):
                    pass
                if not isinstance(error_payload, dict):
                    return body

                raw_status = error_payload.get("code") or error_payload.get("status") or 500
                try:
                    status = int(raw_status)
                except (TypeError, ValueError):
                    status = 500
                body_excerpt = body[:500]
                print(
                    f"[api-call:error] provider=openai-compatible url={url} "
                    f"attempt={attempt}/{attempts} embedded HTTP {status}: {body_excerpt}",
                    flush=True,
                )
                if attempt >= attempts or status not in self.retry_status_codes:
                    error = f"embedded HTTP {status} error from {url}: {body_excerpt}"
                    if status == 402:
                        raise OpenAICompatibleFatalError(error)
                    raise RuntimeError(error)
                self._sleep_before_retry(attempt, None, body)
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8")
                except Exception:
                    pass
                body_excerpt = body[:500]
                print(
                    f"[api-call:error] provider=openai-compatible url={url} "
                    f"attempt={attempt}/{attempts} HTTP {exc.code}: {body_excerpt}",
                    flush=True,
                )
                if attempt >= attempts or exc.code not in self.retry_status_codes:
                    error = f"HTTP {exc.code} from {url}: {body_excerpt}"
                    if exc.code == 402:
                        raise OpenAICompatibleFatalError(error) from exc
                    raise RuntimeError(error) from exc
                self._sleep_before_retry(attempt, exc.headers.get("Retry-After"), body)
            except urllib.error.URLError as exc:
                print(
                    f"[api-call:error] provider=openai-compatible url={url} "
                    f"attempt={attempt}/{attempts} error={exc}",
                    flush=True,
                )
                if attempt >= attempts:
                    raise RuntimeError(f"request failed at {url}: {exc}") from exc
                self._sleep_before_retry(attempt, None, None)
        raise RuntimeError(f"request failed at {url}: exhausted retry attempts")

    def _sleep_before_retry(
        self,
        attempt: int,
        retry_after: str | None,
        response_body: str | None,
    ) -> None:
        delay = _retry_delay_s(
            attempt=attempt,
            retry_after=retry_after or _retry_after_from_body(response_body),
            initial_delay_s=self.retry_initial_delay_s,
            max_delay_s=self.retry_max_delay_s,
        )
        if delay > 0.0:
            time.sleep(delay)

    def _task_pass(self, text: str, parsed_json: dict[str, Any] | None) -> tuple[bool, str | None]:
        if self.task_validator is None:
            return True, None
        try:
            return self.task_validator(text, parsed_json)
        except Exception as exc:
            return False, f"task validator raised {type(exc).__name__}: {exc}"

    def _write_log(self, row: LLMCallLogRow) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(row.model_dump(exclude_none=True), ensure_ascii=False, sort_keys=True)
            )
            fh.write("\n")


def _normalize_response_format(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, str):
        if value.lower() == "json":
            return {"type": "json_object"}
        return {"type": value}
    return dict(value)


def _parse_strict_json_object(text: str) -> tuple[dict[str, Any] | None, str | None]:
    stripped = text.strip()
    if not stripped:
        return None, "empty response"
    decoder = json.JSONDecoder()
    try:
        value, end = decoder.raw_decode(stripped)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    if stripped[end:].strip():
        return None, "extra prose after JSON object"
    if not isinstance(value, dict):
        return None, "JSON root is not an object"
    return value, None


def _retry_delay_s(
    *,
    attempt: int,
    retry_after: str | None,
    initial_delay_s: float,
    max_delay_s: float,
) -> float:
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), max_delay_s)
        except ValueError:
            pass
    return min(max(initial_delay_s, 0.0) * (2 ** max(attempt - 1, 0)), max_delay_s)


def _retry_after_from_body(response_body: str | None) -> str | None:
    if not response_body:
        return None
    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError:
        return None
    metadata = payload.get("error", {}).get("metadata", {})
    value = metadata.get("retry_after_seconds") or metadata.get("retry_after_seconds_raw")
    return str(value) if value is not None else None
