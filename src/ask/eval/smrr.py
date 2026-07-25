"""Stale-memory retrieval rate utilities.

SMRR is only meaningful when a run has a gold notion of superseded memory.
LongMemEval-S does not natively provide action-level supersession labels, so
the final thesis should report this metric only for constructed/evaluable
settings such as MGP-6 or explicitly audited retrieval rows.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SMRRResult:
    stale_retrieval_count: int
    smrr_denominator: int
    stale_memory_texts: tuple[str, ...] = ()

    @property
    def smrr(self) -> float | None:
        if self.smrr_denominator == 0:
            return None
        return self.stale_retrieval_count / self.smrr_denominator

    def to_dict(self) -> dict[str, Any]:
        return {
            "stale_retrieval_count": self.stale_retrieval_count,
            "smrr_denominator": self.smrr_denominator,
            "smrr": self.smrr,
            "stale_memory_texts": list(self.stale_memory_texts),
            "smrr_status": "computed",
        }


def normalize_memory_text(value: Any) -> str:
    """Normalize memory text for deterministic fixture-level equivalence."""
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def compute_smrr(
    retrieved_items: Iterable[Mapping[str, Any]],
    stale_items: Iterable[Mapping[str, Any]],
    *,
    text_key: str = "text",
) -> SMRRResult:
    """Compute stale retrievals by normalized text overlap."""
    stale_texts = tuple(
        sorted(
            {
                normalize_memory_text(item.get(text_key, ""))
                for item in stale_items
                if normalize_memory_text(item.get(text_key, ""))
            }
        )
    )
    stale_set = set(stale_texts)
    retrieved = list(retrieved_items)
    stale_count = sum(
        1 for item in retrieved if normalize_memory_text(item.get(text_key, "")) in stale_set
    )
    return SMRRResult(
        stale_retrieval_count=stale_count,
        smrr_denominator=len(retrieved),
        stale_memory_texts=stale_texts,
    )


def mgp6_stale_items(scenario: Any) -> list[dict[str, Any]]:
    """Return initial MGP-6 memories that gold state no longer keeps active."""
    initial = [_dump(item) for item in getattr(scenario, "initial_memory_state", [])]
    gold = [_dump(item) for item in getattr(scenario, "gold_memory_state", [])]
    gold_active_ids = {str(item.get("id")) for item in gold if item.get("status", "active") == "active"}
    return [item for item in initial if str(item.get("id")) not in gold_active_ids]


def _dump(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    if hasattr(item, "model_dump"):
        return dict(item.model_dump())
    return {
        key: getattr(item, key)
        for key in ("id", "text", "status", "type")
        if hasattr(item, key)
    }
