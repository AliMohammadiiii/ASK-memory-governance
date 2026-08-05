"""Reconstruct StudyChat once per chat from canonical prompt/response rows."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from mgp_natural.errors import ValidationError
from mgp_natural.util.io import iter_jsonl, write_json, write_jsonl


def _turns_from_interactions(interactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for index, row in enumerate(interactions):
        turns.append({"turn_id": f"T{2 * index + 1:04d}", "role": "user", "text": row["prompt"]})
        turns.append(
            {"turn_id": f"T{2 * index + 2:04d}", "role": "assistant", "text": row["response"]}
        )
    return turns


def reconstruct_long_chat(row: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    required = {"user_id_hash", "chat_id_hash", "topic", "semester", "interactions"}
    missing = required - set(row)
    if missing:
        raise ValidationError(f"long chat missing fields: {sorted(missing)}")
    interactions = row["interactions"]
    if not isinstance(interactions, list) or not interactions:
        raise ValidationError("long chat interactions must be nonempty")
    anomalies: list[dict[str, Any]] = []
    counts = [interaction["interaction_count"] for interaction in interactions]
    if counts != sorted(counts) or len(counts) != len(set(counts)):
        anomalies.append({"code": "NON_MONOTONIC_INTERACTION_COUNTS", "counts": counts})
    expected = list(range(counts[0], counts[0] + len(counts)))
    if counts != expected:
        anomalies.append({"code": "INTERACTION_COUNT_GAPS", "observed": counts})
    if counts[0] != 0:
        anomalies.append({"code": "PARTIAL_HISTORY_START", "first_count": counts[0]})
    prior: list[tuple[str, str]] = []
    for position, interaction in enumerate(interactions):
        expected_messages: list[dict[str, str]] = []
        for prompt, response in prior:
            expected_messages.extend(
                [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": response},
                ]
            )
        expected_messages.append({"role": "user", "content": interaction["prompt"]})
        observed_messages = interaction.get("messages")
        if observed_messages != expected_messages:
            anomalies.append(
                {
                    "code": "CUMULATIVE_HISTORY_CONFLICT",
                    "interaction_position": position,
                    "interaction_count": interaction["interaction_count"],
                    "expected_message_count": len(expected_messages),
                    "observed_message_count": len(observed_messages or []),
                }
            )
        prior.append((interaction["prompt"], interaction["response"]))
    reconstructed = {
        "schema_version": "1.0",
        "source_track": "STUDYCHAT",
        "source_user_private": row["user_id_hash"],
        "source_chat_private": row["chat_id_hash"],
        "topic_private": row["topic"],
        "semester_private": row["semester"],
        "turns": _turns_from_interactions(interactions),
        "source_rows_private": [interaction["row_index"] for interaction in interactions],
        "reconstruction_status": "ANOMALOUS" if anomalies else "VALIDATED",
    }
    return reconstructed, anomalies


def reconstruct_file(input_path: Path, output_path: Path, anomaly_path: Path) -> dict[str, Any]:
    chats = []
    anomalies = []
    seen_chats: set[str] = set()
    for row in iter_jsonl(input_path):
        chat_id = row["chat_id_hash"]
        if chat_id in seen_chats:
            anomalies.append({"code": "DUPLICATE_CHAT_RECORD", "source_chat_private": chat_id})
            continue
        seen_chats.add(chat_id)
        chat, chat_anomalies = reconstruct_long_chat(row)
        chats.append(chat)
        for anomaly in chat_anomalies:
            anomaly["source_chat_private"] = chat_id
            anomalies.append(anomaly)
    write_jsonl(output_path, chats, mode=0o600)
    write_jsonl(anomaly_path, anomalies, mode=0o600)
    summary = {
        "chats": len(chats),
        "anomalies": len(anomalies),
        "anomaly_codes": dict(Counter(item["code"] for item in anomalies)),
        "status": "VALID_WITH_RECORDED_ANOMALIES" if anomalies else "VALID",
    }
    return summary


def reconstruct_candidate_context(row: dict[str, Any]) -> list[dict[str, str]]:
    messages = row.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValidationError("candidate row lacks message context")
    turns = []
    for index, message in enumerate(messages, 1):
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant", "system"} or not isinstance(content, str):
            raise ValidationError("invalid message")
        if not content.strip():
            continue
        turns.append({"turn_id": f"T{index:04d}", "role": role, "text": content})
    if turns[-1]["role"] != "user" or turns[-1]["text"] != row.get("prompt"):
        raise ValidationError("candidate prompt does not align with last user message")
    return turns


def _required_interaction_fields(record: dict[str, Any], context: str) -> None:
    required = {"row_index", "interaction_count", "prompt", "response"}
    missing = required - set(record)
    if missing:
        raise ValidationError(f"{context} missing fields: {sorted(missing)}")
    if not isinstance(record["interaction_count"], int) or isinstance(record["interaction_count"], bool):
        raise ValidationError(f"{context} interaction_count must be an integer")
    if not isinstance(record["prompt"], str) or not isinstance(record["response"], str):
        raise ValidationError(f"{context} prompt/response must be strings")


def reconstruct_available_sources(
    candidate_input_path: Path,
    long_chat_input_path: Path,
    output_path: Path,
    anomaly_path: Path,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Merge all available canonical prompt/response rows without trusting cumulative histories.

    The candidate derivative and long-chat derivative can overlap. Canonical rows are keyed by
    pseudonymous user, chat, and interaction count. Repeated ``messages`` histories are retained
    only as consistency evidence; they never provide dialogue turns or fill source gaps.
    """

    canonical: dict[tuple[str, str, int], dict[str, Any]] = {}
    chat_metadata: dict[tuple[str, str], dict[str, Any]] = {}
    anomalies: list[dict[str, Any]] = []
    message_history_hashes: Counter[str] = Counter()
    source_record_counts: Counter[str] = Counter()
    exact_overlap_rows = 0
    canonical_conflicts = 0

    def add_record(
        *,
        user_id: str,
        chat_id: str,
        topic: str,
        semester: str,
        record: dict[str, Any],
        source_name: str,
        expected_total: int | None,
    ) -> None:
        nonlocal exact_overlap_rows, canonical_conflicts
        _required_interaction_fields(record, source_name)
        source_record_counts[source_name] += 1
        key = (user_id, chat_id, record["interaction_count"])
        meta_key = (user_id, chat_id)
        meta = chat_metadata.setdefault(
            meta_key,
            {
                "topic_values": set(),
                "semester_values": set(),
                "expected_totals": set(),
                "source_names": set(),
            },
        )
        meta["topic_values"].add(topic)
        meta["semester_values"].add(semester)
        meta["source_names"].add(source_name)
        if expected_total is not None:
            meta["expected_totals"].add(expected_total)
        messages = record.get("messages")
        if isinstance(messages, list):
            import hashlib
            import json

            encoded = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            message_history_hashes[hashlib.sha256(encoded.encode("utf-8")).hexdigest()] += 1
        existing = canonical.get(key)
        source_ref = {
            "source": source_name,
            "row_index": record["row_index"],
            "messages": messages,
        }
        if existing is None:
            canonical[key] = {
                "user_id_hash": user_id,
                "chat_id_hash": chat_id,
                "topic": topic,
                "semester": semester,
                "interaction_count": record["interaction_count"],
                "prompt": record["prompt"],
                "response": record["response"],
                "row_indices_private": [record["row_index"]],
                "source_refs_private": [source_ref],
                "source_conflict_private": False,
            }
            return
        existing["row_indices_private"].append(record["row_index"])
        existing["source_refs_private"].append(source_ref)
        if existing["prompt"] == record["prompt"] and existing["response"] == record["response"]:
            exact_overlap_rows += 1
            return
        existing["source_conflict_private"] = True
        canonical_conflicts += 1
        anomalies.append(
            {
                "code": "CANONICAL_ROW_CONFLICT",
                "source_chat_private": chat_id,
                "source_user_private": user_id,
                "interaction_count": record["interaction_count"],
                "source_names": sorted({ref["source"] for ref in existing["source_refs_private"]}),
            }
        )

    for row in iter_jsonl(candidate_input_path):
        required = {"user_id_hash", "chat_id_hash", "topic", "semester"}
        missing = required - set(row)
        if missing:
            raise ValidationError(f"candidate derivative row missing fields: {sorted(missing)}")
        total = row.get("chat_total_interaction_count")
        if total is not None and (not isinstance(total, int) or isinstance(total, bool) or total < 0):
            raise ValidationError("chat_total_interaction_count must be a nonnegative integer")
        add_record(
            user_id=row["user_id_hash"],
            chat_id=row["chat_id_hash"],
            topic=row["topic"],
            semester=row["semester"],
            record=row,
            source_name="candidate_sample",
            # The observed derivative uses this field as the zero-based final interaction index.
            expected_total=(total + 1) if total is not None else None,
        )

    for chat in iter_jsonl(long_chat_input_path):
        required = {"user_id_hash", "chat_id_hash", "topic", "semester", "interactions"}
        missing = required - set(chat)
        if missing:
            raise ValidationError(f"long-chat derivative row missing fields: {sorted(missing)}")
        if not isinstance(chat["interactions"], list) or not chat["interactions"]:
            raise ValidationError("long-chat interactions must be a nonempty list")
        for record in chat["interactions"]:
            if not isinstance(record, dict):
                raise ValidationError("long-chat interaction must be an object")
            add_record(
                user_id=chat["user_id_hash"],
                chat_id=chat["chat_id_hash"],
                topic=chat["topic"],
                semester=chat["semester"],
                record=record,
                source_name="long_chat_sample",
                expected_total=None,
            )

    chat_id_to_users: dict[str, set[str]] = {}
    for user_id, chat_id in chat_metadata:
        chat_id_to_users.setdefault(chat_id, set()).add(user_id)
    for chat_id, users in chat_id_to_users.items():
        if len(users) > 1:
            anomalies.append(
                {
                    "code": "CHAT_ID_USER_CONFLICT",
                    "source_chat_private": chat_id,
                    "user_count": len(users),
                }
            )

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for (user_id, chat_id, _), record in canonical.items():
        grouped.setdefault((user_id, chat_id), []).append(record)

    chats: list[dict[str, Any]] = []
    completeness_counts: Counter[str] = Counter()
    message_consistency_counts: Counter[str] = Counter()
    gap_count = 0
    for (user_id, chat_id), records in sorted(grouped.items()):
        records.sort(key=lambda item: (item["interaction_count"], min(item["row_indices_private"])))
        counts = [record["interaction_count"] for record in records]
        observed = set(counts)
        max_count = max(counts)
        missing_between = sorted(set(range(min(counts), max_count + 1)) - observed)
        missing_from_zero = sorted(set(range(0, max_count + 1)) - observed)
        meta = chat_metadata[(user_id, chat_id)]
        expected_totals = sorted(meta["expected_totals"])
        if len(expected_totals) > 1:
            anomalies.append(
                {
                    "code": "CONFLICTING_EXPECTED_CHAT_TOTALS",
                    "source_chat_private": chat_id,
                    "source_user_private": user_id,
                    "expected_totals": expected_totals,
                }
            )
        expected_total = expected_totals[0] if len(expected_totals) == 1 else None
        missing_to_expected: list[int] = []
        if expected_total is not None:
            missing_to_expected = sorted(set(range(expected_total)) - observed)
        source_conflict = any(record["source_conflict_private"] for record in records)
        metadata_conflict = len(meta["topic_values"]) > 1 or len(meta["semester_values"]) > 1
        if metadata_conflict:
            anomalies.append(
                {
                    "code": "CHAT_METADATA_CONFLICT",
                    "source_chat_private": chat_id,
                    "source_user_private": user_id,
                    "topic_value_count": len(meta["topic_values"]),
                    "semester_value_count": len(meta["semester_values"]),
                }
            )
        complete = counts[0] == 0 and not missing_from_zero
        if expected_total is not None:
            complete = complete and max_count + 1 == expected_total
        if source_conflict or metadata_conflict:
            completeness = "CONFLICTED"
        elif complete:
            completeness = "COMPLETE_OBSERVED"
        else:
            completeness = "PARTIAL_AVAILABLE"
        completeness_counts[completeness] += 1
        if missing_between or missing_to_expected or counts[0] != 0:
            gap_count += 1
            anomalies.append(
                {
                    "code": "SOURCE_INTERACTION_GAPS",
                    "source_chat_private": chat_id,
                    "source_user_private": user_id,
                    "first_interaction_count": counts[0],
                    "last_interaction_count": counts[-1],
                    "missing_between_count": len(missing_between),
                    "missing_to_expected_count": len(missing_to_expected),
                }
            )

        canonical_by_count = {record["interaction_count"]: record for record in records}
        for record in records:
            count = record["interaction_count"]
            for ref in record["source_refs_private"]:
                messages = ref.get("messages")
                if not isinstance(messages, list):
                    message_consistency_counts["MISSING"] += 1
                    continue
                if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != record["prompt"]:
                    message_consistency_counts["CANDIDATE_TURN_MISMATCH"] += 1
                    anomalies.append(
                        {
                            "code": "CANDIDATE_PROMPT_MESSAGE_MISMATCH",
                            "source_chat_private": chat_id,
                            "source_user_private": user_id,
                            "interaction_count": count,
                            "source": ref["source"],
                        }
                    )
                    continue
                if any(index not in canonical_by_count for index in range(0, count + 1)):
                    message_consistency_counts["UNVERIFIABLE_DUE_TO_SOURCE_GAPS"] += 1
                    continue
                expected_messages: list[dict[str, str]] = []
                for prior_count in range(0, count):
                    prior = canonical_by_count[prior_count]
                    expected_messages.extend(
                        [
                            {"role": "user", "content": prior["prompt"]},
                            {"role": "assistant", "content": prior["response"]},
                        ]
                    )
                expected_messages.append({"role": "user", "content": record["prompt"]})
                if messages == expected_messages:
                    message_consistency_counts["MATCH"] += 1
                else:
                    message_consistency_counts["CONFLICT"] += 1
                    anomalies.append(
                        {
                            "code": "CUMULATIVE_HISTORY_CONFLICT",
                            "source_chat_private": chat_id,
                            "source_user_private": user_id,
                            "interaction_count": count,
                            "source": ref["source"],
                            "expected_message_count": len(expected_messages),
                            "observed_message_count": len(messages),
                        }
                    )

        output_interactions = []
        source_rows: list[int] = []
        for record in records:
            source_rows.extend(record["row_indices_private"])
            output_interactions.append(
                {
                    "interaction_count": record["interaction_count"],
                    "prompt": record["prompt"],
                    "response": record["response"],
                    "row_indices_private": sorted(set(record["row_indices_private"])),
                    "source_names_private": sorted(
                        {ref["source"] for ref in record["source_refs_private"]}
                    ),
                    "source_conflict_private": record["source_conflict_private"],
                }
            )
        chats.append(
            {
                "schema_version": "1.0",
                "source_track": "STUDYCHAT",
                "source_user_private": user_id,
                "source_chat_private": chat_id,
                "topic_private": sorted(meta["topic_values"])[0],
                "semester_private": sorted(meta["semester_values"])[0],
                "interactions": output_interactions,
                "source_rows_private": sorted(set(source_rows)),
                "observed_interaction_counts_private": counts,
                "missing_interaction_counts_private": missing_from_zero,
                "expected_total_interactions_private": expected_total,
                "source_names_private": sorted(meta["source_names"]),
                "source_completeness": completeness,
                "reconstruction_status": "CONFLICTED"
                if source_conflict or metadata_conflict
                else ("VALIDATED" if complete else "PARTIAL_WITH_RECORDED_GAPS"),
            }
        )

    duplicate_histories = sum(count - 1 for count in message_history_hashes.values() if count > 1)
    write_jsonl(output_path, chats, mode=0o600)
    write_jsonl(anomaly_path, anomalies, mode=0o600)
    report = {
        "schema_version": "1.0",
        "source_record_counts": dict(source_record_counts),
        "canonical_interactions": len(canonical),
        "canonical_chats": len(chats),
        "canonical_users": len({chat["source_user_private"] for chat in chats}),
        "exact_overlap_rows_merged": exact_overlap_rows,
        "canonical_row_conflicts": canonical_conflicts,
        "duplicate_cumulative_histories": duplicate_histories,
        "message_consistency_counts": dict(message_consistency_counts),
        "source_completeness_counts": dict(completeness_counts),
        "chats_with_gaps": gap_count,
        "anomaly_count": len(anomalies),
        "anomaly_codes": dict(Counter(item["code"] for item in anomalies)),
        "messages_used_for_reconstruction": False,
        "status": "VALID_WITH_RECORDED_ANOMALIES" if anomalies else "VALID",
    }
    if report_path is not None:
        write_json(report_path, report)
    return report

