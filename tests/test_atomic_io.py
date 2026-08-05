"""Atomic text-write contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from ask import atomic_io


def test_atomic_write_text_replaces_exact_utf8_bytes(tmp_path: Path) -> None:
    target = tmp_path / "artifact.jsonl"
    target.write_text("old\n", encoding="utf-8")

    atomic_io.atomic_write_text(target, '{"text":"چای"}\n')

    assert target.read_bytes() == '{"text":"چای"}\n'.encode()
    assert list(tmp_path.glob(".artifact.jsonl.*.tmp")) == []


def test_atomic_write_text_creates_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "report.md"

    atomic_io.atomic_write_text(target, "complete\n")

    assert target.read_text(encoding="utf-8") == "complete\n"


def test_atomic_write_text_preserves_target_on_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "manifest.json"
    target.write_text("baseline", encoding="utf-8")

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(atomic_io.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated"):
        atomic_io.atomic_write_text(target, "replacement")

    assert target.read_text(encoding="utf-8") == "baseline"
    assert list(tmp_path.glob(".manifest.json.*.tmp")) == []
