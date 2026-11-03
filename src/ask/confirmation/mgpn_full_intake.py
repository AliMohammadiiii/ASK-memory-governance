"""Fail-closed aggregate intake audit for private MGP-Natural v0.2.2 sources.

The audit deliberately accepts an external directory and emits only aggregate
integrity facts.  It never copies source records, identifiers, excerpts, or
absolute paths into the repository-facing report.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import stat
import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any

FULL_INPUT_FILENAMES = (
    "studychat.zip",
    "studychat_full_source_manifest.json",
    "wikiconv-english-2003.corpus.zip",
    "wikiconv-english-2018data.zip",
    "wikiconv_compact_manifest.json",
    "utterances.part001.jsonl.gz",
    "utterances.part002.jsonl.gz",
    "utterances.part003.jsonl.gz",
    "utterances.part004.jsonl.gz",
    "utterances.part005.jsonl.gz",
    "utterances.part006.jsonl.gz",
    "utterances.part007.jsonl.gz",
)

STUDYCHAT_MEMBERS = (
    "studychat/data.jsonl",
    "studychat/dialogues/f24_labeled_dialogues.jsonl",
    "studychat/dialogues/s25_labeled_dialogues.jsonl",
)
WIKICONV_2003_MEMBER = "utterances.jsonl"

DERIVED_WORKSPACE_FILENAMES = (
    "wikiconv_split_private.jsonl",
    "studychat_rows.jsonl",
    "privacy_findings.jsonl",
    "studychat_reconstruction_anomalies.jsonl",
    "redaction_log.jsonl",
    "studychat_candidates.jsonl",
    "studychat_construction_items_redacted.jsonl",
    "studychat_components.jsonl",
    "wikiconv_components.jsonl",
    "studychat_split_private.jsonl",
    "construction_items_redacted.jsonl",
    "wikiconv_candidate_windows.jsonl",
    "wikiconv_construction_items_redacted.jsonl",
    "studychat_rejections.jsonl",
    "source_id_hmac_secret.bin",
    "packets/combined/blind_mapping.jsonl",
    "packets/combined/blinding_secret.bin",
    "packets/mgp_natural_full_annotation.zip",
)
DERIVED_SECRET_FILENAMES = frozenset(
    {"source_id_hmac_secret.bin", "packets/combined/blinding_secret.bin"}
)


class FullIntakeError(ValueError):
    """Raised when a private full-source input fails the intake contract."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_safe_zip(zf: zipfile.ZipFile, *, archive_name: str) -> None:
    names = [member.filename for member in zf.infolist()]
    if len(names) != len(set(names)):
        raise FullIntakeError(f"{archive_name}: duplicate member names are not allowed")
    for member in zf.infolist():
        path = PurePosixPath(member.filename)
        mode = member.external_attr >> 16
        if path.is_absolute() or ".." in path.parts:
            raise FullIntakeError(f"{archive_name}: unsafe member path")
        if member.flag_bits & 0x1:
            raise FullIntakeError(f"{archive_name}: encrypted members are not allowed")
        file_type = stat.S_IFMT(mode)
        if file_type and stat.S_ISLNK(mode):
            raise FullIntakeError(f"{archive_name}: symbolic-link members are not allowed")
        if file_type and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise FullIntakeError(f"{archive_name}: special-file members are not allowed")
    if zf.testzip() is not None:
        raise FullIntakeError(f"{archive_name}: ZIP integrity check failed")


def _count_nonempty_jsonl_lines(lines: Iterable[bytes], *, source_name: str) -> int:
    count = 0
    first_value_checked = False
    for line in lines:
        if not line.strip():
            continue
        if not first_value_checked:
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise FullIntakeError(f"{source_name}: malformed JSONL") from exc
            if not isinstance(value, dict):
                raise FullIntakeError(f"{source_name}: JSONL rows must be objects")
            first_value_checked = True
        count += 1
    if not first_value_checked:
        raise FullIntakeError(f"{source_name}: JSONL is empty")
    return count


