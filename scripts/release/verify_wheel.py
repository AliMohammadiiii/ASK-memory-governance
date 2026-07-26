#!/usr/bin/env python3
"""Verify package metadata and required runtime resources in the built wheel."""

from __future__ import annotations

import argparse
import email
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_MEMBERS = {
    "ask/__init__.py",
    "ask/py.typed",
    "ask/baselines/prompts/controller_cot.j2",
    "ask/resources/configs/controller_legacy_proposal.yaml",
    "ask/resources/configs/inference.yaml",
    "ask/resources/schema/ask_memory.schema.json",
    "ask/resources/schema/schema.sql",
}


def expected_metadata() -> tuple[str, str, str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return str(project["name"]), str(project["version"]), str(project["requires-python"])


def verify_wheel(path: Path) -> list[str]:
    errors: list[str] = []
    expected_name, expected_version, expected_python = expected_metadata()
    with zipfile.ZipFile(path) as wheel:
        members = set(wheel.namelist())
        missing = sorted(REQUIRED_MEMBERS - members)
        if missing:
            errors.append(f"missing packaged resources: {missing}")
        polluted = sorted(
            member
            for member in members
            if "__pycache__/" in member or member.endswith((".pyc", ".pyo"))
        )
        if polluted:
            errors.append(f"generated Python files in wheel: {polluted[:10]}")
        metadata_paths = sorted(
            member for member in members if member.endswith(".dist-info/METADATA")
        )
        if len(metadata_paths) != 1:
            errors.append(f"expected one METADATA file, found {len(metadata_paths)}")
            return errors
        metadata = email.message_from_bytes(wheel.read(metadata_paths[0]))
        if metadata.get("Name") != expected_name:
            errors.append(
                f"wheel name mismatch: expected={expected_name!r}, observed={metadata.get('Name')!r}"
            )
        if metadata.get("Version") != expected_version:
            errors.append(
                "wheel version mismatch: "
                f"expected={expected_version!r}, observed={metadata.get('Version')!r}"
            )
        observed_python = metadata.get("Requires-Python") or ""
        if _normalized_specifiers(observed_python) != _normalized_specifiers(expected_python):
            errors.append(
                "wheel Python range mismatch: "
                f"expected={expected_python!r}, observed={observed_python!r}"
            )
    return errors


def _normalized_specifiers(value: str) -> tuple[str, ...]:
    return tuple(sorted(part.strip() for part in value.split(",") if part.strip()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()

    _, version, _ = expected_metadata()
    wheels = sorted(args.dist_dir.glob(f"ask_memory_governance-{version}-*.whl"))
    if len(wheels) != 1:
        print(
            f"Wheel verification failed: expected one version {version} wheel, found {len(wheels)}",
            file=sys.stderr,
        )
        return 1
    errors = verify_wheel(wheels[0])
    if errors:
        print("Wheel verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Wheel metadata and packaged resources: OK ({wheels[0].name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
