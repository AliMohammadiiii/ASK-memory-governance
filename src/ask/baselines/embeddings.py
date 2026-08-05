"""Turn-level dense embedder for the flat-vector baseline (M1-W3 §3.1).

Design (carried in `NOTES/m1w3_design.md` §2):

  * Model: `sentence-transformers/all-MiniLM-L6-v2`. 384-dim, ~80 MB,
    CPU-friendly, single most-cited general-purpose dense embedder of the
    pre-memory-governance era. No fine-tuning. Deliberate
    median-of-literature default that no reviewer can call adversarial.
  * Chunking unit: ONE TURN = ONE EMBEDDED ITEM. Two-turn windows and
    full-session chunks are deferred to a Month-4 (or PhD) ablation.
  * Role tagging: every turn is embedded as `"[USER] ..."` or
    `"[ASSISTANT] ..."`. The role tag is essential for the Month-3
    controller; introducing it only for the controller would create
    schema drift between baselines and controller.
  * Output: L2-normalized float32 rows. **Non-negotiable** — FAISS
    inner-product (`IndexFlatIP`) over normalized vectors equals cosine
    similarity, which is the metric the literature reports. Test
    `tests/test_embeddings.py::test_rows_are_l2_normalized` enforces
    norm ≈ 1.0 to float32 tolerance.

Implementation discipline (mirrors `ask.inference.llm.HuggingFaceLLM`):

  * Heavy deps (`sentence_transformers`, `torch`) are imported LAZILY on
    the first `embed()` call so `pytest` on the skeleton does not pull
    multi-GB GPU stacks. The Protocol + `FakeEmbedder` pattern is what
    Week-2's `_RecordingLLM` does for the LLM Protocol.
  * Module-level singleton cache: multiple baselines / multiple
    `FlatVectorStore` instances inside one process must share a single
    loaded model. Reloading MiniLM costs ~1 s × N stores, which adds up.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel, ConfigDict

from ask.inference.openai_headers import openai_compatible_headers

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _is_loopback_url(url: str) -> bool:
    """Return whether *url* targets this machine's loopback interface."""
    return urllib.parse.urlparse(url).hostname in _LOOPBACK_HOSTS


def _urlopen(
    request: urllib.request.Request,
    *,
    url: str,
    timeout: float,
) -> Any:
    """Open a request while ensuring loopback traffic never enters a proxy.

    On macOS, ``urllib`` imports the system proxy configuration even when no
    proxy environment variables are exported.  A local embedding request can
    therefore be sent to Privoxy instead of ``127.0.0.1``.  Remote endpoints
    retain normal system/environment proxy behavior; only loopback is forced
    through a proxy-free opener.
    """
    if _is_loopback_url(url):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)


# --------------------------------------------------------------------- #
# Public Protocol                                                        #
# --------------------------------------------------------------------- #


@runtime_checkable
class Embedder(Protocol):
    """Anything that turns a list of strings into an `(n, dim)` float32 array.

    Contract:
      * Output dtype is `numpy.float32`.
      * Output shape is `(len(texts), self.embedding_dim)`.
      * Every row has L2 norm = 1.0 within float32 tolerance.
      * `embed()` is deterministic on the same loaded weights — i.e. given
        the same list of strings, it returns identical floats.
    """

    @property
    def embedding_dim(self) -> int: ...

    @property
    def model_id(self) -> str: ...

    def embed(self, texts: list[str]) -> np.ndarray: ...


# --------------------------------------------------------------------- #
# Role-tagging helper                                                    #
# --------------------------------------------------------------------- #

_ROLE_PREFIX_USER = "[USER] "
_ROLE_PREFIX_ASSISTANT = "[ASSISTANT] "


def role_tag(role: str, content: str) -> str:
    """Return the role-tagged string the embedder will see.

    Reuse this anywhere a turn is rendered as a single embeddable string —
    the `FlatVectorStore.add()` path AND any debug/inspection code MUST
    agree on the exact tag, otherwise the embedded form drifts from what
    the prompt template eventually renders.
    """
    role_l = (role or "").lower()
    if role_l == "user":
        return _ROLE_PREFIX_USER + content
    if role_l == "assistant":
        return _ROLE_PREFIX_ASSISTANT + content
    # Defensive: tolerate unknown roles by uppercasing — the data loader
    # already restricts roles to {"user", "assistant"} via dataclass
    # validation, so this branch is only hit by future schema changes.
    return f"[{role.upper()}] {content}"


