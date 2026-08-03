from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _load() -> ModuleType:
    path = ROOT / "scripts/research/build_artifact_inventory.py"
    spec = importlib.util.spec_from_file_location("build_artifact_inventory", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_has_required_fields_and_path_neutral_root() -> None:
    inventory = _load().build_inventory()
    assert inventory["repository_root"] == "."
    required = {
        "logical_name",
        "relative_path",
        "type",
        "owner",
        "source",
        "generated_by",
        "configuration_id",
        "input_hashes",
        "output_sha256",
        "visibility",
        "model_facing",
        "consumption_status",
        "referenced_by_paper",
        "reproducibility",
        "known_problems",
        "exists",
    }
    assert inventory["artifacts"]
    assert all(required <= row.keys() for row in inventory["artifacts"])
    assert all(not str(row["relative_path"]).startswith("/") for row in inventory["artifacts"])


def test_hidden_gold_is_never_model_facing_or_public() -> None:
    rows = _load().build_inventory()["artifacts"]
    hidden_gold = [row for row in rows if "hidden_gold" in row["relative_path"]]
    assert hidden_gold
    assert all(row["visibility"] == "private" for row in hidden_gold)
    assert all(row["model_facing"] is False for row in hidden_gold)
