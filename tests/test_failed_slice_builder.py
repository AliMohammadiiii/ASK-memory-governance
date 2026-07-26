"""Failed-only LongMemEval slice builder contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_failed_slice_from_run import (
    build_failed_slice,  # type: ignore[import-not-found]  # noqa: E402
)

from ask.data.longmemeval import LongMemEvalSession, LongMemEvalTurn, iter_longmemeval_s


def _session(session_id: str) -> LongMemEvalSession:
    return LongMemEvalSession(
        session_id=session_id,
        turns=(LongMemEvalTurn(role="user", content=f"content {session_id}"),),
        question="Question?",
        gold_answer="Gold",
        competency="multi-session",
    )


def test_build_failed_slice_from_run_keeps_only_incorrect_sessions(tmp_path: Path) -> None:
    source = tmp_path / "slice.jsonl"
    sessions = [_session("s-ok"), _session("s-bad"), _session("s-missing")]
    source.write_text(
        "".join(json.dumps(session.to_dict()) + "\n" for session in sessions),
        encoding="utf-8",
    )
    run_dir = tmp_path / "run" / "controller"
    run_dir.mkdir(parents=True)
    (run_dir / "judgments.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"session_id": "s-ok", "correct": True}),
                json.dumps({"session_id": "s-bad", "correct": False}),
                json.dumps({"session_id": "not-in-source", "correct": False}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "failed.jsonl"
    ids_out = tmp_path / "failed.ids"

    summary = build_failed_slice(
        source_slice=source,
        run=run_dir,
        out=out,
        ids_out=ids_out,
    )

    written = list(iter_longmemeval_s(out))
    assert [session.session_id for session in written] == ["s-bad"]
    assert ids_out.read_text(encoding="utf-8").splitlines() == ["s-bad"]
    assert summary["n_failed"] == 2
    assert summary["n_written"] == 1
    assert summary["missing_session_ids"] == ["not-in-source"]


def _write_judgments(run_dir: Path, rows: list[dict[str, object]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "judgments.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )


def test_build_failed_slice_fails_loudly_on_disjoint_slice_and_run(tmp_path: Path) -> None:
    source = tmp_path / "slice.jsonl"
    source.write_text(
        "".join(json.dumps(_session(sid).to_dict()) + "\n" for sid in ("a", "b")),
        encoding="utf-8",
    )
    run_dir = tmp_path / "run" / "controller"
    # Judgments reference an entirely different session universe.
    _write_judgments(run_dir, [{"session_id": "x", "correct": False}])

    with pytest.raises(ValueError, match="share no session IDs"):
        build_failed_slice(source_slice=source, run=run_dir, out=tmp_path / "failed.jsonl")


def test_build_failed_slice_fails_loudly_when_no_judgments_found(tmp_path: Path) -> None:
    source = tmp_path / "slice.jsonl"
    source.write_text(json.dumps(_session("a").to_dict()) + "\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        build_failed_slice(
            source_slice=source,
            run=tmp_path / "no_such_run",
            out=tmp_path / "failed.jsonl",
        )


def test_build_failed_slice_fails_when_failures_absent_from_slice(tmp_path: Path) -> None:
    # Slice and run overlap on a correct session, but every FAILED id is missing
    # from the slice -> writing an empty failed slice would be a silent footgun.
    source = tmp_path / "slice.jsonl"
    source.write_text(
        "".join(json.dumps(_session(sid).to_dict()) + "\n" for sid in ("a", "b")),
        encoding="utf-8",
    )
    run_dir = tmp_path / "run" / "controller"
    _write_judgments(
        run_dir,
        [
            {"session_id": "a", "correct": True},
            {"session_id": "b", "correct": True},
            {"session_id": "c-not-in-slice", "correct": False},
        ],
    )
    with pytest.raises(ValueError, match="refusing to write an empty failed slice"):
        build_failed_slice(source_slice=source, run=run_dir, out=tmp_path / "failed.jsonl")
