from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from mgp_natural.errors import SourceChangedError, ValidationError
from mgp_natural.ingestion.studychat import (
    audit_archive,
    safe_extract_zip,
    summarize_derivative,
    verify_archive_hash,
)
from mgp_natural.reconstruction.studychat import reconstruct_file, reconstruct_long_chat
from mgp_natural.util.io import iter_jsonl


def test_malformed_zip(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    archive.write_bytes(b"not a zip")
    with pytest.raises(ValidationError, match="malformed ZIP"):
        safe_extract_zip(archive, tmp_path / "out")


def test_zip_slip_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.txt", "bad")
    with pytest.raises(ValidationError, match="unsafe archive member"):
        safe_extract_zip(archive, tmp_path / "out")


def test_incorrect_hash(tmp_path: Path) -> None:
    path = tmp_path / "source.zip"
    path.write_bytes(b"fixture")
    with pytest.raises(SourceChangedError, match="hash mismatch"):
        verify_archive_hash(path, "0" * 64)


def test_incomplete_studychat_sample_classified_unknown(tmp_path: Path) -> None:
    archive = tmp_path / "partial.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("stats.json", json.dumps({"rows": 10}))
        bundle.writestr("mgp_candidate_sample.jsonl", "{}\n")
    report = audit_archive(archive, tmp_path / "extract")
    assert report["classification"] == "UNKNOWN_DERIVATIVE"
    with pytest.raises(ValidationError, match="missing derivative files"):
        summarize_derivative(tmp_path / "extract")


def _long_chat(counts: list[int], messages: list[list[dict[str, str]]] | None = None) -> dict:
    interactions = []
    for index, count in enumerate(counts):
        prompt = f"prompt {index}"
        response = f"response {index}"
        interactions.append(
            {
                "row_index": index,
                "interaction_count": count,
                "prompt": prompt,
                "response": response,
                "messages": messages[index] if messages else [],
            }
        )
    return {
        "user_id_hash": "u",
        "chat_id_hash": "c",
        "topic": "fixture",
        "semester": "fixture",
        "interactions": interactions,
    }


def test_non_monotonic_counts_and_conflicting_history_are_recorded() -> None:
    row = _long_chat([1, 0])
    _, anomalies = reconstruct_long_chat(row)
    codes = {entry["code"] for entry in anomalies}
    assert "NON_MONOTONIC_INTERACTION_COUNTS" in codes
    assert "PARTIAL_HISTORY_START" in codes
    assert "CUMULATIVE_HISTORY_CONFLICT" in codes


def test_interaction_count_gap_is_recorded() -> None:
    row = _long_chat([0, 2])
    _, anomalies = reconstruct_long_chat(row)
    assert "INTERACTION_COUNT_GAPS" in {entry["code"] for entry in anomalies}


def test_missing_required_fields() -> None:
    with pytest.raises(ValidationError, match="missing fields"):
        reconstruct_long_chat({"interactions": []})


def test_stable_reconstruction_fixture(tmp_path: Path) -> None:
    source = Path("data/fixtures/studychat_long_chat_fixture.jsonl")
    output = tmp_path / "chats.jsonl"
    anomaly = tmp_path / "anomalies.jsonl"
    first = reconstruct_file(source, output, anomaly)
    first_bytes = output.read_bytes()
    second = reconstruct_file(source, output, anomaly)
    assert first == second
    assert output.read_bytes() == first_bytes
    assert first["chats"] == 2
    assert first["anomalies"] > 0
    rows = list(iter_jsonl(output))
    assert rows[0]["turns"][0]["role"] == "user"


def test_duplicate_chat_rows_are_recorded(tmp_path: Path) -> None:
    source_rows = Path("data/fixtures/studychat_long_chat_fixture.jsonl").read_text()
    source = tmp_path / "duplicate.jsonl"
    first = source_rows.splitlines()[0]
    source.write_text(first + "\n" + first + "\n", encoding="utf-8")
    summary = reconstruct_file(source, tmp_path / "out.jsonl", tmp_path / "anomaly.jsonl")
    assert summary["anomaly_codes"]["DUPLICATE_CHAT_RECORD"] == 1


def test_audit_archive_accepts_relative_destination(tmp_path: Path, monkeypatch) -> None:
    import zipfile

    from mgp_natural.ingestion.studychat import audit_archive

    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("studychat_audit/stats.json", "{}")
        bundle.writestr("studychat_audit/mgp_candidate_sample.jsonl", "{}\n")
        bundle.writestr("studychat_audit/long_chat_sample.jsonl", "{}\n")
    monkeypatch.chdir(tmp_path)
    report = audit_archive(Path("sample.zip"), Path("relative_extract"))
    assert len(report["files"]) == 3


def test_available_source_reconstruction_uses_canonical_rows_not_messages(tmp_path: Path) -> None:
    from mgp_natural.reconstruction.studychat import reconstruct_available_sources
    from mgp_natural.util.io import write_jsonl

    candidate = tmp_path / "candidate.jsonl"
    long_chat = tmp_path / "long.jsonl"
    output = tmp_path / "out.jsonl"
    anomalies = tmp_path / "anomalies.jsonl"
    report_path = tmp_path / "report.json"
    rows = [
        {
            "row_index": 10,
            "user_id_hash": "u",
            "chat_id_hash": "c",
            "topic": "fixture",
            "semester": "fixture",
            "interaction_count": 0,
            "chat_total_interaction_count": 1,
            "prompt": "Please use cleaned.csv.",
            "response": "Okay.",
            "messages": [{"role": "user", "content": "conflicting cumulative text"}],
        },
        {
            "row_index": 11,
            "user_id_hash": "u",
            "chat_id_hash": "c",
            "topic": "fixture",
            "semester": "fixture",
            "interaction_count": 1,
            "chat_total_interaction_count": 1,
            "prompt": "Use final.csv instead of cleaned.csv.",
            "response": "Switched.",
            "messages": [{"role": "user", "content": "also conflicting"}],
        },
    ]
    write_jsonl(candidate, rows)
    write_jsonl(
        long_chat,
        [
            {
                "user_id_hash": "u",
                "chat_id_hash": "c",
                "topic": "fixture",
                "semester": "fixture",
                "interactions": [
                    {
                        **rows[0],
                        "row_index": 20,
                        "messages": [{"role": "user", "content": "wrong prefix"}],
                    }
                ],
            }
        ],
    )

    report = reconstruct_available_sources(candidate, long_chat, output, anomalies, report_path)
    chats = list(iter_jsonl(output))
    assert report["exact_overlap_rows_merged"] == 1
    assert report["messages_used_for_reconstruction"] is False
    assert report["message_consistency_counts"]["CANDIDATE_TURN_MISMATCH"] >= 1
    assert chats[0]["interactions"][0]["prompt"] == "Please use cleaned.csv."
    assert chats[0]["interactions"][1]["response"] == "Switched."


def test_available_source_reconstruction_records_gaps_and_conflicts(tmp_path: Path) -> None:
    from mgp_natural.reconstruction.studychat import reconstruct_available_sources
    from mgp_natural.util.io import write_jsonl

    candidate = tmp_path / "candidate.jsonl"
    long_chat = tmp_path / "long.jsonl"
    output = tmp_path / "out.jsonl"
    anomalies = tmp_path / "anomalies.jsonl"
    base = {
        "user_id_hash": "u",
        "chat_id_hash": "c",
        "topic": "fixture",
        "semester": "fixture",
        "chat_total_interaction_count": 2,
    }
    write_jsonl(
        candidate,
        [
            {
                **base,
                "row_index": 1,
                "interaction_count": 0,
                "prompt": "p0",
                "response": "r0",
                "messages": [{"role": "user", "content": "p0"}],
            },
            {
                **base,
                "row_index": 2,
                "interaction_count": 2,
                "prompt": "p2",
                "response": "r2",
                "messages": [{"role": "user", "content": "p2"}],
            },
        ],
    )
    write_jsonl(
        long_chat,
        [
            {
                "user_id_hash": "u",
                "chat_id_hash": "c",
                "topic": "fixture",
                "semester": "fixture",
                "interactions": [
                    {
                        "row_index": 3,
                        "interaction_count": 2,
                        "prompt": "different p2",
                        "response": "different r2",
                        "messages": [{"role": "user", "content": "different p2"}],
                    }
                ],
            }
        ],
    )
    report = reconstruct_available_sources(candidate, long_chat, output, anomalies)
    assert report["canonical_row_conflicts"] == 1
    assert report["chats_with_gaps"] == 1
    codes = {row["code"] for row in iter_jsonl(anomalies)}
    assert "CANONICAL_ROW_CONFLICT" in codes
    assert "SOURCE_INTERACTION_GAPS" in codes

