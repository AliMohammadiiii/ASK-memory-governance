"""Shared safeguards for prospective blinded confirmation packets."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from typing import Any

# These keys either are labels, directly encode a constructor's judgment, expose
# the source-to-gold join, or contain post-decision state.  Rejecting them at any
# nesting depth is intentionally stricter than deleting a few top-level fields.
PROHIBITED_KEYS = frozenset(
    {
        "action",
        "answer",
        "annotation",
        "annotation_status",
        "author_gold",
        "candidate_relation",
        "decision",
        "design_target",
        "evidence_spans",
        "expected_action",
        "expected_state",
        "final_consensus",
        "gold",
        "gold_action",
        "gold_rationale",
        "hidden_gold",
        "human_gold",
        "label",
        "label_relation",
        "lineage",
        "mgpn_id",
        "oldid",
        "permalink",
        "provisional_action",
        "relation_to_prior",
        "release_constraints",
        "resulting_state",
        "seed_code",
        "source_author",
        "source_author_kind",
        "source_item_id",
        "source_locator",
        "split",
        "split_group",
        "target_label",
    }
)

ALLOWED_TOP_LEVEL = frozenset(
    {
        "candidate",
        "consent_basis",
        "context",
        "id",
        "predecessor",
        "redaction_record",
        "source_class",
        "task_version",
    }
)
PUBLIC_TOP_LEVEL = ALLOWED_TOP_LEVEL - {"id"}
REQUIRED_TOP_LEVEL = frozenset({"candidate", "context", "id", "predecessor"})
PREFIX_RE = re.compile(r"^[A-Z]$")


def nested_keys(value: Any) -> set[str]:
    """Return every mapping key below ``value`` as a string."""

    if isinstance(value, Mapping):
        keys = {str(key) for key in value}
        for child in value.values():
            keys.update(nested_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(nested_keys(child))
        return keys
    return set()


def _validate_row(row: Mapping[str, Any], index: int) -> None:
    unknown = sorted(set(row) - ALLOWED_TOP_LEVEL)
    if unknown:
        raise ValueError(f"row {index} contains non-allowlisted top-level keys: {unknown}")
    missing = sorted(REQUIRED_TOP_LEVEL - set(row))
    if missing:
        raise ValueError(f"row {index} missing required fields: {missing}")
    found = sorted(nested_keys(row) & PROHIBITED_KEYS)
    if found:
        raise ValueError(f"row {index} contains prohibited keys: {found}")


def build_packet(
    rows: list[dict[str, Any]], blinding_secret: int, prefix: str = "C"
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Shuffle allowlisted rows and replace source identifiers with blind IDs.

    ``blinding_secret`` is private key material.  It belongs in the private
    reveal record and must not be published before annotation is frozen.
    """

    if not PREFIX_RE.fullmatch(prefix):
        raise ValueError("blind ID prefix must be exactly one uppercase ASCII letter")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"row {index} must be an object")
        _validate_row(row, index)
    source_ids = [str(row["id"]) for row in rows]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("source IDs must be unique before blinding")

    if blinding_secret < 0:
        raise ValueError("blinding secret must be non-negative")
    secret_bytes = blinding_secret.to_bytes(
        max(16, (blinding_secret.bit_length() + 7) // 8), byteorder="big"
    )
    order = sorted(
        range(len(rows)),
        key=lambda index: hmac.new(
            secret_bytes,
            f"{index}:{source_ids[index]}".encode(),
            hashlib.sha256,
        ).digest(),
    )
    packet: list[dict[str, Any]] = []
    mapping: dict[str, str] = {}
    for output_index, source_index in enumerate(order, start=1):
        source = rows[source_index]
        blind_id = f"{prefix}{output_index:06d}"
        stable_source_id = str(source["id"])
        mapping[blind_id] = stable_source_id
        public_row = {key: copy.deepcopy(source[key]) for key in PUBLIC_TOP_LEVEL if key in source}
        packet.append({"blind_id": blind_id, **public_row})
    return packet, mapping


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_commitment(
    packet: list[dict[str, Any]], mapping: dict[str, str], blinding_secret: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a public commitment and the corresponding private reveal record."""

    private_record = {
        "schema_version": "1.1",
        "blinding_secret": str(blinding_secret),
        "mapping": mapping,
    }
    commitment = {
        "schema_version": "1.1",
        "item_count": len(packet),
        "packet_sha256": canonical_hash(packet),
        "private_mapping_sha256": canonical_hash(private_record),
        "blinding_secret_sha256": hashlib.sha256(str(blinding_secret).encode("ascii")).hexdigest(),
        "labels_present": False,
        "source_ids_present": False,
        "blinding_secret_disclosed": False,
    }
    return commitment, private_record
