"""Deterministic baseline controllers and fail-closed model adapters."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from mgp_natural.errors import ValidationError
from mgp_natural.mining.studychat import EXPLICIT_UPDATE, UNCERTAINTY
from mgp_natural.util.io import write_jsonl


class Controller(Protocol):
    name: str

    def predict(self, item: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class RunMetadata:
    model_identifier: str
    provider: str
    model_revision: str | None
    prompt_hash: str | None
    code_hash: str
    seed: int
    temperature: float
    tool_settings: dict[str, Any]
    retry_policy: str
    fallback_policy: str
    input_manifest_hash: str
    output_hash: str | None
    cost: float
    failure_count: int


class NoMemoryBaseline:
    name = "no-memory"

    def predict(self, item: dict[str, Any]) -> dict[str, Any]:
        return {"blind_id": item["blind_id"], "action": "ABSTAIN", "evidence_turn_ids": [item["candidate_turn_id"]]}


class RecencyBaseline:
    name = "recency"

    def predict(self, item: dict[str, Any]) -> dict[str, Any]:
        text = next(turn["text"] for turn in item["dialogue"] if turn["turn_id"] == item["candidate_turn_id"])
        action = "ABSTAIN" if UNCERTAINTY.search(text) else "KEEP"
        return {"blind_id": item["blind_id"], "action": action, "evidence_turn_ids": [item["candidate_turn_id"]]}


class OverwriteBaseline:
    name = "overwrite"

    def predict(self, item: dict[str, Any]) -> dict[str, Any]:
        candidate = next(turn["text"] for turn in item["dialogue"] if turn["turn_id"] == item["candidate_turn_id"])
        return {
            "blind_id": item["blind_id"],
            "action": "SUPERSEDE",
            "resulting_value": candidate,
            "evidence_turn_ids": [item["candidate_turn_id"]],
        }


class DeterministicRuleBaseline:
    name = "deterministic-rule"

    def predict(self, item: dict[str, Any]) -> dict[str, Any]:
        text = next(turn["text"] for turn in item["dialogue"] if turn["turn_id"] == item["candidate_turn_id"])
        if UNCERTAINTY.search(text):
            action = "ABSTAIN"
        elif EXPLICIT_UPDATE.search(text):
            action = "SUPERSEDE"
        else:
            action = "KEEP"
        row = {"blind_id": item["blind_id"], "action": action, "evidence_turn_ids": [item["candidate_turn_id"]]}
        if action == "SUPERSEDE":
            row["resulting_value"] = text
        return row


class ExternalModelAdapter:
    """Frozen interface; network use requires explicit caller authorization."""

    def __init__(self, provider: str, model_identifier: str, authorized: bool = False) -> None:
        self.provider = provider
        self.model_identifier = model_identifier
        self.authorized = authorized

    def predict(self, item: dict[str, Any]) -> dict[str, Any]:
        if not self.authorized:
            raise ValidationError("external model call blocked: explicit authorization required")
        raise ValidationError("no provider implementation configured; silent fallback is disabled")


def run_controller(controller: Controller, items: list[dict[str, Any]], output_path: Path) -> str:
    rows = [controller.predict(item) for item in items]
    write_jsonl(output_path, rows)
    return hashlib.sha256(output_path.read_bytes()).hexdigest()


def metadata_for_offline_run(
    name: str,
    input_manifest_hash: str,
    code_hash: str,
    output_hash: str,
    seed: int = 1729,
) -> RunMetadata:
    return RunMetadata(
        model_identifier=name,
        provider="local-deterministic",
        model_revision=None,
        prompt_hash=None,
        code_hash=code_hash,
        seed=seed,
        temperature=0.0,
        tool_settings={},
        retry_policy="none",
        fallback_policy="disabled",
        input_manifest_hash=input_manifest_hash,
        output_hash=output_hash,
        cost=0.0,
        failure_count=0,
    )

