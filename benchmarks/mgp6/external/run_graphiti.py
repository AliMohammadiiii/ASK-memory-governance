#!/usr/bin/env python3
"""Zep/Graphiti external baseline on MGP-6 v2.

Optimized setup:
- FalkorDB server via Docker on localhost:6379
- Local MiniLM embeddings on localhost:8100
- Modal/OpenRouter LLM through an isolated AsyncOpenAI client
- Native json_schema structured output
- Configurable Graphiti internal concurrency
- Resume-safe per-scenario graph cleanup
- No heavyweight BGE cross-encoder
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from graphiti_core.cross_encoder.client import CrossEncoderClient

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import ExternalAdapter, WriteObservation, run_external  # noqa: E402

MODEL = os.environ.get("MGP6_MODEL", "qwen/qwen3.5-9b")

BASE_URL = os.environ.get(
    "MGP6_BASE_URL",
    "https://openrouter.ai/api/v1",
)

EMBED_URL = os.environ.get(
    "GRAPHITI_EMBED_URL",
    os.environ.get("MGP6_EMBED_BASE_URL", "http://localhost:8100/v1"),
)

EMBED_MODEL = os.environ.get(
    "GRAPHITI_EMBED_MODEL",
    os.environ.get("MGP6_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
)

EMBED_DIM = int(
    os.environ.get(
        "GRAPHITI_EMBED_DIM",
        os.environ.get("MGP6_EMBED_DIM", "384"),
    )
)

FALKOR_HOST = os.environ.get(
    "GRAPHITI_FALKORDB_HOST",
    "127.0.0.1",
)

FALKOR_PORT = int(
    os.environ.get(
        "GRAPHITI_FALKORDB_PORT",
        "6379",
    )
)

FALKOR_DATABASE = os.environ.get(
    "GRAPHITI_FALKORDB_DATABASE",
    "mgp6_graphiti",
)

MAX_COROUTINES = int(
    os.environ.get(
        "GRAPHITI_MAX_COROUTINES",
        "4",
    )
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _graphiti_group_id(scenario_id: str) -> str:
    """Translate the public-run namespace to Graphiti's restricted ID form.

    The v4.3 harness deliberately records ``mgp6-v43:<public_id>`` as its
    public namespace.  Graphiti accepts only alphanumerics, dashes, and
    underscores in a group ID, so the adapter uses an equivalent internal
    spelling while leaving the public audit namespace untouched.
    """
    return re.sub(r"[^a-z0-9_-]", "_", scenario_id.lower())


class _NoThinkingCompletions:
    """Inject non-thinking mode into every chat completion."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    async def create(self, *args: Any, **kwargs: Any) -> Any:
        # Align every external LLM call with the frozen ASK controller's
        # deterministic decoding policy.
        kwargs.setdefault("temperature", 0.0)
        extra_body = dict(kwargs.get("extra_body") or {})

        chat_template_kwargs = dict(extra_body.get("chat_template_kwargs") or {})
        chat_template_kwargs["enable_thinking"] = False

        extra_body["reasoning"] = {"enabled": False}
        extra_body["chat_template_kwargs"] = chat_template_kwargs
        kwargs["extra_body"] = extra_body

        return await self._inner.create(*args, **kwargs)


class _NoThinkingChat:
    def __init__(self, inner: Any) -> None:
        self.completions = _NoThinkingCompletions(inner.completions)


