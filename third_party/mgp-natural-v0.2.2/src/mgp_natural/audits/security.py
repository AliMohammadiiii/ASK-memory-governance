"""Repository-level, offline security and secret-boundary checks."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from mgp_natural.audits.private_permissions import audit_private_permissions
from mgp_natural.errors import ValidationError
from mgp_natural.release.package import verify_boundary
from mgp_natural.util.io import write_json

REQUIRED_GITIGNORE_LINES = {
    ".private/",
    "data/raw/**",
    "data/interim/**",
    "data/derived/**",
    "*.key",
    "*.pem",
    "*.token",
}


def _gitignore_audit(root: Path) -> dict[str, Any]:
    path = root / ".gitignore"
    if not path.exists():
        return {"passed": False, "missing": sorted(REQUIRED_GITIGNORE_LINES)}
    active = {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    missing = sorted(REQUIRED_GITIGNORE_LINES - active)
    return {"passed": not missing, "missing": missing}


def repository_security_scan(
    root: Path,
    *,
    report_path: Path | None = None,
    inventory_path: Path | None = None,
) -> dict[str, Any]:
    """Run deterministic security checks that require no network or paid service."""

    root = root.resolve()
    excluded = {path.resolve() for path in (report_path, inventory_path) if path is not None}
    boundary_error: str | None = None
    try:
        boundary = verify_boundary(root, exclude=excluded, inventory_path=inventory_path)
    except ValidationError as exc:
        boundary = {"status": "FAIL", "files": 0, "violations": []}
        boundary_error = str(exc)

    permissions = audit_private_permissions(root / ".private", repair=False)
    gitignore = _gitignore_audit(root)
    external_tools = {
        name: {"available": shutil.which(name) is not None}
        for name in ("gitleaks", "bandit", "pip-audit")
    }
    passed = (
        boundary.get("status") == "PASS"
        and permissions.get("status") in {"PASS", "PASS_NOT_PRESENT"}
        and gitignore["passed"]
    )
    report = {
        "schema_version": "1.0",
        "status": "PASS" if passed else "FAIL",
        "public_boundary": boundary,
        "public_boundary_error": boundary_error,
        "private_permissions": {
            "status": permissions["status"],
            "directories": permissions["directories"],
            "files": permissions["files"],
            "symlinks": permissions["symlinks"],
            "remaining_violations": permissions["remaining_violations"],
        },
        "gitignore": gitignore,
        "external_tools": external_tools,
        "scope_note": (
            "Deterministic offline checks for public-boundary leakage, token-like values, "
            "symlinks, private modes, and ignore rules. This is not a substitute for an "
            "independent security review or unavailable external scanners."
        ),
    }
    if report_path is not None:
        write_json(report_path, report)
    return report

