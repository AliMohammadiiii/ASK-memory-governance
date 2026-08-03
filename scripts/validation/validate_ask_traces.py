#!/usr/bin/env python3
"""Validate serialized ASK transition events and their local semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schema/ask_transition_event.schema.json"


def _event_id_body(event: dict[str, Any]) -> dict[str, Any]:
    config = event["configuration"]
    return {
        "action": event["action"],
        "store_mode": event["store_mode"],
        "prior_record_id": event["prior_record_id"],
        "candidate_record_id": event["candidate_record_id"],
        "resulting_record_id": event["resulting_record_id"],
        "predecessor_record_id": event["predecessor_record_id"],
        "configuration_id": config["configuration_id"],
        "configuration_sha256": config["sha256"],
        "evidence_digest": event["evidence_digest"],
        "before_digest": event["before_digest"],
        "after_digest": event["after_digest"],
        "keep_admitted_candidate": event["keep_admitted_candidate"],
    }


def _stable_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def semantic_errors(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    action = event["action"]
    if _stable_digest(_event_id_body(event)) != event["event_id"]:
        errors.append("event_id does not match canonical event body")
    if action == "Abstain":
        if event["before_digest"] != event["after_digest"]:
            errors.append("Abstain changed the state digest")
        if event["resulting_record_id"] is not None or event["keep_admitted_candidate"]:
            errors.append("Abstain recorded a committed result")
    elif action == "Keep":
        if not event["keep_admitted_candidate"] and event["before_digest"] != event["after_digest"]:
            errors.append("non-admitting Keep changed the state digest")
        if event["store_mode"] == "single_slot_versioned" and event["keep_admitted_candidate"]:
            errors.append("single-slot Keep cannot admit a candidate")
    elif action == "Supersede":
        if not all(
            event[key] for key in ("prior_record_id", "candidate_record_id", "resulting_record_id")
        ):
            errors.append("Supersede lacks prior/candidate/result identifiers")
        if event["predecessor_record_id"] != event["prior_record_id"]:
            errors.append("Supersede predecessor differs from compared prior")
        if event["resulting_record_id"] != event["candidate_record_id"]:
            errors.append("Supersede result differs from candidate")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=Path, nargs="*")
    args = parser.parse_args()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    problems: list[str] = []
    count = 0
    for path in args.inputs:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        for index, event in enumerate(rows):
            count += 1
            problems.extend(
                f"{path}:{index + 1}: {error.message}" for error in validator.iter_errors(event)
            )
            problems.extend(f"{path}:{index + 1}: {message}" for message in semantic_errors(event))
    if problems:
        raise SystemExit("ASK trace validation failed:\n- " + "\n- ".join(problems))
    print(json.dumps({"status": "PASS", "events_validated": count, "schema": str(SCHEMA)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
