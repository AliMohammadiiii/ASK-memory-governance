"""Memory schema operations — load-bearing substrate tests (M1-W4 §3.1).

This is the substrate test suite the rest of the thesis depends on.
Every later component (extractor, controller, qualitative analysis,
chapter writing) trusts these invariants. If any of these regress, the
W4 acceptance criteria are not met even if the report.json technically
exists. See `NOTES/m1w4_design.md` §3.1 for the operations contract.
"""

from __future__ import annotations

import sqlite3

import pytest

from ksa.memory import (
    MemoryItem,
    MemoryStatus,
    MemoryType,
    get_by_id,
    get_lineage,
    insert_active,
    retrieve_active,
    supersede,
    supersede_evict,
)

# --------------------------------------------------------------------- #
# Helpers                                                                #
# --------------------------------------------------------------------- #


def _mk(text: str, type_: MemoryType = MemoryType.EPISODIC_FACT, conf: float = 1.0) -> MemoryItem:
    return MemoryItem(id=None, type=type_, text=text, confidence=conf)


# --------------------------------------------------------------------- #
# Insert                                                                 #
# --------------------------------------------------------------------- #


def test_insert_n_items_active_count_equals_n_and_ids_monotonic(db: sqlite3.Connection) -> None:
    """Insert N items; count(*) WHERE status='active' equals N; ids monotonic."""
    n = 7
    ids = [insert_active(db, _mk(f"item-{i}")) for i in range(n)]

    # Active count == n.
    count = db.execute(
        "SELECT COUNT(*) AS c FROM memory_items WHERE status = 'active'"
    ).fetchone()["c"]
    assert count == n

    # Ids monotonically increasing.
    assert ids == sorted(ids)
    assert len(set(ids)) == n  # unique

    # Each row has the expected text + type.
    items = retrieve_active(db)
    assert [it.text for it in items] == [f"item-{i}" for i in range(n)]
    assert all(it.status == MemoryStatus.ACTIVE for it in items)


def test_insert_active_rejects_non_active_status(db: sqlite3.Connection) -> None:
    """insert_active() requires status=active. Defensive contract."""
    bad = MemoryItem(
        id=None,
        type=MemoryType.EPISODIC_FACT,
        text="x",
        confidence=1.0,
        status=MemoryStatus.SUPERSEDED,
    )
    with pytest.raises(ValueError):
        insert_active(db, bad)


# --------------------------------------------------------------------- #
# Supersede                                                              #
# --------------------------------------------------------------------- #


def test_supersede_flips_prior_inserts_replacement_and_writes_relation(
    db: sqlite3.Connection,
) -> None:
    a_id = insert_active(db, _mk("likes coffee", MemoryType.STABLE_PREF, 0.9))
    b_id = supersede(
        db,
        new_item=_mk("drinks tea", MemoryType.STABLE_PREF, 0.85),
        prior_id=a_id,
    )

    # Post-state.
    a = db.execute("SELECT * FROM memory_items WHERE id = ?", (a_id,)).fetchone()
    b = db.execute("SELECT * FROM memory_items WHERE id = ?", (b_id,)).fetchone()
    assert a["status"] == "superseded"
    assert b["status"] == "active"
    assert b["supersedes_id"] == a_id

    # Relation row exists.
    rel = db.execute(
        "SELECT relation FROM memory_relations WHERE from_memory_id = ? AND to_memory_id = ?",
        (b_id, a_id),
    ).fetchone()
    assert rel is not None and rel["relation"] == "supersedes"


