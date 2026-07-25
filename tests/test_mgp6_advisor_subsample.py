"""M3-W12 advisor subsample and agreement scoring tests."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from ask.eval.mgp6_agreement import score_agreement, write_agreement_csv
from ask.eval.mgp6_schema import MGP6AdvisorAnnotation, load_mgp6_jsonl


def test_advisor_subsample_is_cold_and_stratified() -> None:
    path = Path("data/mgp6_advisor_subsample_v1.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    assert len(rows) == 12
    assert Counter(row["type"] for row in rows) == {
        "T1": 2,
        "T2": 2,
        "T3": 2,
        "T4": 2,
        "T5": 2,
        "T6": 2,
    }
    forbidden = {"gold_memory_state", "gold_action", "expected_answer", "rationale_notes"}
    for row in rows:
        assert forbidden.isdisjoint(row)
        assert {
            "scenario_id",
            "type",
            "base_dialogue_prefix",
            "initial_memory_state",
            "perturbation_event",
            "evaluation_query",
        } <= set(row)


def test_agreement_scorer_writes_detail_and_summary_rows(tmp_path: Path) -> None:
    scenarios = load_mgp6_jsonl("data/mgp6_v1_seed0.jsonl")[:2]
    advisor = {
        scenarios[0].scenario_id: MGP6AdvisorAnnotation(
            scenario_id=scenarios[0].scenario_id,
            gold_memory_state=scenarios[0].gold_memory_state,
            gold_action=scenarios[0].gold_action,
            expected_answer=scenarios[0].expected_answer,
        ),
        scenarios[1].scenario_id: MGP6AdvisorAnnotation(
            scenario_id=scenarios[1].scenario_id,
            gold_memory_state=scenarios[1].gold_memory_state,
            gold_action="ABSTAIN",
            expected_answer="different answer",
        ),
    }
    rows = score_agreement(scenarios, advisor)
    out = tmp_path / "agreement.csv"
    write_agreement_csv(rows, out)

    parsed = list(csv.DictReader(out.open(encoding="utf-8")))
    assert sum(1 for row in parsed if row["row_type"] == "detail") == 6
    overall = [
        row
        for row in parsed
        if row["row_type"] == "summary" and row["scope"] == "overall"
    ][0]
    assert overall["n"] == "6"
    assert float(overall["agreement"]) < 1.0


def test_agreement_cli_explains_missing_advisor_file(tmp_path: Path) -> None:
    missing = tmp_path / "advisor_annotations_v1.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/compute_mgp6_agreement.py",
            "--advisor",
            str(missing),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "advisor annotation file not found" in result.stderr
    assert "advisor_annotation_template_v1.jsonl" in result.stderr
