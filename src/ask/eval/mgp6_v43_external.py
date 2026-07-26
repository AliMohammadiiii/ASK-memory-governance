"""Public-only adapter protocol for external memory systems on MGP-6 v4.3.

MGP-6 asks for a governance action, whereas published memory products expose
storage and retrieval primitives rather than ``KEEP``/``SUPERSEDE``/``ABSTAIN``.
This module therefore records a *derived* action from the adapter's observable
post-write state.  It must never be reported as a native action of Mem0,
Graphiti, Letta, or MemOS.

The conversion deliberately accepts only :meth:`MGP6V43Record.model_input`.
Development labels remain available to the separate public scorer, but are
never sent to an external backend or written into backend observations.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ask.eval.mgp6_v43 import MGP6V43Record, assert_model_safe

EXTERNAL_MGP6V43_BACKENDS = ("mem0", "graphiti", "letta", "memos")
EXTERNAL_DERIVATION_VERSION = "observable-state-v1"
_REQUESTED_VALUE_RE = re.compile(r"\brequested value is\s+(.+?)[.?!]?\s*$", re.IGNORECASE)


class ExternalWriteObservation(Protocol):
    """Minimal native-write result used by the v4.3 harness."""

    replaced_old: bool
    committed_new: bool
    raw: Any


class ExternalMemoryBackend(Protocol):
    """Common synchronous surface implemented by the optional external adapters."""

    name: str

    def reset(self, scenario_id: str) -> None: ...

    def seed(self, records: list[dict[str, Any]], dialogue: list[dict[str, str]]) -> None: ...

    def write(self, text: str) -> ExternalWriteObservation: ...

    def snapshot(self) -> list[str]: ...

    def search(self, query: str, k: int = 5) -> list[str]: ...

    def close(self) -> None: ...

    def meta(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class DerivedExternalAction:
    """A schema-safe prediction plus the public evidence for its derivation."""

    action: str
    state_classification: str
    prior_value_present: bool
    candidate_value_present: bool


def _normalise(value: str) -> str:
    return " ".join(value.lower().split())


def _contains(texts: list[str], value: str | None) -> bool:
    if not value:
        return False
    return _normalise(value) in _normalise("\n".join(texts))


def requested_value(record: MGP6V43Record) -> str | None:
    """Extract the explicitly public closing request, if one is present."""
    for turn in reversed(record.model_input()["dialogue"]):
        if not isinstance(turn, Mapping):
            continue
        text = turn.get("text")
        if isinstance(text, str):
            match = _REQUESTED_VALUE_RE.search(text)
            if match:
                return match.group(1).strip(" .,:;!?\\\"'")
    return None


def backend_seed_payload(
    record: MGP6V43Record,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Convert a public record to the legacy adapters' generic text contract."""
    model_input = record.model_input()
    memory_before = model_input["memory_before"]
    if not isinstance(memory_before, Mapping):
        raise ValueError("v4.3 memory_before must be an object")
    slot = memory_before.get("memory_slot", "unspecified memory slot")
    principal = memory_before.get("principal", "the user")
    standing_value = memory_before.get("standing_value", "")
    prior_text = f"Stored memory: {principal}'s {slot} is {standing_value}."
    records = [{"status": "active", "text": prior_text}]
    dialogue: list[dict[str, str]] = []
    for turn in model_input["dialogue"]:
        if not isinstance(turn, Mapping):
            continue
        text = turn.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        speaker = str(turn.get("speaker", "USER")).upper()
        dialogue.append(
            {"role": "assistant" if speaker == "ASSISTANT" else "user", "content": text}
        )
    payload = {"records": records, "dialogue": dialogue, "query": model_input["evaluation_query"]}
    assert_model_safe(payload)
    return records, dialogue


def derive_external_action(
    *, prior_value: str | None, candidate_value: str | None, post_texts: list[str]
) -> DerivedExternalAction:
    """Map observable state to an action without consulting a development label.

    ``ABSTAIN`` is intentionally used for both ambiguous dual-active state and
    unavailable evidence: external stores do not expose MGP-6's typed lineage.
    The classification field keeps those cases distinguishable in audit output.
    """
    prior_present = _contains(post_texts, prior_value)
    candidate_present = _contains(post_texts, candidate_value)
    if candidate_value and prior_value and _normalise(candidate_value) == _normalise(prior_value):
        return DerivedExternalAction(
            "KEEP", "candidate_equals_prior", prior_present, candidate_present
        )
    if candidate_present and not prior_present:
        return DerivedExternalAction(
            "SUPERSEDE", "candidate_only", prior_present, candidate_present
        )
    if prior_present and not candidate_present:
        return DerivedExternalAction("KEEP", "prior_only", prior_present, candidate_present)
    if prior_present and candidate_present:
        return DerivedExternalAction(
            "ABSTAIN", "dual_active_ambiguous", prior_present, candidate_present
        )
    return DerivedExternalAction(
        "ABSTAIN", "state_unavailable_or_candidate_missing", prior_present, candidate_present
    )


def run_external_record(
    backend: ExternalMemoryBackend, record: MGP6V43Record, *, retrieval_k: int = 5
) -> dict[str, Any]:
    """Drive exactly one isolated public record through an external backend."""
    model_input = record.model_input()
    records, dialogue = backend_seed_payload(record)
    namespace = f"mgp6-v43:{record.public_id}"
    backend.reset(namespace)
    # Initial stored state is seeded verbatim.  Every dialogue turn then uses
    # the backend's native write path, preserving the order supplied publicly.
    backend.seed(records, [])
    writes: list[dict[str, Any]] = []
    for index, turn in enumerate(dialogue, start=1):
        observation = backend.write(f"{turn['role']}: {turn['content']}")
        writes.append(
            {
                "turn_index": index,
                "role": turn["role"],
                "replaced_old": bool(observation.replaced_old),
                "committed_new": bool(observation.committed_new),
                "native_observation": observation.raw,
            }
        )
    post_texts = [str(value) for value in backend.snapshot() if str(value).strip()]
    retrieved = [
        str(value) for value in backend.search(model_input["evaluation_query"], k=retrieval_k)
    ]
    standing_value = model_input["memory_before"].get("standing_value")
    prior_value = str(standing_value) if isinstance(standing_value, str) else None
    candidate_value = requested_value(record)
    derived = derive_external_action(
        prior_value=prior_value, candidate_value=candidate_value, post_texts=post_texts
    )
    result = {
        "public_id": record.public_id,
        "namespace": namespace,
        "derived_action": derived.action,
        "derivation_version": EXTERNAL_DERIVATION_VERSION,
        "state_classification": derived.state_classification,
        "prior_value_present": derived.prior_value_present,
        "candidate_value_present": derived.candidate_value_present,
        "candidate_value": candidate_value,
        "native_writes": writes,
        "post_state": post_texts[:50],
        "retrieved_memories": retrieved[:retrieval_k],
    }
    assert_model_safe(result)
    return result
