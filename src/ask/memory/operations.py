"""Core memory operations: insert, supersede, retrieve-active, lineage walk.

These are the operations that every later component (extraction, controller,
supersession, the audit UI) plugs into. The substrate is load-bearing: bugs
introduced here propagate to the controller, the MGP-6 evaluation, and the
qualitative analysis. Test density in `tests/test_memory_operations.py`
matches that load-bearing position.

M1-W4 contract (see `NOTES/m1w4_design.md` §3.1):

* `insert_active(item)`         → returns row id; precondition `status=active`.
* `supersede(new_item, prior)`  → atomic insert + flip + relation row; returns new id.
* `retrieve_active(...)`        → only `status='active'` rows; optional type filter.
* `get_by_id(id)`               → returns row regardless of status (audit-time).
* `get_lineage(id)`             → full supersession chain ending at id, oldest first.
* `supersede_evict(prior_id, action_log_writer, ...)` → status flip with no replacement,
                                  the FIFO eviction primitive used by Baseline 3
                                  (recency-pruning). Destroys lineage by design;
                                  see `NOTES/m1w4_design.md` §1c.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from .models import MemoryItem, MemoryStatus, MemoryType

# --------------------------------------------------------------------- #
# Insert                                                                 #
# --------------------------------------------------------------------- #


def insert_active(
    conn: sqlite3.Connection,
    item: MemoryItem,
    evidence_span_ids: Iterable[int] = (),
) -> int:
    """Insert a new active memory_item and optional evidence links.

    Returns the new row's id. Precondition: `item.status == MemoryStatus.ACTIVE`.
    """
    if item.status != MemoryStatus.ACTIVE:
        raise ValueError("insert_active requires status=active")
    cur = conn.execute(
        """
        INSERT INTO memory_items (type, text, normalized_value, status, confidence,
                                  valid_from, supersedes_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item.type.value,
            item.text,
            item.normalized_value,
            item.status.value,
            item.confidence,
            item.valid_from.isoformat() if item.valid_from else None,
            item.supersedes_id,
        ),
    )
    mem_id = cur.lastrowid
    assert mem_id is not None
    for ev_id in evidence_span_ids:
        conn.execute(
            "INSERT OR IGNORE INTO memory_evidence (memory_id, evidence_id) VALUES (?, ?)",
            (mem_id, ev_id),
        )
    return mem_id


# --------------------------------------------------------------------- #
# Supersede (with replacement) — controller's primary write path         #
# --------------------------------------------------------------------- #