def _zip_jsonl_counts(path: Path, members: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    with zipfile.ZipFile(path) as zf:
        _assert_safe_zip(zf, archive_name=path.name)
        available = set(zf.namelist())
        missing = sorted(set(members) - available)
        if missing:
            raise FullIntakeError(f"{path.name}: required member is missing")
        for member in members:
            with zf.open(member) as handle:
                counts[member] = _count_nonempty_jsonl_lines(handle, source_name=path.name)
    return counts


def _gzip_jsonl_count(path: Path) -> int:
    try:
        with gzip.open(path, "rb") as handle:
            return _count_nonempty_jsonl_lines(handle, source_name=path.name)
    except OSError as exc:
        raise FullIntakeError(f"{path.name}: gzip integrity check failed") from exc


def _input_set_commitment(input_root: Path, filenames: Iterable[str]) -> str:
    entries = [
        {
            "filename": name,
            "bytes": (input_root / name).stat().st_size,
            "sha256": _sha256_file(input_root / name),
        }
        for name in filenames
    ]
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def audit_full_input_directory(input_root: Path, *, repository_root: Path) -> dict[str, Any]:
    """Audit the expected private inputs without retaining their payloads."""

    input_root = input_root.resolve()
    repository_root = repository_root.resolve()
    if not input_root.is_dir():
        raise FullIntakeError("full input directory does not exist")
    try:
        input_root.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise FullIntakeError("full input directory must remain outside the repository")

    raw_missing = [name for name in FULL_INPUT_FILENAMES if not (input_root / name).is_file()]
    derived_missing = [
        name for name in DERIVED_WORKSPACE_FILENAMES if not (input_root / name).is_file()
    ]
    if not raw_missing:
        return _audit_raw_source_layout(input_root)
    if not derived_missing:
        return _audit_private_derived_layout(input_root)
    raise FullIntakeError("input directory does not match a supported MGP-Natural v0.2.2 layout")


def _audit_raw_source_layout(input_root: Path) -> dict[str, Any]:
    """Audit the original 13-file source layout without retaining payloads."""

    for manifest_name in ("studychat_full_source_manifest.json", "wikiconv_compact_manifest.json"):
        try:
            value = json.loads((input_root / manifest_name).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FullIntakeError(f"{manifest_name}: malformed JSON") from exc
        if not isinstance(value, dict):
            raise FullIntakeError(f"{manifest_name}: expected a JSON object")

    studychat = _zip_jsonl_counts(input_root / "studychat.zip", STUDYCHAT_MEMBERS)
    wikiconv_2003 = _zip_jsonl_counts(
        input_root / "wikiconv-english-2003.corpus.zip", (WIKICONV_2003_MEMBER,)
    )
    with zipfile.ZipFile(input_root / "wikiconv-english-2018data.zip") as zf:
        _assert_safe_zip(zf, archive_name="wikiconv-english-2018data.zip")
    wikiconv_2018_parts = [
        _gzip_jsonl_count(input_root / f"utterances.part{index:03d}.jsonl.gz")
        for index in range(1, 8)
    ]

    return {
        "schema_version": "ask-mgpn-full-intake/v1",
        "artifact_id": "mgp-natural-v0.2.2-full-source-intake",
        "status": "QUARANTINED_PRIVATE_SOURCE_INTAKE",
        "input_root_recorded_as": "$MGP_NATURAL_FULL_INPUTS",
        "input_layout": "RAW_SOURCE_ARCHIVES",
        "input_file_count": len(FULL_INPUT_FILENAMES),
        "input_set_sha256": _input_set_commitment(input_root, FULL_INPUT_FILENAMES),
        "archive_safety": {
            "duplicate_member_names_rejected": True,
            "encrypted_members_rejected": True,
            "symbolic_link_members_rejected": True,
            "unsafe_paths_rejected": True,
            "zip_and_gzip_integrity_checked": True,
        },
        "source_tracks": {
            "studychat": {
                "kind": "natural_human_llm_educational_interaction",
                "canonical_interaction_count": studychat["studychat/data.jsonl"],
                "dialogue_record_counts": {
                    "fall_2024": studychat["studychat/dialogues/f24_labeled_dialogues.jsonl"],
                    "spring_2025": studychat["studychat/dialogues/s25_labeled_dialogues.jsonl"],
                },
            },
            "wikiconv": {
                "kind": "natural_human_human_editorial_conversation",
                "utterance_count_2003": wikiconv_2003[WIKICONV_2003_MEMBER],
                "utterance_count_2018": sum(wikiconv_2018_parts),
                "utterance_counts_2018_parts": wikiconv_2018_parts,
            },
        },
        "claim_boundary": {
            "raw_sources_embedded": False,
            "source_identifiers_embedded": False,
            "conversation_text_embedded": False,
            "annotations_embedded": False,
            "natural_gold_available": False,
            "publication_eligible": False,
            "mixed_track_headline_allowed": False,
        },
        "required_gates": {
            "rights_and_redistribution_review": "PENDING_HUMAN_DECISION",
            "manual_privacy_review": "PENDING_HUMAN_DECISION",
            "protocol_freeze_before_annotation": "PENDING_HUMAN_DECISION",
            "independent_annotation_and_adjudication": "PENDING_HUMAN_DECISION",
            "track_specific_continuity_splits": "PENDING_MACHINE_AND_HUMAN_REVIEW",
        },
    }


def _audit_private_derived_layout(input_root: Path) -> dict[str, Any]:
    """Audit a private workflow directory without interpreting its labels or text."""

    for archive_name in ("packets/mgp_natural_full_annotation.zip",):
        with zipfile.ZipFile(input_root / archive_name) as zf:
            _assert_safe_zip(zf, archive_name=Path(archive_name).name)

    counts = {
        name: _count_nonempty_jsonl_lines(
            (input_root / name).open("rb"), source_name=Path(name).name
        )
        for name in DERIVED_WORKSPACE_FILENAMES
        if name.endswith(".jsonl") and name != "packets/combined/blind_mapping.jsonl"
    }
    nonsecret_filenames = tuple(
        name for name in DERIVED_WORKSPACE_FILENAMES if name not in DERIVED_SECRET_FILENAMES
    )
    return {
        "schema_version": "ask-mgpn-full-intake/v1",
        "artifact_id": "mgp-natural-v0.2.2-full-source-intake",
        "status": "QUARANTINED_PRIVATE_DERIVED_WORKSPACE",
        "input_layout": "PRIVATE_DERIVED_WORKSPACE",
        "input_root_recorded_as": "$MGP_NATURAL_FULL_INPUTS",
        "input_file_count": len(DERIVED_WORKSPACE_FILENAMES),
        "nonsecret_input_set_sha256": _input_set_commitment(input_root, nonsecret_filenames),
        "raw_source_archive_integrity_verified": False,
        "archive_safety": {
            "annotation_bundle_zip_integrity_checked": True,
            "duplicate_member_names_rejected": True,
            "encrypted_members_rejected": True,
            "symbolic_link_members_rejected": True,
            "unsafe_paths_rejected": True,
        },
        "source_tracks": {
            "studychat": {
                "kind": "natural_human_llm_educational_interaction",
                "private_row_count": counts["studychat_rows.jsonl"],
                "private_split_row_count": counts["studychat_split_private.jsonl"],
                "redacted_constructor_item_count": counts[
                    "studychat_construction_items_redacted.jsonl"
                ],
            },
            "wikiconv": {
                "kind": "natural_human_human_editorial_conversation",
                "private_row_count": counts["wikiconv_split_private.jsonl"],
                "redacted_constructor_item_count": counts[
                    "wikiconv_construction_items_redacted.jsonl"
                ],
            },
        },
        "private_workflow": {
            "redaction_log_row_count": counts["redaction_log.jsonl"],
            "privacy_finding_row_count": counts["privacy_findings.jsonl"],
            "annotation_mapping_count_not_reported": True,
            "private_secret_material_present_not_hashed": True,
        },
        "claim_boundary": {
            "raw_sources_embedded": False,
            "source_identifiers_embedded": False,
            "conversation_text_embedded": False,
            "annotations_embedded": False,
            "natural_gold_available": False,
            "publication_eligible": False,
            "mixed_track_headline_allowed": False,
        },
        "required_gates": {
            "raw_source_archive_reacquisition_and_integrity_review": "PENDING_MACHINE_REVIEW",
            "rights_and_redistribution_review": "PENDING_HUMAN_DECISION",
            "manual_privacy_review": "PENDING_HUMAN_DECISION",
            "protocol_freeze_before_annotation": "PENDING_HUMAN_DECISION",
            "independent_annotation_and_adjudication": "PENDING_HUMAN_DECISION",
            "track_specific_continuity_splits": "PENDING_MACHINE_AND_HUMAN_REVIEW",
        },
    }
