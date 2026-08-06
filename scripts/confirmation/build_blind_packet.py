#!/usr/bin/env python3
"""Build a label-free, shuffled confirmation packet and private reveal map."""

from __future__ import annotations

import argparse
import json
import os
import secrets
from pathlib import Path

from ask.confirmation.blinding import build_packet, make_commitment

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT / ".private"


def _require_private_mapping_path(path: Path) -> None:
    try:
        path.resolve().relative_to(PRIVATE_ROOT.resolve())
    except ValueError as exc:
        raise SystemExit(f"--private-map must be written below {PRIVATE_ROOT}") from exc


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number}: row must be an object")
        rows.append(row)
    return rows


def _write_private_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--private-map", type=Path, required=True)
    parser.add_argument("--commitment", type=Path, required=True)
    parser.add_argument("--prefix", choices=tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), default="C")
    parser.add_argument(
        "--blinding-secret",
        type=int,
        help="private 128-bit-or-stronger integer; omit to generate 256 bits",
    )
    parser.add_argument("--write", action="store_true", help="write outputs; default is audit-only")
    args = parser.parse_args()

    rows = _read_jsonl(args.input)
    blinding_secret = (
        args.blinding_secret if args.blinding_secret is not None else secrets.randbits(256)
    )
    if args.write and blinding_secret.bit_length() < 128:
        parser.error("--blinding-secret must contain at least 128 bits when writing a packet")
    packet, mapping = build_packet(rows, blinding_secret, prefix=args.prefix)
    commitment, private_record = make_commitment(packet, mapping, blinding_secret)

    if not args.write:
        print(json.dumps(commitment, indent=2, sort_keys=True))
        return 0

    _require_private_mapping_path(args.private_map)
    for path in (args.packet, args.private_map, args.commitment):
        path.parent.mkdir(parents=True, exist_ok=True)
    private_root = PRIVATE_ROOT.resolve()
    current = args.private_map.parent.resolve()
    while current.is_relative_to(private_root):
        os.chmod(current, 0o700)
        if current == private_root:
            break
        current = current.parent
    args.packet.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in packet),
        encoding="utf-8",
    )
    _write_private_json(args.private_map, private_record)
    args.commitment.write_text(
        json.dumps(commitment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
