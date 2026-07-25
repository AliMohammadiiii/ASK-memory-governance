"""Schema invariants: constraints fire, enums restrict values."""

from __future__ import annotations

import sqlite3

import pytest

from ask.memory import MemoryItem, MemoryType, insert_active


def test_init_creates_tables(db: sqlite3.Connection) -> None:
    names = {
        row["name"]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    expected = {
        "memory_items",
        "evidence_spans",
        "memory_evidence",
        "memory_relations",
        "action_log",
    }
    assert expected.issubset(names)


def test_insert_active_roundtrip(db: sqlite3.Connection) -> None:
    mem = MemoryItem(
        id=None,
        type=MemoryType.STABLE_PREF,
        text="User likes coffee",
        confidence=0.9,
    )
    mem_id = insert_active(db, mem)
    row = db.execute(
        "SELECT * FROM memory_items WHERE id = ?", (mem_id,)
    ).fetchone()
    assert row["status"] == "active"
    assert row["type"] == "stable_pref"
    assert row["confidence"] == pytest.approx(0.9)


def test_type_check_constraint(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO memory_items (type, text, confidence) VALUES (?, ?, ?)",
            ("not_a_real_type", "x", 0.5),
        )


def test_confidence_range_constraint(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO memory_items (type, text, confidence) VALUES (?, ?, ?)",
            ("stable_pref", "x", 1.5),
        )


def test_action_log_enum(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO action_log (action, candidate_text, rationale)
            VALUES ('Delete', 'x', 'nope')
            """
        )
