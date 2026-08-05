"""Allowlisted public packaging with mandatory human and gold gates."""
from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any

from mgp_natural.errors import GateBlockedError, ValidationError
from mgp_natural.util.io import file_manifest, read_json, sha256_file, write_json

BLOCK_MESSAGE = "BLOCKED_PENDING_HUMAN_LEGAL_PRIVACY_APPROVAL_INDEPENDENT_GOLD_AND_VALID_SPLITS"
FORBIDDEN_PARTS = {".private", "raw", "annotations", "adjudications", "gold", "scores"}
FORBIDDEN_SUFFIXES = {".token", ".key", ".pem"}
RUNTIME_ONLY_SUFFIXES = {".log"}
FORBIDDEN_GENERATED_NAMES = {"pytest.xml"}
TOKEN_SCAN_EXEMPT_PREFIXES = ("tests/", "data/fixtures/")
FORBIDDEN_NAME = re.compile(r"(?i)(secret|mapping|credential|source_locator|raw_studychat|raw_wikiconv)")
TOKEN_VALUE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b"
)


def _human_release_approved(approvals_path: Path) -> bool:
    approvals = read_json(approvals_path)
    required = {
        "legal_and_redistribution",
        "manual_privacy_review",
        "independent_gold",
        "valid_splits",
        "release_decision",
    }
    entries = approvals.get("human_approvals", {})
    return all(
        entries.get(key, {}).get("status") == "APPROVED_BY_RECORDED_HUMAN"
        and entries.get(key, {}).get("approver")
        for key in required
    )


def _excluded_from_public_scope(path: Path, root: Path, excluded: set[Path]) -> bool:
    if path.resolve() in excluded:
        return True
    relative = path.relative_to(root)
    if any(part in FORBIDDEN_PARTS for part in relative.parts):
        return True
    if path.name in FORBIDDEN_GENERATED_NAMES:
        return True
    if (
        path.suffix in FORBIDDEN_SUFFIXES
        or path.suffix in RUNTIME_ONLY_SUFFIXES
        or FORBIDDEN_NAME.search(path.name)
    ):
        return True
    if any(part.startswith(".") and part not in {".gitignore"} for part in relative.parts):
        return True
    return "dist" in relative.parts or "build" in relative.parts or "__pycache__" in relative.parts


def public_file_candidates(root: Path, exclude: set[Path] | None = None) -> list[Path]:
    root = root.resolve()
    excluded = {path.resolve() for path in (exclude or set())}
    files = []
    for path in root.rglob("*"):
        if _excluded_from_public_scope(path, root, excluded):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        files.append(path)
    return sorted(files)


def _symlink_violations(root: Path, excluded: set[Path]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if _excluded_from_public_scope(path, root, excluded):
            continue
        if path.is_symlink():
            violations.append(
                {"path": path.relative_to(root).as_posix(), "kind": "PUBLIC_SYMLINK_NOT_ALLOWED"}
            )
    return violations


def _content_violations(root: Path, files: list[Path]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    absolute_root = root.resolve().as_posix()
    for path in files:
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if absolute_root in text:
            violations.append({"path": relative, "kind": "ABSOLUTE_REPOSITORY_PATH"})
        if not relative.startswith(TOKEN_SCAN_EXEMPT_PREFIXES):
            for match in TOKEN_VALUE.finditer(text):
                violations.append(
                    {
                        "path": relative,
                        "kind": "TOKEN_LIKE_VALUE_"
                        + hashlib.sha256(match.group(0).encode()).hexdigest()[:12],
                    }
                )
    return violations


def verify_boundary(
    root: Path,
    *,
    exclude: set[Path] | None = None,
    inventory_path: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    excluded = {path.resolve() for path in (exclude or set())}
    files = public_file_candidates(root, exclude=exclude)
    violations = _symlink_violations(root, excluded) + _content_violations(root, files)
    report = {
        "schema_version": "1.0",
        "status": "PASS" if not violations else "FAIL",
        "files": len(files),
        "violations": violations,
    }
    if inventory_path is not None:
        write_json(
            inventory_path,
            {
                "schema_version": "1.0",
                "generation_status": "CANDIDATE_INVENTORY_RELEASE_BLOCKED",
                "package_created": False,
                "files": file_manifest(files, root),
                "note": "Candidate public inventory only; legal, privacy, gold, split, and release gates remain unresolved.",
            },
        )
    if violations:
        raise ValidationError(f"public boundary violations: {violations}")
    return report


def _verify_zip_against_manifest(output_zip: Path, manifest: list[dict[str, Any]]) -> None:
    expected = {entry["path"]: entry["sha256"] for entry in manifest}
    with zipfile.ZipFile(output_zip) as bundle:
        names = set(bundle.namelist())
        if names != set(expected):
            raise ValidationError("public package file coverage does not match inventory")
        for name, digest in expected.items():
            observed = hashlib.sha256(bundle.read(name)).hexdigest()
            if observed != digest:
                raise ValidationError(f"public package hash mismatch: {name}")


def package_public(root: Path, approvals_path: Path, output_zip: Path, inventory_path: Path) -> dict[str, Any]:
    root = root.resolve()
    output_zip = output_zip.resolve()
    inventory_path = inventory_path.resolve()
    excluded = {output_zip, inventory_path}
    verify_boundary(root, exclude=excluded)
    output_zip.unlink(missing_ok=True)
    if not _human_release_approved(approvals_path):
        raise GateBlockedError(BLOCK_MESSAGE)
    files = public_file_candidates(root, exclude=excluded)
    manifest = file_manifest(files, root)
    inventory = {
        "schema_version": "1.0",
        "generation_status": "PUBLIC_PACKAGE_CREATED",
        "package_created": True,
        "files": manifest,
    }
    write_json(inventory_path, inventory)
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, path.relative_to(root).as_posix())
    _verify_zip_against_manifest(output_zip, manifest)
    return {
        "status": "PACKAGED",
        "files": len(files),
        "sha256": sha256_file(output_zip),
        "inventory_sha256": sha256_file(inventory_path),
    }

