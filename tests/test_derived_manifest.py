from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
PARENT_MANIFEST = ROOT / "runs_local/lme_final_controller_v12_qwen_180/manifest.json"


def _load() -> ModuleType:
    path = ROOT / "scripts/provenance/build_lme_v12_derived_manifest.py"
    spec = importlib.util.spec_from_file_location("derived_manifest", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(
    not PARENT_MANIFEST.is_file(),
    reason="local immutable V12 evidence is not publicly redistributed",
)
def test_derived_manifest_preserves_historical_failure_and_anomalies() -> None:
    manifest = _load().build("2026-08-02T00:00:00+00:00")
    assert manifest["status"] == "DERIVED_AUDIT_ONLY"
    assert manifest["historical_status"] == "running"
    assert manifest["historical_exit_code"] == 1
    assert len(manifest["resume_history"]) == 3
    assert manifest["known_anomalies"]
    assert manifest["missing_expected_outputs"] == []
    assert all(not path.startswith("/") for path in manifest["output_sha256"])