def test_supersede_is_atomic_under_forced_exception(
    db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A forced exception mid-transaction leaves NEITHER the insert NOR the flip.

    This is the §3.1 acceptance check that fails Gate G1 if it regresses.
    We force the failure by patching `insert_active` to raise after the
    BEGIN IMMEDIATE acquires the lock.
    """
    a_id = insert_active(db, _mk("original"))

    # Capture the count of active rows before.
    before = db.execute(
        "SELECT COUNT(*) AS c FROM memory_items WHERE status = 'active'"
    ).fetchone()["c"]
    assert before == 1

    # Patch `insert_active` (called by supersede) to raise.
    import ksa.memory.operations as ops

    def _raise(*_a: object, **_kw: object) -> int:
        raise RuntimeError("forced mid-transaction failure")

    monkeypatch.setattr(ops, "insert_active", _raise)

    with pytest.raises(RuntimeError, match="forced mid-transaction"):
        supersede(db, new_item=_mk("replacement"), prior_id=a_id)

    # Post-state: prior row is STILL active (no flip), no new row exists.
    after = db.execute(
        "SELECT COUNT(*) AS c FROM memory_items WHERE status = 'active'"
    ).fetchone()["c"]
    assert after == 1, f"atomicity violated: active count went {before} → {after}"

    a_status = db.execute(
        "SELECT status FROM memory_items WHERE id = ?", (a_id,)
    ).fetchone()["status"]
    assert a_status == "active", "atomicity violated: prior row was flipped despite rollback"


def test_supersede_double_supersede_raises_loudly(db: sqlite3.Connection) -> None:
    """Two consecutive supersede calls on the same prior_id — second must fail.

    The §3.1 concurrency-friendliness check. SQLite-level row-version
    test is sufficient here.
    """
    a_id = insert_active(db, _mk("v1"))
    b_id = supersede(db, new_item=_mk("v2"), prior_id=a_id)
    # First supersede succeeded; a is now superseded.

    # A second supersede of the same prior_id must fail.
    with pytest.raises(RuntimeError, match="not active"):
        supersede(db, new_item=_mk("v2-bis"), prior_id=a_id)

    # Post-state: only b is active; no half-superseded mess.
    actives = retrieve_active(db)
    assert len(actives) == 1
    assert actives[0].id == b_id
    assert actives[0].text == "v2"


# --------------------------------------------------------------------- #
# Retrieve-active                                                        #
# --------------------------------------------------------------------- #


def test_retrieve_active_excludes_superseded_even_when_more_relevant(
    db: sqlite3.Connection,
) -> None:
    """With 10 active and 5 superseded items, retrieve_active() returns exactly 10.

    The 5 superseded ones never appear, even when query similarity to a
    superseded item is higher than to any active item. (We do not run a
    similarity query here — `retrieve_active` is the active-only filter
    primitive; the FAISS path is exercised in `test_recency_pruning.py`.)
    """
    active_ids = [insert_active(db, _mk(f"keep-{i}")) for i in range(10)]
    super_seeded_ids = [insert_active(db, _mk(f"old-{i}")) for i in range(5)]
    for prior in super_seeded_ids:
        supersede(db, new_item=_mk(f"new-replacement-{prior}"), prior_id=prior)

    actives = retrieve_active(db)

    # Exactly the 10 originally active + the 5 replacement rows from the
    # supersedes = 15 active rows total. Every superseded id MUST be
    # absent from the active result.
    active_id_set = {it.id for it in actives}
    assert len(actives) == 15
    for prior in super_seeded_ids:
        assert prior not in active_id_set, f"superseded id {prior} leaked into retrieve_active"
    for kept in active_ids:
        assert kept in active_id_set, f"active id {kept} missing from retrieve_active"


def test_retrieve_active_type_filter(db: sqlite3.Connection) -> None:
    """With mixed types, retrieve_active(type='stable_pref') returns only stable_prefs."""
    stable_id = insert_active(db, _mk("user likes coffee", MemoryType.STABLE_PREF, 0.9))
    transient_id = insert_active(
        db, _mk("user wants to leave by 5pm", MemoryType.TRANSIENT_PREF, 0.7)
    )
    fact_id = insert_active(db, _mk("meeting was at 2pm", MemoryType.EPISODIC_FACT, 0.95))

    only_stable = retrieve_active(db, memory_type=MemoryType.STABLE_PREF)
    assert [it.id for it in only_stable] == [stable_id]

    only_transient = retrieve_active(db, memory_type=MemoryType.TRANSIENT_PREF)
    assert [it.id for it in only_transient] == [transient_id]

    only_fact = retrieve_active(db, memory_type=MemoryType.EPISODIC_FACT)
    assert [it.id for it in only_fact] == [fact_id]


# --------------------------------------------------------------------- #
# Lineage                                                                #
# --------------------------------------------------------------------- #


def test_lineage_three_step_chain(db: sqlite3.Connection) -> None:
    """A→B→C: get_lineage(C) returns [A, B, C]; get_lineage(B) returns [A, B]."""
    a_id = insert_active(db, _mk("v1"))
    b_id = supersede(db, new_item=_mk("v2"), prior_id=a_id)
    c_id = supersede(db, new_item=_mk("v3"), prior_id=b_id)

    lineage_c = get_lineage(db, c_id)
    assert [it.id for it in lineage_c] == [a_id, b_id, c_id]
    assert [it.text for it in lineage_c] == ["v1", "v2", "v3"]

    lineage_b = get_lineage(db, b_id)
    assert [it.id for it in lineage_b] == [a_id, b_id]
    assert [it.text for it in lineage_b] == ["v1", "v2"]

    lineage_a = get_lineage(db, a_id)
    assert [it.id for it in lineage_a] == [a_id]


def test_get_by_id_returns_regardless_of_status(db: sqlite3.Connection) -> None:
    """get_by_id walks BOTH active and superseded rows. Audit-time access."""
    a_id = insert_active(db, _mk("v1"))
    supersede(db, new_item=_mk("v2"), prior_id=a_id)

    a = get_by_id(db, a_id)
    assert a is not None
    assert a.status == MemoryStatus.SUPERSEDED
    assert a.text == "v1"


def test_get_by_id_returns_none_for_missing(db: sqlite3.Connection) -> None:
    assert get_by_id(db, 9999) is None


# --------------------------------------------------------------------- #
# Supersede-evict (the FIFO primitive)                                   #
# --------------------------------------------------------------------- #


def test_supersede_evict_flips_status_no_lineage_no_relation(db: sqlite3.Connection) -> None:
    """The recency-pruning eviction path. Destructiveness is the contract.

    Post-state:
      * row.status = 'superseded'
      * row.supersedes_id IS STILL NULL (no pointer; no replacement)
      * NO row in memory_relations
      * get_lineage(id) returns [id] (no chain — destructiveness)
    """
    a_id = insert_active(db, _mk("evictee"))

    supersede_evict(db, prior_id=a_id)

    row = db.execute("SELECT * FROM memory_items WHERE id = ?", (a_id,)).fetchone()
    assert row["status"] == "superseded"
    assert row["supersedes_id"] is None, "FIFO eviction must NOT set supersedes_id"

    rel = db.execute(
        "SELECT * FROM memory_relations WHERE to_memory_id = ?", (a_id,)
    ).fetchone()
    assert rel is None, "FIFO eviction must NOT write a memory_relations row"

    # Lineage walk is single-element: lineage destruction is the point.
    lineage = get_lineage(db, a_id)
    assert [it.id for it in lineage] == [a_id]


def test_supersede_evict_double_evict_raises(db: sqlite3.Connection) -> None:
    """Two consecutive supersede_evict on the same prior_id — second must fail loudly."""
    a_id = insert_active(db, _mk("evictee"))
    supersede_evict(db, prior_id=a_id)

    with pytest.raises(RuntimeError, match="not active"):
        supersede_evict(db, prior_id=a_id)


def test_supersede_evict_missing_id_raises(db: sqlite3.Connection) -> None:
    with pytest.raises(RuntimeError, match="does not exist"):
        supersede_evict(db, prior_id=9999)
