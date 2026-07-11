"""Failure analysis bucket tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analyze_longmemeval_failures import analyze_run  # type: ignore[import-not-found]  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_failure_analysis_classifies_actionable_buckets(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    answers = [
        {
            "session_id": "blank",
            "text": "",
            "baseline": "controller",
            "raw_prompt": "",
            "extras": {"n_retrieved": 1, "action_counts": {"Keep": 1}},
        },
        {
            "session_id": "extract",
            "text": "green",
            "baseline": "controller",
            "raw_prompt": "",
            "extras": {"n_retrieved": 0, "action_counts": {"Keep": 0, "Abstain": 0}},
        },
        {
            "session_id": "retrieve",
            "text": "green",
            "baseline": "controller",
            "raw_prompt": "----- RETRIEVED MEMORY -----\n[0.9] unrelated\n----- DIALOG -----",
            "extras": {"n_retrieved": 1, "action_counts": {"Keep": 2}},
        },
        {
            "session_id": "answer",
            "text": "green",
            "baseline": "controller",
            "raw_prompt": "----- RETRIEVED MEMORY -----\n[0.9] blue\n----- DIALOG -----",
            "extras": {"n_retrieved": 1, "action_counts": {"Keep": 2}},
        },
        {
            "session_id": "judge",
            "text": "blue",
            "baseline": "controller",
            "raw_prompt": "----- RETRIEVED MEMORY -----\n[0.9] blue\n----- DIALOG -----",
            "extras": {"n_retrieved": 1, "action_counts": {"Keep": 2}},
        },
    ]
    judgments = [
        {"session_id": row["session_id"], "correct": False, "gold": "blue"}
        for row in answers
    ]
    _write_jsonl(run_dir / "answers.jsonl", answers)
    _write_jsonl(run_dir / "judgments.jsonl", judgments)

    report = analyze_run(run_dir)

    assert report["counts"] == {
        "answer_generation_miss": 1,
        "blank_or_refusal": 1,
        "extraction_miss": 1,
        "judge_guard_issue": 1,
        "retrieval_miss": 1,
    }
