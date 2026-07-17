"""JSONL writer for ActionLogEntry, validated against the generated JSON Schema.

Every controller / baseline decision writes exactly one line:
    {"id": 1, "timestamp": "...", "action": "Keep", ... "rationale": "..."}

Validation fails loudly — an invalid action_log is a thesis-level bug.

M1-W4 §3.2 contract:
  * `ActionLogWriter(path, baseline=...)` binds a baseline label to every
    entry it writes (overrides ActionLogEntry.baseline if set on the entry).
  * `mode='w'` truncates the file on a fresh run; `mode='a'` appends.
    Default is 'w' (matches the §3.2 spec: "Truncates file on a fresh run").
  * `flush=True` (default) calls `flush()` + `fsync()` after every write,
    so a process kill leaves the file parseable up to the last fully-
    flushed line. Disable for batch loads where the throughput matters
    more than crash safety.
  * Context-manager use is required: opens on enter, closes on exit.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TextIO, cast

import jsonschema
from pydantic import BaseModel, ConfigDict, Field

from ..controller.active import ScorecardDecision
from ..memory.models import ActionLogEntry, ControllerAction, MemoryType

_SCHEMA_FILE = (
    Path(__file__).resolve().parents[1] / "resources" / "schema" / "ksa_memory.schema.json"
)


class ActionLogRecord(BaseModel):
    """Pydantic round-trip model for action_log JSONL rows."""

    model_config = ConfigDict(extra="forbid")

    id: int
    timestamp: datetime
    action: ControllerAction
    candidate_text: str
    candidate_type: MemoryType | None = None
    candidate_id: int | None = None
    session_id: str | None = None
    baseline: str | None = None
    prior_memory_id: int | None = None
    resulting_memory_id: int | None = None
    feature_c: float | None = Field(default=None, ge=0.0, le=1.0)
    feature_e: float | None = Field(default=None, ge=0.0, le=1.0)
    feature_f: float | None = Field(default=None, ge=0.0, le=1.0)
    feature_r: float | None = Field(default=None, ge=-1.0, le=1.0)
    feature_rho: float | None = Field(default=None, ge=0.0, le=1.0)
    s_rev: float | None = None
    s_abs: float | None = None
    theta_sup: float | None = None
    theta_abs: float | None = None
    rationale: str

    @classmethod
    def from_entry(cls, entry: ActionLogEntry) -> ActionLogRecord:
        return cls.model_validate(entry.to_json_dict())


class ActionLogWriter:
    """Append ActionLogEntry objects to a JSONL file, validating each against the schema.

    Args:
        path: target JSONL path. Parent dirs are created.
        schema_path: optional override for the JSON Schema file. Defaults
            to `schema/generated/ksa_memory.schema.json` (the file
            generated from `schema/ksa_memory.yaml`).
        baseline: optional baseline label to stamp on every entry. If
            set, this overrides whatever ActionLogEntry.baseline carries.
            One of {"no_memory", "flat_vector", "recency",
            "naive_overwrite", "controller", None}.
        mode: 'w' (default; truncate on entry) or 'a' (append). M1-W4
            §3.2 specifies fresh-run truncation.
        fsync_on_write: if True (default), call `os.fsync(fd)` after
            every line. Crash-safety guarantee for the action_log; the
            cost is dominated by the file_open + LLM call so this is
            negligible at our scale (~50 sessions × ≤ 30 turns).
    """

    _ALLOWED_BASELINES = frozenset(
        {"no_memory", "flat_vector", "recency", "naive_overwrite", "controller"}
    )
    _CONTROLLER_REQUIRED_FIELDS = frozenset(
        {
            "candidate_id",
            "feature_c",
            "feature_e",
            "feature_f",
            "feature_r",
            "feature_rho",
            "s_rev",
            "s_abs",
            "theta_sup",
            "theta_abs",
        }
    )

    def __init__(
        self,
        path: str | Path,
        schema_path: Path | None = None,
        *,
        baseline: str | None = None,
        mode: str = "w",
        fsync_on_write: bool = True,
    ) -> None:
        if mode not in {"w", "a"}:
            raise ValueError(f"mode must be 'w' or 'a'; got {mode!r}")
        if baseline is not None and baseline not in self._ALLOWED_BASELINES:
            raise ValueError(
                f"baseline {baseline!r} not in allowed set {sorted(self._ALLOWED_BASELINES)}"
            )
        self.path = Path(path)
        self.baseline = baseline
        self.mode = mode
        self.fsync_on_write = fsync_on_write

        schema_text = (schema_path or _SCHEMA_FILE).read_text(encoding="utf-8")
        self._schema = json.loads(schema_text)
        # Validate schema itself is well-formed.
        jsonschema.Draft202012Validator.check_schema(self._schema)
        self._validator = jsonschema.Draft202012Validator(self._schema)
        self._fp: TextIO | None = None

    def __enter__(self) -> ActionLogWriter:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = cast(TextIO, self.path.open(self.mode, encoding="utf-8"))
        return self

    def __exit__(self, *_exc_info: object) -> None:
        if self._fp is not None:
            self._fp.flush()
            try:
                os.fsync(self._fp.fileno())
            except (OSError, ValueError):
                # Closed / non-fsync-capable file: be tolerant.
                pass
            self._fp.close()
            self._fp = None

    def write(self, entry: ActionLogEntry) -> None:
        """Validate, append one JSONL line, optionally fsync.

        Validation runs BEFORE any byte hits the file — invalid entries
        cannot leave the file in a half-written state. (Enforced by
        `test_schema_rejection_does_not_write` in tests/test_action_log.py.)
        """
        if self._fp is None:
            raise RuntimeError("ActionLogWriter not opened (use as context manager)")

        record = entry.to_json_dict()
        # Apply the writer-level baseline override if set.
        if self.baseline is not None:
            record["baseline"] = self.baseline
        self._validate_controller_snapshot(record)

        # Validate first — must NOT mutate the file if the entry is bad.
        self._validator.validate(record)

        line = json.dumps(record, ensure_ascii=False) + "\n"
        self._fp.write(line)
        if self.fsync_on_write:
            self._fp.flush()
            try:
                os.fsync(self._fp.fileno())
            except (OSError, ValueError):
                pass

    def write_decision(
        self,
        *,
        entry_id: int,
        timestamp: datetime,
        candidate_text: str,
        candidate_type: MemoryType | str,
        candidate_id: int,
        prior_memory_id: int | None,
        decision: ScorecardDecision,
        resulting_memory_id: int | None = None,
        session_id: str | None = None,
    ) -> None:
        """Write a fully reproducible M3-W9 controller decision row."""
        entry = ActionLogEntry(
            id=entry_id,
            timestamp=timestamp,
            action=decision.action,
            candidate_text=candidate_text,
            rationale=decision.rationale,
            session_id=session_id,
            baseline=self.baseline or "controller",
            candidate_type=_memory_type(candidate_type),
            candidate_id=candidate_id,
            prior_memory_id=prior_memory_id,
            resulting_memory_id=resulting_memory_id,
            feature_c=decision.features.c,
            feature_e=decision.features.e,
            feature_f=decision.features.f,
            feature_r=decision.features.r,
            feature_rho=decision.features.rho,
            s_rev=decision.s_rev,
            s_abs=decision.s_abs,
            theta_sup=decision.theta_sup,
            theta_abs=decision.theta_abs,
        )
        self.write(entry)

    def _validate_controller_snapshot(self, record: dict) -> None:
        if record.get("baseline") != "controller":
            return
        missing = sorted(
            field for field in self._CONTROLLER_REQUIRED_FIELDS if record.get(field) is None
        )
        if missing:
            raise ValueError(
                f"controller action_log rows require full feature snapshot; missing {missing}"
            )


def _memory_type(value: MemoryType | str) -> MemoryType:
    if isinstance(value, MemoryType):
        return value
    return MemoryType(str(value))
