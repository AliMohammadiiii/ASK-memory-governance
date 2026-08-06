"""Audit and blind the external MGP-Natural v0.1.0 candidate archive.

The parent archive is evidence input, not an authoritative source tree.  This
module emits only aggregate audit facts and private annotation materials.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import stat
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from .blinding import PROHIBITED_KEYS, build_packet, canonical_hash, make_commitment, nested_keys

PARENT_ARCHIVE_NAME = "MGP-Natural-v0.1.0-release.zip"
PARENT_ARCHIVE_SHA256 = "0ffe92eba00bcec503e81589965c381857f4524fdd955902678d636eca7b7f26"
SEED_PATH = "data/seed/all.extended.jsonl"
BLIND_PACKET_PATH = "annotation/blind_packet.jsonl"
MANIFEST_PATH = "MANIFEST.sha256"
RELEASE_CHECKLIST_PATH = "governance/release_checklist.md"

ARCHIVE_FAMILY_RE = re.compile(r"/Archive(?:[ _-]*\d+)?$", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
SECRET_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b")


class CandidateArchiveError(ValueError):
    """Raised when the parent archive fails an integrity or shape requirement."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _root_prefix(zf: zipfile.ZipFile) -> str:
    candidates = {
        name[: -len(MANIFEST_PATH)] for name in zf.namelist() if name.endswith(MANIFEST_PATH)
    }
    if len(candidates) != 1:
        raise CandidateArchiveError("archive must contain exactly one root MANIFEST.sha256")
    return candidates.pop()


def _safe_file_infos(zf: zipfile.ZipFile, root: str) -> list[zipfile.ZipInfo]:
    files: list[zipfile.ZipInfo] = []
    names = [info.filename for info in zf.infolist()]
    duplicate_names = [name for name, count in Counter(names).items() if count > 1]
    if duplicate_names:
        raise CandidateArchiveError(
            f"archive contains duplicate member names: {duplicate_names[:3]}"
        )
    for info in zf.infolist():
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts or not info.filename.startswith(root):
            raise CandidateArchiveError(f"unsafe or out-of-root archive path: {info.filename}")
        mode = info.external_attr >> 16
        if info.flag_bits & 0x1:
            raise CandidateArchiveError(f"archive contains an encrypted member: {info.filename}")
        if stat.S_ISLNK(mode):
            raise CandidateArchiveError(f"archive contains a symbolic link: {info.filename}")
        if mode and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise CandidateArchiveError(f"archive contains a special file: {info.filename}")
        if not info.is_dir():
            files.append(info)
    return files


def _read_text(zf: zipfile.ZipFile, root: str, relative_path: str) -> str:
    try:
        return zf.read(root + relative_path).decode("utf-8")
    except KeyError as exc:
        raise CandidateArchiveError(f"required archive member is missing: {relative_path}") from exc


