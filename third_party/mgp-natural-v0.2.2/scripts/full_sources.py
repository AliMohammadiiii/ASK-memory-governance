from __future__ import annotations

import argparse
import codecs
import csv
import gzip
import hashlib
import heapq
import hmac
import json
import os
import re
import tempfile
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any, BinaryIO

from mgp_natural.blinding.packet import build_packet, verify_packet
from mgp_natural.errors import ValidationError
from mgp_natural.mining.studychat import mine_file as mine_studychat_file
from mgp_natural.ontology.contract import validate_construction_item
from mgp_natural.privacy.redaction import redact_text
from mgp_natural.privacy.scanner import scan_text
from mgp_natural.util.io import (
    canonical_json_bytes,
    canonical_json_hash,
    ensure_private_dir,
    iter_jsonl,
    read_json,
    sha256_file,
    write_json,
    write_jsonl,
)

EXPECTED_INPUTS = (
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
STUDYCHAT_CANONICAL = "studychat/data.jsonl"
STUDYCHAT_PARTITIONS = (
    "studychat/dialogues/f24_labeled_dialogues.jsonl",
    "studychat/dialogues/s25_labeled_dialogues.jsonl",
)
WIKICONV_2003_UTTERANCES = "utterances.jsonl"
ACTION_KEYS = ("modification", "deletion", "restoration")
SPLIT_SEED = 1729


def _input_root(explicit: Path | None) -> Path:
    root = explicit
    if root is None:
        raw = os.environ.get("MGP_FULL_INPUTS", "").strip()
        if not raw:
            raise ValidationError(
                "MGP_FULL_INPUTS is not set; point it to the private source directory"
            )
        root = Path(raw)
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValidationError(f"full input directory does not exist: {root}")
    missing = [name for name in EXPECTED_INPUTS if not (root / name).is_file()]
    if missing:
        raise ValidationError(f"missing full-source inputs: {missing}")
    return root


def _private_root(repo_root: Path) -> Path:
    path = repo_root / ".private" / "full"
    ensure_private_dir(path)
    return path


def _atomic_jsonl_stream(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    mode: int = 0o600,
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    count = 0
    try:
        with os.fdopen(fd, "wb") as handle:
            for row in rows:
                handle.write(canonical_json_bytes(dict(row)))
                handle.write(b"\n")
                count += 1
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()
    return count


def _hash_stream(handle: BinaryIO, *, count_lines: bool = False) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    total = 0
    lines = 0
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
        total += len(chunk)
        if count_lines:
            lines += chunk.count(b"\n")
    return digest.hexdigest(), total, lines


def _read_first_jsonl(handle: BinaryIO) -> dict[str, Any]:
    line = handle.readline()
    if not line:
        raise ValidationError("JSONL source is empty")
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValidationError("JSONL source must contain objects")
    return value


def _zip_inventory(
    path: Path,
    *,
    jsonl_members: set[str] | None = None,
    expected_manifest: dict[str, dict[str, Any]] | None = None,
    strip_prefix: str = "",
    manifest_ignore_prefixes: tuple[str, ...] = (),
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    jsonl_members = jsonl_members or set()
    member_details: dict[str, dict[str, Any]] = {}
    mismatches: list[dict[str, Any]] = []
    ignored_macos = 0
    ignored_manifest_auxiliary: list[str] = []
    with zipfile.ZipFile(path) as bundle:
        for info in bundle.infolist():
            if info.filename.startswith("__MACOSX/") or "/._" in info.filename:
                ignored_macos += 1
                continue
            if info.is_dir():
                continue
            with bundle.open(info) as source:
                digest, observed_bytes, rows = _hash_stream(
                    source, count_lines=info.filename in jsonl_members
                )
            detail: dict[str, Any] = {
                "archive_path": info.filename,
                "compressed_bytes": info.compress_size,
                "uncompressed_bytes": observed_bytes,
                "sha256": digest,
            }
            if info.filename in jsonl_members:
                detail["records"] = rows
                with bundle.open(info) as source:
                    detail["observed_keys"] = sorted(_read_first_jsonl(source))
            member_details[info.filename] = detail
            if expected_manifest is not None:
                relative = info.filename
                if strip_prefix and relative.startswith(strip_prefix):
                    relative = relative[len(strip_prefix) :]
                expected = expected_manifest.get(relative)
                if expected is None:
                    if any(relative.startswith(prefix) for prefix in manifest_ignore_prefixes):
                        ignored_manifest_auxiliary.append(relative)
                        continue
                    mismatches.append(
                        {"path": relative, "reason": "member absent from supplied manifest"}
                    )
                else:
                    if expected.get("bytes") != observed_bytes:
                        mismatches.append(
                            {
                                "path": relative,
                                "reason": "byte mismatch",
                                "expected": expected.get("bytes"),
                                "observed": observed_bytes,
                            }
                        )
                    if expected.get("sha256") != digest:
                        mismatches.append(
                            {
                                "path": relative,
                                "reason": "hash mismatch",
                                "expected": expected.get("sha256"),
                                "observed": digest,
                            }
                        )
    report = {
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "archive_members": len(member_details),
        "ignored_macos_metadata_members": ignored_macos,
        "manifest_ignored_auxiliary_members": len(ignored_manifest_auxiliary),
        "manifest_ignored_auxiliary_prefixes": list(manifest_ignore_prefixes),
        "zip_integrity": "PASS",
        "manifest_mismatches": mismatches,
    }
    return report, member_details


def _gzip_inventory(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    rows = 0
    uncompressed_bytes = 0
    observed_keys: set[str] = set()
    first = True
    with path.open("rb") as raw:
        for chunk in iter(lambda: raw.read(1024 * 1024), b""):
            digest.update(chunk)
    with gzip.open(path, "rb") as source:
        for line in source:
            uncompressed_bytes += len(line)
            if not line.strip():
                continue
            rows += 1
            if first:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValidationError(f"{path.name} contains a non-object row")
                observed_keys.update(value)
                first = False
    return {
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
        "uncompressed_bytes": uncompressed_bytes,
        "records": rows,
        "observed_keys": sorted(observed_keys),
        "gzip_integrity": "PASS",
    }


def audit_full_inputs(input_root: Path, repo_root: Path) -> dict[str, Any]:
    studychat_manifest_raw = read_json(input_root / "studychat_full_source_manifest.json")
    studychat_expected = {
        str(entry["path"]): entry for entry in studychat_manifest_raw.get("files", [])
    }
    studychat_archive, studychat_members = _zip_inventory(
        input_root / "studychat.zip",
        jsonl_members={STUDYCHAT_CANONICAL, *STUDYCHAT_PARTITIONS},
        expected_manifest=studychat_expected,
        strip_prefix="studychat/",
        manifest_ignore_prefixes=(".cache/",),
    )
    studychat_archive["manifest_entries"] = len(studychat_expected)

    wiki_manifest = read_json(input_root / "wikiconv_compact_manifest.json")
    expected_by_year = {
        int(entry["year"]): entry for entry in wiki_manifest.get("files", [])
    }
    wiki_2003_archive, wiki_2003_members = _zip_inventory(
        input_root / "wikiconv-english-2003.corpus.zip",
        jsonl_members={WIKICONV_2003_UTTERANCES},
    )
    expected_2003 = expected_by_year.get(2003, {})
    wiki_2003_archive["compact_manifest_match"] = {
        "bytes": expected_2003.get("expected_bytes") == wiki_2003_archive["bytes"],
        "sha256": expected_2003.get("sha256") == wiki_2003_archive["sha256"],
    }

    wiki_2018_metadata, _wiki_2018_members = _zip_inventory(
        input_root / "wikiconv-english-2018data.zip"
    )
    parts = [
        _gzip_inventory(input_root / f"utterances.part{index:03d}.jsonl.gz")
        for index in range(1, 8)
    ]
    observed_2018_bytes = wiki_2018_metadata["bytes"] + sum(part["bytes"] for part in parts)
    expected_2018 = expected_by_year.get(2018, {})
    wiki_2018_metadata["representation_note"] = (
        "The supplied 2018 source is a metadata ZIP plus seven gzip utterance parts; "
        "it is content-equivalent in scope to, but not byte-identical with, the monolithic "
        "archive recorded by the compact manifest."
    )
    wiki_2018_metadata["combined_split_representation_bytes"] = observed_2018_bytes
    wiki_2018_metadata["compact_manifest_monolithic_expected_bytes"] = expected_2018.get(
        "expected_bytes"
    )

    inventory = {
        "schema_version": "2.0",
        "source_scope": "FULL_SUPPLIED_SOURCES",
        "input_root_recorded_as": "$MGP_FULL_INPUTS",
        "studychat": {
            "archive": studychat_archive,
            "canonical_records": studychat_members[STUDYCHAT_CANONICAL]["records"],
            "partition_records": {
                member: studychat_members[member]["records"] for member in STUDYCHAT_PARTITIONS
            },
            "canonical_keys": studychat_members[STUDYCHAT_CANONICAL]["observed_keys"],
            "excluded_from_candidate_mining": [
                "studychat/scores/",
                "studychat/submissions/",
                "studychat/assignment_text/",
                "studychat/.cache/",
            ],
        },
        "wikiconv": {
            "year_2003": {
                "archive": wiki_2003_archive,
                "utterance_records": wiki_2003_members[WIKICONV_2003_UTTERANCES]["records"],
                "utterance_keys": wiki_2003_members[WIKICONV_2003_UTTERANCES][
                    "observed_keys"
                ],
            },
            "year_2018": {
                "metadata_archive": wiki_2018_metadata,
                "parts": parts,
                "utterance_records": sum(part["records"] for part in parts),
                "all_seven_parts_present": len(parts) == 7,
            },
        },
    }
    source_integrity = {
        "schema_version": "2.0",
        "status": "PASS"
        if not studychat_archive["manifest_mismatches"]
        and wiki_2003_archive["compact_manifest_match"] == {"bytes": True, "sha256": True}
        else "FAIL",
        "studychat_manifest_mismatches": studychat_archive["manifest_mismatches"],
        "wikiconv_2003_compact_manifest_match": wiki_2003_archive[
            "compact_manifest_match"
        ],
        "wikiconv_2018_split_representation_complete": len(parts) == 7,
        "raw_sources_immutable": True,
    }
    reports = repo_root / "reports"
    manifests = repo_root / "manifests"
    write_json(reports / "INPUT_INVENTORY_FULL.json", inventory)
    write_json(reports / "SOURCE_INTEGRITY.json", source_integrity)
    write_json(
        manifests / "source_manifest_full.json",
        {
            "schema_version": "2.0",
            "files": [
                {
                    "path": name,
                    "bytes": (input_root / name).stat().st_size,
                    "sha256": sha256_file(input_root / name),
                }
                for name in EXPECTED_INPUTS
            ],
            "raw_data_in_repository": False,
        },
    )
    markdown = [
        "---",
        "ai_generated: true",
        "artifact_status: machine_inventory",
        "---",
        "",
        "# Full input inventory",
        "",
        f"- StudyChat canonical rows: **{inventory['studychat']['canonical_records']:,}**",
        (
            "- WikiConv 2003 utterances: "
            f"**{inventory['wikiconv']['year_2003']['utterance_records']:,}**"
        ),
        (
            "- WikiConv 2018 utterances: "
            f"**{inventory['wikiconv']['year_2018']['utterance_records']:,}**"
        ),
        "- WikiConv 2018 parts: **7 of 7**",
        "- Raw sources remain outside the repository and public packages.",
        "- `__MACOSX` metadata was recorded and ignored.",
        "",
        f"Integrity status: `{source_integrity['status']}`",
    ]
    (reports / "INPUT_INVENTORY_FULL.md").write_text("\n".join(markdown) + "\n")
    if source_integrity["status"] != "PASS":
        raise ValidationError("full-source integrity verification failed")
    return inventory


def _load_or_create_secret(path: Path) -> bytes:
    if path.is_file():
        secret = path.read_bytes()
        if len(secret) < 16:
            raise ValidationError("private source-ID secret is too short")
        return secret
    secret = os.urandom(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(secret)
    os.chmod(path, 0o600)
    return secret


def _private_token(secret: bytes, namespace: str, value: str) -> str:
    return hmac.new(secret, f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()[:24]


def _partition_hash(row: dict[str, Any]) -> str:
    normalized = {key: value for key, value in row.items() if key != "semester"}
    return canonical_json_hash(normalized)


def reconstruct_studychat_full(input_root: Path, repo_root: Path) -> dict[str, Any]:
    private = _private_root(repo_root)
    normalized_path = private / "studychat_rows.jsonl"
    anomaly_path = private / "studychat_reconstruction_anomalies.jsonl"
    secret = _load_or_create_secret(private / "source_id_hmac_secret.bin")
    chat_state: dict[tuple[str, str], dict[str, Any]] = {}
    canonical_hashes: Counter[str] = Counter()
    anomalies: list[dict[str, Any]] = []
    users: set[str] = set()
    chats: set[tuple[str, str]] = set()
    semesters: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    source_keys: set[str] = set()

    def normalized_rows() -> Iterator[dict[str, Any]]:
        with (
            zipfile.ZipFile(input_root / "studychat.zip") as bundle,
            bundle.open(STUDYCHAT_CANONICAL) as source,
        ):
            for row_index, line in enumerate(source, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValidationError("StudyChat canonical row must be an object")
                source_keys.update(row)
                required = {
                    "prompt",
                    "response",
                    "chatId",
                    "userId",
                    "interactionCount",
                }
                missing = required - set(row)
                if missing:
                    raise ValidationError(
                        f"StudyChat canonical row {row_index} missing {sorted(missing)}"
                    )
                prompt = row["prompt"]
                response = row["response"]
                user_id = str(row["userId"])
                chat_id = str(row["chatId"])
                count = row["interactionCount"]
                if not isinstance(prompt, str) or not isinstance(response, str):
                    raise ValidationError("StudyChat prompt/response must be strings")
                if not isinstance(count, int) or isinstance(count, bool):
                    raise ValidationError("StudyChat interactionCount must be an integer")
                users.add(user_id)
                chats.add((user_id, chat_id))
                semester = str(row.get("semester", "UNKNOWN"))
                semesters[semester] += 1
                topic_counts[str(row.get("topic", "UNKNOWN"))] += 1
                canonical_hashes[_partition_hash(row)] += 1
                state = chat_state.setdefault(
                    (user_id, chat_id),
                    {
                        "counts": [],
                        "previous_expected_messages": None,
                        "expected_totals": set(),
                    },
                )
                state["counts"].append(count)
                total = row.get("chatTotalInteractionCount")
                if isinstance(total, int) and not isinstance(total, bool):
                    state["expected_totals"].add(total)
                messages = row.get("messages")
                if not isinstance(messages, list):
                    anomalies.append(
                        {
                            "code": "MESSAGES_MISSING_OR_INVALID",
                            "row_index": row_index,
                            "chat_private": _private_token(secret, "chat", chat_id),
                        }
                    )
                    messages = [{"role": "user", "content": prompt}]
                current_turn_ok = bool(
                    messages
                    and isinstance(messages[-1], dict)
                    and messages[-1].get("role") == "user"
                    and messages[-1].get("content") == prompt
                )
                if not current_turn_ok:
                    anomalies.append(
                        {
                            "code": "CURRENT_TURN_MESSAGES_MISMATCH",
                            "row_index": row_index,
                            "chat_private": _private_token(secret, "chat", chat_id),
                        }
                    )
                previous = state["previous_expected_messages"]
                if previous is not None and messages[: len(previous)] != previous:
                    anomalies.append(
                        {
                            "code": "CUMULATIVE_PREFIX_CONFLICT",
                            "row_index": row_index,
                            "chat_private": _private_token(secret, "chat", chat_id),
                        }
                    )
                state["previous_expected_messages"] = [
                    *messages,
                    {"role": "assistant", "content": response},
                ]
                yield {
                    "row_index": row_index,
                    "user_id_hash": _private_token(secret, "user", user_id),
                    "chat_id_hash": _private_token(secret, "chat", chat_id),
                    "prompt": prompt,
                    "response": response,
                    "topic": str(row.get("topic", "UNKNOWN")),
                    "messages": messages,
                    "interaction_count": count,
                    "chat_total_interaction_count": row.get(
                        "chatTotalInteractionCount"
                    ),
                    "semester": semester,
                }

    row_count = _atomic_jsonl_stream(normalized_path, normalized_rows())

    completeness: Counter[str] = Counter()
    for (user_id, chat_id), state in chat_state.items():
        counts = list(state["counts"])
        sorted_counts = sorted(counts)
        if counts != sorted_counts or len(counts) != len(set(counts)):
            anomalies.append(
                {
                    "code": "NON_MONOTONIC_OR_DUPLICATE_INTERACTION_COUNT",
                    "chat_private": _private_token(secret, "chat", chat_id),
                    "user_private": _private_token(secret, "user", user_id),
                }
            )
        expected = list(range(min(sorted_counts), max(sorted_counts) + 1))
        if sorted_counts != expected:
            anomalies.append(
                {
                    "code": "INTERACTION_COUNT_GAP",
                    "chat_private": _private_token(secret, "chat", chat_id),
                    "observed_count": len(sorted_counts),
                }
            )
        complete = bool(sorted_counts and sorted_counts[0] == 0 and sorted_counts == expected)
        totals = state["expected_totals"]
        if len(totals) == 1:
            reported_total = next(iter(totals))
            complete = complete and max(sorted_counts) + 1 == reported_total
        elif len(totals) > 1:
            anomalies.append(
                {
                    "code": "CONFLICTING_CHAT_TOTALS",
                    "chat_private": _private_token(secret, "chat", chat_id),
                }
            )
            complete = False
        completeness["COMPLETE" if complete else "PARTIAL_OR_ANOMALOUS"] += 1

    partition_reports: dict[str, Any] = {}
    combined_partition_hashes: Counter[str] = Counter()
    with zipfile.ZipFile(input_root / "studychat.zip") as bundle:
        for member in STUDYCHAT_PARTITIONS:
            hashes: Counter[str] = Counter()
            rows = 0
            with bundle.open(member) as source:
                for line in source:
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValidationError(f"{member} contains a non-object row")
                    hashes[_partition_hash(value)] += 1
                    rows += 1
            combined_partition_hashes.update(hashes)
            partition_reports[member] = {"records": rows, "unique_row_hashes": len(hashes)}
    partition_exact_match = combined_partition_hashes == canonical_hashes
    if not partition_exact_match:
        anomalies.append(
            {
                "code": "SEMESTER_PARTITION_CONTENT_MISMATCH",
                "canonical_hash_count": sum(canonical_hashes.values()),
                "partition_hash_count": sum(combined_partition_hashes.values()),
            }
        )

    write_jsonl(anomaly_path, anomalies, mode=0o600)
    report = {
        "schema_version": "2.0",
        "source_track": "STUDYCHAT",
        "canonical_interactions": row_count,
        "chats": len(chats),
        "pseudonymous_users": len(users),
        "semesters": dict(semesters),
        "topics": dict(topic_counts),
        "observed_keys": sorted(source_keys),
        "canonical_source": STUDYCHAT_CANONICAL,
        "partition_comparison": {
            "partitions": partition_reports,
            "combined_exact_normalized_row_multiset_match": partition_exact_match,
            "double_ingestion_prevented": True,
        },
        "excluded_source_areas": ["scores", "submissions", "assignment_text", ".cache"],
        "llm_label_used_as_mgp_target": False,
        "anomalies": len(anomalies),
        "anomaly_codes": dict(Counter(item["code"] for item in anomalies)),
        "chat_completeness": dict(completeness),
        "normalized_private_rows": row_count,
        "private_output_sha256": sha256_file(normalized_path),
        "status": "VALID_WITH_RECORDED_ANOMALIES",
    }
    write_json(repo_root / "reports" / "STUDYCHAT_FULL_RECONSTRUCTION.json", report)
    markdown = [
        "---",
        "ai_generated: true",
        "artifact_status: machine_reconstruction_report",
        "---",
        "",
        "# StudyChat full-data quality",
        "",
        f"- Canonical interactions: **{row_count:,}**",
        f"- Chats: **{len(chats):,}**",
        f"- Pseudonymous users: **{len(users):,}**",
        f"- Recorded anomalies: **{len(anomalies):,}**",
        (
            "- Semester partitions exactly reproduce canonical normalized rows: "
            f"**{partition_exact_match}**"
        ),
        "- Scores, submissions, assignment files, and cache data were excluded.",
        "- Source `llm_label` was not used as an MGP label.",
    ]
    (repo_root / "reports" / "STUDYCHAT_DATA_QUALITY.md").write_text(
        "\n".join(markdown) + "\n"
    )
    return report


def _stable_score(year: int, kind: str, action_id: str) -> int:
    digest = hashlib.sha256(f"{year}:{kind}:{action_id}".encode()).digest()
    return int.from_bytes(digest, "big")


def _action_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    text = value.get("text")
    return text if isinstance(text, str) else ""


def _candidate_from_action(
    *,
    year: int,
    utterance: dict[str, Any],
    original: dict[str, Any],
    action: dict[str, Any],
    kind: str,
    secret: bytes,
) -> tuple[dict[str, Any] | None, str | None]:
    prior = _action_text(original).strip()
    action_text = _action_text(action).strip()
    if not prior:
        return None, "NO_PRIOR_STATE"
    if len(prior) > 5000 or len(action_text) > 5000:
        return None, "NON_ATOMIC_CANDIDATE"
    action_id = str(action.get("id") or utterance.get("id") or "")
    if not action_id:
        return None, "SOURCE_INCOMPLETE"
    original_id = str(original.get("id") or "")
    action_meta = action.get("meta_dict") if isinstance(action.get("meta_dict"), dict) else {}
    parent_id = str(action_meta.get("parent_id") or "")
    if parent_id and original_id and parent_id != original_id:
        return None, "SOURCE_INCOMPLETE"
    prior_timestamp = original.get("timestamp")
    action_timestamp = action.get("timestamp")
    if (
        isinstance(prior_timestamp, (int, float))
        and isinstance(action_timestamp, (int, float))
        and action_timestamp < prior_timestamp
    ):
        return None, "SOURCE_INCOMPLETE"
    if kind == "modification":
        if not action_text:
            return None, "RESULTING_VALUE_UNRESOLVED"
        if re.sub(r"\s+", " ", prior).strip() == re.sub(r"\s+", " ", action_text).strip():
            return None, "NO_STATEFUL_CONTENT"
        scope = "WORDING_STATE"
        candidate_value = action_text
        candidate_turn_text = action_text
        relation = "SUPERSEDES"
        signal = "SOURCE_MODIFICATION_HISTORY"
    elif kind == "deletion":
        scope = "CONTENT_REMOVAL"
        candidate_value = "[DELETED]"
        candidate_turn_text = "[CONTENT REMOVED IN SOURCE REVISION HISTORY]"
        relation = "DELETES"
        signal = "SOURCE_DELETION_HISTORY"
    else:
        if not action_text:
            return None, "RESULTING_VALUE_UNRESOLVED"
        scope = "DELETION_RESTORATION"
        candidate_value = action_text
        candidate_turn_text = action_text
        relation = "RESTORES"
        signal = "SOURCE_RESTORATION_HISTORY"
    conversation_id = str(utterance.get("conversation_id") or action.get("root") or "")
    contributor = ""
    speaker = action.get("speaker")
    if isinstance(speaker, dict):
        contributor = str(speaker.get("id") or speaker.get("speaker_id") or "")
    source_id = _private_token(secret, "wikiconv-action", action_id)
    item = {
        "schema_version": "1.0",
        "item_id": f"WC{year}-{source_id}",
        "blind_id": None,
        "source_track": "WIKICONV",
        "scope": scope,
        "principal_type": "EDITORIAL_CONTENT_ENTITY",
        "memory_slot": "editorial_utterance_content",
        "prior_value": prior,
        "candidate_value": candidate_value,
        "dialogue": [
            {"turn_id": "T001", "role": "editor", "text": prior},
            {"turn_id": "T002", "role": "editor", "text": candidate_turn_text},
        ],
        "prior_evidence_turn_ids": ["T001"],
        "candidate_turn_id": "T002",
        "context_turn_ids": ["T001", "T002"],
        "constructor_provisional_action": "SUPERSEDE",
        "constructor_provisional_resulting_value": candidate_value,
        "constructor_rationale": (
            f"AI-assisted provisional construction from WikiConv {year} {kind} history; "
            "not gold and requires human semantic, source, privacy, and legal review."
        ),
        "lineage_relation_private": relation,
        "source_locator_private": {
            "source_year": year,
            "conversation_id": conversation_id,
            "action_id": action_id,
            "original_id": original_id,
            "revision_id": str(action_meta.get("rev_id") or ""),
        },
        "continuity_keys_private": [
            f"conversation:{_private_token(secret, 'conversation', conversation_id)}",
            f"revision_lineage:{_private_token(secret, 'ancestor', original_id)}",
            f"contributor:{_private_token(secret, 'contributor', contributor)}",
        ],
        "stage1_signals": [signal],
        "privacy_status": "PENDING_HUMAN_REVIEW",
        "construction_status": "CANDIDATE",
        "rejection_reason": None,
    }
    try:
        validate_construction_item(item)
    except ValidationError as exc:
        message = str(exc)
        if "prior_value" in message:
            return None, "NON_ATOMIC_PRIOR"
        if "candidate" in message:
            return None, "NON_ATOMIC_CANDIDATE"
        if "resulting" in message:
            return None, "RESULTING_VALUE_UNRESOLVED"
        return None, "OTHER_DOCUMENTED"
    return item, None


def _iter_wikiconv_year(input_root: Path, year: int) -> Iterator[dict[str, Any]]:
    if year == 2003:
        with (
            zipfile.ZipFile(input_root / "wikiconv-english-2003.corpus.zip") as bundle,
            bundle.open(WIKICONV_2003_UTTERANCES) as source,
        ):
            for line in source:
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValidationError("WikiConv 2003 contains a non-object row")
                    yield value
        return
    for index in range(1, 8):
        path = input_root / f"utterances.part{index:03d}.jsonl.gz"
        with gzip.open(path, "rt", encoding="utf-8") as source:
            for line in source:
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValidationError("WikiConv 2018 contains a non-object row")
                    yield value


def scan_wikiconv_full(
    input_root: Path,
    repo_root: Path,
    *,
    max_per_action_year: int,
) -> dict[str, Any]:
    private = _private_root(repo_root)
    secret = _load_or_create_secret(private / "source_id_hmac_secret.bin")
    selected: dict[tuple[int, str], list[tuple[int, str, dict[str, Any]]]] = defaultdict(list)
    year_reports: dict[int, dict[str, Any]] = {}
    all_rejections: Counter[str] = Counter()
    for year in (2003, 2018):
        utterances = 0
        action_counts: Counter[str] = Counter()
        candidate_eligible: Counter[str] = Counter()
        rejection_counts: Counter[str] = Counter()
        for utterance in _iter_wikiconv_year(input_root, year):
            utterances += 1
            meta = utterance.get("meta")
            if not isinstance(meta, dict):
                rejection_counts["SOURCE_INCOMPLETE"] += 1
                continue
            original = meta.get("original")
            for kind in ACTION_KEYS:
                raw_actions = meta.get(kind)
                if not isinstance(raw_actions, list):
                    continue
                action_counts[kind.upper()] += len(raw_actions)
                for action in raw_actions:
                    if not isinstance(original, dict) or not isinstance(action, dict):
                        rejection_counts["SOURCE_INCOMPLETE"] += 1
                        continue
                    item, rejection = _candidate_from_action(
                        year=year,
                        utterance=utterance,
                        original=original,
                        action=action,
                        kind=kind,
                        secret=secret,
                    )
                    if item is None:
                        rejection_counts[rejection or "OTHER_DOCUMENTED"] += 1
                        continue
                    candidate_eligible[kind.upper()] += 1
                    action_id = str(
                        item["source_locator_private"].get("action_id", item["item_id"])
                    )
                    score = _stable_score(year, kind, action_id)
                    heap = selected[(year, kind)]
                    entry = (-score, item["item_id"], item)
                    if len(heap) < max_per_action_year:
                        heapq.heappush(heap, entry)
                    elif entry[0] > heap[0][0]:
                        heapq.heapreplace(heap, entry)
        all_rejections.update(rejection_counts)
        year_report = {
            "schema_version": "2.0",
            "source_track": "WIKICONV",
            "source_year": year,
            "utterances": utterances,
            "action_events": dict(action_counts),
            "candidate_eligible_before_bounded_selection": dict(candidate_eligible),
            "rejection_reasons": dict(rejection_counts),
            "selection_policy": {
                "method": "stable minimum SHA-256 score per year/action bucket",
                "max_per_action_year": max_per_action_year,
                "prevalence_estimate": False,
            },
        }
        year_reports[year] = year_report
        write_json(
            repo_root / "reports" / f"WIKICONV_{year}_RECONSTRUCTION.json", year_report
        )

    selected_items = [
        item
        for key in sorted(selected)
        for _, _, item in sorted(selected[key], key=lambda entry: (-entry[0], entry[1]))
    ]
    selected_items.sort(key=lambda item: item["item_id"])
    _atomic_jsonl_stream(private / "wikiconv_candidate_windows.jsonl", selected_items)
    rejection_report = {
        "schema_version": "2.0",
        "rejection_reasons": dict(all_rejections),
        "note": "Counts are construction dispositions, not benchmark labels.",
    }
    write_json(repo_root / "reports" / "WIKICONV_REJECTIONS.json", rejection_report)
    yield_report = {
        "schema_version": "2.0",
        "candidates_selected": len(selected_items),
        "by_year": dict(Counter(str(item["source_locator_private"]["source_year"]) for item in selected_items)),
        "scope_counts": dict(Counter(item["scope"] for item in selected_items)),
        "constructor_action_counts_provisional_only": dict(
            Counter(item["constructor_provisional_action"] for item in selected_items)
        ),
        "publication_eligible": False,
        "bounded_sample_not_prevalence_estimate": True,
    }
    write_json(repo_root / "reports" / "WIKICONV_CANDIDATE_YIELD.json", yield_report)
    markdown = [
        "---",
        "ai_generated: true",
        "artifact_status: machine_data_quality_report",
        "---",
        "",
        "# WikiConv data quality",
        "",
        f"- WikiConv 2003 utterances scanned: **{year_reports[2003]['utterances']:,}**",
        f"- WikiConv 2018 utterances scanned: **{year_reports[2018]['utterances']:,}**",
        f"- Bounded provisional candidate windows: **{len(selected_items):,}**",
        "- The bounded retained set is not an estimate of natural action prevalence.",
        "- Discussion state, content state, and revision action remain separate concepts.",
    ]
    (repo_root / "reports" / "WIKICONV_DATA_QUALITY.md").write_text(
        "\n".join(markdown) + "\n"
    )
    return {"years": year_reports, "yield": yield_report}


def _decode_json_value(
    decoder: json.JSONDecoder,
    buffer: str,
    position: int,
    read_more: Any,
) -> tuple[Any, str, int]:
    while True:
        try:
            value, end = decoder.raw_decode(buffer, position)
            return value, buffer, end
        except json.JSONDecodeError:
            more = read_more()
            if more == "":
                raise
            buffer += more


def _iter_json_object_items(source: BinaryIO) -> Iterator[tuple[str, Any]]:
    utf8_decoder = codecs.getincrementaldecoder("utf-8")()
    decoder = json.JSONDecoder()
    buffer = ""
    position = 0
    eof = False

    def read_more() -> str:
        nonlocal eof
        chunk = source.read(1024 * 1024)
        if not chunk:
            if eof:
                return ""
            eof = True
            return utf8_decoder.decode(b"", final=True)
        return utf8_decoder.decode(chunk)

    buffer += read_more()
    while True:
        while position >= len(buffer) and not eof:
            buffer += read_more()
        while position < len(buffer) and buffer[position].isspace():
            position += 1
        if position < len(buffer) and buffer[position] == "{":
            position += 1
            break
        if eof:
            raise ValidationError("metadata JSON does not begin with an object")
        buffer += read_more()

    while True:
        while True:
            while position < len(buffer) and (buffer[position].isspace() or buffer[position] == ","):
                position += 1
            if position < len(buffer):
                break
            more = read_more()
            if more == "":
                raise ValidationError("unexpected end of metadata JSON")
            buffer += more
        if buffer[position] == "}":
            return
        key, buffer, position = _decode_json_value(decoder, buffer, position, read_more)
        if not isinstance(key, str):
            raise ValidationError("metadata JSON object key is not a string")
        while True:
            while position < len(buffer) and buffer[position].isspace():
                position += 1
            if position < len(buffer):
                break
            buffer += read_more()
        if buffer[position] != ":":
            raise ValidationError("metadata JSON is missing a colon")
        position += 1
        while True:
            while position < len(buffer) and buffer[position].isspace():
                position += 1
            if position < len(buffer):
                break
            more = read_more()
            if more == "":
                raise ValidationError("unexpected end after metadata JSON colon")
            buffer += more
        value, buffer, position = _decode_json_value(decoder, buffer, position, read_more)
        yield key, value
        if position > 4 * 1024 * 1024:
            buffer = buffer[position:]
            position = 0


def _conversation_metadata(
    input_root: Path, year: int, selected_ids: set[str]
) -> dict[str, dict[str, Any]]:
    if not selected_ids:
        return {}
    archive = (
        input_root / "wikiconv-english-2003.corpus.zip"
        if year == 2003
        else input_root / "wikiconv-english-2018data.zip"
    )
    found: dict[str, dict[str, Any]] = {}
    with (
        zipfile.ZipFile(archive) as bundle,
        bundle.open("conversations.json") as source,
    ):
        for conversation_id, value in _iter_json_object_items(source):
            if conversation_id not in selected_ids or not isinstance(value, dict):
                continue
            meta = value.get("meta")
            if isinstance(meta, dict):
                found[conversation_id] = meta
            if len(found) == len(selected_ids):
                break
    return found


def context_wikiconv_full(input_root: Path, repo_root: Path) -> dict[str, Any]:
    private = _private_root(repo_root)
    path = private / "wikiconv_candidate_windows.jsonl"
    items = list(iter_jsonl(path))
    ids_by_year: dict[int, set[str]] = defaultdict(set)
    for item in items:
        locator = item["source_locator_private"]
        ids_by_year[int(locator["source_year"])].add(str(locator["conversation_id"]))
    metadata = {
        year: _conversation_metadata(input_root, year, identifiers)
        for year, identifiers in ids_by_year.items()
    }
    found = 0
    for item in items:
        locator = item["source_locator_private"]
        year = int(locator["source_year"])
        conversation_id = str(locator["conversation_id"])
        meta = metadata.get(year, {}).get(conversation_id)
        if meta is None:
            locator["page_metadata_status"] = "NOT_FOUND"
            continue
        found += 1
        page_title = str(meta.get("page_title") or "")
        page_id = str(meta.get("page_id") or "")
        locator["page_title"] = page_title
        locator["page_id"] = page_id
        locator["page_metadata_status"] = "FOUND"
        page_key = re.sub(r"\s+", " ", page_title.casefold()).strip() or conversation_id
        item["continuity_keys_private"].append(f"page_family:{page_key}")
        item["continuity_keys_private"] = sorted(set(item["continuity_keys_private"]))
    _atomic_jsonl_stream(path, items)
    report = {
        "schema_version": "2.0",
        "candidate_windows": len(items),
        "conversation_metadata_found": found,
        "conversation_metadata_missing": len(items) - found,
        "status": "COMPLETE_WITH_RECORDED_MISSING_METADATA"
        if found < len(items)
        else "COMPLETE",
    }
    write_json(repo_root / "reports" / "WIKICONV_CONTEXT_RECOVERY.json", report)
    return report


def _redact_candidate_item(item: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    redacted = json.loads(json.dumps(item))
    events: list[dict[str, Any]] = []
    fields: list[tuple[str, Any]] = [
        ("$.prior_value", redacted.get("prior_value")),
        ("$.candidate_value", redacted.get("candidate_value")),
    ]
    for index, turn in enumerate(redacted.get("dialogue", [])):
        fields.append((f"$.dialogue[{index}].text", turn.get("text")))
    for location, value in fields:
        if not isinstance(value, str):
            continue
        replacement, local_events = redact_text(value)
        for event in local_events:
            event["location"] = location
            events.append(event)
        if location == "$.prior_value":
            redacted["prior_value"] = replacement
        elif location == "$.candidate_value":
            redacted["candidate_value"] = replacement
        else:
            index = int(location.split("[")[1].split("]")[0])
            redacted["dialogue"][index]["text"] = replacement
    redacted["privacy_status"] = (
        "AUTOMATED_REDACTION_APPLIED" if events else "PENDING_HUMAN_REVIEW"
    )
    return redacted, events


def _privacy_scan_items(
    items: list[dict[str, Any]], repo_root: Path, private: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    redaction_logs: list[dict[str, Any]] = []
    redacted_items: list[dict[str, Any]] = []
    for item in items:
        review_id = hashlib.sha256(item["item_id"].encode()).hexdigest()[:20]
        for location, value in [
            ("$.prior_value", item.get("prior_value")),
            ("$.candidate_value", item.get("candidate_value")),
            *[
                (f"$.dialogue[{index}].text", turn.get("text"))
                for index, turn in enumerate(item.get("dialogue", []))
            ],
        ]:
            if not isinstance(value, str):
                continue
            for finding in scan_text(value, location):
                finding["record_id_private"] = item["item_id"]
                finding["review_id"] = review_id
                findings.append(finding)
        redacted, events = _redact_candidate_item(item)
        redacted_items.append(redacted)
        redaction_logs.append(
            {
                "record_id_private": item["item_id"],
                "review_id": review_id,
                "before_sha256": canonical_json_hash(item),
                "after_sha256": canonical_json_hash(redacted),
                "events": events,
            }
        )
    write_jsonl(private / "privacy_findings.jsonl", findings, mode=0o600)
    write_jsonl(private / "redaction_log.jsonl", redaction_logs, mode=0o600)
    queue_path = repo_root / "reports" / "MANUAL_PRIVACY_REVIEW_QUEUE.csv"
    grouped = Counter(
        (finding["review_id"], finding["category"], finding["severity"])
        for finding in findings
    )
    with queue_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "review_id",
                "category",
                "severity",
                "finding_count",
                "review_status",
                "reviewer_notes",
            ],
        )
        writer.writeheader()
        for (review_id, category, severity), count in sorted(grouped.items()):
            writer.writerow(
                {
                    "review_id": review_id,
                    "category": category,
                    "severity": severity,
                    "finding_count": count,
                    "review_status": "PENDING_HUMAN_REVIEW",
                    "reviewer_notes": "",
                }
            )
    report = {
        "schema_version": "2.0",
        "records_scanned": len(items),
        "findings": len(findings),
        "records_with_findings": len({finding["review_id"] for finding in findings}),
        "categories": dict(Counter(finding["category"] for finding in findings)),
        "severity": dict(Counter(finding["severity"] for finding in findings)),
        "manual_queue_rows": len(grouped),
        "automated_redaction_events": sum(
            len(record["events"]) for record in redaction_logs
        ),
        "manual_review_required": True,
        "anonymity_guaranteed": False,
        "human_review_passed_items": 0,
        "status": "AUTOMATED_REVIEW_SUPPORT_COMPLETE_HUMAN_REVIEW_PENDING",
    }
    write_json(repo_root / "reports" / "PII_SCAN_FULL.json", report)
    return redacted_items, report


def build_full_privacy_blind(repo_root: Path) -> dict[str, Any]:
    private = _private_root(repo_root)
    studychat_candidates = private / "studychat_candidates.jsonl"
    studychat_rejections = private / "studychat_rejections.jsonl"
    studychat_report = repo_root / "reports" / "STUDYCHAT_CANDIDATE_YIELD.json"
    mine_studychat_file(
        private / "studychat_rows.jsonl",
        studychat_candidates,
        studychat_rejections,
        studychat_report,
    )
    studychat_rejection_counts = Counter(
        row["rejection_reason"] for row in iter_jsonl(studychat_rejections)
    )
    write_json(
        repo_root / "reports" / "STUDYCHAT_REJECTIONS.json",
        {
            "schema_version": "2.0",
            "rejection_reasons": dict(studychat_rejection_counts),
            "rejected": sum(studychat_rejection_counts.values()),
        },
    )
    studychat_items = list(iter_jsonl(studychat_candidates))
    wiki_items = list(iter_jsonl(private / "wikiconv_candidate_windows.jsonl"))
    all_items = [*studychat_items, *wiki_items]
    if not all_items:
        raise ValidationError("full-source mining produced no candidates")
    redacted_items, privacy_report = _privacy_scan_items(all_items, repo_root, private)
    redacted_path = private / "construction_items_redacted.jsonl"
    write_jsonl(redacted_path, redacted_items, mode=0o600)
    for track in ("STUDYCHAT", "WIKICONV"):
        track_path = private / f"{track.casefold()}_construction_items_redacted.jsonl"
        write_jsonl(
            track_path,
            (item for item in redacted_items if item["source_track"] == track),
            mode=0o600,
        )
    packet_dir = private / "packets" / "combined"
    packet = private / "packets" / "mgp_natural_full_annotation.zip"
    commitment = repo_root / "manifests" / "full_mapping_commitment.json"
    build_packet(redacted_path, packet_dir, packet, commitment)
    verification = verify_packet(packet)
    write_json(repo_root / "reports" / "FULL_PRIVATE_PACKET_VERIFICATION.json", verification)
    report = {
        "schema_version": "2.0",
        "studychat_candidates": len(studychat_items),
        "wikiconv_candidates": len(wiki_items),
        "combined_candidates": len(redacted_items),
        "privacy": privacy_report,
        "private_packet": verification,
        "publication_eligible": False,
    }
    write_json(repo_root / "reports" / "FULL_PRIVACY_BLINDING_SUMMARY.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Full-source MGP-Natural private pipeline")
    parser.add_argument(
        "command",
        choices=[
            "audit",
            "reconstruct-studychat",
            "scan-wikiconv",
            "context-wikiconv",
            "privacy-blind",
        ],
    )
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--max-per-action-year", type=int, default=250)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    if args.command == "privacy-blind":
        result = build_full_privacy_blind(repo_root)
    else:
        input_root = _input_root(args.input_root)
        if args.command == "audit":
            result = audit_full_inputs(input_root, repo_root)
        elif args.command == "reconstruct-studychat":
            result = reconstruct_studychat_full(input_root, repo_root)
        elif args.command == "scan-wikiconv":
            result = scan_wikiconv_full(
                input_root,
                repo_root,
                max_per_action_year=args.max_per_action_year,
            )
        else:
            result = context_wikiconv_full(input_root, repo_root)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

