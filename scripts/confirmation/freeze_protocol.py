#!/usr/bin/env python3
"""Emit a cryptographic commitment for a prospective confirmation protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=Path("confirmation/protocol.yaml"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = args.protocol.read_bytes()
    protocol = yaml.safe_load(raw)
    if protocol.get("status") != "READY_TO_FREEZE":
        raise SystemExit("protocol status must be READY_TO_FREEZE after independent human review")
    if protocol.get("human_legal_approval") is not True:
        raise SystemExit("human/legal approval is required before freeze")
    record = {
        "schema_version": "1.0",
        "frozen_at": datetime.now(UTC).isoformat(),
        "protocol_path": args.protocol.as_posix(),
        "protocol_sha256": hashlib.sha256(raw).hexdigest(),
        "status": "FROZEN_BEFORE_LABELS",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
