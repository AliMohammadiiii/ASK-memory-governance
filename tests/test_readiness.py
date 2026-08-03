from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load() -> ModuleType:
    path = ROOT / "scripts/check_readiness.py"
    spec = importlib.util.spec_from_file_location("check_readiness", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_readiness_is_no_go() -> None:
    checker = _load()
    gates = yaml.safe_load((ROOT / "readiness/gates.yaml").read_text())
    report = checker.evaluate(gates)
    assert report["status"] == "NO_GO"
    assert report["tmlr_go"] is False
    assert report["jmlr_go"] is False
    assert any(item["authority"] == "human_legal" for item in report["blockers"])


def test_jmlr_requires_every_tmlr_gate() -> None:
    checker = _load()
    gates = yaml.safe_load((ROOT / "readiness/gates.yaml").read_text())
    for gate in gates["jmlr"].values():
        gate["passed"] = True
    assert checker.evaluate(gates)["status"] == "NO_GO"


def test_all_tmlr_only_gates_yield_tmlr_go_only() -> None:
    checker = _load()
    gates = yaml.safe_load((ROOT / "readiness/gates.yaml").read_text())
    for gate in gates["tmlr"].values():
        gate["passed"] = True
    assert checker.evaluate(gates)["status"] == "TMLR_GO_ONLY"


def test_human_gate_cannot_be_implicit() -> None:
    checker = _load()
    gates = yaml.safe_load((ROOT / "readiness/gates.yaml").read_text())
    gates["tmlr"]["licenses_and_redistribution_resolved"]["passed"] = None
    with pytest.raises(ValueError, match="human gate"):
        checker.evaluate(gates)
