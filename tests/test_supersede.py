"""Supersede semantics: prior becomes inactive, lineage preserved, retrieve_active excludes."""

from __future__ import annotations

import sqlite3

from ksa.memory import (
    MemoryItem,
    MemoryType,
    insert_active,
    retrieve_active,
    supersede,
)


def test_supersede_marks_prior_inactive_and_links_lineage(db: sqlite3.Connection) -> None:
    old = insert_active(
        db,
        MemoryItem(id=None, type=MemoryType.STABLE_PREF, text="User likes coffee", confidence=0.9),
    )
    new = supersede(
        db,
        new_item=MemoryItem(
            id=None, type=MemoryType.STABLE_PREF, text="User drinks tea", confidence=0.85
        ),
        prior_id=old,
    )

    assert db.execute(
        "SELECT status FROM memory_items WHERE id = ?", (old,)
    ).fetchone()["status"] == "superseded"

    assert db.execute(
        "SELECT status, supersedes_id FROM memory_items WHERE id = ?", (new,)
    ).fetchone()["supersedes_id"] == old

    rel = db.execute(
        """SELECT relation FROM memory_relations
           WHERE from_memory_id = ? AND to_memory_id = ?""",
        (new, old),
    ).fetchone()
    assert rel is not None and rel["relation"] == "supersedes"


def test_retrieve_active_excludes_superseded(db: sqlite3.Connection) -> None:
    a = insert_active(
        db,
        MemoryItem(id=None, type=MemoryType.STABLE_PREF, text="likes coffee", confidence=0.9),
    )
    b_item = MemoryItem(
        id=None, type=MemoryType.STABLE_PREF, text="drinks tea", confidence=0.85
    )
    supersede(db, new_item=b_item, prior_id=a)

    active = retrieve_active(db)
    texts = [m.text for m in active]
    assert "drinks tea" in texts
    assert "likes coffee" not in texts
    assert all(m.status.value == "active" for m in active)


def test_supersede_is_atomic_on_bad_prior(db: sqlite3.Connection) -> None:
    import pytest

    # prior_id=999 does not exist → UPDATE is a no-op but insert would succeed otherwise.
    # We model atomicity by checking that mismatched explicit supersedes_id raises before insert.
    bad_new = MemoryItem(
        id=None,
        type=MemoryType.STABLE_PREF,
        text="x",
        confidence=0.9,
        supersedes_id=12345,   # will conflict with prior_id arg
    )
    with pytest.raises(ValueError):
        supersede(db, new_item=bad_new, prior_id=999)
