"""MGP-6 action-level metric tests."""

from __future__ import annotations

import subprocess
import sys

from ask.eval.mgp6 import build_prediction, compute_report
from ask.eval.mgp6_schema import load_mgp6_jsonl, validate_mgp6_coverage


def _scenario(scenario_id: str):
    rows = {row.scenario_id: row for row in load_mgp6_jsonl("data/mgp6_v1_seed0.jsonl")}
    return rows[scenario_id]


def _state_from_gold(scenario_id: str) -> list[dict]:
    return [item.model_dump() for item in _scenario(scenario_id).gold_memory_state]


def test_mgp6_fixture_has_expected_coverage() -> None:
    rows = load_mgp6_jsonl("data/mgp6_v1_seed0.jsonl")
    validate_mgp6_coverage(rows)
    assert len(rows) == 60


def test_build_prediction_flags_under_and_over_forgetting() -> None:
    supersede = _scenario("MGP6-T1-01")
    under = build_prediction(
        supersede,
        predicted_action="KEEP",
        memory_state=[supersede.initial_memory_state[0].model_dump()],
        action_sequence=["KEEP"],
    )
    assert under.under_forgetting is True
    assert under.over_forgetting is False
    assert under.state_correct is False

    abstain = _scenario("MGP6-T4-01")
    wrong_state = [abstain.initial_memory_state[0].model_dump()]
    wrong_state[0]["status"] = "superseded"
    over = build_prediction(
        abstain,
        predicted_action="SUPERSEDE",
        memory_state=wrong_state,
        action_sequence=["SUPERSEDE"],
    )
    assert over.over_forgetting is True
    assert over.under_forgetting is False


def test_compute_report_confusion_and_per_action_metrics() -> None:
    rows = [
        build_prediction(
            _scenario("MGP6-T1-01"),
            predicted_action="SUPERSEDE",
            memory_state=_state_from_gold("MGP6-T1-01"),
            action_sequence=["SUPERSEDE"],
            candidate_type="stable_pref",
            theta_sup=0.9,
        ),
        build_prediction(
            _scenario("MGP6-T4-01"),
            predicted_action="KEEP",
            memory_state=[_scenario("MGP6-T4-01").initial_memory_state[0].model_dump()],
            action_sequence=["KEEP"],
            candidate_type="stable_pref",
            theta_sup=0.9,
        ),
        build_prediction(
            _scenario("MGP6-T5-01"),
            predicted_action="KEEP",
            memory_state=_state_from_gold("MGP6-T5-01"),
            action_sequence=["KEEP"],
            candidate_type="transient_pref",
            theta_sup=0.55,
        ),
    ]

    report = compute_report(rows, baseline="test", n_bootstrap=20, seed=0)

    assert report["n_scenarios"] == 3
    assert report["action_accuracy"] == 2 / 3
    assert report["confusion_matrix"]["ABSTAIN"]["KEEP"] == 1
    assert report["per_action"]["KEEP"]["precision"] == 0.5
    assert report["per_action"]["SUPERSEDE"]["recall"] == 1.0
    assert report["threshold_ordering"]["confirmed"] is False


def test_run_mgp6_dry_run_does_not_require_ollama() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_mgp6.py",
            "--systems",
            "no_memory",
            "--limit",
            "1",
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "would run b1/no_memory" in result.stdout
