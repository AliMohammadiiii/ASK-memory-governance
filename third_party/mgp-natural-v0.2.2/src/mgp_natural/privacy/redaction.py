"""Deterministic redaction with auditable before/after commitments."""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mgp_natural.privacy.scanner import PATTERNS, SECRET_CHUNK, shannon_entropy
from mgp_natural.util.io import canonical_json_hash, iter_jsonl, write_json, write_jsonl


def redact_text(
    text: str,
    known_identity_tokens: Sequence[str] = (),
) -> tuple[str, list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    redacted = text
    token_specs = [
        ("KNOWN_IDENTITY_TOKEN", re.compile(re.escape(token), re.IGNORECASE), "[IDENTITY]")
        for token in sorted({value for value in known_identity_tokens if value}, key=len, reverse=True)
    ]
    regex_specs = [
        (spec.name, spec.regex, f"[{spec.name}]")
        for spec in PATTERNS
    ]
    # Replace in deterministic category order; exact source strings never enter logs.
    for category, pattern, placeholder in (*token_specs, *regex_specs):
        matches = list(pattern.finditer(redacted))
        if not matches:
            continue
        for match in reversed(matches):
            original = match.group(0)
            redacted = redacted[: match.start()] + placeholder + redacted[match.end() :]
            events.append(
                {
                    "category": category,
                    "before_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
                    "placeholder": placeholder,
                }
            )
    matches = [
        match
        for match in SECRET_CHUNK.finditer(redacted)
        if shannon_entropy(match.group(0)) >= 4.0 and not match.group(0).isdigit()
    ]
    for match in reversed(matches):
        original = match.group(0)
        placeholder = "[SECRET_LIKE]"
        redacted = redacted[: match.start()] + placeholder + redacted[match.end() :]
        events.append(
            {
                "category": "HIGH_ENTROPY_SECRET_LIKE",
                "before_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
                "placeholder": placeholder,
            }
        )
    return redacted, events


def _redact_value(
    value: Any,
    path: str,
    events: list[dict[str, Any]],
    known_identity_tokens: Sequence[str],
) -> Any:
    if isinstance(value, str):
        result, local = redact_text(value, known_identity_tokens)
        for event in local:
            event["path"] = path
            events.append(event)
        return result
    if isinstance(value, list):
        return [
            _redact_value(child, f"{path}[{index}]", events, known_identity_tokens)
            for index, child in enumerate(value)
        ]
    if isinstance(value, dict):
        return {
            key: _redact_value(child, f"{path}.{key}", events, known_identity_tokens)
            for key, child in value.items()
        }
    return value


def redact_jsonl(
    input_path: Path,
    output_path: Path,
    log_path: Path,
    summary_path: Path,
    known_identity_tokens: Sequence[str] = (),
) -> dict[str, Any]:
    output: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []
    for row in iter_jsonl(input_path):
        events: list[dict[str, Any]] = []
        redacted = _redact_value(row, "$", events, known_identity_tokens)
        output.append(redacted)
        logs.append(
            {
                "record_id_private": row.get("item_id"),
                "review_id": hashlib.sha256(str(row.get("item_id")).encode("utf-8")).hexdigest()[:20],
                "before_sha256": canonical_json_hash(row),
                "after_sha256": canonical_json_hash(redacted),
                "events": events,
            }
        )
    write_jsonl(output_path, output, mode=0o600)
    write_jsonl(log_path, logs, mode=0o600)
    summary = {
        "schema_version": "1.0",
        "records": len(output),
        "redaction_events": sum(len(log["events"]) for log in logs),
        "categories": dict(
            Counter(event["category"] for log in logs for event in log["events"])
        ),
        "manual_review_required": True,
        "anonymity_guaranteed": False,
        "status": "DETERMINISTIC_REDACTION_COMPLETE_HUMAN_REVIEW_PENDING",
    }
    write_json(summary_path, summary)
    return summary

