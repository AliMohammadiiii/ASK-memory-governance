"""Baseline 4 — naive overwrite.

This baseline uses the same extractor, relation classifier, retrieval, and
answer prompt as the controller pipeline. The only difference is policy:
there is no Abstain action and relation contradictions destructively delete the
prior row before inserting the candidate, leaving no supersession lineage.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from ..audit import ActionLogWriter
from ..memory import ActionLogEntry, ControllerAction, MemoryType, insert_active
from ..pipeline.orchestrator import (
    CandidateContext,
    ControllerOrchestrator,
    MemoryProvenance,
    PipelineDecision,
    _db_item,
    _provenance,
    _require_id,
    relation_label,
)


@dataclass
class NaiveOverwriteBaseline(ControllerOrchestrator):
    """LLM-extractor baseline with destructive overwrite on contradictions."""

    BASELINE_NAME: str = "naive_overwrite"

    def _process_candidate(
        self,
        conn: sqlite3.Connection,
        candidate: CandidateContext,
        provenance: dict[int, MemoryProvenance],
        decisions: list[PipelineDecision],
        log_writer: ActionLogWriter | None,
    ) -> None:
        prior, relation, _prior_map = self._select_prior_relation(conn, candidate, provenance)

        relation_value = relation_label(relation)
        action = (
            ControllerAction.SUPERSEDE
            if prior is not None and relation_value in {"contradict", "supersede"}
            else ControllerAction.KEEP
        )
        prior_id = _require_id(prior) if prior is not None else None
        resulting_id = self._execute_naive(conn, candidate, provenance, prior_id, action)
        rationale = self._rationale(action, relation_value, prior_id, resulting_id)

        decisions.append(
            PipelineDecision(
                candidate_id=candidate.candidate_id,
                session_id=candidate.session_id,
                turn_idx=candidate.turn_idx,
                candidate_text=candidate.item.text,
                candidate_type=candidate.item.type_guess,
                action=action,
                prior_memory_id=prior_id,
                resulting_memory_id=resulting_id,
                rationale=rationale,
                relation=relation_value,
            )
        )
        self._write_naive_decision(
            log_writer,
            candidate,
            action,
            rationale,
            prior_id,
            resulting_id,
        )

    def _execute_naive(
        self,
        conn: sqlite3.Connection,
        candidate: CandidateContext,
        provenance: dict[int, MemoryProvenance],
        prior_id: int | None,
        action: ControllerAction,
    ) -> int:
        if action == ControllerAction.SUPERSEDE and prior_id is not None:
            conn.execute("DELETE FROM memory_items WHERE id = ?", (prior_id,))
            provenance.pop(prior_id, None)

        new_id = insert_active(conn, _db_item(candidate))
        provenance[new_id] = _provenance(candidate)
        return new_id

    def _rationale(
        self,
        action: ControllerAction,
        relation: str | None,
        prior_id: int | None,
        resulting_id: int | None,
    ) -> str:
        relation_text = relation or "no_prior"
        if action == ControllerAction.SUPERSEDE:
            return (
                f"naive overwrite: relation={relation_text}; deleted prior id={prior_id} "
                f"and inserted candidate id={resulting_id}; no supersession lineage."
            )
        if prior_id is None:
            return (
                f"naive overwrite: relation={relation_text}; no prior slot; "
                f"inserted candidate id={resulting_id}."
            )
        return (
            f"naive overwrite: relation={relation_text}; inserted candidate id={resulting_id} "
            "directly; no abstain policy."
        )

    def _write_naive_decision(
        self,
        writer: ActionLogWriter | None,
        candidate: CandidateContext,
        action: ControllerAction,
        rationale: str,
        prior_id: int | None,
        resulting_id: int | None,
    ) -> None:
        if writer is None:
            return
        writer.write(
            ActionLogEntry(
                id=self._next_log_id,
                timestamp=datetime.now(UTC),
                action=action,
                candidate_text=candidate.item.text,
                rationale=rationale,
                session_id=candidate.session_id,
                baseline=self.BASELINE_NAME,
                candidate_type=MemoryType(candidate.item.type_guess),
                candidate_id=candidate.candidate_id,
                prior_memory_id=prior_id,
                resulting_memory_id=resulting_id,
            )
        )
        self._next_log_id += 1
