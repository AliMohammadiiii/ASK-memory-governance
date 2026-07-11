#!/usr/bin/env python3
"""Mem0 external baseline on MGP-6 v2 (Chhikara et al., 2025).

Native write path: `Memory.add(..., infer=True)` — Mem0's own LLM decides
ADD / UPDATE / DELETE / NONE per fact. We map: UPDATE|DELETE -> replaced;
ADD -> committed; NONE -> NOOP (dual-mapped by the framework).

Setup (once):
    pip install "mem0ai==2.0.11" qdrant-client sentence-transformers
    export OPENROUTER_API_KEY=sk-or-...   # mem0 auto-detects OpenRouter

Notes:
- LLM: OpenRouter model from MGP6_MODEL (default qwen/qwen3.5-9b) — the same
  backbone as the other LLM systems, so the comparison isolates the memory
  layer, not the model.
- Embedder: local sentence-transformers all-MiniLM-L6-v2 (no API cost),
  the same embedder family as the LongMemEval pipeline.
- Vector store: embedded Qdrant at a per-run temp path (no server).
- Isolation: one mem0 user_id per scenario.

Smoke test first:
    python3 external/run_mem0.py --limit 2 --out runs/ext_mem0_smoke/controller
Full run:
    python3 external/run_mem0.py --out runs/ext_mem0/controller
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import ExternalAdapter, WriteObservation, run_external  # noqa: E402

MODEL = os.environ.get("MGP6_MODEL", "qwen/qwen3.5-9b")


class Mem0Adapter(ExternalAdapter):
    name = "mem0"

    def __init__(self) -> None:
        try:
            from mem0 import Memory
        except ImportError as exc:
            raise SystemExit(
                "mem0 not installed: pip install 'mem0ai==2.0.11' "
                "qdrant-client sentence-transformers") from exc
        
        modal_url = os.environ.get("MODAL_ENDPOINT_URL")
        if modal_url:
            import openai
            modal_base_url = f"{modal_url.rstrip('/')}/v1"
            
            def make_patched_init(original_init):
                def patched_init(self, *args, **kwargs):
                    kwargs["base_url"] = modal_base_url
                    kwargs["api_key"] = "dummy"
                    
                    default_headers = kwargs.get("default_headers") or {}
                    m_key = os.getenv("MODAL_KEY")
                    m_secret = os.getenv("MODAL_SECRET")
                    if m_key:
                        default_headers["Modal-Key"] = m_key
                    if m_secret:
                        default_headers["Modal-Secret"] = m_secret
                    kwargs["default_headers"] = default_headers
                    
                    original_init(self, *args, **kwargs)
                return patched_init

            for client_cls in (openai.OpenAI, openai.AsyncOpenAI):
                client_cls.__init__ = make_patched_init(client_cls.__init__)

        self._tmp = tempfile.mkdtemp(prefix="mgp6_mem0_")
        config = {
            "llm": {"provider": "openai",
                    "config": {"model": MODEL, "temperature": 0.0,
                               "max_tokens": 800}},
            "embedder": {"provider": "huggingface",
                         "config": {"model": "sentence-transformers/all-MiniLM-L6-v2",
                                    "embedding_dims": 384}},
            "vector_store": {"provider": "qdrant",
                             "config": {"path": self._tmp,
                                        "collection_name": "mgp6_ext",
                                        "embedding_model_dims": 384,
                                        "on_disk": False}},
        }
        self.memory = Memory.from_config(config)
        self.user_id = "unset"

    # -- protocol ----------------------------------------------------------
    def reset(self, scenario_id: str) -> None:
        self.user_id = scenario_id
        try:
            self.memory.delete_all(filters={"user_id": self.user_id})
        except Exception:  # noqa: BLE001 - fresh user has nothing to delete
            pass

    def seed(self, records: list[dict[str, Any]],
             dialogue: list[dict[str, str]]) -> None:
        facts = [r.get("text", "") for r in records
                 if r.get("status") == "active" and r.get("text")]
        if facts:
            # infer=False installs the prior state verbatim (ground truth).
            self.memory.add([{"role": "user", "content": t} for t in facts],
                            user_id=self.user_id, infer=False)
        turns = [{"role": m.get("role", "user"), "content": m.get("content", "")}
                 for m in dialogue if m.get("content")]
        if turns:
            self.memory.add(turns, user_id=self.user_id, infer=False)

    def write(self, text: str) -> WriteObservation:
        res = self.memory.add([{"role": "user", "content": text}],
                              user_id=self.user_id, infer=True)
        events = [str(r.get("event", "")).upper()
                  for r in (res or {}).get("results", [])]
        return WriteObservation(
            replaced_old=any(e in ("UPDATE", "DELETE") for e in events),
            committed_new=any(e in ("ADD", "UPDATE") for e in events),
            raw={"events": events})

    def snapshot(self) -> list[str]:
        res = self.memory.get_all(filters={"user_id": self.user_id})
        items = res.get("results", res) if isinstance(res, dict) else res
        return [str(m.get("memory", "")) for m in items if m.get("memory")]

    def search(self, query: str, k: int = 5) -> list[str]:
        res = self.memory.search(query, filters={"user_id": self.user_id}, limit=k)
        items = res.get("results", res) if isinstance(res, dict) else res
        return [str(m.get("memory", "")) for m in items if m.get("memory")]

    def close(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def meta(self) -> dict[str, Any]:
        try:
            import mem0
            version = getattr(mem0, "__version__", "unknown")
        except ImportError:
            version = "unknown"
        return {"mem0_version": version, "llm_model": MODEL,
                "embedder": "all-MiniLM-L6-v2", "vector_store": "qdrant(local)"}


if __name__ == "__main__":
    raise SystemExit(run_external(Mem0Adapter))
