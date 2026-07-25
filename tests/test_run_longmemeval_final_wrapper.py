from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPETENCIES = (
    "knowledge-update",
    "multi-session",
    "single-session-assistant",
    "single-session-preference",
    "single-session-user",
    "temporal-reasoning",
)


def _write_frozen_shape_slice(path: Path, *, per_competency: int = 30) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for competency in COMPETENCIES:
            for index in range(per_competency):
                support_id = f"support-{competency}-{index}"
                row = {
                    "session_id": f"question-{competency}-{index}",
                    "turns": [],
                    "question": "What does the memory say?",
                    "gold_answer": "A grounded answer.",
                    "competency": competency,
                    "supporting_session_ids": [support_id],
                    "corpus_sessions": [
                        {
                            "session_id": support_id,
                            "turns": [{"role": "user", "content": "Grounded evidence."}],
                        }
                    ],
                }
                handle.write(json.dumps(row) + "\n")


def _dry_run(slice_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHON": sys.executable,
        "LONGMEMEVAL_DATA": "/dry-run/full.jsonl",
        "LONGMEMEVAL_SRC": "/dry-run/cleaned.json",
        "LONGMEMEVAL_STRATIFIED_SLICE": str(slice_path),
    }
    return subprocess.run(
        ["bash", "scripts/evaluation/run_longmemeval_final.sh", *args, "--dry-run"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_final_wrapper_controller_only_dry_run_uses_frozen_path(tmp_path: Path) -> None:
    slice_path = tmp_path / "slice.jsonl"
    _write_frozen_shape_slice(slice_path)

    result = _dry_run(slice_path, "--full", "--controller-only")

    assert result.returncode == 0, result.stderr
    assert "frozen slice preflight ok: rows=180 competencies=6x30" in result.stdout
    assert "SYSTEMS=controller SHARDS=8 SAMPLE_FROM=0 SAMPLE_TO=179" in result.stdout
    assert "out=runs_local/lme_final_controller_v12_qwen_180" in result.stdout
    assert "answer model     : qwen/qwen3.5-9b (reasoning disabled)" in result.stdout
    assert "ANSWER_MAX_NEW_TOKENS=4096" in result.stdout
    assert "ANSWER_ESCALATION_MODEL=qwen/qwen3.5-9b" in result.stdout
    assert "JUDGE_MODEL=google/gemma-4-31b-it" in result.stdout
    assert "JUDGE_OPENAI_FALLBACK_MODEL=<disabled>" in result.stdout
    assert "memory/answer provider pool=venice,deepinfra,siliconflow" in result.stdout
    assert "post-run controller gate: >=153/180 (0.85)" in result.stdout
    assert "gpt-5-mini" not in result.stdout.lower()


def test_final_freeze_uses_qwen_for_every_controller_model_role() -> None:
    config = yaml.safe_load((REPO_ROOT / "configs/release/final.yaml").read_text(encoding="utf-8"))

    assert config["freeze"]["version"] == "final-2.0"
    assert config["run"]["shards"] == 8
    assert config["run"]["extraction_concurrency"] == 4
    assert config["models"]["main_model"] == "qwen/qwen3.5-9b"
    assert config["models"]["answer_model"] == config["models"]["main_model"]
    assert config["models"]["answer_escalation_model"] == config["models"]["main_model"]
    assert config["judge"]["primary_model"] == "google/gemma-4-31b-it"
    assert config["judge"]["fallback_model"] is None
    assert config["judge"]["fallback_trigger"] == ("disabled_fail_shard_after_primary_retries")
    assert config["run"]["competency_user_candidate_k"] == 120
    assert config["run"]["competency_assistant_candidate_k"] == 60
    assert config["run"]["competency_session_top_k"] == 12
    assert config["run"]["competency_preference_session_top_k"] == 18
    assert config["embedder"]["loopback_proxy_bypass"] is True
    assert config["models"]["answer_request"] == {
        "max_new_tokens": 4096,
        "reasoning_enabled": False,
        "provider_order": [],
        "provider_only": ["venice", "deepinfra", "siliconflow"],
        "provider_fallbacks": True,
    }


def test_final_wrapper_rejects_non_frozen_slice_before_api_use(tmp_path: Path) -> None:
    slice_path = tmp_path / "slice.jsonl"
    _write_frozen_shape_slice(slice_path, per_competency=29)

    result = _dry_run(slice_path, "--full", "--controller-only")

    assert result.returncode != 0
    assert "invalid frozen slice" in result.stderr
    assert "expected 180" in result.stderr
