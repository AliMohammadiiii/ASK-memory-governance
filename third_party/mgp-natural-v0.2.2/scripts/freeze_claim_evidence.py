from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from mgp_natural.audits.claims import evidence_commitment
from mgp_natural.util.io import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pin evidence-file hashes and aggregate commitments in a claim ledger"
    )
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    ledger_path = args.ledger
    root = ledger_path.parent.parent if ledger_path.parent.name == "claims" else ledger_path.parent
    ledger: dict[str, Any] = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    for claim in ledger.get("claims", []):
        if claim.get("status") not in {"SUPPORTED", "QUALIFIED_SUPPORTED"}:
            continue
        raw = claim.get("evidence", [])
        entries = raw if isinstance(raw, list) else [raw]
        normalized = []
        records = []
        for entry in entries:
            relative = entry if isinstance(entry, str) else entry["path"]
            path = Path(relative)
            resolved = path if path.is_absolute() else root / path
            digest = sha256_file(resolved)
            normalized.append({"path": relative, "sha256": digest})
            records.append({"path": relative, "sha256": digest})
        normalized.sort(key=lambda value: value["path"])
        records.sort(key=lambda value: value["path"])
        claim["evidence"] = normalized
        claim["evidence_hash"] = evidence_commitment(records)
    ledger_path.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    main()

