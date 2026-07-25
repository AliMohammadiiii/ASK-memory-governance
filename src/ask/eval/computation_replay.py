"""No-LLM replay harness for the deterministic computation answerer."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from ask.controller.computation import ComputedAnswer, RetrievedEvidence, compute_answer
from ask.data.longmemeval import LongMemEvalSession, iter_longmemeval_s

ReplayMode = Literal["supporting", "haystack"]

_PROMPT_ITEM_RE = re.compile(
    r"^\[(?P<score>[0-9.]+)\]\s+"
    r"(?P<role>[A-Z]+)\s+"
    r"\(session\s+(?P<session_id>[^,()]+),\s+turn\s+(?P<turn_idx>\d+)"
    r"(?:,\s+(?P<timestamp>.*))?\):\s*(?P<text>.*)$"
)
_PROMPT_START = "----- RETRIEVED MEMORY"
_PROMPT_END_MARKERS = (
    "----- TEMPORAL",
    "----- NORMALIZED EVENT DATES",
    "----- DETERMINISTIC",
    "----- DIALOG -----",
    "----- QUESTION -----",
)


def retrieved_from_prompt(raw_prompt: str) -> list[RetrievedEvidence]:
    """Parse retrieved-memory prompt rows into computation evidence.

    This intentionally understands the repository's rendered prompt format
    rather than a private in-memory object, so saved ``answers.jsonl`` files can
    be replayed without rerunning retrieval or model inference.
    """
    block = _retrieved_block(raw_prompt)
    rows: list[RetrievedEvidence] = []
    current: dict[str, object] | None = None
    text_parts: list[str] = []
    for line in block.splitlines():
        match = _PROMPT_ITEM_RE.match(line)
        if match:
            if current is not None:
                rows.append(_evidence_from_match(current, text_parts))
            current = match.groupdict()
            text_parts = [str(current.pop("text") or "")]
            continue
        if current is not None:
            text_parts.append(line)
    if current is not None:
        rows.append(_evidence_from_match(current, text_parts))
    return rows


def evidence_from_session(
    session: LongMemEvalSession,
    *,
    mode: ReplayMode = "supporting",
) -> list[RetrievedEvidence]:
    """Build oracle or haystack evidence from a cleaned LongMemEval session."""
    selected = set(session.supporting_session_ids) if mode == "supporting" else None
    rows: list[RetrievedEvidence] = []
    for corpus_session in session.corpus_sessions:
        if selected is not None and corpus_session.session_id not in selected:
            continue
        for idx, turn in enumerate(corpus_session.turns):
            rows.append(
                RetrievedEvidence(
                    session_id=corpus_session.session_id,
                    turn_idx=idx,
                    role=turn.role,
                    text=turn.content,
                    timestamp=turn.timestamp,
                    score=1.0,
                )
            )
    if rows or session.corpus_sessions:
        return rows
    for idx, turn in enumerate(session.turns):
        rows.append(
            RetrievedEvidence(
                session_id=session.session_id,
                turn_idx=idx,
                role=turn.role,
                text=turn.content,
                timestamp=turn.timestamp,
                score=1.0,
            )
        )
    return rows


def simulate_computation_on_slice(
    slice_path: str | Path,
    *,
    mode: ReplayMode = "supporting",
    session_id: str | None = None,
) -> list[dict[str, object]]:
    """Run the computation answerer over a slice without any LLM calls."""
    rows = []
    for session in iter_longmemeval_s(slice_path):
        if session_id is not None and session.session_id != session_id:
            continue
        evidence = evidence_from_session(session, mode=mode)
        result = compute_answer(session.question, evidence, question_date=session.question_date)
        rows.append(_result_row(session, result, len(evidence), source=mode))
    return rows


def simulate_computation_on_answers(
    slice_path: str | Path,
    answers_path: str | Path,
    *,
    session_id: str | None = None,
) -> list[dict[str, object]]:
    """Replay computation from saved answer prompts instead of oracle evidence."""
    sessions = {session.session_id: session for session in iter_longmemeval_s(slice_path)}
    rows = []
    with Path(answers_path).open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            answer = json.loads(line)
            sid = str(answer.get("session_id") or "")
            if session_id is not None and sid != session_id:
                continue
            session = sessions.get(sid)
            if session is None:
                continue
            evidence = retrieved_from_prompt(str(answer.get("raw_prompt") or ""))
            result = compute_answer(session.question, evidence, question_date=session.question_date)
            rows.append(_result_row(session, result, len(evidence), source="prompt"))
    return rows


def _retrieved_block(raw_prompt: str) -> str:
    start = raw_prompt.find(_PROMPT_START)
    if start < 0:
        return raw_prompt
    end_candidates = [
        raw_prompt.find(marker, start + len(_PROMPT_START)) for marker in _PROMPT_END_MARKERS
    ]
    end_candidates = [idx for idx in end_candidates if idx >= 0]
    end = min(end_candidates) if end_candidates else len(raw_prompt)
    return raw_prompt[start:end]


def _evidence_from_match(raw: dict[str, object], text_parts: list[str]) -> RetrievedEvidence:
    score_raw = str(raw.get("score") or "")
    try:
        score = float(score_raw)
    except ValueError:
        score = None
    return RetrievedEvidence(
        session_id=str(raw["session_id"]),
        turn_idx=int(str(raw["turn_idx"])),
        role=str(raw["role"]).casefold(),
        text="\n".join(text_parts).strip(),
        timestamp=str(raw["timestamp"]) if raw.get("timestamp") else None,
        score=score,
    )


def _result_row(
    session: LongMemEvalSession,
    result: ComputedAnswer | None,
    evidence_count: int,
    *,
    source: str,
) -> dict[str, object]:
    return {
        "session_id": session.session_id,
        "competency": session.competency,
        "question": session.question,
        "gold_answer": session.gold_answer,
        "question_date": session.question_date,
        "evidence_source": source,
        "evidence_count": evidence_count,
        "intent": None if result is None else result.intent.value,
        "computed_answer": None if result is None else result.answer,
        "confidence": None if result is None else result.confidence,
        "safe_to_bypass": False if result is None else result.safe_to_bypass_llm,
        "computation": None if result is None else result.computation,
    }
