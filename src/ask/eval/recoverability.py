"""Superseded-memory recoverability: the lineage metric that tests H2.

SMRR (`ask.eval.smrr`) measures how many *stale* items remain active after a
revision. It cannot separate the controller from naive overwrite, because both
remove the stale item from the active set — they tie at the same SMRR by
construction (verified on runs/m4w14: controller and b4 both 22/65).

H2 is about *auditability*, not staleness: after a revision, can the system still
produce the superseded prior value and its lineage edge? That is exactly what
distinguishes lineage-preserving Supersede (prior kept as an inactive row linked
by ``supersedes_id``) from destructive overwrite (prior row deleted). This module
computes that distinction.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RecoverabilityResult:
    """Per-scenario recoverability of a superseded prior."""

    prior_id: str
    revision_occurred: bool
    superseded_record_present: bool
    lineage_edge_present: bool

    @property
    def recoverable(self) -> bool:
        return (
            self.revision_occurred and self.superseded_record_present and self.lineage_edge_present
        )


def recoverability_for_scenario(
    prior_id: str,
    memory_state: Iterable[Mapping[str, Any]],
) -> RecoverabilityResult:
    """Assess whether the prior is still recoverable after a revision.

    A revision is considered to have occurred when the prior is no longer
    *active* in the final state (it was either superseded or deleted). The prior
    is recoverable only when it survives as an inactive (``superseded``) row and
    some active row carries a ``supersedes_id`` lineage edge back to it.
    """
    items = list(memory_state)
    prior_active = False
    superseded_record_present = False
    for item in items:
        if str(item.get("id")) == str(prior_id):
            status = str(item.get("status", "active"))
            if status == "active":
                prior_active = True
            elif status == "superseded":
                superseded_record_present = True
    lineage_edge_present = any(
        str(item.get("supersedes_id")) == str(prior_id)
        and str(item.get("status", "active")) == "active"
        for item in items
    )
    return RecoverabilityResult(
        prior_id=str(prior_id),
        revision_occurred=not prior_active,
        superseded_record_present=superseded_record_present,
        lineage_edge_present=lineage_edge_present,
    )


def aggregate_recoverability(results: Iterable[RecoverabilityResult]) -> dict[str, Any]:
    """Aggregate per-scenario results into a system-level rate.

    The denominator is the number of scenarios in which a revision actually
    occurred; scenarios the system left unrevised (correct or not) are excluded
    so the metric scores the auditability of the revisions the system *made*.
    """
    rows = list(results)
    revised = [row for row in rows if row.revision_occurred]
    recoverable = sum(1 for row in revised if row.recoverable)
    denominator = len(revised)
    return {
        "n_scenarios": len(rows),
        "n_revisions": denominator,
        "n_recoverable": recoverable,
        "superseded_recoverability": None if denominator == 0 else recoverable / denominator,
    }
