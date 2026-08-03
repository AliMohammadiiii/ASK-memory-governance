from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
V12_PARENT = ROOT / "runs_local/lme_final_controller_v12_qwen_180/manifest.json"


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(
    not V12_PARENT.is_file(), reason="local immutable V12 evidence is not publicly redistributed"
)
def test_derived_manifest_verifies() -> None:
    verifier = _load("scripts/provenance/verify_lme_v12_derived_manifest.py", "verify_lme_manifest")
    report = verifier.verify()
    assert report["status"] == "PASS"
    assert report["manifest_status"] == "DERIVED_AUDIT_ONLY"


def test_trace_semantics_accept_abstain_fixture() -> None:
    validator = _load("scripts/validation/validate_ask_traces.py", "validate_ask_traces")
    digest = "a" * 64
    body = {
        "action": "Abstain",
        "store_mode": "single_slot_versioned",
        "prior_record_id": "p",
        "candidate_record_id": "c",
        "resulting_record_id": None,
        "predecessor_record_id": None,
        "configuration_id": "cfg",
        "configuration_sha256": digest,
        "evidence_digest": digest,
        "before_digest": digest,
        "after_digest": digest,
        "keep_admitted_candidate": False,
    }
    event = {
        "event_id": validator._stable_digest(body),
        **{key: value for key, value in body.items() if not key.startswith("configuration_")},
        "configuration": {
            "configuration_id": "cfg",
            "adapter_version": "v1",
            "sha256": digest,
        },
        "metadata": {},
    }
    assert validator.semantic_errors(event) == []


def test_readiness_remains_no_go() -> None:
    report = json.loads((ROOT / "reports/readiness.json").read_text())
    assert report["status"] == "NO_GO"