# --------------------------------------------------------------------- #
# Module-level singleton cache                                           #
# --------------------------------------------------------------------- #
#
# Keyed by `(model_id, revision, device, trust_remote_code)` because a future caller might want one
# CPU embedder and one CUDA embedder side-by-side. Within one process,
# every `TurnEmbedder` instance with the same `(model_id, device)` reuses
# the same loaded weights.

_MODEL_CACHE: dict[tuple[str, str | None, str, bool], Any] = {}


_REMOTE_IMPORT_SHIM_APPLIED = False


def _apply_remote_code_import_shim() -> None:
    """Work around a transformers `get_imports` bug for fallback-import models.

    Custom-architecture models such as `jinaai/jina-embeddings-v5-*` (built on
    EuroBERT) use the standard idiom:

        try:
            from .configuration_eurobert import EuroBertConfig
        except ImportError:
            from configuration_eurobert import EuroBertConfig

    transformers (<=4.49) strips try/except blocks with a non-greedy regex that
    only removes through the `except:` header, leaving the except-body absolute
    import behind. That leftover `from configuration_eurobert import ...` is then
    misread as a missing PyPI package, raising
    `ImportError: ... Run pip install configuration_eurobert`.

    The referenced file actually sits next to the modeling file and the relative
    import (tried first) succeeds at runtime. So we wrap `get_imports` to drop
    any reported dependency that is really a sibling `.py` module in the same
    directory. Model-agnostic and idempotent; a no-op if transformers already
    handles it.
    """
    global _REMOTE_IMPORT_SHIM_APPLIED
    if _REMOTE_IMPORT_SHIM_APPLIED:
        return
    try:
        from transformers import dynamic_module_utils  # type: ignore[import-not-found]
    except Exception:
        return

    _original_get_imports = dynamic_module_utils.get_imports

    def _get_imports_ignoring_siblings(filename: Any) -> list[str]:
        imports = _original_get_imports(filename)
        module_dir = os.path.dirname(os.fspath(filename))
        return [imp for imp in imports if not os.path.isfile(os.path.join(module_dir, f"{imp}.py"))]

    dynamic_module_utils.get_imports = _get_imports_ignoring_siblings
    _REMOTE_IMPORT_SHIM_APPLIED = True


def _torch_cuda_is_available() -> bool:
    """Return whether the installed torch build can actually use CUDA."""
    try:
        import torch  # type: ignore[import-not-found]
    except Exception:
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _resolve_sentence_transformer_device(device: str) -> str:
    """Resolve the requested SentenceTransformer device defensively.

    Colab can expose a CPU-only torch build even when a notebook cell passes
    `--embedder-device cuda`. MiniLM is small enough to run on CPU, so fallback
    here is better than crashing mid-run after the answerer has loaded.
    """
    requested = (device or "cpu").strip()
    requested_l = requested.lower()
    if not requested or requested_l == "auto":
        return "cuda" if _torch_cuda_is_available() else "cpu"
    if requested_l.startswith("cuda") and not _torch_cuda_is_available():
        print(
            "[embedder] requested CUDA for sentence-transformer embeddings, "
            "but torch.cuda.is_available() is false; falling back to CPU. "
            "In Colab, select a GPU runtime or install a CUDA-enabled torch "
            "wheel if you need GPU embeddings.",
            flush=True,
        )
        return "cpu"
    return requested


def _get_or_load_model(
    model_id: str,
    device: str,
    revision: str | None = None,
    trust_remote_code: bool = False,
) -> Any:
    """Lazy-load the sentence-transformers model the first time it's needed."""
    resolved_device = _resolve_sentence_transformer_device(device)
    key = (model_id, revision, resolved_device, bool(trust_remote_code))
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover — only on bare envs
        raise RuntimeError(
            "sentence-transformers is required for TurnEmbedder. Install with: pip install -e .[ml]"
        ) from exc
    # trust_remote_code is required by custom-architecture embedders such as
    # jinaai/jina-embeddings-v5-*; harmless for plain models like MiniLM.
    if trust_remote_code:
        # jina-embeddings-v5 (EuroBERT) trips a transformers get_imports bug;
        # see _apply_remote_code_import_shim. No-op for plain models.
        _apply_remote_code_import_shim()
    try:
        model = SentenceTransformer(
            model_id,
            device=resolved_device,
            revision=revision,
            trust_remote_code=trust_remote_code,
        )
    except TypeError:
        # Very old sentence-transformers without the trust_remote_code kwarg.
        model = SentenceTransformer(model_id, device=resolved_device)
    _MODEL_CACHE[key] = model
    return model