def _read_jsonl(zf: zipfile.ZipFile, root: str, relative_path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(_read_text(zf, root, relative_path).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CandidateArchiveError(
                f"{relative_path}:{line_number}: invalid JSON: {exc.msg}"
            ) from exc
        if not isinstance(row, dict):
            raise CandidateArchiveError(f"{relative_path}:{line_number}: row must be an object")
        rows.append(row)
    return rows


def _verify_manifest(
    zf: zipfile.ZipFile, root: str, files: list[zipfile.ZipInfo]
) -> dict[str, Any]:
    entries: dict[str, str] = {}
    duplicates: list[str] = []
    for line_number, line in enumerate(_read_text(zf, root, MANIFEST_PATH).splitlines(), start=1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise CandidateArchiveError(f"manifest line {line_number} has invalid syntax")
        expected, relative_path = match.groups()
        if relative_path in entries:
            duplicates.append(relative_path)
        entries[relative_path] = expected

    archive_relpaths = {
        info.filename[len(root) :] for info in files if info.filename != root + MANIFEST_PATH
    }
    missing = sorted(set(entries) - archive_relpaths)
    extra = sorted(archive_relpaths - set(entries))
    mismatches: list[str] = []
    for relative_path, expected in entries.items():
        member = root + relative_path
        if relative_path in missing:
            continue
        actual = hashlib.sha256(zf.read(member)).hexdigest()
        if actual != expected:
            mismatches.append(relative_path)
    return {
        "entry_count": len(entries),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "duplicate_count": len(duplicates),
        "hash_mismatch_count": len(mismatches),
        "verified": not (missing or extra or duplicates or mismatches),
    }


def _page_family(title: str) -> str:
    return ARCHIVE_FAMILY_RE.sub("", title).strip()


def _split_file_equivalence(zf: zipfile.ZipFile, root: str, records: list[dict[str, Any]]) -> bool:
    expected = {
        split: [row for row in records if row.get("split") == split]
        for split in ("train", "dev", "test")
    }
    return all(
        _read_jsonl(zf, root, f"data/splits/{split}.jsonl") == rows
        for split, rows in expected.items()
    )


def _leakage_rule(relation: object) -> str:
    if relation == "supports":
        return "KEEP"
    if relation == "supersedes":
        return "SUPERSEDE"
    return "ABSTAIN"


def _continuity_component_sizes(records: list[dict[str, Any]]) -> tuple[list[int], int]:
    parents = list(range(len(records)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    seen_family: dict[str, int] = {}
    seen_contributor: dict[str, int] = {}
    for index, row in enumerate(records):
        source_value = row.get("source")
        source = source_value if isinstance(source_value, dict) else {}
        family = _page_family(str(source.get("page_title", "")))
        if family in seen_family:
            union(index, seen_family[family])
        else:
            seen_family[family] = index
        dialogue_value = row.get("dialogue")
        dialogue = dialogue_value if isinstance(dialogue_value, list) else []
        contributors = {
            str(turn.get("source_author"))
            for turn in dialogue
            if isinstance(turn, dict) and turn.get("source_author")
        }
        for contributor in contributors:
            if contributor in seen_contributor:
                union(index, seen_contributor[contributor])
            else:
                seen_contributor[contributor] = index

    component_members: dict[int, list[int]] = defaultdict(list)
    for index in range(len(records)):
        component_members[find(index)].append(index)
    mixed_split_components = 0
    for members in component_members.values():
        splits = {str(records[index].get("split")) for index in members}
        mixed_split_components += len(splits) > 1
    return sorted((len(members) for members in component_members.values()), reverse=True), int(
        mixed_split_components
    )


def audit_candidate_archive(path: Path, *, require_known_parent: bool = True) -> dict[str, Any]:
    """Return a non-sensitive, aggregate audit of the supplied candidate ZIP."""

    archive_sha256 = _sha256_file(path)
    if require_known_parent and archive_sha256 != PARENT_ARCHIVE_SHA256:
        raise CandidateArchiveError(
            "parent archive SHA-256 does not match the audited MGP-Natural v0.1.0 input"
        )

    with zipfile.ZipFile(path) as zf:
        root = _root_prefix(zf)
        files = _safe_file_infos(zf, root)
        bad_zip_member = zf.testzip()
        manifest = _verify_manifest(zf, root, files)
        records = _read_jsonl(zf, root, SEED_PATH)
        blind_rows = _read_jsonl(zf, root, BLIND_PACKET_PATH)
        checklist = _read_text(zf, root, RELEASE_CHECKLIST_PATH)

        ids = [str(row.get("mgpn_id")) for row in records]
        gold_by_id = {str(row.get("mgpn_id")): str(row.get("gold_action")) for row in records}
        packet_relations: list[object] = []
        for row in blind_rows:
            candidate_value = row.get("candidate")
            packet_relations.append(
                candidate_value.get("relation_to_prior")
                if isinstance(candidate_value, dict)
                else None
            )
        rule_predictions = [_leakage_rule(value) for value in packet_relations]
        packet_gold = [gold_by_id.get(str(row.get("mgpn_id"))) for row in blind_rows]
        rule_correct = sum(
            pred == gold for pred, gold in zip(rule_predictions, packet_gold, strict=True)
        )

        split_pages: dict[str, set[str]] = defaultdict(set)
        split_families: dict[str, set[str]] = defaultdict(set)
        contributor_splits: dict[str, set[str]] = defaultdict(set)
        multipart = 0
        single_contributor = 0
        dialogue_turns = 0
        for row in records:
            split = str(row.get("split"))
            source_value = row.get("source")
            source = source_value if isinstance(source_value, dict) else {}
            page = str(source.get("page_title", ""))
            split_pages[split].add(page)
            split_families[split].add(_page_family(page))
            dialogue_value = row.get("dialogue")
            dialogue = dialogue_value if isinstance(dialogue_value, list) else []
            dialogue_turns += len(dialogue)
            contributors = {
                str(turn.get("source_author"))
                for turn in dialogue
                if isinstance(turn, dict) and turn.get("source_author")
            }
            for contributor in contributors:
                contributor_splits[contributor].add(split)
            if len(contributors) >= 2:
                multipart += 1
            else:
                single_contributor += 1

        test_page_overlap = split_pages["test"] & (split_pages["train"] | split_pages["dev"])
        test_family_overlap = split_families["test"] & (
            split_families["train"] | split_families["dev"]
        )
        contributor_test_overlap = sum(
            "test" in splits and bool(splits & {"train", "dev"})
            for splits in contributor_splits.values()
        )
        annotation_statuses = Counter(
            str((row.get("annotation") or {}).get("status"))
            for row in records
            if isinstance(row.get("annotation"), dict)
        )
        independent_complete = sum(
            bool((row.get("annotation") or {}).get("independent_adjudication_complete"))
            for row in records
            if isinstance(row.get("annotation"), dict)
        )
        confirmation_required = sum(
            (row.get("annotation") or {}).get("requires_independent_confirmation") is True
            for row in records
            if isinstance(row.get("annotation"), dict)
        )
        continuity_component_sizes, mixed_split_components = _continuity_component_sizes(records)

        split_files_reconstruct_seed = _split_file_equivalence(zf, root, records)
        core_integrity = all(
            (
                bad_zip_member is None,
                manifest["verified"],
                len(ids) == len(set(ids)),
                split_files_reconstruct_seed,
            )
        )
        release_unchecked = checklist.count("- [ ]")

    blockers = [
        "BLIND_PACKET_LABEL_LEAKAGE",
        "NO_INDEPENDENT_ANNOTATION_OR_ADJUDICATION",
        "HUMAN_LEGAL_AND_PRIVACY_APPROVAL_PENDING",
        "PAGE_FAMILY_AND_CONTRIBUTOR_SPLIT_LEAKAGE",
        "NO_INDEPENDENT_CONTINUITY_HELD_OUT_SPLIT",
        "SOURCE_EXTRACTION_LEDGER_NOT_REPRODUCIBLE",
        "SCORER_AND_VALIDATOR_HARDENING_REQUIRED",
    ]
    return {
        "schema_version": "1.0",
        "audit_date": "2026-08-03",
        "status": "QUARANTINED_RELEASE_CANDIDATE",
        "gold_or_public_release_eligible": False,
        "parent_archive": {
            "filename": PARENT_ARCHIVE_NAME,
            "sha256": archive_sha256,
            "known_parent_match": archive_sha256 == PARENT_ARCHIVE_SHA256,
            "zip_integrity_passed": bad_zip_member is None,
        },
        "manifest": manifest,
        "core_integrity_passed": core_integrity,
        "dataset": {
            "record_count": len(records),
            "unique_id_count": len(set(ids)),
            "dialogue_excerpt_row_count": dialogue_turns,
            "action_counts": dict(sorted(Counter(gold_by_id.values()).items())),
            "split_counts": dict(sorted(Counter(str(row.get("split")) for row in records).items())),
            "annotation_status_counts": dict(sorted(annotation_statuses.items())),
            "independent_adjudication_complete_count": independent_complete,
            "requires_independent_confirmation_count": confirmation_required,
            "multi_contributor_excerpt_count": multipart,
            "single_contributor_excerpt_count": single_contributor,
        },
        "split_audit": {
            "exact_test_page_overlap_count": len(test_page_overlap),
            "test_page_family_overlap_count": len(test_family_overlap),
            "test_contributor_overlap_count": contributor_test_overlap,
            "split_files_reconstruct_seed": split_files_reconstruct_seed,
            "continuity_component_count": len(continuity_component_sizes),
            "continuity_component_sizes": continuity_component_sizes,
            "mixed_split_continuity_component_count": mixed_split_components,
            "benchmark_held_out_split_valid": False,
        },
        "blind_packet_audit": {
            "record_count": len(blind_rows),
            "relation_to_prior_present_count": sum(value is not None for value in packet_relations),
            "direct_source_id_join_count": sum(
                str(row.get("mgpn_id")) in gold_by_id for row in blind_rows
            ),
            "deterministic_relation_rule_correct": rule_correct,
            "deterministic_relation_rule_total": len(packet_gold),
            "safe_for_independent_annotation": False,
        },
        "release_checklist": {
            "unchecked_item_count": release_unchecked,
            "all_required_signoffs_complete": False,
        },
        "blockers": blockers,
        "allowed_claim": (
            "Internally coherent 36-item Wikipedia editorial-discussion feasibility seed "
            "with provisional constructor labels."
        ),
        "prohibited_claims": [
            "independently annotated gold benchmark",
            "public-release-cleared dataset",
            "representative real-world personal-assistant memory benchmark",
            "page-family-held-out evaluation",
            "leaderboard-quality test set",
        ],
    }


def _replace_identity_tokens(text: str, identities: list[str]) -> tuple[str, int]:
    redacted = text
    replacements = 0
    for identity in sorted(set(identities), key=len, reverse=True):
        if len(identity) < 4:
            continue
        redacted, count = re.subn(
            rf"(?<!\w){re.escape(identity)}(?!\w)",
            "[CONTRIBUTOR_REDACTED]",
            redacted,
            flags=re.IGNORECASE,
        )
        replacements += count
    for pattern, replacement in (
        (EMAIL_RE, "[EMAIL_REDACTED]"),
        (IPV4_RE, "[IP_REDACTED]"),
        (URL_RE, "[URL_REDACTED]"),
        (SECRET_RE, "[SECRET_REDACTED]"),
    ):
        redacted, count = pattern.subn(replacement, redacted)
        replacements += count
    return redacted, replacements


def make_mgpn_annotation_rows(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Project gold-bearing MGP-Natural records into label-free annotation inputs."""

    rows: list[dict[str, Any]] = []
    redacted_text_occurrences = 0
    global_identities: list[str] = []
    for record in records:
        dialogue_value = record.get("dialogue")
        dialogue = dialogue_value if isinstance(dialogue_value, list) else []
        global_identities.extend(
            str(turn.get("source_author"))
            for turn in dialogue
            if isinstance(turn, dict) and turn.get("source_author")
        )
    for index, record in enumerate(records):
        record_id = record.get("mgpn_id")
        before = record.get("memory_before")
        candidate = record.get("candidate")
        dialogue_raw = record.get("dialogue")
        if not isinstance(record_id, str):
            raise CandidateArchiveError(f"record {index} is missing mgpn_id")
        if (
            not isinstance(before, dict)
            or not isinstance(candidate, dict)
            or not isinstance(dialogue_raw, list)
        ):
            raise CandidateArchiveError(f"record {record_id} has malformed annotation inputs")
        dialogue = dialogue_raw

        clean_dialogue: list[dict[str, Any]] = []
        clean_turn_text: dict[object, str] = {}
        speaker_aliases: dict[str, str] = {}
        for turn in dialogue:
            if not isinstance(turn, dict):
                raise CandidateArchiveError(
                    f"record {record_id} contains a malformed dialogue turn"
                )
            clean_text, replacements = _replace_identity_tokens(
                str(turn.get("text", "")), global_identities
            )
            redacted_text_occurrences += replacements
            clean_turn_text[turn.get("turn_id")] = clean_text
            source_speaker = str(turn.get("speaker", ""))
            if source_speaker not in speaker_aliases:
                speaker_aliases[source_speaker] = f"PARTICIPANT_{len(speaker_aliases) + 1}"
            clean_dialogue.append(
                {
                    "turn_id": turn.get("turn_id"),
                    "speaker": speaker_aliases[source_speaker],
                    "text": clean_text,
                }
            )
        candidate_text = clean_turn_text.get(candidate.get("turn_id"))
        if candidate_text is None:
            candidate_text, replacements = _replace_identity_tokens(
                str(candidate.get("text", "")), global_identities
            )
            redacted_text_occurrences += replacements
        rows.append(
            {
                "id": record_id,
                "task_version": "mgpn-natural-annotation/0.1.1-derived",
                "source_class": "public_document",
                "consent_basis": (
                    "public Wikimedia contribution; revision-specific license, "
                    "attribution, privacy, and redistribution review remains pending"
                ),
                "redaction_record": [
                    "source contributor metadata removed from annotation view",
                    "source locators withheld until annotation freeze",
                    "constructor-derived relation, evidence, and post-decision fields removed",
                ],
                "predecessor": {
                    key: before.get(key)
                    for key in ("memory_slot", "principal", "scope", "standing_value", "status")
                },
                "candidate": {
                    "turn_id": candidate.get("turn_id"),
                    "text": candidate_text,
                },
                "context": {
                    "dialogue": clean_dialogue,
                    "evaluation_query": record.get("evaluation_query"),
                    "construction_notice": (
                        "standing state is constructor-normalized and is not a native assistant memory log"
                    ),
                },
            }
        )
    return rows, {"redacted_text_occurrence_count": redacted_text_occurrences}


def load_seed_records(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as zf:
        root = _root_prefix(zf)
        _safe_file_infos(zf, root)
        return _read_jsonl(zf, root, SEED_PATH)


def annotation_packet_semantic_errors(packet: list[dict[str, Any]]) -> list[str]:
    """Check cross-field invariants that JSON Schema cannot express."""

    errors: list[str] = []
    seen_blind_ids: set[str] = set()
    for index, row in enumerate(packet):
        blind_id = str(row.get("blind_id", ""))
        if blind_id in seen_blind_ids:
            errors.append(f"duplicate blind_id at row {index}: {blind_id}")
        seen_blind_ids.add(blind_id)
        candidate_value = row.get("candidate")
        candidate = candidate_value if isinstance(candidate_value, dict) else {}
        context_value = row.get("context")
        context = context_value if isinstance(context_value, dict) else {}
        dialogue_value = context.get("dialogue")
        dialogue = dialogue_value if isinstance(dialogue_value, list) else []
        turn_text: dict[str, str] = {}
        for turn_index, turn in enumerate(dialogue):
            if not isinstance(turn, dict):
                continue
            turn_id = str(turn.get("turn_id", ""))
            if turn_id in turn_text:
                errors.append(f"{blind_id}: duplicate dialogue turn_id at row {turn_index}")
            turn_text[turn_id] = str(turn.get("text", ""))
        candidate_turn_id = str(candidate.get("turn_id", ""))
        if candidate_turn_id not in turn_text:
            errors.append(f"{blind_id}: candidate turn_id is absent from dialogue")
        elif str(candidate.get("text", "")) != turn_text[candidate_turn_id]:
            errors.append(f"{blind_id}: candidate text does not match its dialogue turn")
    return errors


def prepare_private_annotation_materials(
    archive_path: Path, blinding_secret: int
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    str,
    dict[str, Any],
]:
    """Prepare a safe draft packet, public commitment, private map, and answer CSV."""

    if blinding_secret.bit_length() < 128:
        raise CandidateArchiveError("MGP-Natural blinding secret must contain at least 128 bits")
    audit = audit_candidate_archive(archive_path)
    if not audit["core_integrity_passed"]:
        raise CandidateArchiveError("parent archive failed core integrity checks")
    records = load_seed_records(archive_path)
    annotation_rows, redaction_summary = make_mgpn_annotation_rows(records)
    packet, mapping = build_packet(annotation_rows, blinding_secret, prefix="N")
    packet_errors = annotation_packet_semantic_errors(packet)
    if packet_errors:
        raise CandidateArchiveError(f"generated packet has semantic errors: {packet_errors[:3]}")
    commitment, private_record = make_commitment(packet, mapping, blinding_secret)
    private_record.update(
        {
            "parent_archive_sha256": PARENT_ARCHIVE_SHA256,
            "task_version": "mgpn-natural-annotation/0.1.1-derived",
            "ordering_algorithm": "HMAC-SHA256(secret, source_index:source_id)",
            "source_record_sha256": {
                str(record["mgpn_id"]): canonical_hash(record) for record in records
            },
        }
    )
    commitment["private_mapping_sha256"] = canonical_hash(private_record)
    commitment.update(
        {
            "status": "DRAFT_NOT_AUTHORIZED_FOR_DISTRIBUTION",
            "parent_archive_sha256": PARENT_ARCHIVE_SHA256,
            "annotation_protocol_frozen": False,
            "human_legal_approval": False,
            "redaction_summary": redaction_summary,
        }
    )

    serialized = json.dumps(packet, sort_keys=True)
    leaked_ids = [record["mgpn_id"] for record in records if record["mgpn_id"] in serialized]
    found_prohibited = nested_keys(packet) & PROHIBITED_KEYS
    if leaked_ids or found_prohibited:
        raise CandidateArchiveError(
            "generated packet failed leakage guard: "
            f"source_ids={len(leaked_ids)}, prohibited_keys={sorted(found_prohibited)}"
        )

    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer)
    writer.writerow(
        [
            "blind_id",
            "annotator_pseudonym",
            "action",
            "confidence",
            "evidence_turn_ids",
            "resulting_value",
            "rationale",
            "exclude_reason",
        ]
    )
    for row in packet:
        writer.writerow([row["blind_id"], "", "", "", "", "", "", ""])

    safe_summary = {
        "schema_version": "1.0",
        "status": commitment["status"],
        "parent_archive_sha256": PARENT_ARCHIVE_SHA256,
        "item_count": len(packet),
        "packet_sha256": canonical_hash(packet),
        "labels_present": False,
        "source_ids_present": False,
        "source_locators_present": False,
        "relation_to_prior_present": False,
        "private_mapping_written_separately": True,
        "annotation_protocol_frozen": False,
        "human_legal_approval": False,
        "independent_annotation_complete": False,
        "redaction_summary": redaction_summary,
    }
    return packet, commitment, private_record, csv_buffer.getvalue(), safe_summary
