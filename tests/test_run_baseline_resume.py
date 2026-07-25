"""Resumable run_baseline CLI behavior."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ask.data.longmemeval import LongMemEvalSession, LongMemEvalTurn, write_slice_jsonl


def _slice(path: Path, n: int = 3) -> Path:
    sessions = [
        LongMemEvalSession(
            session_id=f"s{i}",
            turns=(
                LongMemEvalTurn(role="user", content=f"My code is {i}."),
                LongMemEvalTurn(role="assistant", content="Noted."),
            ),
            question="What is my code?",
            gold_answer=str(i),
            competency="single-session-user",
            supporting_session_ids=(f"s{i}",),
        )
        for i in range(n)
    ]
    write_slice_jsonl(sessions, path)
    return path


def _run(slice_path: Path, out: Path, limit: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/run_baseline.py",
            "--baseline",
            "no_memory",
            "--slice",
            str(slice_path),
            "--out",
            str(out),
            "--limit",
            str(limit),
            "--fake",
            "--fake-judge",
            "--n-bootstrap",
            "20",
            "--resume",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        text=True,
        capture_output=True,
    )


def test_run_baseline_resume_appends_remaining_sessions(tmp_path: Path) -> None:
    slice_path = _slice(tmp_path / "slice.jsonl")
    out = tmp_path / "run"

    _run(slice_path, out, 2)
    (out / "report.json").unlink()
    (out / "results.md").unlink()

    result = _run(slice_path, out, 3)

    answers = [
        json.loads(line)
        for line in (out / "answers.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    judgments = [
        json.loads(line)
        for line in (out / "judgments.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))

    assert "resume: completed=2/3 remaining=1" in result.stdout
    assert [row["session_id"] for row in answers] == ["s0", "s1", "s2"]
    assert [row["session_id"] for row in judgments] == ["s0", "s1", "s2"]
    assert report["n_sessions"] == 3


def test_run_baseline_sample_from_to_is_one_based_inclusive(tmp_path: Path) -> None:
    slice_path = _slice(tmp_path / "slice.jsonl", n=5)
    out = tmp_path / "range-run"

    subprocess.run(
        [
            sys.executable,
            "scripts/run_baseline.py",
            "--baseline",
            "no_memory",
            "--slice",
            str(slice_path),
            "--out",
            str(out),
            "--sample-from",
            "2",
            "--sample-to",
            "4",
            "--fake",
            "--fake-judge",
            "--n-bootstrap",
            "20",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        text=True,
        capture_output=True,
    )

    answers = [
        json.loads(line)
        for line in (out / "answers.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))

    assert [row["session_id"] for row in answers] == ["s1", "s2", "s3"]
    assert report["n_sessions"] == 3
    assert report["sample_range"] == {
        "sample_from": 2,
        "sample_to": 4,
        "sample_start": None,
        "sample_end": None,
    }
