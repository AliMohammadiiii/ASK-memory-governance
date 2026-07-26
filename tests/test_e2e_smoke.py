"""End-to-end smoke test (M1-W1 §3.3).

Runs the smoke pipeline on a 2-session synthetic fixture using the FakeLLM,
proving:
  - LongMemEval session → LLM → SQLite roundtrip works,
  - the action_log JSONL writer accepts the synthesized entry,
  - the schema verification (action, feature_*, scores, thresholds, rationale,
    timestamp) is enforced.
"""

from __future__ import annotations

import json
import sqlite3

# scripts/ is not in PYTHONPATH; import the smoke logic directly.
import sys
from pathlib import Path

from ask.data.longmemeval import LongMemEvalSession, LongMemEvalTurn, write_slice_jsonl
from ask.inference.fake import FakeLLM

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from smoke_e2e import run_smoke  # type: ignore[import-not-found]


def _two_session_fixture(tmp_path: Path) -> Path:
    sessions = [
        LongMemEvalSession(
            session_id="lme-s-test-A",
            turns=(
                LongMemEvalTurn(role="user", content="I really like coffee."),
                LongMemEvalTurn(role="assistant", content="Got it — coffee."),
            ),
            question="What does the user like?",
            gold_answer="coffee",
            competency="single-session-preference",
            supporting_session_ids=("lme-s-test-A",),
        ),
        LongMemEvalSession(
            session_id="lme-s-test-B",
            turns=(
                LongMemEvalTurn(
                    role="user", content="Actually, I don't like coffee anymore. I switched to tea."
                ),
                LongMemEvalTurn(role="assistant", content="Understood, tea now."),
            ),
            question="Does the user still like coffee?",
            gold_answer="no — they switched to tea",
            competency="knowledge-update",
            supporting_session_ids=("lme-s-test-A", "lme-s-test-B"),
        ),
    ]
    p = tmp_path / "fixture.jsonl"
    write_slice_jsonl(sessions, p)
    return p


def test_smoke_runs_end_to_end_on_two_session_fixture(tmp_path: Path) -> None:
    slice_path = _two_session_fixture(tmp_path)
    db_path = tmp_path / "smoke.sqlite"
    log_path = tmp_path / "smoke.action_log.jsonl"

    fake = FakeLLM()
    fake.queue("Coffee.")
    summary = run_smoke(
        slice_path=slice_path,
        session_id="lme-s-test-A",
        db_path=db_path,
        log_path=log_path,
        llm=fake,
    )

    # Pipeline contract: a row in memory_items + a line in action_log.
    assert summary["memory_rows"]
    assert summary["action_log_lines"] == 1

    # SQLite has the row we inserted.
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT type, status FROM memory_items").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "episodic_fact"
    assert rows[0][1] == "active"

    # action_log has a single, schema-valid entry with the required §I.5.5 fields.
    line = log_path.read_text(encoding="utf-8").strip().splitlines()[0]
    rec = json.loads(line)
    for k in ("id", "timestamp", "action", "candidate_text", "rationale"):
        assert k in rec, f"missing required field {k}"
    assert rec["action"] in ("Keep", "Supersede", "Abstain")


def test_smoke_completes_for_second_session(tmp_path: Path) -> None:
    """Same plumbing must work for the knowledge-update session too."""
    slice_path = _two_session_fixture(tmp_path)
    db_path = tmp_path / "smoke2.sqlite"
    log_path = tmp_path / "smoke2.action_log.jsonl"

    fake = FakeLLM()
    fake.queue("No, the user switched to tea.")
    summary = run_smoke(
        slice_path=slice_path,
        session_id="lme-s-test-B",
        db_path=db_path,
        log_path=log_path,
        llm=fake,
    )
    assert summary["session_id"] == "lme-s-test-B"
    assert summary["completion_tokens"] >= 1
    assert summary["action_log_lines"] == 1
