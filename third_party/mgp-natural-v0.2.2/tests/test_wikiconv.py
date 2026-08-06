from __future__ import annotations

from pathlib import Path

import pytest

from mgp_natural.errors import SourceChangedError, ValidationError
from mgp_natural.ingestion.wikiconv import (
    DownloadSpec,
    official_source_manifest,
    resumable_download,
)
from mgp_natural.mining.wikiconv import mine_reconstructed
from mgp_natural.reconstruction.wikiconv import normalize_action, reconstruct_actions
from mgp_natural.util.io import iter_jsonl


def test_official_manifest_is_fail_closed() -> None:
    manifest = official_source_manifest("2026-08-04")
    assert manifest["real_acquisition_status"] == "NOT_ACQUIRED_IN_THIS_EXECUTION"
    assert manifest["legal_status"] == "HUMAN_LEGAL_REVIEW_REQUIRED"


def test_unknown_action_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown WikiConv action"):
        normalize_action({"id": "x", "conversation_id": "c", "page_title": "p", "type": "UNKNOWN", "timestamp": "t"})


def test_modification_requires_parent() -> None:
    with pytest.raises(ValidationError, match="requires parent_id"):
        normalize_action({"id": "x", "conversation_id": "c", "page_title": "p", "type": "MODIFICATION", "timestamp": "t"})


def test_wikiconv_reconstruction_and_lineage(tmp_path: Path) -> None:
    output = tmp_path / "reconstructed.jsonl"
    summary = reconstruct_actions(Path("data/fixtures/wikiconv_actions.jsonl"), output)
    assert summary == {"conversations": 1, "actions": 4}
    conversation = next(iter_jsonl(output))
    assert all(action["lineage_status"] == "SUPPORTED" for action in conversation["actions"])
    report = mine_reconstructed(output, tmp_path / "candidates.jsonl", tmp_path / "report.json")
    assert report["candidates"] == 3
    assert report["publication_eligible"] is False


def test_download_hash_change_fails(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"official fixture")
    spec = DownloadSpec(identifier="fixture", url=source.as_uri(), filename="copy.bin", expected_sha256="0" * 64)
    with pytest.raises(SourceChangedError, match="hash changed"):
        resumable_download(spec, tmp_path / "download")

