from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from mgp_natural.errors import GateBlockedError
from mgp_natural.release.package import (
    BLOCK_MESSAGE,
    package_public,
    public_file_candidates,
    verify_boundary,
)


def _approvals(path: Path, approved: bool) -> None:
    status = "APPROVED_BY_RECORDED_HUMAN" if approved else "HUMAN_LEGAL_REVIEW_REQUIRED"
    names = [
        "legal_and_redistribution",
        "manual_privacy_review",
        "independent_gold",
        "valid_splits",
        "release_decision",
    ]
    path.write_text(json.dumps({"human_approvals": {name: {"status": status, "approver": "human" if approved else ""} for name in names}}), encoding="utf-8")


def test_public_candidates_exclude_private_raw_and_gold(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("public", encoding="utf-8")
    (tmp_path / ".private").mkdir()
    (tmp_path / ".private" / "secret.txt").write_text("secret", encoding="utf-8")
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "source.jsonl").write_text("raw", encoding="utf-8")
    (tmp_path / "gold").mkdir()
    (tmp_path / "gold" / "gold.jsonl").write_text("gold", encoding="utf-8")
    paths = {path.relative_to(tmp_path).as_posix() for path in public_file_candidates(tmp_path)}
    assert paths == {"README.md"}
    assert verify_boundary(tmp_path)["status"] == "PASS"


def test_public_candidates_exclude_runtime_logs(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("public", encoding="utf-8")
    (tmp_path / "full-reproduce.log").write_text(
        tmp_path.resolve().as_posix(), encoding="utf-8"
    )
    paths = {path.relative_to(tmp_path).as_posix() for path in public_file_candidates(tmp_path)}
    assert paths == {"README.md"}
    assert verify_boundary(tmp_path)["status"] == "PASS"


def test_blocking_human_gates(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("public", encoding="utf-8")
    approvals = tmp_path / "approvals.json"
    _approvals(approvals, False)
    with pytest.raises(GateBlockedError, match=BLOCK_MESSAGE):
        package_public(tmp_path, approvals, tmp_path / "package.zip", tmp_path / "inventory.json")


def test_approved_fixture_package_has_hash_inventory(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("public", encoding="utf-8")
    approvals = tmp_path / "approvals.json"
    _approvals(approvals, True)
    report = package_public(tmp_path, approvals, tmp_path / "package.zip", tmp_path / "inventory.json")
    assert report["status"] == "PACKAGED"
    with zipfile.ZipFile(tmp_path / "package.zip") as bundle:
        assert "README.md" in bundle.namelist()
        assert all(".private" not in name for name in bundle.namelist())
    inventory = json.loads((tmp_path / "inventory.json").read_text())
    assert all(entry["sha256"] for entry in inventory["files"])


def test_public_inventory_is_external_and_exact(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("public", encoding="utf-8")
    approvals = tmp_path / "approvals.json"
    inventory = tmp_path / "inventory.json"
    package = tmp_path / "package.zip"
    _approvals(approvals, True)
    package_public(tmp_path, approvals, package, inventory)
    manifest = json.loads(inventory.read_text(encoding="utf-8"))["files"]
    assert "inventory.json" not in {row["path"] for row in manifest}
    assert "package.zip" not in {row["path"] for row in manifest}
    with zipfile.ZipFile(package) as bundle:
        assert set(bundle.namelist()) == {row["path"] for row in manifest}


def test_boundary_rejects_actual_absolute_repository_path(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(tmp_path.resolve().as_posix(), encoding="utf-8")
    with pytest.raises(Exception, match="ABSOLUTE_REPOSITORY_PATH"):
        verify_boundary(tmp_path)


def test_private_permission_audit_repairs_exact_modes(tmp_path: Path) -> None:
    import os

    from mgp_natural.audits.private_permissions import audit_private_permissions

    private = tmp_path / ".private"
    nested = private / "nested"
    nested.mkdir(parents=True)
    secret = nested / "secret.bin"
    secret.write_bytes(b"private")
    os.chmod(private, 0o755)
    os.chmod(nested, 0o750)
    os.chmod(secret, 0o644)

    before = audit_private_permissions(private)
    assert before["status"] == "FAIL"
    assert before["remaining_violations"]

    after = audit_private_permissions(private, repair=True)
    assert after["status"] == "PASS"
    assert after["changes_applied"] == 3
    assert (private.stat().st_mode & 0o7777) == 0o700
    assert (nested.stat().st_mode & 0o7777) == 0o700
    assert (secret.stat().st_mode & 0o7777) == 0o600


def test_private_permission_audit_rejects_symlink(tmp_path: Path) -> None:
    from mgp_natural.audits.private_permissions import audit_private_permissions

    private = tmp_path / ".private"
    private.mkdir()
    target = tmp_path / "target"
    target.write_text("value", encoding="utf-8")
    (private / "link").symlink_to(target)
    report = audit_private_permissions(private, repair=True)
    assert report["status"] == "FAIL"
    assert report["symlinks"] == 1


def test_public_boundary_rejects_public_symlink(tmp_path: Path) -> None:
    target = tmp_path / ".private"
    target.mkdir()
    secret = target / "secret.txt"
    secret.write_text("private", encoding="utf-8")
    (tmp_path / "public.txt").symlink_to(secret)
    with pytest.raises(Exception, match="SYMLINK"):
        verify_boundary(tmp_path)


def test_repository_security_scan_checks_ignore_and_permissions(tmp_path: Path) -> None:
    import os

    from mgp_natural.audits.security import repository_security_scan

    (tmp_path / ".gitignore").write_text(
        ".private/\ndata/raw/**\ndata/interim/**\ndata/derived/**\n*.key\n*.pem\n*.token\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("public", encoding="utf-8")
    private = tmp_path / ".private"
    private.mkdir()
    os.chmod(private, 0o700)
    report = repository_security_scan(tmp_path)
    assert report["status"] == "PASS"


def test_private_inventory_includes_full_source_workspace(tmp_path: Path) -> None:
    from scripts.generate_private_inventory import aggregate

    private_full = tmp_path / ".private" / "full"
    private_full.mkdir(parents=True)
    (private_full / "construction_items.jsonl").write_text("{}\n", encoding="utf-8")

    report = aggregate(tmp_path)
    classes = {row["class"]: row for row in report["classes"]}
    assert classes[".private/full"]["present"] is True
    assert classes[".private/full"]["files"] == 1

