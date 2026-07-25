"""HF M4-W13 runner command and resume-skip contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_m4w13_hf import (  # type: ignore[import-not-found]  # noqa: E402
    _apply_quality_preset,
    _command_for,
    _dataset_family,
    _preferred_python,
    _required_modules,
)
from run_m4w13_hf_a100_parallel import (  # type: ignore[import-not-found]  # noqa: E402
    _is_complete_run,
    _write_command_manifest,
)


def _args(**overrides):
    values = {
        "slice": Path("slice.jsonl"),
        "seed": 0,
        "n_bootstrap": 20,
        "hf_model": "Qwen/Qwen2.5-3B-Instruct",
        "hf_dtype": "float16",
        "hf_device_map": "auto",
        "hf_max_seq_len": 4096,
        "hf_load_in_4bit": False,
        "hf_trust_remote_code": False,
        "resume": True,
        "limit": 12,
        "embedder_backend": "sentence_transformer",
        "embedder_device": "cuda",
        "embedder_ollama_model": "llama3.2:3b",
        "embedder_timeout_s": 1800.0,
        "embedder_batch_size": 16,
        "fake_embedder": False,
        "ollama_host": "http://127.0.0.1:11434",
        "judge_backend": "same_as_answerer",
        "judge_model": None,
        "judge_timeout_s": 1800.0,
        "retrieval_k": 8,
        "recency_memory_top_k": 16,
        "recency_raw_turn_fallback": True,
        "recency_progress": True,
        "controller_memory_top_k": 16,
        "controller_raw_turn_fallback": True,
        "controller_retrieval_neighbor_window": 2,
        "controller_progress": True,
        "extractor_model": None,
        "classifier_model": None,
        "extraction_max_new_tokens": 128,
        "relation_max_new_tokens": 64,
        "quality_preset": "none",
        "controller_include_assistant_context": False,
        "controller_include_raw_user_context": False,
        "controller_retrieval_query_augmentation": False,
        "controller_deterministic_numeric_supersede": False,
        "answer_retry_on_unknown": False,
        "controller_prior_top_k": 1,
        "controller_prior_similarity_threshold": 0.0,
        "controller_temporal_scaffold": False,
        "controller_computation_answerer": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_retrieval_k_is_forwarded_to_memory_systems() -> None:
    args = _args(retrieval_k=8)

    controller = _command_for(
        baseline_alias="controller",
        baseline="controller",
        out_dir=Path("runs/x"),
        args=args,
    )
    b4 = _command_for(
        baseline_alias="b4",
        baseline="naive_overwrite",
        out_dir=Path("runs/x"),
        args=args,
    )
    b1 = _command_for(
        baseline_alias="b1",
        baseline="no_memory",
        out_dir=Path("runs/x"),
        args=args,
    )

    assert controller[controller.index("--k") + 1] == "8"
    assert b4[b4.index("--k") + 1] == "8"
    assert "--k" not in b1


def test_command_prefers_configured_python(monkeypatch) -> None:
    monkeypatch.setenv("ASK_PYTHON", "/tmp/ask-python")

    cmd = _command_for(
        baseline_alias="controller",
        baseline="controller",
        out_dir=Path("runs/x"),
        args=_args(),
    )

    assert _preferred_python() == "/tmp/ask-python"
    assert cmd[0] == "/tmp/ask-python"


def test_quality_preset_is_forwarded_to_run_baseline() -> None:
    cmd = _command_for(
        baseline_alias="controller",
        baseline="controller",
        out_dir=Path("runs/x"),
        args=_args(
            quality_preset="max-a10g",
            retrieval_k=12,
            controller_memory_top_k=64,
            controller_retrieval_neighbor_window=2,
            answer_retry_on_unknown=True,
            controller_prior_top_k=3,
            controller_prior_similarity_threshold=0.45,
            controller_include_assistant_context=True,
            controller_include_raw_user_context=True,
            controller_retrieval_query_augmentation=True,
            controller_deterministic_numeric_supersede=True,
            hf_model="Qwen/Qwen2.5-7B-Instruct",
        ),
    )

    assert cmd[cmd.index("--quality-preset") + 1] == "max-a10g"
    assert cmd[cmd.index("--k") + 1] == "12"
    assert cmd[cmd.index("--controller-memory-top-k") + 1] == "64"
    assert cmd[cmd.index("--controller-prior-top-k") + 1] == "3"
    assert cmd[cmd.index("--controller-prior-similarity-threshold") + 1] == "0.45"
    assert "--answer-retry-on-unknown" in cmd
    assert "--controller-include-assistant-context" in cmd
    assert "--controller-include-raw-user-context" in cmd
    assert "--controller-retrieval-query-augmentation" in cmd
    assert "--controller-deterministic-numeric-supersede" in cmd


def test_a100_quality_preset_keeps_parallel_worker_setting() -> None:
    args = _args(quality_preset="max-a100-40gb", max_workers=2, hf_max_seq_len=4096)

    _apply_quality_preset(args)

    assert args.hf_model == "Qwen/Qwen2.5-7B-Instruct"
    assert args.hf_max_seq_len == 8192
    assert args.max_workers == 2
    assert args.retrieval_k == 12
    assert args.controller_include_raw_user_context is True
    assert args.controller_retrieval_query_augmentation is True
    assert args.controller_deterministic_numeric_supersede is True
    assert args.controller_prior_similarity_threshold == 0.45


def test_hf_manifest_dataset_family_infers_longmemeval_m() -> None:
    assert _dataset_family(Path("data/slices/longmemeval_m_full.jsonl")) == "m"
    assert _dataset_family(Path("data/slices/longmemeval_s_50_seed0.jsonl")) == "s"


def test_preflight_requires_faiss_for_memory_systems() -> None:
    args = _args(embedder_backend="sentence_transformer", fake_embedder=False)

    memory_modules = _required_modules(args, [("controller", "controller")])
    no_memory_modules = _required_modules(args, [("b1", "no_memory")])

    assert "faiss" in memory_modules
    assert "sentence_transformers" in memory_modules
    assert "faiss" not in no_memory_modules


def _write_jsonl(path: Path, n: int) -> None:
    path.write_text("".join(json.dumps({"i": i}) + "\n" for i in range(n)), encoding="utf-8")


def test_complete_run_requires_report_rows_and_matching_command(tmp_path: Path) -> None:
    run_dir = tmp_path / "controller"
    run_dir.mkdir()
    cmd = [sys.executable, "scripts/run_baseline.py", "--baseline", "controller"]
    expected_rows = 3
    (run_dir / "report.json").write_text(
        json.dumps({"n_sessions": expected_rows}),
        encoding="utf-8",
    )
    _write_jsonl(run_dir / "answers.jsonl", expected_rows)
    _write_jsonl(run_dir / "predictions.jsonl", expected_rows)
    _write_jsonl(run_dir / "judgments.jsonl", expected_rows)
    _write_jsonl(run_dir / "action_log.jsonl", 1)
    _write_command_manifest(
        run_dir=run_dir,
        alias="controller",
        baseline="controller",
        cmd=cmd,
        expected_rows=expected_rows,
    )

    complete, reason = _is_complete_run(run_dir=run_dir, cmd=cmd, expected_rows=expected_rows)
    assert complete, reason

    complete, reason = _is_complete_run(
        run_dir=run_dir,
        cmd=cmd + ["--controller-memory-top-k", "24"],
        expected_rows=expected_rows,
    )
    assert not complete
    assert "fingerprint" in reason

    _write_jsonl(run_dir / "answers.jsonl", expected_rows - 1)
    complete, reason = _is_complete_run(run_dir=run_dir, cmd=cmd, expected_rows=expected_rows)
    assert not complete
    assert "answers.jsonl" in reason


def test_complete_run_requires_predictions_and_controller_action_log(tmp_path: Path) -> None:
    run_dir = tmp_path / "controller"
    run_dir.mkdir()
    cmd = [sys.executable, "scripts/run_baseline.py", "--baseline", "controller"]
    expected_rows = 2
    (run_dir / "report.json").write_text(
        json.dumps({"baseline_name": "controller", "n_sessions": expected_rows, "overall_accuracy": 0.5}),
        encoding="utf-8",
    )
    _write_jsonl(run_dir / "answers.jsonl", expected_rows)
    _write_jsonl(run_dir / "judgments.jsonl", expected_rows)
    _write_command_manifest(
        run_dir=run_dir,
        alias="controller",
        baseline="controller",
        cmd=cmd,
        expected_rows=expected_rows,
    )

    complete, reason = _is_complete_run(run_dir=run_dir, cmd=cmd, expected_rows=expected_rows)
    assert not complete
    assert "predictions.jsonl" in reason

    _write_jsonl(run_dir / "predictions.jsonl", expected_rows)
    complete, reason = _is_complete_run(run_dir=run_dir, cmd=cmd, expected_rows=expected_rows)
    assert not complete
    assert "action_log.jsonl" in reason