class NoThinkingOpenAIClientProxy:
    """Transparent AsyncOpenAI proxy forcing Qwen non-thinking mode."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.chat = _NoThinkingChat(inner.chat)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class PassthroughCrossEncoder(CrossEncoderClient):
    """Preserve retrieval order without loading a reranker model."""

    async def rank(
        self,
        query: str,
        passages: list[str],
    ) -> list[tuple[str, float]]:
        del query
        n = len(passages)
        return [(passage, float(n - i)) for i, passage in enumerate(passages)]


class GraphitiAdapter(ExternalAdapter):
    name = "graphiti"

    def __init__(self) -> None:
        try:
            import openai
            from graphiti_core import Graphiti
            from graphiti_core.driver.falkordb_driver import FalkorDriver
            from graphiti_core.embedder.openai import (
                OpenAIEmbedder,
                OpenAIEmbedderConfig,
            )
            from graphiti_core.llm_client.config import LLMConfig
            from graphiti_core.llm_client.openai_generic_client import (
                OpenAIGenericClient,
            )
        except ImportError as exc:
            raise SystemExit(
                "Graphiti/FalkorDB dependencies missing. Install with:\n"
                "pip install 'graphiti-core[falkordb]==0.29.2'"
            ) from exc

        self._loop = asyncio.new_event_loop()

        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")

        llm_headers: dict[str, str] = {}

        llm_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "base_url": BASE_URL,
            "max_retries": 8,
            "timeout": httpx.Timeout(
                connect=30.0,
                read=600.0,
                write=60.0,
                pool=60.0,
            ),
        }

        if llm_headers:
            llm_kwargs["default_headers"] = llm_headers

        llm_openai_client: Any = openai.AsyncOpenAI(
            **llm_kwargs,
        )

        # Qwen3.5 thinks by default. Graphiti extraction does not need
        # long chain-of-thought; force direct structured responses.
        llm_openai_client = NoThinkingOpenAIClientProxy(llm_openai_client)

        llm = OpenAIGenericClient(
            config=LLMConfig(
                api_key=api_key,
                model=MODEL,
                base_url=BASE_URL,
            ),
            client=llm_openai_client,
            max_tokens=int(
                os.environ.get(
                    "GRAPHITI_LLM_MAX_TOKENS",
                    "2048",
                )
            ),
            structured_output_mode="json_schema",
        )

        # Completely independent local embedding client.
        embed_openai_client = openai.AsyncOpenAI(
            api_key="local",
            base_url=EMBED_URL,
            max_retries=3,
            timeout=httpx.Timeout(
                connect=10.0,
                read=180.0,
                write=180.0,
                pool=30.0,
            ),
        )

        embedder = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key="local",
                base_url=EMBED_URL,
                embedding_model=EMBED_MODEL,
                embedding_dim=EMBED_DIM,
            ),
            client=embed_openai_client,
        )

        # External FalkorDB server running in Docker.
        driver = FalkorDriver(
            host=FALKOR_HOST,
            port=FALKOR_PORT,
            database=FALKOR_DATABASE,
        )

        self.graphiti = Graphiti(
            graph_driver=driver,
            llm_client=llm,
            embedder=embedder,
            cross_encoder=PassthroughCrossEncoder(),
            max_coroutines=MAX_COROUTINES,
        )

        self._run(self.graphiti.build_indices_and_constraints())

        self.group_id = "unset"
        self._episode_i = 0

        print(
            "[graphiti-config] "
            f"model={MODEL} "
            f"llm={BASE_URL} "
            f"embed={EMBED_URL} "
            f"embed_dim={EMBED_DIM} "
            f"falkor={FALKOR_HOST}:{FALKOR_PORT}/{FALKOR_DATABASE} "
            f"max_coroutines={MAX_COROUTINES}"
        )

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    # -- protocol ----------------------------------------------------------

    def reset(self, scenario_id: str) -> None:
        self.group_id = _graphiti_group_id(scenario_id)
        self._episode_i = 0

        # Important for Docker/persistent DB:
        # clear any partial state from a previously failed attempt.
        t0 = time.perf_counter()

        self._run(
            self.graphiti.driver.execute_query(
                """
                MATCH (n {group_id: $group_id})
                DETACH DELETE n
                """,
                group_id=self.group_id,
            )
        )

        print(f"[graphiti-timing] reset={time.perf_counter() - t0:.2f}s group={self.group_id}")

    def _add(
        self,
        body: str,
        desc: str,
    ) -> Any:
        from graphiti_core.nodes import EpisodeType

        self._episode_i += 1

        t0 = time.perf_counter()

        result = self._run(
            self.graphiti.add_episode(
                name=(f"{self.group_id}-ep{self._episode_i}"),
                episode_body=body,
                source_description=desc,
                reference_time=(T0 + timedelta(days=self._episode_i)),
                source=EpisodeType.message,
                group_id=self.group_id,
            )
        )

        print(f"[graphiti-timing] add_episode[{self._episode_i}]={time.perf_counter() - t0:.2f}s")

        return result

    def seed(
        self,
        records: list[dict[str, Any]],
        dialogue: list[dict[str, str]],
    ) -> None:
        lines = [f"user: {m.get('content', '')}" for m in dialogue if m.get("content")]

        lines += [
            f"user: {r.get('text', '')}"
            for r in records
            if (r.get("status") == "active" and r.get("text"))
        ]

        if lines:
            self._add(
                "\n".join(lines),
                "session_1 prior memory",
            )

    def _edges(
        self,
        query: str,
        k: int = 20,
    ) -> list[Any]:
        t0 = time.perf_counter()

        result = (
            self._run(
                self.graphiti.search(
                    query=query,
                    group_ids=[self.group_id],
                    num_results=k,
                )
            )
            or []
        )

        print(f"[graphiti-timing] search={time.perf_counter() - t0:.2f}s k={k}")

        return result

    def write(
        self,
        text: str,
    ) -> WriteObservation:
        before = {e.uuid: e.invalid_at for e in self._edges(text)}

        result = self._add(
            f"user: {text}",
            "session_2 new event",
        )

        after_edges = self._edges(text)

        newly_invalidated = [
            e for e in after_edges if (e.invalid_at is not None and before.get(e.uuid) is None)
        ]

        new_edges = (
            getattr(
                result,
                "edges",
                None,
            )
            or []
        )

        return WriteObservation(
            replaced_old=bool(newly_invalidated),
            committed_new=bool(new_edges),
            raw={
                "n_new_edges": len(new_edges),
                "n_newly_invalidated": len(newly_invalidated),
            },
        )

    def snapshot(self) -> list[str]:
        seen: set[str] = set()
        texts: list[str] = []

        for e in self._edges(
            "user preference fact value",
            k=40,
        ):
            if e.invalid_at is None and e.fact not in seen:
                seen.add(e.fact)
                texts.append(e.fact)

        return texts

    def search(
        self,
        query: str,
        k: int = 5,
    ) -> list[str]:
        out: list[str] = []

        for e in self._edges(
            query,
            k=k * 3,
        ):
            status = " [outdated]" if e.invalid_at is not None else ""

            out.append(f"{e.fact}{status}")

            if len(out) >= k:
                break

        return out

    def close(self) -> None:
        try:
            self._run(self.graphiti.close())
        except Exception as exc:  # noqa: BLE001
            print(
                "[graphiti] close warning:",
                exc,
            )
        finally:
            self._loop.close()

    def meta(self) -> dict[str, Any]:
        return {
            "graphiti_version": "0.29.2",
            "driver": "falkordb-docker",
            "falkordb_host": FALKOR_HOST,
            "falkordb_port": FALKOR_PORT,
            "falkordb_database": FALKOR_DATABASE,
            "llm_model": MODEL,
            "llm_base_url": BASE_URL,
            "embed_url": EMBED_URL,
            "embed_model": EMBED_MODEL,
            "embed_dim": EMBED_DIM,
            "max_coroutines": MAX_COROUTINES,
            "cross_encoder": "passthrough",
        }


if __name__ == "__main__":
    raise SystemExit(run_external(GraphitiAdapter))
