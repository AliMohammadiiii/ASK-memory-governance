from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load() -> ModuleType:
    path = ROOT / "scripts/provenance/build_mgpn_derived_manifest.py"
    spec = importlib.util.spec_from_file_location("build_mgpn_derived_manifest", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_inputs(module: ModuleType, tmp_path: Path) -> dict[str, object]:
    repository_root = tmp_path / "repository"
    for paths in module.REPOSITORY_EVIDENCE_FILES.values():
        for relative_path in paths:
            path = repository_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixture for {relative_path}\n", encoding="utf-8")

    archive = tmp_path / "private-input" / "candidate.zip"
    delivery = tmp_path / "external-reports" / "delivery.txt"
    research = tmp_path / "external-reports" / "research.txt"
    for path, payload in (
        (archive, b"pinned archive fixture\n"),
        (delivery, b"delivery report with /Users/example/private/path\n"),
        (research, b"research report PRIVATE_PAYLOAD_MARKER\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    expected = {
        "parent_archive": _sha256(archive),
        "delivery_report": _sha256(delivery),
        "research_report": _sha256(research),
    }
    audit = tmp_path / "audit" / "archive_audit.json"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "status": "QUARANTINED_RELEASE_CANDIDATE",
                "core_integrity_passed": True,
                "gold_or_public_release_eligible": False,
                "parent_archive": {"sha256": expected["parent_archive"]},
                "manifest": {"entry_count": 136, "verified": True},
                "dataset": {
                    "record_count": 36,
                    "unique_id_count": 36,
                    "dialogue_excerpt_row_count": 76,
                    "multi_contributor_excerpt_count": 31,
                    "single_contributor_excerpt_count": 5,
                    "independent_adjudication_complete_count": 0,
                    "requires_independent_confirmation_count": 36,
                },
                "blind_packet_audit": {
                    "record_count": 36,
                    "relation_to_prior_present_count": 36,
                    "deterministic_relation_rule_correct": 36,
                    "safe_for_independent_annotation": False,
                },
                "split_audit": {
                    "benchmark_held_out_split_valid": False,
                    "continuity_component_count": 2,
                    "continuity_component_sizes": [35, 1],
                    "mixed_split_continuity_component_count": 1,
                },
                "release_checklist": {
                    "unchecked_item_count": 32,
                    "all_required_signoffs_complete": False,
                },
                "private_payload": {
                    "absolute_path": "/Users/example/private/source.jsonl",
                    "mgpn_id": "MGPN01-PRIVATE_PAYLOAD_MARKER",
                    "gold_action": "SUPERSEDE",
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "repository_root": repository_root,
        "archive": archive,
        "delivery": delivery,
        "research": research,
        "audit": audit,
        "expected": expected,
    }


def _build(module: ModuleType, inputs: dict[str, object]) -> dict[str, object]:
    return module.build_manifest(
        inputs["archive"],
        inputs["delivery"],
        inputs["research"],
        inputs["audit"],
        repository_root=inputs["repository_root"],
        expected_external_sha256=inputs["expected"],
    )


def test_mgpn_manifest_success_is_deterministic_and_atomic(tmp_path: Path) -> None:
    module = _load()
    inputs = _fixture_inputs(module, tmp_path)

    first = _build(module, inputs)
    second = _build(module, inputs)
    assert first == second
    assert module.canonical_json_bytes(first) == module.canonical_json_bytes(second)
    assert first["status"] == "DERIVED_AUDIT_ONLY"
    assert first["candidate_audit"]["summary"]["dataset"]["record_count"] == 36
    assert set(first["repository_identity"]) == {"code", "schema", "protocol"}
    assert first["anomaly_ledger"]
    assert first["claim_boundary"]["prohibited"]
    assert all(value is False for value in first["gates"].values())

    output = tmp_path / "out" / "manifest.json"
    module.atomic_write_manifest(output, first)
    first_bytes = output.read_bytes()
    module.atomic_write_manifest(output, second)
    assert output.read_bytes() == first_bytes == module.canonical_json_bytes(first)
    assert not list(output.parent.glob(f".{output.name}.*.tmp"))


@pytest.mark.parametrize("role", ["parent_archive", "delivery_report", "research_report"])
def test_mgpn_manifest_refuses_wrong_pinned_hash(tmp_path: Path, role: str) -> None:
    module = _load()
    inputs = _fixture_inputs(module, tmp_path)
    expected = dict(inputs["expected"])
    expected[role] = "0" * 64

    with pytest.raises(module.ManifestInputError, match="SHA-256 mismatch"):
        module.build_manifest(
            inputs["archive"],
            inputs["delivery"],
            inputs["research"],
            inputs["audit"],
            repository_root=inputs["repository_root"],
            expected_external_sha256=expected,
        )


def test_mgpn_manifest_contains_no_absolute_path_or_private_payload(tmp_path: Path) -> None:
    module = _load()
    inputs = _fixture_inputs(module, tmp_path)
    manifest = _build(module, inputs)
    serialized = module.canonical_json_bytes(manifest).decode("utf-8")

    assert str(tmp_path) not in serialized
    assert "/Users/" not in serialized
    assert "PRIVATE_PAYLOAD_MARKER" not in serialized
    assert "private_payload" not in serialized
    assert "mgpn_id" not in serialized
    assert "gold_action" not in serialized
    assert "source_item_id" not in serialized
    assert manifest["privacy_boundary"] == {
        "external_payloads_embedded": False,
        "machine_local_paths_embedded": False,
        "provisional_item_labels_embedded": False,
        "raw_conversation_embedded": False,
        "source_identifiers_embedded": False,
    }
