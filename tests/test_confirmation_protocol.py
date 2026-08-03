from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def _load_builder():
    path = ROOT / "scripts/confirmation/build_blind_packet.py"
    spec = importlib.util.spec_from_file_location("build_blind_packet", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_blind_packet_is_deterministic_and_removes_source_id() -> None:
    builder = _load_builder()
    rows = [
        {"id": "source-a", "predecessor": None, "candidate": {"text": "a"}, "context": {}},
        {"id": "source-b", "predecessor": {}, "candidate": {"text": "b"}, "context": {}},
    ]
    packet_a, mapping_a = builder.build_packet(rows, 7)
    packet_b, mapping_b = builder.build_packet(rows, 7)
    assert packet_a == packet_b
    assert mapping_a == mapping_b
    assert all("id" not in row and "blind_id" in row for row in packet_a)


def test_blind_packet_rejects_gold_anywhere() -> None:
    builder = _load_builder()
    with pytest.raises(ValueError, match="prohibited"):
        builder.build_packet(
            [{"predecessor": None, "candidate": {"gold_action": "KEEP"}, "context": {}}],
            1,
        )


@pytest.mark.parametrize(
    "name",
    ["item", "annotation", "adjudication", "natural_challenge", "trajectory"],
)
def test_confirmation_schema_is_valid(name: str) -> None:
    schema = json.loads((ROOT / f"confirmation/schemas/{name}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
