"""Session-shard merge rebuilds the aggregate report from the union of grades."""

from __future__ import annotations

import json
from pathlib import Path

from ask.eval.longmemeval import GradeResult
from ask.eval.merge import grade_from_dict, merge_run_shards


def _grade(sid: str, comp: str, correct: bool) -> GradeResult:
    return GradeResult(
        session_id=sid,
        competency=comp,
        correct=correct,
        judge_score=1.0 if correct else 0.0,
        judge_rationale="r",
        judge_model_id="judge-x",
        predicted="p",
        gold="g",
    )


def _write_shard(d: Path, grades: list[GradeResult]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "judgments.jsonl").write_text(
        "\n".join(json.dumps(g.to_dict()) for g in grades) + "\n", encoding="utf-8"
    )
    (d / "answers.jsonl").write_text(
        "\n".join(json.dumps({"session_id": g.session_id, "text": "p"}) for g in grades) + "\n",
        encoding="utf-8",
    )
    # only shard 0 carries a report.json (the launcher reads meta from shard 0)
    (d / "report.json").write_text(
        json.dumps({"baseline_name": "controller", "judge_model_id": "judge-x"}), encoding="utf-8"
    )


def test_grade_from_dict_roundtrip() -> None:
    g = _grade("s1", "multi-session", True)
    assert grade_from_dict(g.to_dict()) == g
    assert grade_from_dict({"session_id": "s1"}) is None  # missing fields


def test_grade_from_dict_accepts_historical_schema() -> None:
    """New audit fields have defaults so historical judgments stay mergeable."""
    row = _grade("old", "multi-session", True).to_dict()
    for key in (
        "requested_judge_model_id",
        "judge_was_called",
        "judge_cache_hit",
        "used_model_fallback",
        "used_scoring_fallback",
        "fallback_reason",
        "judge_attempt_index",
        "judge_prompt_hash",
        "judge_raw_response_hash",
        "judge_raw_output",
    ):
        row.pop(key)

    parsed = grade_from_dict(row)
    assert parsed is not None
    assert parsed.session_id == "old"
    assert parsed.used_model_fallback is False


def test_merge_unions_grades_and_rebuilds_report(tmp_path: Path) -> None:
    s0 = tmp_path / "_shard0"
    s1 = tmp_path / "_shard1"
    _write_shard(s0, [_grade("a", "multi-session", True), _grade("c", "knowledge-update", False)])
    _write_shard(s1, [_grade("b", "multi-session", False), _grade("d", "knowledge-update", True)])

    out = tmp_path / "merged"
    report = merge_run_shards(
        [s0, s1], out, baseline_name="controller", judge_model_id="judge-x", n_bootstrap=200
    )

    assert report.n_sessions == 4
    assert abs(report.overall_accuracy - 0.5) < 1e-9
    # merged artifacts written and complete
    judg = [json.loads(line) for line in (out / "judgments.jsonl").read_text().splitlines()]
    assert {j["session_id"] for j in judg} == {"a", "b", "c", "d"}
    assert (out / "report.json").exists() and (out / "results.md").exists()


def test_merge_dedups_overlapping_sessions(tmp_path: Path) -> None:
    s0 = tmp_path / "_shard0"
    s1 = tmp_path / "_shard1"
    _write_shard(s0, [_grade("a", "multi-session", True)])
    _write_shard(s1, [_grade("a", "multi-session", True), _grade("b", "multi-session", False)])
    out = tmp_path / "merged"
    report = merge_run_shards(
        [s0, s1], out, baseline_name="controller", judge_model_id="judge-x", n_bootstrap=100
    )
    assert report.n_sessions == 2  # 'a' counted once
