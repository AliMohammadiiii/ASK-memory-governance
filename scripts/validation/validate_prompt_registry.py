#!/usr/bin/env python3
"""Validate prompt paths, identifiers, hashes, and lineage metadata."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "prompts/registry.yaml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_registry(root: Path = ROOT, registry_path: Path = REGISTRY) -> list[str]:
    errors: list[str] = []
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    records = payload.get("prompts") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return ["registry must contain a prompts list"]

    ids: set[str] = set()
    paths: set[str] = set()
    records_by_id: dict[str, dict[str, object]] = {}
    required = {
        "id",
        "version",
        "purpose",
        "status",
        "path",
        "sha256",
        "related_experiments",
        "related_results",
        "supersedes",
        "superseded_by",
    }
    for index, record in enumerate(records):
        label = f"prompts[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{label} must be a mapping")
            continue
        missing = sorted(required - set(record))
        if missing:
            errors.append(f"{label} is missing fields: {', '.join(missing)}")
            continue
        prompt_id = str(record["id"])
        relative = str(record["path"])
        if prompt_id in ids:
            errors.append(f"duplicate prompt id: {prompt_id}")
        if relative in paths:
            errors.append(f"duplicate prompt path: {relative}")
        ids.add(prompt_id)
        paths.add(relative)
        records_by_id[prompt_id] = record

        prompt_path = root / relative
        if not prompt_path.is_file():
            errors.append(f"missing prompt file: {relative}")
        elif sha256_file(prompt_path) != record["sha256"]:
            errors.append(f"hash mismatch: {relative}")
        if record["status"] not in {"active", "historical"}:
            errors.append(f"invalid status for {prompt_id}: {record['status']}")

    prompt_files = {path.relative_to(root).as_posix() for path in (root / "prompts").glob("*.j2")}
    for relative in sorted(prompt_files - paths):
        errors.append(f"unregistered prompt: {relative}")
    for relative in sorted(paths - prompt_files):
        errors.append(f"registry path is not a prompt template: {relative}")

    for prompt_id, record in records_by_id.items():
        for field in ("supersedes", "superseded_by"):
            target = record[field]
            if target is not None and target not in records_by_id:
                errors.append(f"{prompt_id}.{field} refers to unknown id: {target}")
        previous = record["supersedes"]
        if (
            previous is not None
            and previous in records_by_id
            and records_by_id[previous]["superseded_by"] != prompt_id
        ):
            errors.append(f"lineage is not reciprocal: {previous} -> {prompt_id}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    args = parser.parse_args()
    errors = validate_registry(ROOT, args.registry)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("PASS: prompt registry paths, hashes, and lineage are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
