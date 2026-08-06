"""Ollama M4-W13 runner shard logging/fail-fast behavior."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_m4w13_ollama.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_m4w13_ollama_for_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_model_preflight_rejects_invalid_endpoint_before_network(monkeypatch) -> None:
    runner = _load_runner()

    def unexpected_network_call(*args, **kwargs):
        raise AssertionError("network access must not occur for an invalid endpoint")

    monkeypatch.setattr(runner.urllib.request, "urlopen", unexpected_network_call)

    with pytest.raises(ValueError, match="scheme"):
        runner._installed_ollama_models("localhost:11434")


def test_session_shard_failure_tails_log_and_stops_other_shards(tmp_path: Path) -> None:
    runner = _load_runner()
    env = {"PYTHONUNBUFFERED": "1"}
    log_dir = tmp_path / "logs"
    jobs = {
        0: runner._start_shard(
            index=0,
            cmd=[
                sys.executable,
                "-c",
                "print('boom from shard 0', flush=True); raise SystemExit(7)",
            ],
            env=env,
            log_dir=log_dir,
            baseline_alias="controller",
        ),
        1: runner._start_shard(
            index=1,
            cmd=[sys.executable, "-c", "import time; time.sleep(30)"],
            env=env,
            log_dir=log_dir,
            baseline_alias="controller",
        ),
    }

    with pytest.raises(RuntimeError, match=r"shard 0 rc=7"):
        runner._wait_for_shards(
            baseline_alias="controller",
            jobs=jobs,
            tail_lines_on_failure=20,
        )

    assert "boom from shard 0" in (log_dir / "controller_shard0.log").read_text()
    assert jobs[1].process.poll() is not None
