from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import scripts.run_vllm_cascade as cascade
from scripts.run_vllm_cascade import (
    _base_cmd,
    _command_for_log,
    _run_logged_with_retries,
    _write_command_header,
)


def test_command_for_log_redacts_direct_openai_key() -> None:
    cmd = [
        "python",
        "scripts/run_baseline.py",
        "--openai-api-key",
        "sk-test-secret",
    ]

    redacted = _command_for_log(cmd)

    assert "sk-test-secret" not in redacted
    assert redacted[-1] == "<redacted>"


def test_command_for_log_redacts_secret_value_passed_as_env_name() -> None:
    cmd = [
        "python",
        "scripts/run_baseline.py",
        "--openai-api-key-env",
        "sk-test-secret",
    ]

    redacted = _command_for_log(cmd)

    assert "sk-test-secret" not in redacted
    assert redacted[-1] == "<redacted>"


def test_command_for_log_keeps_normal_env_names() -> None:
    cmd = [
        "python",
        "scripts/run_baseline.py",
        "--openai-api-key-env",
        "OPENROUTER_API_KEY",
    ]

    assert _command_for_log(cmd) == cmd


def test_command_headers_append_across_relaunches(tmp_path: Path) -> None:
    log_path = tmp_path / "shard.log"

    _write_command_header(log_path, ["python", "first.py"])
    _write_command_header(log_path, ["python", "second.py"])

    text = log_path.read_text(encoding="utf-8")
    assert "first.py" in text
    assert "second.py" in text


def test_shard_runner_retries_called_process_errors(monkeypatch, tmp_path: Path) -> None:
    attempts = 0

    def fake_run(cmd, log_path):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(cascade, "_run_logged", fake_run)
    monkeypatch.setattr(cascade.time, "sleep", lambda _seconds: None)

    _run_logged_with_retries(
        ["python", "worker.py"],
        tmp_path / "shard.log",
        retries=1,
        backoff_s=0,
    )

    assert attempts == 2


def test_base_cmd_forwards_judge_body_and_fallback_models() -> None:
    judge_body = {
        "provider": {
            "order": ["wandb", "venice"],
            "only": ["wandb", "venice"],
            "allow_fallbacks": True,
        },
        "reasoning": {"enabled": False},
    }
    args = SimpleNamespace(
        slice=Path("range.jsonl"),
        seed=0,
        n_bootstrap=10,
        big_base_url="https://openrouter.ai/api/v1",
        big_model="qwen/qwen3.5-9b",
        openai_api_key_env="OPENROUTER_API_KEY",
        openai_timeout_s=300,
        enable_thinking=False,
        openai_chat_template_kwargs_json=None,
        openai_extra_body_json=None,
        openmodel_primary=False,
        openai_api_key=None,
        sample_from=None,
        sample_to=None,
        sample_start=None,
        sample_end=None,
        embed_base_url=None,
        embedder_device="cpu",
        embedder_st_model=None,
        embedder_task=None,
        retrieval_k=12,
        judge="big",
        judge_model="google/gemma-4-31b-it",
        judge_openai_chat_template_kwargs_json=None,
        judge_openai_extra_body_json=json.dumps(judge_body, separators=(",", ":")),
        judge_openai_fallback_model=["qwen/qwen3.5-9b"],
        fast_model="qwen/qwen3.5-9b",
        fast_base_url="https://openrouter.ai/api/v1",
        extraction_max_new_tokens=256,
        relation_max_new_tokens=128,
        openai_max_model_len=16384,
        controller_memory_top_k=64,
        escalation=False,
        extraction_concurrency=8,
        shared_extraction_cache=None,
        answer_context_max_tokens=12000,
        v7_fixes=True,
        v8_fixes=True,
        answer_escalation_model="qwen/qwen3.5-35b-a3b",
        answer_escalation_base_url="https://openrouter.ai/api/v1",
        history_retrieval_k=4,
        answer_context_session_cap=4,
    )

    cmd = _base_cmd("controller", "controller", Path("out"), args)

    body_flag = cmd.index("--judge-openai-extra-body-json")
    assert json.loads(cmd[body_flag + 1]) == judge_body
    fallback_flag = cmd.index("--judge-openai-fallback-model")
    assert cmd[fallback_flag + 1] == "qwen/qwen3.5-9b"
    escalation_flag = cmd.index("--answer-escalation-openai-model")
    assert cmd[escalation_flag + 1] == "qwen/qwen3.5-35b-a3b"
    assert "--controller-history-aware-retrieval" in cmd
    assert "--fail-on-extraction-error" in cmd
    assert cmd[cmd.index("--answer-context-session-cap") + 1] == "4"
    assert "--controller-aggregation-scaffold" not in cmd
