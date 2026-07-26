#!/usr/bin/env python3
"""Letta (MemGPT) external baseline on MGP-6 v2 (Packer et al., 2023).

Letta is agentic: the agent itself edits its memory blocks with
core_memory_replace / core_memory_append tool calls, and answers questions
from its own memory. So this adapter (a) observes the agent's memory-edit
tool calls for the action mapping and (b) uses the agent's NATIVE answer
(flagged `native_answer` in extras — Letta's answerer is its own loop, not
the shared answer prompt; report this in the paper).

Setup (once) — requires a local Letta server (Docker):
    docker run -d --name letta -p 8283:8283 \
      -e OPENAI_API_KEY="$OPENROUTER_API_KEY" \
      -e OPENAI_API_BASE="https://openrouter.ai/api/v1" \
      letta/letta:latest
    pip install letta-client
    # pick the model handle your server exposes (client.models.list()):
    export LETTA_MODEL="openai/qwen/qwen3.5-9b"

BETA adapter: the letta-client SDK surface moves quickly; ALWAYS smoke-test
first and, if a call fails, check `client.agents` method names against your
installed letta-client version.

Smoke test:
    python3 external/run_letta.py --limit 2 --out runs/ext_letta_smoke/controller
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import ExternalAdapter, WriteObservation, run_external  # noqa: E402

LETTA_URL = os.environ.get("LETTA_BASE_URL", "http://localhost:8283")
LETTA_MODEL = os.environ.get("LETTA_MODEL", "openai/qwen/qwen3.5-9b")
PERSONA = (
    "I am a personal assistant. I maintain accurate long-term memory "
    "about the user and update it when the user's information changes."
)


class LettaAdapter(ExternalAdapter):
    name = "letta"
    answers_natively = True

    def __init__(self) -> None:
        try:
            from letta_client import Letta
        except ImportError as exc:
            raise SystemExit("letta-client not installed: pip install letta-client") from exc
        self.client = Letta(base_url=LETTA_URL)
        self.agent_id: str | None = None

    # -- protocol ----------------------------------------------------------
    def reset(self, scenario_id: str) -> None:
        if self.agent_id:
            try:
                self.client.agents.delete(self.agent_id)
            except Exception:  # noqa: BLE001
                pass
        agent = self.client.agents.create(
            name=f"mgp6-{scenario_id.lower()}",
            model=LETTA_MODEL,
            memory_blocks=[
                {"label": "persona", "value": PERSONA},
                {"label": "human", "value": ""},
                {
                    "label": "context",
                    "value": "",
                    "read_only": True,
                },
            ],
        )
        self.agent_id = agent.id

    def _blocks_text(self) -> list[str]:
        blocks = self.client.agents.blocks.list(agent_id=self.agent_id)
        excluded_labels = {"persona", "context"}
        return [
            f"{b.label}: {b.value}"
            for b in blocks
            if getattr(b, "label", "") not in excluded_labels and getattr(b, "value", "")
        ]

    def seed(self, records: list[dict[str, Any]], dialogue: list[dict[str, str]]) -> None:
        facts = "\n".join(
            r.get("text", "") for r in records if r.get("status") == "active" and r.get("text")
        )
        dlg = "\n".join(
            f"{m.get('role')}: {m.get('content')}" for m in dialogue if m.get("content")
        )
        human = f"Known user facts:\n{facts}"
        context = f"Earlier dialogue:\n{dlg}" if dlg else "Earlier dialogue: (none)"

        self.client.agents.blocks.update(
            block_label="human",
            agent_id=self.agent_id,
            value=human,
        )
        self.client.agents.blocks.update(
            block_label="context",
            agent_id=self.agent_id,
            value=context,
        )

    def _send(self, text: str) -> Any:
        return self.client.agents.messages.create(
            agent_id=self.agent_id, messages=[{"role": "user", "content": text}]
        )

    def write(self, text: str) -> WriteObservation:
        response = self._send(text)
        tool_calls = []
        for msg in getattr(response, "messages", []) or []:
            tc = getattr(msg, "tool_call", None)
            if tc is not None:
                tool_calls.append(getattr(tc, "name", "") or "")
            name = getattr(msg, "tool_call_name", None) or getattr(msg, "name", None)
            if name:
                tool_calls.append(str(name))
        replaced = any(
            any(
                name in t
                for name in (
                    "core_memory_replace",
                    "memory_replace",
                    "memory_rethink",
                )
            )
            for t in tool_calls
        )
        appended = any(
            any(
                name in t
                for name in (
                    "core_memory_append",
                    "memory_insert",
                    "archival_memory_insert",
                )
            )
            for t in tool_calls
        )
        return WriteObservation(
            replaced_old=replaced,
            committed_new=replaced or appended,
            raw={"tool_calls": tool_calls},
        )

    def snapshot(self) -> list[str]:
        return self._blocks_text()

    def search(self, query: str, k: int = 5) -> list[str]:
        return self._blocks_text()[:k]

    def answer_natively(self, query: str) -> str | None:
        response = self._send(query)
        for msg in reversed(getattr(response, "messages", []) or []):
            content = getattr(msg, "content", None)
            mtype = str(getattr(msg, "message_type", ""))
            if content and ("assistant" in mtype or mtype == ""):
                return str(content)
        return None

    def close(self) -> None:
        if self.agent_id:
            try:
                self.client.agents.delete(self.agent_id)
            except Exception:  # noqa: BLE001
                pass

    def meta(self) -> dict[str, Any]:
        return {
            "letta_url": LETTA_URL,
            "letta_model": LETTA_MODEL,
            "note": "native agent answers; answer model = letta agent",
        }


if __name__ == "__main__":
    raise SystemExit(run_external(LettaAdapter))
