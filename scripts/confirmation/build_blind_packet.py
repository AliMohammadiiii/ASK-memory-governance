#!/usr/bin/env python3
"""Build a label-free, deterministically shuffled confirmation packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

PROHIBITED_KEYS = {
    "action",
    "answer",
    "author_gold",
    "design_target",
    "expected_action",
    "final_consensus",
    "gold",
    "gold_action",
    "hidden_gold",
    "human_gold",
    "label",
    "source_item_id",
}
ALLOWED_TOP_LEVEL = {"predecessor", "candidate", "context", "task_version", "id"}


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(map(str, value)) | set().union(*(_keys(v) for v in value.values()))
    if isinstance(value, list) and value:
        return set().union(*(_keys(v) for v in value))
    return set()


def build_packet(
    rows: list[dict[str, Any]], seed: int
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    for index, row in enumerate(rows):
        found = sorted(_keys(row) & PROHIBITED_KEYS)
        if found:
            raise ValueError(f"row {index} contains prohibited keys: {found}")
        missing = {"candidate", "context", "predecessor"} - set(row)
        if missing:
            raise ValueError(f"row {index} missing required fields: {sorted(missing)}")
    order = list(range(len(rows)))
    random.Random(seed).shuffle(order)
    packet: list[dict[str, Any]] = []
    mapping: dict[str, str] = {}
    for output_index, source_index in enumerate(order, start=1):
        source = rows[source_index]
        blind_id = f"C{output_index:06d}"
        stable_source_id = str(source.get("id", source_index))
        mapping[blind_id] = stable_source_id
        packet.append(
            {
                "blind_id": blind_id,
                "predecessor": source["predecessor"],
                "candidate": source["candidate"],
                "context": source["context"],
                **({"task_version": source["task_version"]} if "task_version" in source else {}),
            }
        )
    return packet, mapping


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--private-map", type=Path, required=True)
    parser.add_argument("--commitment", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=43017)
    parser.add_argument("--write", action="store_true", help="write outputs; default is audit-only")
    args = parser.parse_args()
    rows = [
        json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line
    ]
    packet, mapping = build_packet(rows, args.seed)
    commitment = {
        "schema_version": "1.0",
        "item_count": len(packet),
        "seed": args.seed,
        "packet_sha256": canonical_hash(packet),
        "private_mapping_sha256": canonical_hash(mapping),
        "labels_present": False,
    }
    if not args.write:
        print(json.dumps(commitment, indent=2, sort_keys=True))
        return 0
    for path in (args.packet, args.private_map, args.commitment):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.packet.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in packet), encoding="utf-8"
    )
    args.private_map.write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.commitment.write_text(
        json.dumps(commitment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
