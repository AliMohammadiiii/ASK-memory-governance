"""A10G sweep driver contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_m4w13_a10g_sweep import (  # type: ignore[import-not-found]  # noqa: E402
    PILOT_CONFIGS,
    build_stage_runs,
    config_slug,
    parse_config_slug,
    select_top_configs,
)


def _args(tmp_path: Path, **overrides):
    values = {
        "slice": Path("/content/longmemeval/longmemeval_s_cleaned.json"),
        "out": tmp_path,
        "stage": "pilot",
        "pilot_limit": 12,
        "confirm_limit": 50,
        "resume": True,
        "status_s": 30.0,
        "hf_model": "Qwen/Qwen2.5-3B-Instruct",
        "hf_dtype": "float16",
        "quality_preset": "none",
        "judge_backend": "same_as_answerer",
        "judge_model": None,
        "extractor_model": None,
        "classifier_model": None,
        "hf_load_in_4bit": False,
        "hf_trust_remote_code": False,
        "embedder_backend": "sentence_transformer",
        "embedder_device": "cuda",
        "controller_include_assistant_context": False,
        "answer_retry_on_unknown": False,
        "controller_prior_top_k": 1,
        "no_prefetch": False,
        "clean_incomplete": False,
        "no_zip": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_pilot_configs_are_exact_fixed_grid() -> None:
    assert [
        (c.top_k, c.retrieval_k, c.neighbor_window, c.extraction_tokens, c.relation_tokens)
        for c in PILOT_CONFIGS
    ] == [
        (8, 5, 2, 128, 64),
        (16, 5, 2, 128, 64),
        (16, 8, 2, 128, 64),
        (16, 8, 0, 128, 64),
        (16, 8, 2, 192, 96),
        (24, 8, 2, 192, 96),
    ]


def test_pilot_dry_run_builds_six_controller_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASK_PYTHON", "/tmp/ask-python")

    runs = build_stage_runs(_args(tmp_path))

    assert [config_slug(run.config) for run in runs] == [
        "tk08-rk05-w02-t128-64",
        "tk16-rk05-w02-t128-64",
        "tk16-rk08-w02-t128-64",
        "tk16-rk08-w00-t128-64",
        "tk16-rk08-w02-t192-96",
        "tk24-rk08-w02-t192-96",
    ]
    assert len(runs) == 6
    for run in runs:
        cmd = run.command
        assert cmd[0] == "/tmp/ask-python"
        assert cmd[cmd.index("--systems") + 1] == "controller"
        assert cmd[cmd.index("--limit") + 1] == "12"
        assert cmd[cmd.index("--max-workers") + 1] == "1"
        assert "--no-require-a100" in cmd
        assert "--no-zip" in cmd


def test_max_a10g_quality_preset_builds_single_locked_command(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASK_PYTHON", "/tmp/ask-python")

    runs = build_stage_runs(
        _args(
            tmp_path,
            quality_preset="max-a10g",
            hf_model="Qwen/Qwen2.5-7B-Instruct",
            controller_include_assistant_context=True,
            answer_retry_on_unknown=True,
            controller_prior_top_k=3,
        )
    )

    assert [config_slug(run.config) for run in runs] == ["tk64-rk12-w02-t256-128"]
    cmd = runs[0].command
    assert cmd[cmd.index("--quality-preset") + 1] == "max-a10g"
    assert cmd[cmd.index("--hf-model") + 1] == "Qwen/Qwen2.5-7B-Instruct"
    assert cmd[cmd.index("--hf-dtype") + 1] == "float16"
    assert cmd[cmd.index("--max-workers") + 1] == "1"
    assert "--answer-retry-on-unknown" in cmd
    assert cmd[cmd.index("--controller-prior-top-k") + 1] == "3"
    assert "--controller-include-assistant-context" in cmd


def _write_valid_controller_run(run_dir: Path, *, n: int, correct: int, wall_s: float) -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "baseline_name": "controller",
                "judge_model_id": "judge",
                "n_sessions": n,
                "overall_accuracy": correct / n,
                "overall_ci_low": 0.0,
                "overall_ci_high": 1.0,
                "wall_clock_seconds": wall_s,
            }
        ),
        encoding="utf-8",
    )
    rows = []
    for i in range(n):
        sid = f"s{i}"
        rows.append((sid, i < correct))
    for name in ("answers.jsonl", "predictions.jsonl"):
        (run_dir / name).write_text(
            "".join(json.dumps({"session_id": sid, "text": str(ok)}) + "\n" for sid, ok in rows),
            encoding="utf-8",
        )
    (run_dir / "judgments.jsonl").write_text(
        "".join(json.dumps({"session_id": sid, "correct": ok}) + "\n" for sid, ok in rows),
        encoding="utf-8",
    )
    (run_dir / "action_log.jsonl").write_text('{"action":"Keep"}\n', encoding="utf-8")


def test_config_slug_round_trip() -> None:
    for config in PILOT_CONFIGS:
        assert parse_config_slug(config_slug(config)) == config


def test_confirm_selection_requires_valid_complete_pilot_outputs(tmp_path: Path) -> None:
    fast = PILOT_CONFIGS[0]
    slow = PILOT_CONFIGS[1]
    invalid = PILOT_CONFIGS[2]
    _write_valid_controller_run(
        tmp_path / "pilot" / config_slug(fast) / "controller",
        n=12,
        correct=7,
        wall_s=10.0,
    )
    _write_valid_controller_run(
        tmp_path / "pilot" / config_slug(slow) / "controller",
        n=12,
        correct=7,
        wall_s=20.0,
    )
    invalid_dir = tmp_path / "pilot" / config_slug(invalid) / "controller"
    invalid_dir.mkdir(parents=True)
    (invalid_dir / "report.json").write_text(
        json.dumps({"baseline_name": "controller", "n_sessions": 12, "overall_accuracy": 1.0}),
        encoding="utf-8",
    )
    for name in ("answers.jsonl", "predictions.jsonl", "judgments.jsonl", "action_log.jsonl"):
        (invalid_dir / name).write_text("", encoding="utf-8")

    selected = select_top_configs(tmp_path, "pilot", 2, expected_rows=12)

    assert selected == [fast, slow]
