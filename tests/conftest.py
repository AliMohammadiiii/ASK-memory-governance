"""Shared fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ask.controller.scoring import ControllerConfig, load_config
from ask.memory import connect, init_schema


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def config() -> ControllerConfig:
    return load_config()


@pytest.fixture()
def tmp_log_path(tmp_path: Path) -> Path:
    return tmp_path / "action_log.jsonl"
