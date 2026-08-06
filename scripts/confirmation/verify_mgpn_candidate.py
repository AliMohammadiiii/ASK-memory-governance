#!/usr/bin/env python3
"""Verify the private MGP-Natural draft packet without revealing its mapping."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import stat
import tempfile
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from ask.confirmation.blinding import PROHIBITED_KEYS, canonical_hash, nested_keys
from ask.confirmation.mgpn_candidate import (
    annotation_packet_semantic_errors,
    prepare_private_annotation_materials,
)

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT / ".private"
EXPECTED_BUNDLE_MEMBERS = {
    "README.md",
    "SHA256SUMS",
    "annotation_form.csv",
    "blind_packet.jsonl",
    "packet_commitment.json",
}


def _require_private_path(path: Path, option: str) -> Path:
    resolved = path.resolve()
    private_root = PRIVATE_ROOT.resolve()
    try:
        resolved.relative_to(private_root)
    except ValueError as exc:
        raise SystemExit(f"{option} must be below {PRIVATE_ROOT}") from exc
    current = resolved.parent
    while current.is_relative_to(private_root):
        if current.stat().st_mode & 0o077:
            raise SystemExit(f"{option} parent directories must not be group- or world-accessible")
        if current == private_root:
            break
        current = current.parent
    return resolved


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise SystemExit(f"{path}:{line_number}: expected a JSON object")
        rows.append(value)
    return rows


def _atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent, delete=False
    ) as handle:
        temporary_path = Path(handle.name)
        handle.write(payload.encode())
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _verify_bundle(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if len(names) != len(set(names)):
            raise SystemExit("annotation bundle contains duplicate member names")
        if set(names) != EXPECTED_BUNDLE_MEMBERS:
            raise SystemExit("annotation bundle member allowlist mismatch")
        for info in zf.infolist():
            mode = info.external_attr >> 16
            if not stat.S_ISREG(mode) or stat.S_IMODE(mode) != 0o600:
                raise SystemExit("annotation bundle member mode must be regular 0600")
        if zf.testzip() is not None:
            raise SystemExit("annotation bundle failed ZIP integrity")
        manifest_lines = zf.read("SHA256SUMS").decode().splitlines()
        manifest: dict[str, str] = {}
        for line in manifest_lines:
            expected, separator, name = line.partition("  ")
            if not separator or len(expected) != 64:
                raise SystemExit("annotation bundle SHA256SUMS has invalid syntax")
            manifest[name] = expected
        expected_names = EXPECTED_BUNDLE_MEMBERS - {"SHA256SUMS"}
        if set(manifest) != expected_names:
            raise SystemExit("annotation bundle SHA256SUMS coverage mismatch")
        mismatches = [
            name
            for name, expected in manifest.items()
            if hashlib.sha256(zf.read(name)).hexdigest() != expected
        ]
        if mismatches:
            raise SystemExit("annotation bundle contains a hash mismatch")
        return {
            "member_count": len(names),
            "manifest_entry_count": len(manifest),
            "zip_integrity_passed": True,
            "member_modes_private": True,
            "private_mapping_absent": "private_mapping.json" not in names,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--private-map", type=Path, required=True)
    parser.add_argument("--commitment", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    for option, path in (
        ("--packet", args.packet),
        ("--answers", args.answers),
        ("--private-map", args.private_map),
        ("--commitment", args.commitment),
        ("--bundle", args.bundle),
    ):
        _require_private_path(path, option)
        if path.stat().st_mode & 0o077:
            raise SystemExit(f"{option} must not be group- or world-accessible")

    packet = _read_jsonl(args.packet)
    private_record = _read_json(args.private_map)
    commitment = _read_json(args.commitment)
    try:
        blinding_secret = int(str(private_record["blinding_secret"]))
    except (KeyError, ValueError) as exc:
        raise SystemExit("private map is missing a valid blinding secret") from exc
    expected_packet, expected_commitment, expected_private, _, _ = (
        prepare_private_annotation_materials(args.archive, blinding_secret)
    )
    if packet != expected_packet:
        raise SystemExit("packet does not reproduce from the parent and private reveal record")
    if private_record != expected_private:
        raise SystemExit("private reveal record does not reproduce")
    for key, expected in expected_commitment.items():
        if commitment.get(key) != expected:
            raise SystemExit(f"commitment mismatch for {key}")
    if commitment.get("private_mapping_sha256") != canonical_hash(private_record):
        raise SystemExit("private mapping commitment mismatch")
    packet_bytes = args.packet.read_bytes()
    if commitment.get("packet_jsonl_sha256") != hashlib.sha256(packet_bytes).hexdigest():
        raise SystemExit("packet byte hash mismatch")
    if nested_keys(packet) & PROHIBITED_KEYS:
        raise SystemExit("packet contains a prohibited key")

    schema = json.loads((ROOT / "confirmation/schemas/natural_challenge.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    schema_error_count = sum(1 for row in packet for _ in validator.iter_errors(row))
    if schema_error_count:
        raise SystemExit(f"packet has {schema_error_count} schema errors")
    semantic_errors = annotation_packet_semantic_errors(packet)
    if semantic_errors:
        raise SystemExit(f"packet has semantic errors: {semantic_errors[:3]}")

    answer_rows = list(csv.DictReader(io.StringIO(args.answers.read_text(encoding="utf-8"))))
    packet_ids = [str(row["blind_id"]) for row in packet]
    answer_ids = [str(row.get("blind_id")) for row in answer_rows]
    if answer_ids != packet_ids or len(answer_ids) != len(set(answer_ids)):
        raise SystemExit("annotation form IDs do not exactly match packet order")

    expected_hash_files = {
        "protocol_sha256": ROOT / "confirmation/protocol.yaml",
        "packet_schema_sha256": ROOT / "confirmation/schemas/natural_challenge.schema.json",
        "annotation_schema_sha256": ROOT / "confirmation/schemas/annotation.schema.json",
        "blinding_transform_sha256": ROOT / "src/ask/confirmation/blinding.py",
        "mgpn_transform_sha256": ROOT / "src/ask/confirmation/mgpn_candidate.py",
    }
    for field, path in expected_hash_files.items():
        if commitment.get(field) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise SystemExit(f"commitment source hash mismatch for {field}")

    bundle = _verify_bundle(args.bundle)
    with zipfile.ZipFile(args.bundle) as zf:
        if zf.read("blind_packet.jsonl") != packet_bytes:
            raise SystemExit("bundled packet differs from private packet")
        if zf.read("annotation_form.csv") != args.answers.read_bytes():
            raise SystemExit("bundled answer form differs from private answer form")
        if zf.read("packet_commitment.json") != args.commitment.read_bytes():
            raise SystemExit("bundled commitment differs from private commitment")

    result = {
        "schema_version": "1.0",
        "status": "PASS_PRIVATE_DRAFT_VERIFICATION",
        "publication_eligible": False,
        "annotation_authorized": False,
        "item_count": len(packet),
        "packet_schema_error_count": schema_error_count,
        "packet_semantic_error_count": len(semantic_errors),
        "packet_reproduced_from_parent": True,
        "private_mapping_commitment_verified": True,
        "source_and_protocol_hashes_verified": True,
        "prohibited_key_count": 0,
        "bundle": bundle,
    }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        _atomic_write_text(args.output, payload)
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
