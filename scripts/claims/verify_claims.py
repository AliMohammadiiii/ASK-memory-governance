#!/usr/bin/env python3
"""Validate the ASK claim ledger and fail on missing or mismatched evidence."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = ROOT / "claims/claims.json"
DEFAULT_REPORT = ROOT / "claims/mismatch_report.json"
SCHEMA = ROOT / "claims/claims.schema.json"


def _builder() -> ModuleType:
    path = ROOT / "scripts/claims/build_claim_ledger.py"
    spec = importlib.util.spec_from_file_location("build_claim_ledger", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(ledger_path: Path = DEFAULT_LEDGER) -> dict[str, Any]:
    expected = json.loads(ledger_path.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(
        expected
    )
    current = _builder().build_claims(datetime.now(UTC).isoformat())
    current_by_id = {claim["claim_id"]: claim for claim in current["claims"]}
    mismatches: list[dict[str, Any]] = []
    for stored in expected["claims"]:
        claim_id = stored["claim_id"]
        observed = current_by_id.get(claim_id)
        if observed is None:
            mismatches.append({"claim_id": claim_id, "reason": "claim definition missing"})
            continue
        if observed["status"] != "verified":
            mismatches.append(
                {
                    "claim_id": claim_id,
                    "reason": observed["status"],
                    "expected": observed["expected_value"],
                    "observed": observed["observed_value"],
                }
            )
        if stored["source_artifact_sha256"] != observed["source_artifact_sha256"]:
            mismatches.append(
                {
                    "claim_id": claim_id,
                    "reason": "source artifact hash changed",
                    "stored": stored["source_artifact_sha256"],
                    "current": observed["source_artifact_sha256"],
                }
            )
        if stored["expected_value"] != observed["expected_value"]:
            mismatches.append({"claim_id": claim_id, "reason": "claim expectation changed"})
    stored_ids = {claim["claim_id"] for claim in expected["claims"]}
    for claim_id in sorted(current_by_id.keys() - stored_ids):
        mismatches.append({"claim_id": claim_id, "reason": "untracked current claim"})
    return {
        "schema_version": "1.0",
        "verified_at": datetime.now(UTC).isoformat(),
        "claim_count": len(expected["claims"]),
        "unexplained_mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "status": "PASS" if not mismatches else "FAIL",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    report = verify(args.ledger)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
