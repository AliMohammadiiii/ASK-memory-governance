from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

from mgp_natural.blinding.packet import (
    PROHIBITED_FILENAME,
    blind_items,
    build_packet,
    scan_prohibited_keys,
    validate_secret,
    verify_packet,
)
from mgp_natural.errors import ValidationError
from mgp_natural.util.io import write_jsonl


@pytest.mark.parametrize(
    "value,expected",
    [
        ({"label": "KEEP"}, "$.label"),
        ({"nested": {"gold_action": "KEEP"}}, "$.nested.gold_action"),
        ({"relation_to_prior": "same"}, "$.relation_to_prior"),
        ({"source_identifier": "x"}, "$.source_identifier"),
        ({"locator": {"source_locator": "x"}}, "$.locator.source_locator"),
        ({"constructor_rationale": "x"}, "$.constructor_rationale"),
        ({"private_mapping": "x"}, "$.private_mapping"),
    ],
)
def test_nested_prohibited_key_scan(value: dict, expected: str) -> None:
    violations = scan_prohibited_keys(value)
    assert expected in violations


def test_label_filenames_are_rejected() -> None:
    assert PROHIBITED_FILENAME.search("items_KEEP.jsonl")
    assert PROHIBITED_FILENAME.search("blind_mapping.jsonl")


def test_short_secret_rejected() -> None:
    with pytest.raises(ValidationError, match="128 bits"):
        validate_secret(b"too short")


def test_blinding_is_deterministic_for_secret_and_hides_private_fields(construction_item: dict) -> None:
    secret = bytes(range(32))
    first, mapping_a = blind_items([construction_item], secret)
    second, mapping_b = blind_items([construction_item], secret)
    assert first == second
    assert mapping_a == mapping_b
    public = first[0]
    assert not scan_prohibited_keys(public)
    assert "source_locator_private" not in json.dumps(public)
    assert "constructor_provisional_action" not in json.dumps(public)


def test_packet_allowlist_and_permissions(tmp_path: Path, construction_item: dict) -> None:
    source = tmp_path / "items.jsonl"
    write_jsonl(source, [construction_item])
    private = tmp_path / "private"
    packet = tmp_path / "packet.zip"
    commitment = tmp_path / "commitment.json"
    build_packet(source, private, packet, commitment, secret=bytes(range(32)))
    report = verify_packet(packet)
    assert report["status"] == "VERIFIED"
    assert set(zipfile.ZipFile(packet).namelist()) == {
        "items.jsonl", "annotation_form.jsonl", "README.txt", "SHA256SUMS"
    }
    assert os.stat(private).st_mode & 0o777 == 0o700
    assert os.stat(private / "blinding_secret.bin").st_mode & 0o777 == 0o600
    with zipfile.ZipFile(packet) as bundle:
        names = "\n".join(bundle.namelist())
        body = b"\n".join(bundle.read(name) for name in bundle.namelist())
    assert b"private-user" not in body
    assert "mapping" not in names.casefold()
    assert "secret" not in names.casefold()


def test_tampered_packet_checksum_fails(tmp_path: Path, construction_item: dict) -> None:
    source = tmp_path / "items.jsonl"
    write_jsonl(source, [construction_item])
    packet = tmp_path / "packet.zip"
    build_packet(source, tmp_path / "private", packet, tmp_path / "commitment.json", secret=bytes(range(32)))
    with zipfile.ZipFile(packet, "a") as bundle:
        bundle.writestr("items.jsonl", "{}\n")
    with pytest.raises(ValidationError):
        verify_packet(packet)

