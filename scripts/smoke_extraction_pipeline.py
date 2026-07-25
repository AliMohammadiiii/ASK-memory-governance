#!/usr/bin/env python3
"""Smoke test: extractor output -> SQLite memory row -> action log."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.audit import ActionLogWriter  # noqa: E402
from ask.memory import (  # noqa: E402
    ActionLogEntry,
    ControllerAction,
    MemoryItem,
    MemoryType,
    connect,
    init_schema,
    insert_active,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--extractions", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    db_path = args.out_dir / "extraction_smoke.sqlite"
    log_path = args.out_dir / "action_log.jsonl"
    if db_path.exists():
        db_path.unlink()

    conn = connect(db_path)
    init_schema(conn)
    inserted = 0
    with ActionLogWriter(log_path, baseline="controller") as writer:
        with args.extractions.open("r", encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                for item in rec["output"]["items"]:
                    span = item["evidence_span"]
                    cur = conn.execute(
                        """
                        INSERT INTO evidence_spans
                            (session_id, turn_index, start_char, end_char, text)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            span["session_id"],
                            span["turn_idx"],
                            span["char_start"],
                            span["char_end"],
                            item["text"],
                        ),
                    )
                    evidence_id = cur.lastrowid
                    mem_id = insert_active(
                        conn,
                        MemoryItem(
                            id=None,
                            type=MemoryType(item["type_guess"]),
                            text=item["text"],
                            confidence=float(item["extraction_confidence"]),
                        ),
                        evidence_span_ids=[evidence_id],
                    )
                    inserted += 1
                    writer.write(
                        ActionLogEntry(
                            id=inserted,
                            timestamp=datetime.now(UTC),
                            action=ControllerAction.KEEP,
                            candidate_text=item["text"],
                            rationale="extraction admit",
                            session_id=rec["session_id"],
                            baseline="controller",
                            candidate_type=MemoryType(item["type_guess"]),
                            resulting_memory_id=mem_id,
                        )
                    )

    conn.close()
    summary = {"db_path": str(db_path), "action_log_path": str(log_path), "inserted": inserted}
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
