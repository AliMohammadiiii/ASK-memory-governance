from __future__ import annotations

import gzip
import json
import zipfile
from pathlib import Path

import pytest

from ask.confirmation.mgpn_full_intake import (
    FULL_INPUT_FILENAMES,
    FullIntakeError,
    audit_full_input_directory,
)


def _jsonl_row() -> bytes:
    return b'{"safe":"fixture"}\n'


def _inputs(tmp_path: Path) -> Path:
    root = tmp_path / "private-inputs"
    root.mkdir()
    with zipfile.ZipFile(root / "studychat.zip", "w") as bundle:
        bundle.writestr("studychat/data.jsonl", _jsonl_row() * 2)
        bundle.writestr("studychat/dialogues/f24_labeled_dialogues.jsonl", _jsonl_row())
        bundle.writestr("studychat/dialogues/s25_labeled_dialogues.jsonl", _jsonl_row() * 3)
    with zipfile.ZipFile(root / "wikiconv-english-2003.corpus.zip", "w") as bundle:
        bundle.writestr("utterances.jsonl", _jsonl_row() * 4)
    with zipfile.ZipFile(root / "wikiconv-english-2018data.zip", "w") as bundle:
        bundle.writestr("metadata.json", "{}")
    for name in ("studychat_full_source_manifest.json", "wikiconv_compact_manifest.json"):
        (root / name).write_text("{}\n", encoding="utf-8")
    for index in range(1, 8):
        with gzip.open(root / f"utterances.part{index:03d}.jsonl.gz", "wb") as handle:
            handle.write(_jsonl_row() * index)
    assert {path.name for path in root.iterdir()} == set(FULL_INPUT_FILENAMES)
    return root


def test_full_intake_is_path_neutral_and_does_not_embed_source_payload(tmp_path: Path) -> None:
    input_root = _inputs(tmp_path)
    report = audit_full_input_directory(input_root, repository_root=tmp_path / "repository")
    serialized = json.dumps(report, sort_keys=True)

    assert report["status"] == "QUARANTINED_PRIVATE_SOURCE_INTAKE"
    assert report["source_tracks"]["studychat"]["canonical_interaction_count"] == 2
    assert report["source_tracks"]["wikiconv"]["utterance_count_2003"] == 4
    assert report["source_tracks"]["wikiconv"]["utterance_count_2018"] == 28
    assert report["claim_boundary"]["publication_eligible"] is False
    assert str(input_root) not in serialized
    assert "fixture" not in serialized


def test_full_intake_rejects_repository_local_sources_and_unsafe_archives(tmp_path: Path) -> None:
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    with pytest.raises(FullIntakeError, match="outside the repository"):
        audit_full_input_directory(_inputs(repository_root), repository_root=repository_root)

    input_root = _inputs(tmp_path)
    with zipfile.ZipFile(input_root / "studychat.zip", "a") as bundle:
        bundle.writestr("../escape.jsonl", _jsonl_row())
    with pytest.raises(FullIntakeError, match="unsafe member path"):
        audit_full_input_directory(input_root, repository_root=tmp_path / "repository")


def test_full_intake_handles_private_derived_workspace_without_hashing_secrets(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "derived"
    input_root.mkdir()
    for name in (
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
        "packets/combined/blind_mapping.jsonl",
    ):
        path = input_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_jsonl_row())
    for name in ("source_id_hmac_secret.bin", "packets/combined/blinding_secret.bin"):
        path = input_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"private secret")
    archive = input_root / "packets/mgp_natural_full_annotation.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("README.txt", "private packet")

    report = audit_full_input_directory(input_root, repository_root=tmp_path / "repository")
    serialized = json.dumps(report, sort_keys=True)
    assert report["status"] == "QUARANTINED_PRIVATE_DERIVED_WORKSPACE"
    assert report["raw_source_archive_integrity_verified"] is False
    assert report["source_tracks"]["studychat"]["private_row_count"] == 1
    assert "private secret" not in serialized
    assert "source_id_hmac_secret.bin" not in serialized
