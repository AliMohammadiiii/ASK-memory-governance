"""M4-W13 artifact validation and audit contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analyze_longmemeval_failures import (  # type: ignore[import-not-found]  # noqa: E402
    CATEGORY_RETRIEVAL_MISS,
    CATEGORY_SPECIFICITY_MISS,
    classify_failure,
)
from m4w13_validation import (  # type: ignore[import-not-found]  # noqa: E402
    correctness_matrix,
    validate_run_dir,
)
from summarize_m4w13 import main as summarize_main  # type: ignore[import-not-found]  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_run(run_dir: Path, correctness: list[bool]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    n = len(correctness)
    accuracy = sum(1 for value in correctness if value) / n
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "baseline_name": "controller",
                "judge_model_id": "judge",
                "n_sessions": n,
                "overall_accuracy": accuracy,
                "overall_ci_low": 0.0,
                "overall_ci_high": 1.0,
                "wall_clock_seconds": 1.0,
            }
        ),
        encoding="utf-8",
    )
    answer_rows = [
        {"session_id": f"s{i}", "text": "answer", "extras": {"n_retrieved": 1}} for i in range(n)
    ]
    judgment_rows = [
        {"session_id": f"s{i}", "correct": value} for i, value in enumerate(correctness)
    ]
    _write_jsonl(run_dir / "answers.jsonl", answer_rows)
    _write_jsonl(run_dir / "predictions.jsonl", answer_rows)
    _write_jsonl(run_dir / "judgments.jsonl", judgment_rows)
    _write_jsonl(run_dir / "action_log.jsonl", [{"action": "Keep"}])


def test_empty_output_detection_identifies_exact_file(tmp_path: Path) -> None:
    run_dir = tmp_path / "controller"
    run_dir.mkdir()
    (run_dir / "report.json").write_text(
        json.dumps({"baseline_name": "controller", "n_sessions": 2, "overall_accuracy": 0.0}),
        encoding="utf-8",
    )
    for name in ("answers.jsonl", "predictions.jsonl", "judgments.jsonl", "action_log.jsonl"):
        (run_dir / name).write_text("", encoding="utf-8")

    validation = validate_run_dir(
        run_dir,
        expected_rows=2,
        stage="confirm",
        config_slug="tk08-rk05-w02-t128-64",
        system="controller",
    )

    assert not validation.ok
    assert any("answers.jsonl" in error and "empty" in error for error in validation.errors)
    assert any("stage=confirm" in error for error in validation.errors)
    assert any("config=tk08-rk05-w02-t128-64" in error for error in validation.errors)


def test_missing_required_file_fails_validation(tmp_path: Path) -> None:
    run_dir = tmp_path / "controller"
    _write_run(run_dir, [True, False])
    (run_dir / "predictions.jsonl").unlink()

    validation = validate_run_dir(run_dir, expected_rows=2, system="controller")

    assert not validation.ok
    assert any("predictions.jsonl" in error and "missing" in error for error in validation.errors)


def test_correctness_matrix_groups_all_right_wrong_and_disagreements(tmp_path: Path) -> None:
    run_a = tmp_path / "a" / "controller"
    run_b = tmp_path / "b" / "controller"
    _write_run(run_a, [True, False, True])
    _write_run(run_b, [True, False, False])

    matrix = correctness_matrix({"a": run_a, "b": run_b})

    assert matrix["all_right"] == ["s0"]
    assert matrix["all_wrong"] == ["s1"]
    assert matrix["disagreements"] == ["s2"]
    assert matrix["identical_correctness"] is False


def test_summarize_require_complete_fails_on_required_file_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps({"systems": ["controller"], "limit": 2}),
        encoding="utf-8",
    )
    run_dir = root / "controller"
    _write_run(run_dir, [True, False])
    (run_dir / "predictions.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["summarize_m4w13.py", str(root), "--require-complete"])

    with pytest.raises(SystemExit) as exc:
        summarize_main()

    assert "predictions.jsonl" in str(exc.value)


def test_failure_classifier_distinguishes_specificity_from_missing_evidence() -> None:
    specificity = classify_failure(
        {
            "text": "45 minutes",
            "baseline": "controller",
            "raw_prompt": "----- RETRIEVED MEMORY -----\n45 minutes each way\n----- DIALOG -----",
            "extras": {"n_retrieved": 1, "action_counts": {"Keep": 1}},
        },
        {"correct": False, "gold": "45 minutes each way"},
    )
    missing_evidence = classify_failure(
        {
            "text": "Unknown",
            "baseline": "controller",
            "raw_prompt": "----- RETRIEVED MEMORY -----\nno job title here\n----- DIALOG -----",
            "extras": {"n_retrieved": 1, "action_counts": {"Keep": 1}},
        },
        {"correct": False, "gold": "Marketing specialist at a small startup"},
    )

    assert specificity == CATEGORY_SPECIFICITY_MISS
    assert missing_evidence == CATEGORY_RETRIEVAL_MISS
