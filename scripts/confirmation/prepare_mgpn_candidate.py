#!/usr/bin/env python3
"""Audit MGP-Natural v0.1.0 and optionally write a private safe draft packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import tempfile
import zipfile
from pathlib import Path

from ask.confirmation.mgpn_candidate import (
    audit_candidate_archive,
    prepare_private_annotation_materials,
)

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT / ".private"


def _require_private_path(path: Path, option: str) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(PRIVATE_ROOT.resolve())
    except ValueError as exc:
        raise SystemExit(f"{option} must be written below {PRIVATE_ROOT}") from exc


def _ensure_parent(path: Path, *, private: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not private:
        return
    private_root = PRIVATE_ROOT.resolve()
    current = path.parent.resolve()
    while current.is_relative_to(private_root):
        os.chmod(current, 0o700)
        if current == private_root:
            break
        current = current.parent


def _atomic_write_bytes(path: Path, payload: bytes, *, private: bool) -> None:
    _ensure_parent(path, private=private)
    with tempfile.NamedTemporaryFile(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent, delete=False
    ) as handle:
        temporary_path = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temporary_path, 0o600 if private else 0o644)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_json(path: Path, value: object, *, private: bool = False) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    _atomic_write_bytes(path, payload, private=private)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _packet_readme() -> str:
    return """# MGP-Natural draft annotation packet

Status: `DRAFT_NOT_AUTHORIZED_FOR_DISTRIBUTION`.

This bundle contains no provisional actions, constructor rationales, resulting
states, lineage, source IDs, source locators, or `relation_to_prior` fields.  It
is not approved for annotation or external sharing until the canonical
confirmation protocol is frozen and human/legal/privacy approval is recorded.

The original MGP-Natural v0.1.0 archive and private reveal mapping must not be
given to annotators.  Annotators must work independently and must not search for
the parent package.  Use at least three annotators per item, preserve all
original rows, and adjudicate only after the individual forms are immutable.
"""


def _write_bundle(
    path: Path,
    packet_path: Path,
    answers_path: Path,
    commitment_path: Path,
) -> None:
    _ensure_parent(path, private=True)
    entries = {
        "README.md": _packet_readme().encode(),
        "annotation_form.csv": answers_path.read_bytes(),
        "blind_packet.jsonl": packet_path.read_bytes(),
        "packet_commitment.json": commitment_path.read_bytes(),
    }
    entries["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(payload).hexdigest()}  {name}\n"
        for name, payload in sorted(entries.items())
    ).encode()

    def zip_info(name: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = 0o100600 << 16
        return info

    with tempfile.NamedTemporaryFile(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent, delete=False
    ) as handle:
        temporary_path = Path(handle.name)
    try:
        with zipfile.ZipFile(
            temporary_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zf:
            for name, payload in sorted(entries.items()):
                zf.writestr(zip_info(name), payload)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--audit-report", type=Path)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--answers", type=Path)
    parser.add_argument("--private-map", type=Path)
    parser.add_argument("--commitment", type=Path)
    parser.add_argument("--safe-summary", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument(
        "--blinding-secret",
        type=int,
        help="private 128-bit-or-stronger integer; omit to generate 256 bits",
    )
    parser.add_argument("--write-private", action="store_true")
    args = parser.parse_args()

    audit = audit_candidate_archive(args.archive)
    if args.audit_report:
        _write_json(args.audit_report, audit)
    else:
        print(json.dumps(audit, indent=2, sort_keys=True))

    if not args.write_private:
        return 0

    required = {
        "--packet": args.packet,
        "--answers": args.answers,
        "--private-map": args.private_map,
        "--commitment": args.commitment,
        "--safe-summary": args.safe_summary,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        parser.error("--write-private requires " + ", ".join(missing))
    for option, path in required.items():
        assert path is not None
        _require_private_path(path, option)
    if args.bundle is not None:
        _require_private_path(args.bundle, "--bundle")

    blinding_secret = (
        args.blinding_secret if args.blinding_secret is not None else secrets.randbits(256)
    )
    if blinding_secret.bit_length() < 128:
        parser.error("--blinding-secret must contain at least 128 bits")
    packet, commitment, private_record, answers, safe_summary = (
        prepare_private_annotation_materials(args.archive, blinding_secret)
    )
    assert args.packet is not None
    assert args.answers is not None
    assert args.private_map is not None
    assert args.commitment is not None
    assert args.safe_summary is not None
    packet_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in packet)
    packet_bytes = packet_text.encode()
    evidence_hashes = {
        "protocol_sha256": _sha256(ROOT / "confirmation/protocol.yaml"),
        "packet_schema_sha256": _sha256(
            ROOT / "confirmation/schemas/natural_challenge.schema.json"
        ),
        "annotation_schema_sha256": _sha256(ROOT / "confirmation/schemas/annotation.schema.json"),
        "blinding_transform_sha256": _sha256(ROOT / "src/ask/confirmation/blinding.py"),
        "mgpn_transform_sha256": _sha256(ROOT / "src/ask/confirmation/mgpn_candidate.py"),
        "packet_jsonl_sha256": hashlib.sha256(packet_bytes).hexdigest(),
    }
    commitment.update(evidence_hashes)
    safe_summary.update(evidence_hashes)
    _atomic_write_bytes(args.packet, packet_bytes, private=True)
    _atomic_write_bytes(args.answers, answers.encode(), private=True)
    _write_json(args.private_map, private_record, private=True)
    _write_json(args.commitment, commitment, private=True)
    _write_json(args.safe_summary, safe_summary, private=True)
    if args.bundle:
        _write_bundle(args.bundle, args.packet, args.answers, args.commitment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
