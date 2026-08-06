"""Verify claim wording against pinned machine-readable evidence and claim boundaries."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from mgp_natural.errors import ValidationError
from mgp_natural.util.io import canonical_json_bytes, sha256_file, write_json

PROHIBITED_PATTERNS = (
    r"\bindependently annotated gold\b",
    r"\bpublic[- ]release (?:clearance|ready|approved)\b",
    r"\blegal(?:ly)? (?:approved|cleared)\b",
    r"\bprivacy (?:approved|certified|guaranteed)\b",
    r"\brepresentative of (?:all )?(?:personal memory|natural conversation)\b",
    r"\bstate[- ]of[- ]the[- ]art\b",
    r"\bfirst (?:benchmark|dataset)\b",
    r"\bonly (?:benchmark|dataset)\b",
    r"\bpublication[- ]ready\b",
    r"\bJMLR[- ]ready\b",
    r"\bleaderboard[- ]ready\b",
    r"\bsafety[- ]certified\b",
    r"\bsafety certification\b",
    r"\bexhaustive novelty\b",
    r"\bexternal generalization\b",
    r"\bdownstream improvement\b",
    r"\bsuccessful human annotation\b",
    r"\bsuccessful adjudication\b",
    r"\bpublic redistribution rights\b",
)
NUMERIC_RESULT_PATTERNS = (
    r"\bmacro[- ]?F1\s*(?:=|:|of)\s*\d",
    r"\baccuracy\s*(?:=|:|of)\s*\d",
    r"\b(?:outperform|improv(?:e|ed|ement))\b.{0,80}\b\d+(?:\.\d+)?%",
)
NEGATION_MARKERS = (
    "do not claim",
    "must not claim",
    "prohibited",
    "not claim",
    "cannot claim",
    "does not claim",
    "no claim",
    "not yet",
    "pending",
    "blocked",
)
REQUIRED_CLAIM_FIELDS = {
    "id",
    "wording",
    "status",
    "evidence",
    "evidence_hash",
    "generation_command",
    "applicable_version",
    "allowed_qualifiers",
    "prohibited_stronger_wording",
}
SUPPORTED_STATUSES = {"SUPPORTED", "QUALIFIED_SUPPORTED"}


def load_ledger(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("claims"), list):
        raise ValidationError("invalid claim ledger")
    return value


def _repo_root(ledger_path: Path) -> Path:
    return ledger_path.parent.parent if ledger_path.parent.name == "claims" else ledger_path.parent


def _claim_context(text: str, start: int, end: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    return text[line_start : len(text) if line_end == -1 else line_end].strip()


def _is_boundary_context(context: str) -> bool:
    folded = context.casefold()
    return any(marker in folded for marker in NEGATION_MARKERS)


def _evidence_records(
    claim: dict[str, Any], ledger_path: Path
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    root = _repo_root(ledger_path)
    raw = claim.get("evidence")
    values: list[Any]
    if isinstance(raw, (str, dict)):
        values = [raw]
    elif isinstance(raw, list):
        values = raw
    else:
        return [], [{"claim_id": claim.get("id"), "reason": "invalid evidence field"}]

    records: list[dict[str, str]] = []
    mismatches: list[dict[str, Any]] = []
    for entry in values:
        if isinstance(entry, str):
            relative = entry
            expected = None
        elif isinstance(entry, dict) and isinstance(entry.get("path"), str):
            relative = entry["path"]
            expected = entry.get("sha256")
        else:
            mismatches.append(
                {"claim_id": claim.get("id"), "reason": "invalid evidence entry"}
            )
            continue
        path = Path(relative)
        resolved = path if path.is_absolute() else root / path
        if not resolved.is_file():
            mismatches.append(
                {
                    "claim_id": claim.get("id"),
                    "reason": "evidence file missing",
                    "path": relative,
                }
            )
            continue
        actual = sha256_file(resolved)
        if expected not in (None, actual):
            mismatches.append(
                {
                    "claim_id": claim.get("id"),
                    "reason": "evidence entry hash mismatch",
                    "path": relative,
                    "expected": expected,
                    "actual": actual,
                }
            )
        records.append({"path": relative, "sha256": actual})
    return sorted(records, key=lambda record: record["path"]), mismatches


def evidence_commitment(records: list[dict[str, str]]) -> str:
    """Return a deterministic aggregate commitment for a claim's evidence files."""

    return hashlib.sha256(canonical_json_bytes(records)).hexdigest()


def verify_claims(
    ledger_path: Path, document_paths: list[Path], output_path: Path
) -> dict[str, Any]:
    ledger = load_ledger(ledger_path)
    mismatches: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    allowed_exact: set[str] = set()
    evidence_audit: dict[str, Any] = {}

    for raw_claim in ledger["claims"]:
        if not isinstance(raw_claim, dict):
            mismatches.append({"reason": "claim is not an object"})
            continue
        claim = raw_claim
        claim_id = str(claim.get("id", ""))
        if not claim_id or claim_id in seen_ids:
            mismatches.append({"claim_id": claim_id, "reason": "missing or duplicate claim ID"})
            continue
        seen_ids.add(claim_id)
        missing = sorted(REQUIRED_CLAIM_FIELDS - set(claim))
        if missing:
            mismatches.append(
                {"claim_id": claim_id, "reason": "missing required fields", "fields": missing}
            )
        status = claim.get("status")
        if status in SUPPORTED_STATUSES:
            allowed_exact.add(str(claim.get("wording", "")))
            records, evidence_mismatches = _evidence_records(claim, ledger_path)
            mismatches.extend(evidence_mismatches)
            aggregate = evidence_commitment(records) if records else ""
            expected_aggregate = claim.get("evidence_hash")
            # Backward-compatible single-file ledgers may pin the direct file hash.
            valid_hashes = {aggregate}
            if len(records) == 1:
                valid_hashes.add(records[0]["sha256"])
            if not records or expected_aggregate not in valid_hashes:
                mismatches.append(
                    {
                        "claim_id": claim_id,
                        "reason": "aggregate evidence hash mismatch",
                        "expected": expected_aggregate,
                        "actual": aggregate,
                    }
                )
            if not str(claim.get("generation_command", "")).strip():
                mismatches.append({"claim_id": claim_id, "reason": "missing generation command"})
            if not str(claim.get("applicable_version", "")).strip():
                mismatches.append({"claim_id": claim_id, "reason": "missing applicable version"})
            evidence_audit[claim_id] = {"records": records, "aggregate_sha256": aggregate}

    for path in document_paths:
        if not path.is_file():
            mismatches.append({"path": path.as_posix(), "reason": "document missing"})
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in (*PROHIBITED_PATTERNS, *NUMERIC_RESULT_PATTERNS):
            for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
                context = _claim_context(text, match.start(), match.end())
                if _is_boundary_context(context):
                    continue
                mismatches.append(
                    {
                        "path": path.as_posix(),
                        "pattern": pattern,
                        "context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest(),
                    }
                )

    report = {
        "schema_version": "1.0",
        "ledger_claims": len(ledger["claims"]),
        "allowed_exact_claims": sorted(allowed_exact),
        "evidence_audit": evidence_audit,
        "documents_checked": [path.as_posix() for path in document_paths],
        "mismatches": mismatches,
        "status": "PASS" if not mismatches else "FAIL",
    }
    write_json(output_path, report)
    if mismatches:
        raise ValidationError(f"claim verification failed with {len(mismatches)} mismatch(es)")
    return report

