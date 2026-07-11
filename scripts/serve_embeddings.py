"""Shared sentence-transformers embedding server (OpenAI-compatible).

Loads ONE embedder (e.g. jinaai/jina-embeddings-v5-text-small) on the GPU and
serves POST /v1/embeddings so every eval shard is a thin HTTP client. This
avoids loading the 677M jina model in each shard process (which either OOMs the
GPU or crawls on CPU). Requests are serialized on a lock because a single model
on one GPU is the bottleneck anyway; sentence-transformers batches each call.

Run:
  PYTHONPATH=src python scripts/serve_embeddings.py \
    --model jinaai/jina-embeddings-v5-text-small --task retrieval \
    --device cuda --host 0.0.0.0 --port 8100

Then point the eval at it:
  run_baseline ... --embedder-backend openai_compatible \
    --embedder-openai-model jina --embedder-openai-base-url http://localhost:8100/v1
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if "src" not in sys.path:
    sys.path.insert(0, "src")
from ksa.baselines.embeddings import TurnEmbedder  # noqa: E402

_EMBEDDER: TurnEmbedder | None = None
_MODEL_NAME = "embedding-model"
_DEVICE_INFO: dict[str, object] = {}
_LOCK = threading.Lock()


def _torch_device_info(requested_device: str) -> dict[str, object]:
    info: dict[str, object] = {"requested_device": requested_device}
    try:
        import torch  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        info["torch_import_error"] = f"{type(exc).__name__}: {exc}"
        return info
    info["torch_version"] = getattr(torch, "__version__", "unknown")
    info["torch_cuda_version"] = getattr(getattr(torch, "version", None), "cuda", None)
    cuda_available = bool(torch.cuda.is_available())
    info["cuda_available"] = cuda_available
    info["cuda_device_count"] = int(torch.cuda.device_count()) if cuda_available else 0
    if cuda_available:
        try:
            info["cuda_device_name"] = torch.cuda.get_device_name(0)
        except Exception as exc:  # noqa: BLE001
            info["cuda_device_name_error"] = f"{type(exc).__name__}: {exc}"
    return info


def _model_device_summary(model: object) -> str:
    device = getattr(model, "device", None)
    if device is not None:
        return str(device)
    try:
        module = model._first_module()
        module_device = getattr(module, "device", None)
        if module_device is not None:
            return str(module_device)
    except Exception:
        pass
    try:
        for param in model.parameters():  # type: ignore[attr-defined]
            return str(param.device)
    except Exception:
        pass
    return "unknown"


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/health", "/ping"):
            self._send(200, {"status": "ok", "model": _MODEL_NAME, "device": _DEVICE_INFO})
        elif self.path.rstrip("/").endswith("/models") or self.path.rstrip("/") == "/v1/models":
            self._send(200, {"object": "list", "data": [{"id": _MODEL_NAME, "object": "model"}]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.rstrip("/").endswith("embeddings"):
            self._send(404, {"error": f"unknown path {self.path}"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": f"bad request: {exc}"})
            return
        inputs = req.get("input")
        if isinstance(inputs, str):
            inputs = [inputs]
        if not isinstance(inputs, list) or not all(isinstance(t, str) for t in inputs):
            self._send(400, {"error": "'input' must be a string or list of strings"})
            return
        assert _EMBEDDER is not None
        try:
            with _LOCK:
                vecs = _EMBEDDER.embed(inputs)
        except Exception as exc:  # noqa: BLE001
            # Print the full server-side cause (OOM, shape, etc.) so failures
            # are diagnosable from the embed-server terminal, not just a 500.
            print(f"[embed-server] ERROR on {len(inputs)} inputs: "
                  f"{type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc()
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
            return
        data = [
            {"object": "embedding", "index": i, "embedding": vecs[i].tolist()}
            for i in range(len(inputs))
        ]
        self._send(200, {
            "object": "list",
            "model": req.get("model") or _MODEL_NAME,
            "data": data,
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        })

    def log_message(self, fmt: str, *args) -> None:  # quieter logs
        return


def main() -> int:
    global _DEVICE_INFO, _EMBEDDER, _MODEL_NAME
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="jinaai/jina-embeddings-v5-text-small")
    p.add_argument("--served-name", default="jina")
    p.add_argument("--task", default="retrieval")
    p.add_argument("--prompt-name", default=None)
    p.add_argument("--device", default="cuda")
    p.add_argument("--trust-remote-code", action="store_true", default=True)
    p.add_argument("--batch-size", type=int, default=16,
                   help="Encode chunk size. Keep modest: a single LongMemEval-M "
                        "haystack is thousands of turns, and a huge batch spikes "
                        "GPU activation memory (OOM when vLLM already owns most "
                        "of the card).")
    p.add_argument("--max-seq-length", type=int, default=512,
                   help="Maximum token length for sentence-transformers encoding. "
                        "Jina v5 is Qwen3-based; long turns can OOM a T4 unless "
                        "they are truncated.")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8100)
    args = p.parse_args()

    _MODEL_NAME = args.served_name
    _DEVICE_INFO = _torch_device_info(args.device)
    print(f"[embed-server] torch/device info: {json.dumps(_DEVICE_INFO, sort_keys=True)}",
          flush=True)
    if args.device.lower().startswith("cuda") and not _DEVICE_INFO.get("cuda_available"):
        raise SystemExit(
            "[embed-server] requested --device cuda but torch.cuda.is_available() is false. "
            "Use a GPU runtime and install a CUDA-enabled torch build before starting."
        )
    print(f"[embed-server] loading {args.model} task={args.task} device={args.device} "
          f"batch_size={args.batch_size}", flush=True)
    _EMBEDDER = TurnEmbedder(
        model_id=args.model, device=args.device,
        trust_remote_code=args.trust_remote_code, task=args.task,
        prompt_name=args.prompt_name, batch_size=args.batch_size,
    )
    _EMBEDDER._ensure_loaded()
    if args.max_seq_length > 0:
        _EMBEDDER._model.max_seq_length = int(args.max_seq_length)
        print(f"[embed-server] max_seq_length={args.max_seq_length}", flush=True)
    dim = _EMBEDDER.embedding_dim  # force load + resolve dim
    actual_device = _model_device_summary(_EMBEDDER._model)
    _DEVICE_INFO["model_device"] = actual_device
    print(
        f"[embed-server] ready: dim={dim} served-name={_MODEL_NAME} "
        f"model_device={actual_device} on {args.host}:{args.port}",
        flush=True,
    )
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
