"""Audit and optionally repair permissions for private benchmark artifacts."""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Any

from mgp_natural.util.io import write_json

PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.lstat().st_mode)


def _path_commitment(private_root: Path, path: Path) -> str:
    relative = path.relative_to(private_root.parent).as_posix()
    return hashlib.sha256(relative.encode("utf-8")).hexdigest()


def _violation(private_root: Path, path: Path, expected: int) -> dict[str, Any]:
    observed = _mode(path)
    kind = "SYMLINK_NOT_ALLOWED" if path.is_symlink() else "MODE_MISMATCH"
    return {
        "path_commitment_sha256": _path_commitment(private_root, path),
        "entry_type": "symlink" if path.is_symlink() else "directory" if path.is_dir() else "file",
        "kind": kind,
        "observed_mode": format(observed, "04o"),
        "expected_mode": format(expected, "04o"),
    }


def _entries(private_root: Path) -> list[Path]:
    if not private_root.exists():
        return []
    return [private_root, *sorted(private_root.rglob("*"))]


def audit_private_permissions(private_root: Path, *, repair: bool = False) -> dict[str, Any]:
    """Verify exact private modes without disclosing private paths in the report.

    Directories must be ``0700`` and regular files must be ``0600``. Symlinks are
    always rejected. When ``repair`` is true, incorrect regular-file and directory
    modes are changed before a second verification pass.
    """

    private_root = private_root.absolute()
    if not private_root.exists():
        return {
            "schema_version": "1.0",
            "status": "PASS_NOT_PRESENT",
            "private_root_present": False,
            "repair_requested": repair,
            "directories": 0,
            "files": 0,
            "symlinks": 0,
            "initial_violations": [],
            "remaining_violations": [],
            "changes_applied": 0,
            "required_directory_mode": "0700",
            "required_file_mode": "0600",
        }

    initial: list[dict[str, Any]] = []
    directories = 0
    files = 0
    symlinks = 0
    entries = _entries(private_root)
    for path in entries:
        if path.is_symlink():
            symlinks += 1
            initial.append(_violation(private_root, path, PRIVATE_FILE_MODE))
            continue
        if path.is_dir():
            directories += 1
            if _mode(path) != PRIVATE_DIRECTORY_MODE:
                initial.append(_violation(private_root, path, PRIVATE_DIRECTORY_MODE))
        elif path.is_file():
            files += 1
            if _mode(path) != PRIVATE_FILE_MODE:
                initial.append(_violation(private_root, path, PRIVATE_FILE_MODE))

    changes = 0
    if repair:
        for path in entries:
            if path.is_symlink():
                continue
            expected = PRIVATE_DIRECTORY_MODE if path.is_dir() else PRIVATE_FILE_MODE
            if (path.is_dir() or path.is_file()) and _mode(path) != expected:
                os.chmod(path, expected)
                changes += 1

    remaining: list[dict[str, Any]] = []
    for path in _entries(private_root):
        if path.is_symlink():
            remaining.append(_violation(private_root, path, PRIVATE_FILE_MODE))
            continue
        if path.is_dir() and _mode(path) != PRIVATE_DIRECTORY_MODE:
            remaining.append(_violation(private_root, path, PRIVATE_DIRECTORY_MODE))
        elif path.is_file() and _mode(path) != PRIVATE_FILE_MODE:
            remaining.append(_violation(private_root, path, PRIVATE_FILE_MODE))

    return {
        "schema_version": "1.0",
        "status": "PASS" if not remaining else "FAIL",
        "private_root_present": True,
        "repair_requested": repair,
        "directories": directories,
        "files": files,
        "symlinks": symlinks,
        "initial_violations": initial,
        "remaining_violations": remaining,
        "changes_applied": changes,
        "required_directory_mode": "0700",
        "required_file_mode": "0600",
        "path_disclosure": "Only SHA-256 commitments to private relative paths are reported.",
    }


def audit_private_permissions_to_file(
    private_root: Path,
    output: Path,
    *,
    repair: bool = False,
) -> dict[str, Any]:
    report = audit_private_permissions(private_root, repair=repair)
    write_json(output, report)
    return report

