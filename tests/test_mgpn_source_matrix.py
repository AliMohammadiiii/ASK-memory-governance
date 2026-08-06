from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "reports/MGP_NATURAL_SOURCE_MATRIX.csv"
EXPECTED_FIELDS = [
    "source",
    "snapshot_or_version",
    "interaction_origin",
    "continuity",
    "access",
    "license_or_terms",
    "privacy_risk",
    "decision",
    "intended_use",
    "primary_url",
]


def test_mgpn_source_matrix_is_complete_scoped_and_fail_closed() -> None:
    with MATRIX.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert reader.fieldnames == EXPECTED_FIELDS
    assert len(rows) == 13
    assert len({row["source"] for row in rows}) == len(rows)
    assert Counter(row["decision"] for row in rows) == {"AMBER": 9, "RED": 4}
    assert all(row["decision"] != "GO" for row in rows)
    assert all(row["primary_url"].startswith("https://") for row in rows)
    assert all(all(row[field].strip() for field in EXPECTED_FIELDS) for row in rows)
    serialized = MATRIX.read_text(encoding="utf-8")
    assert "/Users/" not in serialized
    assert ".private/" not in serialized
