"""Live rejudge script behavior."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from rejudge import rejudge  # type: ignore[import-not-found]  # noqa: E402

from ask.baselines.base import BaselineAnswer
from ask.data.longmemeval import LongMemEvalSession, LongMemEvalTurn, write_slice_jsonl


def test_rejudge_writes_separate_report_from_persisted_answers(tmp_path: Path) -> None:
    slice_path = tmp_path / "slice.jsonl"
    write_slice_jsonl(
        [
            LongMemEvalSession(
                session_id="s1",
                turns=(LongMemEvalTurn(role="user", content="My code is blue."),),
                question="What is my code?",
                gold_answer="blue",
                competency="single-session-user",
            )
        ],
        slice_path,
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    answer = BaselineAnswer(
        session_id="s1",
        text="blue",
        prompt_tokens=1,
        completion_tokens=1,
        latency_ms=1.0,
        raw_prompt="prompt",
        baseline="controller",
    )
    (run_dir / "answers.jsonl").write_text(
        json.dumps(answer.to_dict(), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "ollama_judge"

    payload = rejudge(
        argparse.Namespace(
            run=run_dir,
            slice=slice_path,
            out=out_dir,
            judge_backend="fake",
            judge_model="fake/judge",
            ollama_host="http://127.0.0.1:11434",
            judge_num_ctx=2048,
            judge_timeout_s=1.0,
            judge_json_format=True,
            judge_think=False,
            hf_dtype="float16",
            hf_device_map="auto",
            hf_load_in_4bit=False,
            hf_trust_remote_code=False,
            hf_max_seq_len=4096,
            n_bootstrap=20,
            seed=0,
        )
    )

    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    answers = (out_dir / "answers.jsonl").read_text(encoding="utf-8").strip().splitlines()

    assert payload["n_sessions"] == 1
    assert report["overall_accuracy"] == 1.0
    assert report["source_run"] == str(run_dir)
    assert len(answers) == 1
    assert (out_dir / "judgments.jsonl").exists()
