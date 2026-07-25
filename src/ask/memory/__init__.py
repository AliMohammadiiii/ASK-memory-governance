"""Memory substrate: SQLite-backed, LinkML-defined."""

from .db import connect, init_schema
from .models import (
    ActionLogEntry,
    ControllerAction,
    EvidenceSpan,
    MemoryItem,
    MemoryRelation,
    MemoryStatus,
    MemoryType,
    RelationKind,
)
from .operations import (
    get_by_id,
    get_lineage,
    insert_active,
    retrieve_active,
    supersede,
    supersede_evict,
)

__all__ = [
    "ActionLogEntry",
    "ControllerAction",
    "EvidenceSpan",
    "MemoryItem",
    "MemoryRelation",
    "MemoryStatus",
    "MemoryType",
    "RelationKind",
    "connect",
    "init_schema",
    "get_by_id",
    "get_lineage",
    "insert_active",
    "retrieve_active",
    "supersede",
    "supersede_evict",
]
