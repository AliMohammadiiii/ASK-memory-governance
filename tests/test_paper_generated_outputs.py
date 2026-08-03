from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_headline_paper_fragments_have_not_drifted() -> None:
    path = ROOT / "scripts/paper/verify_generated_outputs.py"
    spec = importlib.util.spec_from_file_location("paper_drift", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.verify()["status"] == "PASS"
