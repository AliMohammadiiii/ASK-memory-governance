from __future__ import annotations

import json

from ask.eval.m4w15 import (
    LONGMEMEVAL_COMPETENCIES,
    MGP6_TYPES,
    assemble_threshold_report,
    build_main_table,
    compute_rc_at_c,
    threshold_dir_name,
    threshold_values,
    validate_prerequisites,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_threshold_grid_is_21_points():
    values = threshold_values()

    assert len(values) == 21
    assert values[0] == 0.0
    assert values[-1] == 1.0
    assert threshold_dir_name(0.35) == "threshold_0.35"


def test_compute_rc_at_c_uses_only_committed_predictions():
    report = compute_rc_at_c(
        [
            {"predicted_action": "KEEP", "correct_action": True},
            {"predicted_action": "SUPERSEDE", "correct_action": False},
            {"predicted_action": "ABSTAIN", "correct_action": True},
            {"predicted_action": "KEEP", "correct_action": True},
        ],
        n_bootstrap=20,
    )

    assert report["n_total"] == 4
    assert report["n_committed"] == 3
    assert report["coverage"] == 0.75
    assert report["revision_correctness"] == 2 / 3


def test_assemble_threshold_report_reads_nested_controller_outputs(tmp_path):
    threshold_dir = tmp_path / "threshold_0.50"
    _write_json(
        threshold_dir / "mgp6" / "controller" / "mgp6_report.json",
        {
            "action_accuracy": 0.5,
            "action_accuracy_ci": [0.25, 0.75],
            "predictions": [
                {"predicted_action": "KEEP", "gold_action": "KEEP"},
                {"predicted_action": "ABSTAIN", "gold_action": "KEEP"},
            ],
        },
    )
    _write_json(
        threshold_dir / "longmemeval" / "controller" / "report.json",
        {
            "overall_accuracy": 0.6,
            "overall_ci_low": 0.4,
            "overall_ci_high": 0.8,
            "n_sessions": 10,
        },
    )

    report = assemble_threshold_report(threshold_dir, n_bootstrap=20)

    assert report["threshold"] == 0.5
    assert report["mgp6"]["coverage"] == 0.5
    assert report["mgp6"]["revision_correctness"] == 1.0
    assert report["longmemeval"]["overall_accuracy"] == 0.6
    assert (threshold_dir / "report.json").exists()


def test_build_main_table_writes_markdown_and_csv(tmp_path):
    m4w13 = tmp_path / "m4w13"
    m4w14 = tmp_path / "m4w14"
    _write_json(
        m4w13 / "b1" / "report.json",
        {
            "baseline_name": "no_memory",
            "n_sessions": 200,
            "rows": [
                {
                    "competency": competency,
                    "accuracy": 0.5,
                    "accuracy_ci_low": 0.4,
                    "accuracy_ci_high": 0.6,
                }
                for competency in LONGMEMEVAL_COMPETENCIES
            ],
        },
    )
    (m4w13 / "b1" / "predictions.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"extras": {"smrr_denominator": 2, "stale_retrieval_count": 1}}),
                json.dumps({"extras": {"smrr_denominator": 2, "stale_retrieval_count": 0}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        m4w14 / "b1" / "mgp6_report.json",
        {
            "n_scenarios": 60,
            "action_accuracy": 0.7,
            "action_accuracy_ci": [0.6, 0.8],
            "over_forgetting_rate": 0.1,
            "over_forgetting_ci": [0.0, 0.2],
            "under_forgetting_rate": 0.2,
            "under_forgetting_ci": [0.1, 0.3],
            "per_type": {
                scenario_type: {
                    "action_accuracy": 0.5,
                    "action_accuracy_ci": [0.3, 0.7],
                }
                for scenario_type in MGP6_TYPES
            },
        },
    )

    rows = build_main_table(
        m4w13_root=m4w13,
        m4w14_root=m4w14,
        markdown_path=tmp_path / "table.md",
        csv_path=tmp_path / "table.csv",
        n_bootstrap=20,
    )

    assert rows[0]["System"] == "B1"
    assert rows[0]["LME multi-session"] == "50.0% [40.0%, 60.0%]"
    assert rows[0]["SMRR"].startswith("25.0%")
    assert rows[0]["Revision correctness"] == "70.0% [60.0%, 80.0%]"
    assert rows[1]["System"] == "B2"
    assert rows[1]["LME multi-session"] == "MISSING"
    assert (tmp_path / "table.md").exists()
    assert (tmp_path / "table.csv").exists()


def test_validate_prerequisites_reports_missing_files(tmp_path):
    status = validate_prerequisites(tmp_path / "m4w13", tmp_path / "m4w14")

    assert not status.ok
    assert len(status.missing) == 10
    assert "runs" not in status.format()
