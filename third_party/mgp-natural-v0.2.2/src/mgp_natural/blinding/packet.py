"""HMAC-based blind IDs and allowlisted annotation bundles."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import zipfile
from pathlib import Path
from typing import Any

from mgp_natural.errors import ValidationError
from mgp_natural.util.io import (
    atomic_write_bytes,
    canonical_json_bytes,
    ensure_private_dir,
    iter_jsonl,
    sha256_file,
    write_json,
    write_jsonl,
)

PROHIBITED_KEY_FRAGMENTS = (
    "constructor_",
    "source_locator",
    "source_identifier",
    "source_id",
    "user_id",
    "chat_id",
    "page_id",
    "revision_id",
    "continuity_keys",
    "private_mapping",
    "mapping",
    "original_user",
    "original_chat",
    "relation_to_prior",
    "gold",
    "label",
    "action",
    "resulting_value",
)
PROHIBITED_FILENAME = re.compile(r"(?i)(keep|supersede|abstain|gold|label|mapping|secret|source[_-]?id)")
ALLOWED_ITEM_KEYS = {
    "schema_version",
    "blind_id",
    "source_track",
    "scope",
    "principal_type",
    "memory_slot",
    "prior_value",
    "dialogue",
    "candidate_turn_id",
    "annotation_questions",
}


def scan_prohibited_keys(value: Any, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.casefold().replace("-", "_")
            if any(fragment in normalized for fragment in PROHIBITED_KEY_FRAGMENTS):
                violations.append(f"{path}.{key}")
            violations.extend(scan_prohibited_keys(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(scan_prohibited_keys(child, f"{path}[{index}]"))
    return violations


def generate_secret() -> bytes:
    return secrets.token_bytes(32)


def validate_secret(secret: bytes) -> None:
    if len(secret) < 16:
        raise ValidationError("blinding secret must contain at least 128 bits")


def _token(secret: bytes, item_id: str) -> str:
    digest = hmac.new(secret, item_id.encode(), hashlib.sha256).hexdigest()
    return digest


def blind_items(items: list[dict[str, Any]], secret: bytes) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    validate_secret(secret)
    ordered = sorted(items, key=lambda item: _token(secret, item["item_id"]))
    blinded = []
    mapping = []
    for index, item in enumerate(ordered, 1):
        blind_id = f"MGP-{index:06d}-{_token(secret, item['item_id'])[:8].upper()}"
        public = {
            "schema_version": item["schema_version"],
            "blind_id": blind_id,
            "source_track": item["source_track"],
            "scope": item["scope"],
            "principal_type": item["principal_type"],
            "memory_slot": item["memory_slot"],
            "prior_value": item["prior_value"],
            "dialogue": item["dialogue"],
            "candidate_turn_id": item["candidate_turn_id"],
            "annotation_questions": [
                "Select KEEP, SUPERSEDE, or ABSTAIN, unless the item must be excluded.",
                "Give confidence as an integer from 1 through 5.",
                "Select sufficient evidence turn IDs, including the candidate turn.",
                "For SUPERSEDE, enter the replacement standing value.",
                "Provide a rationale and any exclusion or ambiguity category.",
            ],
        }
        extra = set(public) - ALLOWED_ITEM_KEYS
        if extra:
            raise ValidationError(f"unexpected blind keys: {sorted(extra)}")
        violations = scan_prohibited_keys(public)
        if violations:
            raise ValidationError(f"prohibited blind fields: {violations}")
        blinded.append(public)
        mapping.append({"item_id": item["item_id"], "blind_id": blind_id})
    return blinded, mapping


def build_packet(
    input_path: Path,
    private_dir: Path,
    packet_zip: Path,
    commitment_path: Path,
    secret: bytes | None = None,
) -> dict[str, Any]:
    ensure_private_dir(private_dir)
    secret = secret or generate_secret()
    validate_secret(secret)
    items = list(iter_jsonl(input_path))
    if not items:
        raise ValidationError("cannot build an empty annotation packet")
    blinded, mapping = blind_items(items, secret)
    secret_path = private_dir / "blinding_secret.bin"
    atomic_write_bytes(secret_path, secret, mode=0o600)
    mapping_path = private_dir / "blind_mapping.jsonl"
    write_jsonl(mapping_path, mapping, mode=0o600)
    bundle_dir = private_dir / "bundle"
    ensure_private_dir(bundle_dir)
    item_path = bundle_dir / "items.jsonl"
    form_path = bundle_dir / "annotation_form.jsonl"
    readme_path = bundle_dir / "README.txt"
    write_jsonl(item_path, blinded, mode=0o600)
    blank_forms = [
        {
            "schema_version": "1.0",
            "protocol_version": "1.0-prospective",
            "manual_version": "1.0-prospective",
            "blind_id": item["blind_id"],
            "annotator_pseudonym": "",
            "exclude": False,
            "exclusion_reason": None,
            "action": None,
            "confidence": None,
            "evidence_turn_ids": [],
            "resulting_value": None,
            "rationale": "",
            "ambiguity_category": None,
        }
        for item in blinded
    ]
    write_jsonl(form_path, blank_forms, mode=0o600)
    readme_path.write_text(
        "Private annotation packet. Source identifiers, constructor judgments, mappings, and gold are absent.\n",
        encoding="utf-8",
    )
    os.chmod(readme_path, 0o600)
    allowed = [item_path, form_path, readme_path]
    sums = bundle_dir / "SHA256SUMS"
    sums.write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in sorted(allowed)),
        encoding="utf-8",
    )
    os.chmod(sums, 0o600)
    allowed.append(sums)
    ensure_private_dir(packet_zip.parent)
    with zipfile.ZipFile(packet_zip, "w") as bundle:
        for path in sorted(allowed):
            if PROHIBITED_FILENAME.search(path.name):
                raise ValidationError(f"prohibited packet filename: {path.name}")
            info = zipfile.ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o600 << 16
            bundle.writestr(info, path.read_bytes())
    os.chmod(packet_zip, 0o600)
    mapping_commitment = hashlib.sha256(canonical_json_bytes(mapping)).hexdigest()
    secret_commitment = hashlib.sha256(secret).hexdigest()
    commitment = {
        "schema_version": "1.0",
        "item_count": len(blinded),
        "mapping_commitment_sha256": mapping_commitment,
        "secret_commitment_sha256": secret_commitment,
        "packet_sha256": sha256_file(packet_zip),
        "input_sha256": sha256_file(input_path),
        "transformation_code_sha256": sha256_file(Path(__file__)),
        "protocol_version": "1.0-prospective",
        "manual_version": "1.0-prospective",
        "deterministic_with_private_reveal_record": True,
        "mapping_revealed": False,
    }
    write_json(commitment_path, commitment)
    return commitment


def verify_packet(packet_zip: Path) -> dict[str, Any]:
    allowed = {"items.jsonl", "annotation_form.jsonl", "README.txt", "SHA256SUMS"}
    with zipfile.ZipFile(packet_zip) as bundle:
        names = set(bundle.namelist())
        if names != allowed:
            raise ValidationError(f"packet allowlist violation: {sorted(names ^ allowed)}")
        for name in names:
            if PROHIBITED_FILENAME.search(name):
                raise ValidationError(f"prohibited packet filename: {name}")
        expected = {}
        for line in bundle.read("SHA256SUMS").decode().splitlines():
            digest, name = line.split("  ", 1)
            expected[name] = digest
        for name in allowed - {"SHA256SUMS"}:
            observed = hashlib.sha256(bundle.read(name)).hexdigest()
            if expected.get(name) != observed:
                raise ValidationError(f"packet checksum failure: {name}")
        for line_number, line in enumerate(bundle.read("items.jsonl").decode().splitlines(), 1):
            import json

            item = json.loads(line)
            violations = scan_prohibited_keys(item)
            if violations:
                raise ValidationError(f"items.jsonl:{line_number}: prohibited keys {violations}")
            if set(item) - ALLOWED_ITEM_KEYS:
                raise ValidationError(f"items.jsonl:{line_number}: unexpected fields")
    return {"status": "VERIFIED", "packet_sha256": sha256_file(packet_zip), "members": sorted(allowed)}