def supersede(
    conn: sqlite3.Connection,
    new_item: MemoryItem,
    prior_id: int,
    evidence_span_ids: Iterable[int] = (),
) -> int:
    """Atomically:
      1. Insert `new_item` as active with supersedes_id = prior_id.
      2. Mark prior_id as status='superseded'.
      3. Record a ('supersedes') edge in memory_relations.

    Returns the new row's id. Atomic via BEGIN IMMEDIATE / COMMIT — a
    forced exception mid-transaction leaves NEITHER the insert NOR the
    flip in the database (test
    `test_supersede_is_atomic_under_forced_exception` enforces this).

    Args:
        conn: open SQLite connection.
        new_item: the replacement MemoryItem; must have status=active.
        prior_id: the id of the row being superseded.
        evidence_span_ids: optional evidence to link to the new row.

    Raises:
        ValueError: if `new_item.supersedes_id` is set to anything other
            than None or `prior_id`.
        sqlite3.IntegrityError: if `prior_id` does not exist (FK on the
            relation row catches it; transaction rolls back).
        RuntimeError: if `prior_id` is not currently active (a
            double-supersede attempt; concurrency-friendliness check).
    """
    if new_item.supersedes_id not in (None, prior_id):
        raise ValueError("new_item.supersedes_id must match prior_id or be None")
    new_item.supersedes_id = prior_id

    # `BEGIN IMMEDIATE` acquires a write lock at txn start so a second
    # writer cannot race in between the insert and the UPDATE. Combined
    # with the row-version check below, this is sufficient for the
    # M1-W4 §3.1 concurrency-friendliness contract.
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Row-version-style check: the prior row must still be active.
        # If a prior `supersede` already fired against the same id, the
        # row is already 'superseded' and we refuse to flip it twice.
        prior_status = conn.execute(
            "SELECT status FROM memory_items WHERE id = ?", (prior_id,)
        ).fetchone()
        if prior_status is None:
            raise RuntimeError(f"supersede: prior_id={prior_id} does not exist")
        if prior_status["status"] != MemoryStatus.ACTIVE.value:
            raise RuntimeError(
                f"supersede: prior_id={prior_id} is not active "
                f"(current status: {prior_status['status']!r}). "
                "Refusing double-supersede."
            )

        new_id = insert_active(conn, new_item, evidence_span_ids=evidence_span_ids)
        conn.execute(
            "UPDATE memory_items SET status='superseded' WHERE id = ?",
            (prior_id,),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO memory_relations (from_memory_id, to_memory_id, relation)
            VALUES (?, ?, 'supersedes')
            """,
            (new_id, prior_id),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return new_id


# --------------------------------------------------------------------- #
# Supersede-evict — FIFO eviction primitive (Baseline 3 only)            #
# --------------------------------------------------------------------- #


def supersede_evict(conn: sqlite3.Connection, prior_id: int) -> None:
    """Mark `prior_id` as 'superseded' with NO replacement.

    Used by the recency-pruning baseline (M1-W4 §3.3) when the FIFO queue
    is at capacity and the oldest active item must be evicted to admit a
    new one. The action_log entry is the caller's responsibility — this
    function only mutates `memory_items`.

    **No lineage is preserved.** The evicted row's `supersedes_id` stays
    NULL; no `memory_relations` row is written. This is the central
    destructiveness contract of recency-pruning (see
    `NOTES/m1w4_design.md` §1c). The controller in M3 explicitly does
    NOT use this primitive — it uses `supersede()` so that lineage walks
    via `get_lineage()` reconstruct the full version history.

    Atomicity: a single UPDATE under autocommit (the same isolation
    `connect()` configures). No transaction is needed because there is
    nothing else to fail.

    Raises:
        RuntimeError: if `prior_id` does not exist or is already
            superseded — the M1-W4 §3.1 concurrency-friendliness check.
    """
    row = conn.execute(
        "SELECT status FROM memory_items WHERE id = ?", (prior_id,)
    ).fetchone()
    if row is None:
        raise RuntimeError(f"supersede_evict: prior_id={prior_id} does not exist")
    if row["status"] != MemoryStatus.ACTIVE.value:
        raise RuntimeError(
            f"supersede_evict: prior_id={prior_id} is not active "
            f"(current status: {row['status']!r}). Refusing double-evict."
        )
    conn.execute(
        "UPDATE memory_items SET status='superseded' WHERE id = ?",
        (prior_id,),
    )


# --------------------------------------------------------------------- #
# Retrieve                                                               #
# --------------------------------------------------------------------- #


def retrieve_active(
    conn: sqlite3.Connection,
    memory_type: MemoryType | None = None,
) -> list[MemoryItem]:
    """Return all active memory_items, optionally filtered by type.

    Order: ascending by `id` (== insertion order, stable across runs).
    Callers that need most-recent-first should reverse explicitly.
    """
    if memory_type is None:
        rows = conn.execute(
            "SELECT * FROM memory_items WHERE status = 'active' ORDER BY id"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM memory_items WHERE status = 'active' AND type = ? ORDER BY id",
            (memory_type.value,),
        ).fetchall()
    return [_row_to_item(r) for r in rows]


def get_by_id(conn: sqlite3.Connection, item_id: int) -> MemoryItem | None:
    """Return the row regardless of status. Audit-time access.

    Returns None if no such row exists. Used by `get_lineage` and by
    `qualitative.find_eviction_of_truth` (M1-W4 §3.5).
    """
    row = conn.execute(
        "SELECT * FROM memory_items WHERE id = ?", (item_id,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_item(row)


def get_lineage(conn: sqlite3.Connection, item_id: int) -> list[MemoryItem]:
    """Return the full supersession chain ending at `item_id`, oldest first.

    Walks `supersedes_id` backward from `item_id` to the chain root,
    then reverses so the result is in temporal order (oldest → newest).
    Includes `item_id` itself as the last element. If `item_id` does
    not exist, returns the empty list.

    Note: recency-pruning's FIFO eviction does NOT preserve lineage
    (`supersede_evict` writes no edge), so on a recency-only run
    `get_lineage(id)` returns `[id]` even for evicted-then-readmitted
    items. This is the entire point of the destructiveness gap (see
    `NOTES/m1w4_design.md` §1c).
    """
    chain: list[MemoryItem] = []
    seen: set[int] = set()
    cur_id: int | None = item_id
    while cur_id is not None:
        if cur_id in seen:
            # Defensive: a corrupted DB with a cycle in supersedes_id
            # would loop forever otherwise. The schema's REFERENCES
            # constraint prevents this in practice but the walk should
            # still terminate.
            raise RuntimeError(
                f"get_lineage: cycle detected at id={cur_id} (chain={seen})"
            )
        seen.add(cur_id)
        item = get_by_id(conn, cur_id)
        if item is None:
            break
        chain.append(item)
        cur_id = item.supersedes_id
    chain.reverse()
    return chain


# --------------------------------------------------------------------- #
# Internal — row → MemoryItem                                            #
# --------------------------------------------------------------------- #


def _row_to_item(row: sqlite3.Row) -> MemoryItem:
    """Hydrate a sqlite3.Row into a MemoryItem dataclass."""
    return MemoryItem(
        id=row["id"],
        type=MemoryType(row["type"]),
        text=row["text"],
        normalized_value=row["normalized_value"],
        status=MemoryStatus(row["status"]),
        confidence=row["confidence"],
        supersedes_id=row["supersedes_id"],
    )
