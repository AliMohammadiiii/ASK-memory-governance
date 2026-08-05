#!/usr/bin/env python3
"""Build a path-neutral derived manifest for the pinned MGP-Natural candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_EXTERNAL_SHA256 = {
    "parent_archive": "0ffe92eba00bcec503e81589965c381857f4524fdd955902678d636eca7b7f26",
    "delivery_report": "f49082f37f2fb4f7e920c585b84efcb42a2ee4945f4f3e9e50a642dce5cb4a90",
    "research_report": "6459f07ed717624b0fbcf581ce78bf944e89353f37538ac5a60dfde84345c50d",
}

REPOSITORY_EVIDENCE_FILES = {
    "code": (
        "scripts/confirmation/build_blind_packet.py",
        "scripts/confirmation/prepare_mgpn_candidate.py",
        "scripts/confirmation/score_mgpn_predictions.py",
        "scripts/confirmation/validate_mgpn_annotations.py",
        "scripts/confirmation/verify_mgpn_candidate.py",
        "scripts/provenance/build_mgpn_derived_manifest.py",
        "src/ask/confirmation/__init__.py",
        "src/ask/confirmation/blinding.py",
        "src/ask/confirmation/mgpn_candidate.py",
        "src/ask/confirmation/mgpn_scoring.py",
        "src/ask/confirmation/mgpn_validation.py",
    ),
    "schema": (
        "confirmation/schemas/adjudication.schema.json",
        "confirmation/schemas/annotation.schema.json",
        "confirmation/schemas/item.schema.json",
        "confirmation/schemas/natural_challenge.schema.json",
    ),
    "protocol": (
        "confirmation/README.md",
        "confirmation/natural_challenge/README.md",
        "confirmation/protocol.yaml",
    ),
}


class ManifestInputError(ValueError):
    """Raised when an evidence input does not match the frozen manifest contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically without machine-local formatting state."""

    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _verified_file(
    logical_name: str,
    path: Path,
    expected_sha256: str,
) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing {logical_name} evidence input")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ManifestInputError(
            f"{logical_name} SHA-256 mismatch: expected {expected_sha256}, got {actual}"
        )
    return {
        "sha256": actual,
        "size_bytes": path.stat().st_size,
        "verified_against_pin": True,
    }


def _read_audit(path: Path, expected_parent_sha256: str) -> tuple[dict[str, Any], str, int]:
    if not path.is_file():
        raise FileNotFoundError("missing candidate audit report")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestInputError("candidate audit report must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ManifestInputError("candidate audit report must contain one JSON object")

    parent = value.get("parent_archive")
    archive_manifest = value.get("manifest")
    if not isinstance(parent, dict) or parent.get("sha256") != expected_parent_sha256:
        raise ManifestInputError("candidate audit does not identify the pinned parent archive")
    if value.get("status") != "QUARANTINED_RELEASE_CANDIDATE":
        raise ManifestInputError("candidate audit status must remain QUARANTINED_RELEASE_CANDIDATE")
    if value.get("core_integrity_passed") is not True:
        raise ManifestInputError("candidate audit does not pass core integrity")
    if value.get("gold_or_public_release_eligible") is not False:
        raise ManifestInputError("candidate audit must not clear the gold/public-release gate")
    if not isinstance(archive_manifest, dict) or archive_manifest.get("verified") is not True:
        raise ManifestInputError("candidate audit does not verify the embedded archive manifest")
    return value, hashlib.sha256(raw).hexdigest(), len(raw)


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ManifestInputError(f"candidate audit field {field} must be a non-negative integer")
    return value


def _audit_summary(audit: Mapping[str, Any]) -> dict[str, Any]:
    """Project only aggregate, non-identifying facts from the candidate audit."""

    dataset = audit.get("dataset")
    split = audit.get("split_audit")
    blind = audit.get("blind_packet_audit")
    release = audit.get("release_checklist")
    archive_manifest = audit.get("manifest")
    if not all(isinstance(value, Mapping) for value in (dataset, split, blind, release)):
        raise ManifestInputError("candidate audit is missing aggregate audit sections")
    assert isinstance(dataset, Mapping)
    assert isinstance(split, Mapping)
    assert isinstance(blind, Mapping)
    assert isinstance(release, Mapping)
    assert isinstance(archive_manifest, Mapping)

    component_sizes = split.get("continuity_component_sizes")
    if not isinstance(component_sizes, list):
        raise ManifestInputError("candidate audit is missing continuity component sizes")
    sizes = [
        _nonnegative_int(value, "split_audit.continuity_component_sizes")
        for value in component_sizes
    ]

    return {
        "status": "QUARANTINED_RELEASE_CANDIDATE",
        "core_integrity_passed": True,
        "gold_or_public_release_eligible": False,
        "embedded_manifest": {
            "entry_count": _nonnegative_int(
                archive_manifest.get("entry_count"), "manifest.entry_count"
            ),
            "verified": True,
        },
        "dataset": {
            "record_count": _nonnegative_int(dataset.get("record_count"), "dataset.record_count"),
            "unique_id_count": _nonnegative_int(
                dataset.get("unique_id_count"), "dataset.unique_id_count"
            ),
            "dialogue_excerpt_row_count": _nonnegative_int(
                dataset.get("dialogue_excerpt_row_count"),
                "dataset.dialogue_excerpt_row_count",
            ),
            "multi_contributor_excerpt_count": _nonnegative_int(
                dataset.get("multi_contributor_excerpt_count"),
                "dataset.multi_contributor_excerpt_count",
            ),
            "single_contributor_excerpt_count": _nonnegative_int(
                dataset.get("single_contributor_excerpt_count"),
                "dataset.single_contributor_excerpt_count",
            ),
            "independent_adjudication_complete_count": _nonnegative_int(
                dataset.get("independent_adjudication_complete_count"),
                "dataset.independent_adjudication_complete_count",
            ),
            "requires_independent_confirmation_count": _nonnegative_int(
                dataset.get("requires_independent_confirmation_count"),
                "dataset.requires_independent_confirmation_count",
            ),
        },
        "blind_packet": {
            "record_count": _nonnegative_int(
                blind.get("record_count"), "blind_packet_audit.record_count"
            ),
            "relation_to_prior_present_count": _nonnegative_int(
                blind.get("relation_to_prior_present_count"),
                "blind_packet_audit.relation_to_prior_present_count",
            ),
            "deterministic_relation_rule_correct": _nonnegative_int(
                blind.get("deterministic_relation_rule_correct"),
                "blind_packet_audit.deterministic_relation_rule_correct",
            ),
            "safe_for_independent_annotation": blind.get("safe_for_independent_annotation") is True,
        },
        "split_independence": {
            "benchmark_held_out_split_valid": split.get("benchmark_held_out_split_valid") is True,
            "continuity_component_count": _nonnegative_int(
                split.get("continuity_component_count"),
                "split_audit.continuity_component_count",
            ),
            "continuity_component_sizes": sizes,
            "mixed_split_continuity_component_count": _nonnegative_int(
                split.get("mixed_split_continuity_component_count"),
                "split_audit.mixed_split_continuity_component_count",
            ),
        },
        "release_checklist": {
            "unchecked_item_count": _nonnegative_int(
                release.get("unchecked_item_count"), "release_checklist.unchecked_item_count"
            ),
            "all_required_signoffs_complete": release.get("all_required_signoffs_complete") is True,
        },
    }


def _repository_hashes(repository_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for category, relative_paths in REPOSITORY_EVIDENCE_FILES.items():
        files: dict[str, str] = {}
        for relative_path in relative_paths:
            path = repository_root / relative_path
            if not path.is_file():
                raise FileNotFoundError(f"missing repository {category} evidence: {relative_path}")
            files[relative_path] = sha256_file(path)
        result[category] = {
            "files": files,
            "set_sha256": canonical_sha256(files),
        }
    return result


def build_manifest(
    archive: Path,
    delivery_report: Path,
    research_report: Path,
    audit_report: Path,
    *,
    repository_root: Path = ROOT,
    expected_external_sha256: Mapping[str, str] = EXPECTED_EXTERNAL_SHA256,
) -> dict[str, Any]:
    missing_pins = sorted(set(EXPECTED_EXTERNAL_SHA256) - set(expected_external_sha256))
    if missing_pins:
        raise ManifestInputError(f"missing external evidence pins: {missing_pins}")

    external = {
        "parent_archive": _verified_file(
            "parent archive", archive, expected_external_sha256["parent_archive"]
        ),
        "delivery_report": _verified_file(
            "delivery report", delivery_report, expected_external_sha256["delivery_report"]
        ),
        "research_report": _verified_file(
            "research report", research_report, expected_external_sha256["research_report"]
        ),
    }
    audit, audit_sha256, audit_size = _read_audit(
        audit_report, expected_external_sha256["parent_archive"]
    )

    return {
        "schema_version": "ask-mgpn-derived-manifest/v1",
        "artifact_id": "mgp-natural-v0.1.1-derived-audit",
        "status": "DERIVED_AUDIT_ONLY",
        "derivation": (
            "Path-neutral post-hoc audit of the pinned MGP-Natural v0.1.0 candidate; "
            "the parent archive and historical reports remain immutable evidence inputs."
        ),
        "evidence_inputs": external,
        "candidate_audit": {
            "sha256": audit_sha256,
            "size_bytes": audit_size,
            "summary": _audit_summary(audit),
        },
        "repository_identity": _repository_hashes(repository_root),
        "anomaly_ledger": [
            {
                "code": "PARENT_BLIND_PACKET_LABEL_LEAKAGE",
                "effect": (
                    "The parent packet exposes relation_to_prior and its deterministic rule "
                    "recovers all 36 provisional actions."
                ),
            },
            {
                "code": "NO_INDEPENDENT_CONTINUITY_SPLIT",
                "effect": (
                    "Page-family and contributor continuity forms components of sizes 35 and 1; "
                    "the parent train/dev/test split is not an independent benchmark split."
                ),
            },
            {
                "code": "PROVISIONAL_LABEL_PROVENANCE",
                "effect": (
                    "The parent-declared expert-provisional labels have no completed independent "
                    "annotation or adjudication evidence."
                ),
            },
            {
                "code": "SOURCE_STRUCTURE_LIMITATION",
                "effect": (
                    "Five records contain one distinct source contributor and the domain is "
                    "Wikipedia editorial discussion rather than deployed assistant memory."
                ),
            },
            {
                "code": "PUBLICATION_APPROVAL_PENDING",
                "effect": (
                    "Human legal, privacy, attribution, and redistribution approvals are not "
                    "recorded as complete."
                ),
            },
        ],
        "claim_boundary": {
            "allowed": [
                (
                    "The pinned artifact is a 36-item Wikipedia editorial-discussion feasibility "
                    "seed with provisional constructor labels."
                ),
                (
                    "This manifest verifies artifact identity and aggregate technical audit facts; "
                    "it does not create independent labels or public clearance."
                ),
            ],
            "prohibited": [
                "independently annotated gold benchmark",
                "public-release-cleared dataset",
                "representative personal-assistant memory benchmark",
                "independent held-out benchmark split",
                "leaderboard-quality result",
                "independent QA or legal approval",
            ],
        },
        "gates": {
            "protocol_frozen_before_labels": False,
            "minimum_three_independent_annotations_per_item": False,
            "independent_adjudication_complete": False,
            "human_legal_approval": False,
            "privacy_review_complete": False,
            "attribution_review_complete": False,
            "public_redistribution_approved": False,
            "benchmark_release_eligible": False,
        },
        "privacy_boundary": {
            "external_payloads_embedded": False,
            "raw_conversation_embedded": False,
            "provisional_item_labels_embedded": False,
            "source_identifiers_embedded": False,
            "machine_local_paths_embedded": False,
        },
    }


def atomic_write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    payload = canonical_json_bytes(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--delivery-report", type=Path, required=True)
    parser.add_argument("--research-report", type=Path, required=True)
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        manifest = build_manifest(
            args.archive,
            args.delivery_report,
            args.research_report,
            args.audit_report,
        )
        atomic_write_manifest(args.output, manifest)
    except (FileNotFoundError, ManifestInputError) as exc:
        parser.error(str(exc))
    print(
        canonical_json_bytes(
            {
                "manifest_sha256": hashlib.sha256(canonical_json_bytes(manifest)).hexdigest(),
                "status": manifest["status"],
            }
        ).decode("utf-8"),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