def _clear_model_cache() -> None:
    """Test hook — drop the singleton cache. Not part of the public API."""
    _MODEL_CACHE.clear()


def _l2_normalize_rows(emb: np.ndarray) -> np.ndarray:
    """Return float32 rows normalized for cosine-via-inner-product search."""
    emb = np.ascontiguousarray(emb, dtype=np.float32)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms = np.where(norms < 1e-12, 1.0, norms)
    return (emb / norms).astype(np.float32, copy=False)


# --------------------------------------------------------------------- #
# TurnEmbedder                                                           #
# --------------------------------------------------------------------- #


_DEFAULT_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
_DEFAULT_DEVICE = "cpu"  # Week-3 dev path; flip to "cuda" on the host.
_DEFAULT_BATCH_SIZE = 64

# MiniLM-L6-v2 is 384-dim; encode this so `embedding_dim` is queryable
# without paying the load cost. If `model_id` is overridden, the value is
# derived from the loaded model on first `embed()` call.
_KNOWN_DIM: dict[str, int] = {
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}


@dataclass
class TurnEmbedder:
    """Wraps a `sentence_transformers.SentenceTransformer` with the contract above.

    The model is loaded lazily (first `embed()` call) so test suites and
    the harness can construct the embedder without paying the model
    download. Loaded weights are shared across instances via a
    module-level singleton keyed by `(model_id, revision, device, trust_remote_code)`.
    """

    model_id: str = _DEFAULT_MODEL_ID
    revision: str | None = None
    device: str = _DEFAULT_DEVICE
    batch_size: int = _DEFAULT_BATCH_SIZE
    # Custom-architecture embedders (e.g. jinaai/jina-embeddings-v5-*) need
    # trust_remote_code=True and accept task/prompt_name encode kwargs. These
    # are no-ops for the default MiniLM (the kwargs are dropped defensively).
    trust_remote_code: bool = False
    task: str | None = None
    prompt_name: str | None = None

    # Filled in lazily on first embed() call.
    _model: Any = field(default=None, init=False, repr=False)
    _embedding_dim: int | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        # If the model_id is one we know up front, expose the dim
        # immediately so callers can size FAISS indices without a load.
        if self.model_id in _KNOWN_DIM:
            self._embedding_dim = _KNOWN_DIM[self.model_id]

    @property
    def embedding_dim(self) -> int:
        """Output dimensionality. Lazy-resolves by loading the model if unknown.

        Resolution order, because custom-architecture models do not all
        implement the same accessor (jinaai/jina-embeddings-v5-* returns None
        from get_sentence_embedding_dimension and only knows its dim after a
        task-aware encode):
          1. get_embedding_dimension()
          2. get_sentence_embedding_dimension()
          3. a real probe encode via self.embed() (which passes `task`)
        """
        if self._embedding_dim is None:
            self._ensure_loaded()
            dim: int | None = None
            for accessor in ("get_embedding_dimension", "get_sentence_embedding_dimension"):
                fn = getattr(self._model, accessor, None)
                if callable(fn):
                    try:
                        value = fn()
                    except Exception:
                        value = None
                    if value:
                        dim = int(value)
                        break
            if dim is None:
                # Probe: self.embed passes the configured task and L2-normalizes.
                probe = self.embed(["dimension probe"])
                dim = int(probe.shape[-1])
            self._embedding_dim = dim
        return self._embedding_dim

    def _ensure_loaded(self) -> None:
        if self._model is None:
            self._model = _get_or_load_model(
                self.model_id,
                self.device,
                self.revision,
                self.trust_remote_code,
            )

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of strings. Always returns L2-normalized float32 rows.

        Empty input returns an empty `(0, embedding_dim)` array — callers
        rely on this for the no-memory degeneracy case in
        `FlatVectorBaseline`.
        """
        if not texts:
            dim = self.embedding_dim
            return np.zeros((0, dim), dtype=np.float32)

        self._ensure_loaded()
        # `normalize_embeddings=True` returns L2-normalized rows; we still
        # cast and re-check below because some sentence-transformers
        # versions return float64 on CPU paths.
        encode_kwargs: dict[str, Any] = dict(
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        # Jina-v5-style models take a `task` (and optional `prompt_name`) to
        # select the retrieval adapter. Plain models reject these kwargs, so
        # retry without them on TypeError to stay backward-compatible.
        if self.task is not None:
            encode_kwargs["task"] = self.task
        if self.prompt_name is not None:
            encode_kwargs["prompt_name"] = self.prompt_name
        try:
            emb = self._model.encode(texts, **encode_kwargs)
        except TypeError:
            for extra in ("task", "prompt_name"):
                encode_kwargs.pop(extra, None)
            emb = self._model.encode(texts, **encode_kwargs)
        # Belt-and-braces: the contract is "rows are L2-normalized", and
        # `normalize_embeddings=True` is what guarantees it. Re-normalize
        # defensively so a future ST version that flips the default
        # cannot silently break cosine-via-IP downstream.
        return _l2_normalize_rows(emb)


# --------------------------------------------------------------------- #
# OllamaEmbedder — local HTTP embedding backend                          #
# --------------------------------------------------------------------- #


@dataclass
class OllamaEmbedder:
    """Embed text through a local Ollama daemon.

    This avoids the Apple-Silicon `sentence-transformers`/libomp crash path
    while preserving the same `Embedder` contract used by `FlatVectorStore`.
    The embedding dimension is resolved lazily by a one-text `/api/embed`
    request because Ollama model tags do not expose dimensions in `/api/tags`.
    """

    model_id: str = "llama3.2:3b"
    host: str = "http://localhost:11434"
    timeout_s: float = 900.0
    keep_alive: str = "30m"
    batch_size: int = 16
    truncate: bool = True
    max_retries: int = 5
    backoff_s: float = 2.0

    _embedding_dim: int | None = field(default=None, init=False, repr=False)

    @property
    def embedding_dim(self) -> int:
        if self._embedding_dim is None:
            probe = self._embed_batch(["dimension probe"])
            self._embedding_dim = int(probe.shape[1])
        return self._embedding_dim

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        chunks: list[np.ndarray] = []
        for start in range(0, len(texts), self.batch_size):
            chunks.append(self._embed_batch(texts[start : start + self.batch_size]))
        emb = np.vstack(chunks).astype(np.float32, copy=False)
        if self._embedding_dim is None:
            self._embedding_dim = int(emb.shape[1])
        if emb.shape[1] != self.embedding_dim:
            raise RuntimeError(
                f"Ollama embedder returned dim={emb.shape[1]} but expected "
                f"{self.embedding_dim} for model {self.model_id}"
            )
        return _l2_normalize_rows(emb)

    def _embed_batch(self, texts: list[str]) -> np.ndarray:
        payload = {
            "model": self.model_id,
            "input": texts,
            "keep_alive": self.keep_alive,
            "truncate": self.truncate,
        }
        data = self._post("/api/embed", payload)
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise RuntimeError(
                f"Ollama /api/embed returned malformed embeddings for "
                f"{self.model_id}: expected {len(texts)} rows"
            )
        arr = np.asarray(embeddings, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[0] != len(texts) or arr.shape[1] <= 0:
            raise RuntimeError(
                f"Ollama /api/embed returned invalid shape {arr.shape} for {self.model_id}"
            )
        return arr

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, Any]:
        url = f"{self.host.rstrip('/')}{path}"
        body = json.dumps(payload).encode("utf-8")
        last_exc: BaseException | None = None
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with _urlopen(req, url=url, timeout=self.timeout_s) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code in {500, 502, 503, 504} and attempt < self.max_retries:
                    delay = self.backoff_s * (2**attempt)
                    print(
                        f"[ollama-embed] {url} returned HTTP {exc.code}; "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/"
                        f"{self.max_retries})",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue
                break
            except (urllib.error.URLError, TimeoutError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    delay = self.backoff_s * (2**attempt)
                    print(
                        f"[ollama-embed] {url} failed ({exc}); retrying in "
                        f"{delay:.1f}s (attempt {attempt + 1}/{self.max_retries})",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue
                break
        raise RuntimeError(
            f"Ollama embedding request failed at {url}: {last_exc}. "
            "Is the daemon running, and does the model support /api/embed?"
        ) from last_exc


# --------------------------------------------------------------------- #
# OpenAICompatibleEmbedder — FreeLLMAPI /v1/embeddings backend           #
# --------------------------------------------------------------------- #


class OpenAIEmbeddingItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    embedding: list[float]
    index: int | None = None


class OpenAIEmbeddingsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: list[OpenAIEmbeddingItem]
    model: str | None = None


@dataclass
class OpenAICompatibleEmbedder:
    """Embed text through an OpenAI-compatible `/v1/embeddings` endpoint."""

    model_id: str = "auto"
    base_url: str = "http://localhost:3001/v1"
    api_key: str | None = None
    api_key_env: str = "FREELLMAPI_KEY"
    timeout_s: float = 120.0
    batch_size: int = 16
    log_path: str | None = None
    max_retries: int = 6
    backoff_s: float = 10.0
    min_interval_s: float = 0.0
    max_batch_chars: int = 0
    extra_headers: dict[str, str] = field(default_factory=dict)

    _embedding_dim: int | None = field(default=None, init=False, repr=False)
    _last_request_at: float = field(default=0.0, init=False, repr=False)

    @property
    def embedding_dim(self) -> int:
        if self._embedding_dim is None:
            probe = self._embed_batch(["dimension probe"])
            self._embedding_dim = int(probe.shape[1])
        return self._embedding_dim

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        chunks: list[np.ndarray] = []
        for batch in self._iter_batches(texts):
            chunks.append(self._embed_batch(batch))
        emb = np.vstack(chunks).astype(np.float32, copy=False)
        if self._embedding_dim is None:
            self._embedding_dim = int(emb.shape[1])
        if emb.shape[1] != self.embedding_dim:
            raise RuntimeError(
                f"OpenAI-compatible embedder returned dim={emb.shape[1]} but "
                f"expected {self.embedding_dim} for model {self.model_id}"
            )
        return _l2_normalize_rows(emb)

    def _iter_batches(self, texts: list[str]) -> Iterator[list[str]]:
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        batch: list[str] = []
        batch_chars = 0
        for text in texts:
            text_chars = len(str(text))
            would_exceed_count = len(batch) >= self.batch_size
            would_exceed_chars = (
                self.max_batch_chars > 0
                and bool(batch)
                and batch_chars + text_chars > self.max_batch_chars
            )
            if would_exceed_count or would_exceed_chars:
                yield batch
                batch = []
                batch_chars = 0
            batch.append(text)
            batch_chars += text_chars
        if batch:
            yield batch

    def _embed_batch(self, texts: list[str]) -> np.ndarray:
        self._pace()
        t0 = time.perf_counter()
        data = self._post("/embeddings", {"model": self.model_id, "input": texts})
        latency_ms = (time.perf_counter() - t0) * 1000.0
        parsed = OpenAIEmbeddingsResponse.model_validate(data)
        if len(parsed.data) != len(texts):
            raise RuntimeError(
                f"OpenAI-compatible /embeddings returned {len(parsed.data)} rows "
                f"for {len(texts)} inputs"
            )
        rows = sorted(
            enumerate(parsed.data),
            key=lambda pair: pair[1].index if pair[1].index is not None else pair[0],
        )
        arr = np.asarray([item.embedding for _, item in rows], dtype=np.float32)
        if arr.ndim != 2 or arr.shape[0] != len(texts) or arr.shape[1] <= 0:
            raise RuntimeError(
                f"OpenAI-compatible /embeddings returned invalid shape {arr.shape} "
                f"for {self.model_id}"
            )
        self._write_log(
            {
                "model": parsed.model or self.model_id,
                "requested_model": self.model_id,
                "latency_ms": latency_ms,
                "n_texts": len(texts),
                "input_chars": sum(len(str(text)) for text in texts),
                "embedding_dim": int(arr.shape[1]),
            }
        )
        return arr

    def _pace(self) -> None:
        if self.min_interval_s <= 0:
            return
        now = time.monotonic()
        wait_s = self.min_interval_s - (now - self._last_request_at)
        if wait_s > 0:
            self._write_log(
                {
                    "model": self.model_id,
                    "requested_model": self.model_id,
                    "pace_sleep_s": wait_s,
                }
            )
            time.sleep(wait_s)
        self._last_request_at = time.monotonic()

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}{path}"
        is_local = _is_loopback_url(url)
        inputs = payload.get("input")
        input_count = len(inputs) if isinstance(inputs, list) else None
        input_chars = sum(len(str(item)) for item in inputs) if isinstance(inputs, list) else None
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=openai_compatible_headers(
                api_key=self.api_key or ("dummy" if is_local else None),
                api_key_env=self.api_key_env,
                extra_headers=self.extra_headers,
            ),
            method="POST",
        )
        last_exc: BaseException | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with _urlopen(req, url=url, timeout=self.timeout_s) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data
            except urllib.error.HTTPError as exc:
                last_exc = exc
                body = ""
                try:
                    body = exc.read().decode("utf-8")[:500]
                except Exception:
                    pass
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    delay = self.backoff_s * (2**attempt)
                    self._write_log(
                        {
                            "model": self.model_id,
                            "requested_model": self.model_id,
                            "error": f"HTTP {exc.code}: {body}",
                            "retry_in_s": delay,
                            "attempt": attempt + 1,
                            "n_texts": input_count,
                            "input_chars": input_chars,
                        }
                    )
                    print(
                        f"[api-call:retry] provider=embedding-openai-compatible {url} returned HTTP {exc.code}; "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/"
                        f"{self.max_retries})",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue
                print(
                    f"[api-call:error] provider=embedding-openai-compatible url={url} "
                    f"HTTP {exc.code}: {body}",
                    flush=True,
                )
                raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    delay = self.backoff_s * (2**attempt)
                    self._write_log(
                        {
                            "model": self.model_id,
                            "requested_model": self.model_id,
                            "error": f"{type(exc).__name__}: {exc}",
                            "retry_in_s": delay,
                            "attempt": attempt + 1,
                            "n_texts": input_count,
                            "input_chars": input_chars,
                        }
                    )
                    print(
                        f"[api-call:retry] provider=embedding-openai-compatible {url} failed ({exc}); retrying in "
                        f"{delay:.1f}s (attempt {attempt + 1}/{self.max_retries})",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue
                break
        raise RuntimeError(
            f"OpenAI-compatible embedding request failed at {url}: {last_exc}"
        ) from last_exc

    def _write_log(self, row: dict[str, Any]) -> None:
        if not self.log_path:
            return
        path = os.fspath(self.log_path)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


# --------------------------------------------------------------------- #
# FakeEmbedder — hermetic test stub                                      #
# --------------------------------------------------------------------- #


@dataclass
class FakeEmbedder:
    """Deterministic non-ML embedder for tests and the e2e smoke script.

    Mirrors `ask.inference.fake.FakeLLM`'s role for the LLM Protocol.

    Hashes each input string into a `dim`-vector via repeated SHA-256,
    then L2-normalizes. Properties:
      * Same input → same vector across runs / OSes / Python versions.
      * Different inputs → essentially-orthogonal vectors (sufficient
        for "find the embedded text by exact match" tests).
      * `embed("foo")` and `embed(["foo"])` agree byte-for-byte.

    NOT a model. Exists purely so tests can exercise the
    `FlatVectorStore` and `FlatVectorBaseline` plumbing without dragging
    in torch / sentence-transformers.
    """

    embedding_dim: int = 32
    model_id: str = "fake/embed-sha256-1"

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        out: np.ndarray = np.zeros((len(texts), self.embedding_dim), dtype=np.float32)
        for i, t in enumerate(texts):
            out[i] = _sha256_to_vec(t, self.embedding_dim)
        # L2-normalize — same contract as TurnEmbedder.
        return _l2_normalize_rows(out)


def _sha256_to_vec(text: str, dim: int) -> np.ndarray:
    """Deterministic text → `(dim,)` float32 vector via repeated SHA-256.

    Each 4-byte chunk of digest output is interpreted as a uint32 and
    mapped to [-1, 1]. Repeats hashing with a counter prefix until the
    output has `dim` floats. Pure stdlib; no external deps.
    """
    import hashlib
    import struct

    raw = b""
    counter = 0
    while len(raw) < dim * 4:
        h = hashlib.sha256(f"{counter}|{text}".encode()).digest()
        raw += h
        counter += 1
    raw = raw[: dim * 4]
    ints = struct.unpack(f"<{dim}I", raw)
    # Map each uint32 to [-1, 1).
    arr = np.array(ints, dtype=np.uint32).astype(np.float64)
    arr = arr / (2**31) - 1.0
    return arr.astype(np.float32, copy=False)


# Sanity check at import time: both implementations satisfy Embedder.
assert isinstance(FakeEmbedder(), Embedder)  # noqa: S101 — module-level invariant
# Note: not asserting TurnEmbedder() satisfies Embedder at import time
# because the Protocol check would force the model to load (via the
# `embedding_dim` property). The runtime test
# `test_turn_embedder_satisfies_protocol_after_load` covers it.
