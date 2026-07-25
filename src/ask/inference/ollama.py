"""Ollama backend for the LLM Protocol.

Lets the M1-W1 smoke script and dev iterations hit a locally-running Ollama
server (e.g. `gemma3:4b`, `gemma4:e4b`) without downloading multi-GB
HuggingFace weights.

Two endpoints supported:
  - `/api/generate`  — raw completion. Use for base / non-chat-tuned models.
  - `/api/chat`      — applies the model's chat template automatically.
                       Required for instruct models like Gemma, Llama-3-Instruct,
                       Qwen-Instruct (otherwise they emit empty / whitespace).

Default is `chat=True` because every model we care about is chat-tuned.

Resilience (M1-W2 follow-up):
  Cold-start `/api/chat` calls sometimes return HTTP 502 / 503 / 504 while
  Ollama loads the model into its runner. A 24-minute 50-session run
  should not die on a single transient gateway error. `_post` retries 5xx
  responses with exponential backoff; 4xx responses fail fast (those are
  client errors, e.g. unknown model tag).

The Ollama HTTP API is small enough to talk to with the stdlib only; we
deliberately avoid pulling in `ollama-python` to keep dev dependencies thin.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .llm import LLMResponse

# 5xx responses Ollama can emit during cold-start / runner-restart windows.
# 4xx responses (e.g. 404 unknown model) are NOT retried — those are user
# errors that retrying would only delay surfacing.
_RETRY_HTTP_CODES = frozenset({500, 502, 503, 504})
_DEFAULT_RETRIES = 3
_DEFAULT_BACKOFF_S = 2.0  # 2, 4, 8 → ~14s ceiling on cold starts


@dataclass
class OllamaLLM:
    """Talks to an Ollama daemon via /api/chat (default) or /api/generate.

    Determinism: Ollama exposes `seed` and `temperature` options. With
    `temperature=0.0` and a fixed seed, output is reproducible on the same
    server build.

    Note: `chat=True` (the default) sends the prompt as a single user message
    so the model's own chat template is applied. This is what fixes the
    "empty response" failure mode on Gemma / Llama-Instruct / Qwen-Instruct
    when the prompt is treated as raw completion.

    Cold-start resilience: `_post` retries transient 5xx responses with
    exponential backoff (`max_retries`, `backoff_s`). The first /api/chat
    call after `ollama serve` starts can 502 while the model loads into the
    runner; that should not kill a 24-min 50-session evaluation.
    """

    model_id: str = "gemma3:4b"
    host: str = "http://localhost:11434"
    timeout_s: float = 300.0
    keep_alive: str = "30m"  # keep the model resident across the 50-session loop
    chat: bool = True        # use /api/chat (applies chat template)
    system: str | None = None  # optional system prompt for chat mode
    max_retries: int = 5     # 2+4+8+16+32 = 62s — survives one full runner restart
    backoff_s: float = _DEFAULT_BACKOFF_S
    # Override Ollama's default 4096 context. The no-memory baseline never
    # approaches this; halving it cuts the KV-cache footprint by ~50%.
    num_ctx: int | None = 2048
    response_format: str | dict | None = None
    # Ollama 0.24+ reasoning models can spend the whole token budget on hidden
    # thinking and return empty content; callers can pass False to suppress it.
    think: bool | str | None = None

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        seed: int = 0,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        if self.chat:
            return self._chat(prompt, max_new_tokens, temperature, seed, stop)
        return self._completion(prompt, max_new_tokens, temperature, seed, stop)

    # ------------------------------------------------------------------ #

    def _options(
        self, max_new_tokens: int, temperature: float, seed: int, stop: list[str] | None
    ) -> dict[str, object]:
        opts: dict[str, object] = {
            "temperature": float(temperature),
            "seed": int(seed),
            "num_predict": int(max_new_tokens),
        }
        if self.num_ctx is not None:
            opts["num_ctx"] = int(self.num_ctx)
        if stop:
            opts["stop"] = list(stop)
        return opts

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.host.rstrip('/')}{path}"
        body = json.dumps(payload).encode("utf-8")
        last_exc: BaseException | None = None
        last_error_body = ""
        # Try once, then up to `max_retries` more times on 5xx. 4xx fails fast.
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_exc = exc
                try:
                    last_error_body = exc.read().decode("utf-8", errors="replace").strip()
                except Exception:
                    last_error_body = ""
                if exc.code in _RETRY_HTTP_CODES and attempt < self.max_retries:
                    delay = self.backoff_s * (2 ** attempt)
                    print(
                        f"[ollama] {url} returned HTTP {exc.code}; "
                        f"{last_error_body[:240] + '; ' if last_error_body else ''}"
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/"
                        f"{self.max_retries})",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue
                # 4xx, or out of retries — fall through to the raise below.
                break
            except urllib.error.URLError as exc:
                # Connection refused, DNS, etc. Treat as transient on the first
                # try only — daemon may still be coming up — but otherwise fail
                # fast (likely the daemon really is down).
                last_exc = exc
                if attempt < self.max_retries:
                    delay = self.backoff_s * (2 ** attempt)
                    print(
                        f"[ollama] {url} unreachable ({exc}); "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/"
                        f"{self.max_retries})",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue
                break
            except TimeoutError as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    delay = self.backoff_s * (2 ** attempt)
                    print(
                        f"[ollama] {url} timed out after {self.timeout_s:.1f}s; "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/"
                        f"{self.max_retries})",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue
                break

        # Out of retries — surface a single useful error.
        raise RuntimeError(
            f"Ollama request failed at {url}: {last_exc}."
            f"{' Response body: ' + last_error_body if last_error_body else ''} "
            "Is the daemon running? Try `ollama serve`, "
            f"`ollama pull {self.model_id}`, and a quick chat ping: "
            f"`curl {self.host}/api/chat -d '{{\"model\":\"{self.model_id}\","
            f'"messages":[{{"role":"user","content":"hi"}}],"stream":false}}\'`'
        ) from last_exc

    def _warn_if_context_exhausted(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Loudly flag the silent-truncation failure mode.

        When the prompt fills (nearly) the whole context window, Ollama
        truncates the prompt and leaves almost no room to generate, so the
        answer comes back as a single token. This previously tanked a whole
        run silently (every answer became one token). Warn so it is caught
        immediately instead of only in the grades.
        """
        if self.num_ctx is None:
            return
        if prompt_tokens >= int(self.num_ctx) - 8 and completion_tokens <= 1:
            print(
                f"[ollama] WARNING: prompt_tokens={prompt_tokens} fills num_ctx="
                f"{self.num_ctx} for {self.model_id}; only {completion_tokens} "
                "token(s) generated. The prompt is being truncated and there is no "
                "room to answer. Raise --ollama-num-ctx above the prompt size "
                "(or reduce k / neighbor window / assistant context).",
                flush=True,
            )

    def _chat(
        self,
        prompt: str,
        max_new_tokens: int,
        temperature: float,
        seed: int,
        stop: list[str] | None,
    ) -> LLMResponse:
        messages: list[dict[str, str]] = []
        if self.system:
            messages.append({"role": "system", "content": self.system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_id,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": self._options(max_new_tokens, temperature, seed, stop),
        }
        if self.response_format is not None:
            payload["format"] = self.response_format
        if self.think is not None:
            payload["think"] = self.think
        t0 = time.perf_counter()
        data = self._post("/api/chat", payload)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        # /api/chat returns {"message": {"role": "assistant", "content": "..."}}
        msg = data.get("message") or {}
        text = str(msg.get("content", ""))
        if stop:
            for s in stop:
                idx = text.find(s)
                if idx >= 0:
                    text = text[:idx]
        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        self._warn_if_context_exhausted(prompt_tokens, completion_tokens)
        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            seed=seed,
            temperature=temperature,
            model_id=self.model_id,
        )

    def _completion(
        self,
        prompt: str,
        max_new_tokens: int,
        temperature: float,
        seed: int,
        stop: list[str] | None,
    ) -> LLMResponse:
        payload = {
            "model": self.model_id,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": self._options(max_new_tokens, temperature, seed, stop),
        }
        if self.response_format is not None:
            payload["format"] = self.response_format
        if self.think is not None:
            payload["think"] = self.think
        t0 = time.perf_counter()
        data = self._post("/api/generate", payload)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        text = str(data.get("response", ""))
        if stop:
            for s in stop:
                idx = text.find(s)
                if idx >= 0:
                    text = text[:idx]
        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        self._warn_if_context_exhausted(prompt_tokens, completion_tokens)
        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            seed=seed,
            temperature=temperature,
            model_id=self.model_id,
        )
