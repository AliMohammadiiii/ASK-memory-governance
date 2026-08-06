#!/usr/bin/env python3
"""Write a safe aggregate audit of an external MGP-Natural v0.2.2 input set."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from ask.confirmation.mgpn_full_intake import audit_full_input_directory

ROOT = Path(__file__).resolve().parents[2]


def _atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = audit_full_input_directory(args.input_root, repository_root=ROOT)
    _atomic_write_json(args.output, report)
    print(json.dumps({"status": report["status"], "output": args.output.as_posix()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
