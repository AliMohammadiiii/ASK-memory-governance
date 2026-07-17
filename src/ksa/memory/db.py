"""SQLite connection + schema initialization.

The DDL lives in schema/generated/schema.sql, itself generated from
schema/ksa_memory.yaml via `make schema`. We load it verbatim rather than
duplicating it in Python.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA_FILE = (
    Path(__file__).resolve().parents[1] / "resources" / "schema" / "schema.sql"
)


def _enable_fk(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a SQLite connection with FK constraints enabled and row factory set."""
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    _enable_fk(conn)
    return conn


def init_schema(conn: sqlite3.Connection, schema_path: Path | None = None) -> None:
    """Apply schema/generated/schema.sql to `conn`. Idempotent (CREATE TABLE IF NOT EXISTS)."""
    p = Path(schema_path) if schema_path else _SCHEMA_FILE
    if not p.exists():
        raise FileNotFoundError(
            f"Schema file not found at {p}. Run `make schema` to regenerate."
        )
    ddl = p.read_text(encoding="utf-8")
    conn.executescript(ddl)
