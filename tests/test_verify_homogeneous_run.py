from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load_verifier() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_homogeneous_run.py"
    spec = importlib.util.spec_from_file_location("verify_homogeneous_run", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _valid_system(tmp_path: Path) -> tuple[ModuleType, Path]:
    verifier = _load_verifier()
    primary = "google/gemma-4-31b-it:free"
    answer_model = "qwen/qwen3.5-9b"
    system_dir = tmp_path / "controller"
    answers = [
        {
            "session_id": session_id,
            "model_id": answer_model,
            "seed": 0,
            "telemetry": {"requested_model": answer_model},
        }
        for session_id in ("s1", "s2")
    ]
    judgments = [
        {
            "session_id": session_id,
            "correct": correct,
            "judge_model_id": primary,
            "requested_judge_model_id": primary,
            "used_fallback": False,
            "used_model_fallback": False,
            "used_scoring_fallback": False,
            "fallback_reason": None,
            "judge_was_called": True,
            "judge_prompt_hash": f"prompt-{session_id}",
            "judge_raw_response_hash": f"raw-{session_id}",
            "judge_raw_output": '{"correct": true}',
            "judge_attempt_index": 0,
        }
        for session_id, correct in (("s1", True), ("s2", False))
    ]
    provider_policy = {
        "order": ["venice"],
        "only": ["venice"],
        "allow_fallbacks": False,
    }
    calls = [
        {
            "requested_model": answer_model,
            "model": answer_model,
            "provider": "venice",
            "provider_preferences": provider_policy,
        }
    ]
    _write_jsonl(system_dir / "answers.jsonl", answers)
    _write_jsonl(system_dir / "judgments.jsonl", judgments)
    _write_jsonl(system_dir / "logs" / "llm_calls.jsonl", calls)
    (system_dir / "report.json").write_text(
        json.dumps(
            {
                "n_sessions": 2,
                "overall_accuracy": 0.5,
                "judge_model_id": primary,
                "judge_models_used": {primary: 2},
                "n_model_fallbacks": 0,
                "n_scoring_fallbacks": 0,
                "n_deterministic_guards": 0,
            }
        ),
        encoding="utf-8",
    )
    return verifier, tmp_path


def test_homogeneity_gate_accepts_complete_provenance(tmp_path: Path) -> None:
    verifier, run_root = _valid_system(tmp_path)
    result = verifier.check_system(
        run_root,
        "controller",
        ["s1", "s2"],
        2,
        expected_answer_model="qwen/qwen3.5-9b",
        expected_answer_provider="venice",
        expected_judge_primary="google/gemma-4-31b-it:free",
        allowed_judge_fallbacks={"google/gemma-4-31b-it"},
    )
    assert result["errors"] == []
    assert result["recomputed_accuracy"] == 0.5


def test_homogeneity_gate_rejects_model_fallback_when_policy_has_none(
    tmp_path: Path,
) -> None:
    verifier, run_root = _valid_system(tmp_path)
    judgments_path = run_root / "controller" / "judgments.jsonl"
    judgments = verifier.load_jsonl(judgments_path)
    judgments[0]["used_fallback"] = True
    judgments[0]["used_model_fallback"] = True
    judgments[0]["fallback_reason"] = "unexpected route change"
    _write_jsonl(judgments_path, judgments)
    report_path = run_root / "controller" / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["n_model_fallbacks"] = 1
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = verifier.check_system(
        run_root,
        "controller",
        ["s1", "s2"],
        2,
        expected_answer_model="qwen/qwen3.5-9b",
        expected_answer_provider="venice",
        expected_judge_primary="google/gemma-4-31b-it:free",
        allowed_judge_fallbacks=set(),
    )

    assert any("policy declares no fallback model" in error for error in result["errors"])


def test_homogeneity_gate_rejects_missing_raw_audit_and_provider_drift(
    tmp_path: Path,
) -> None:
    verifier, run_root = _valid_system(tmp_path)
    judgments_path = run_root / "controller" / "judgments.jsonl"
    judgments = verifier.load_jsonl(judgments_path)
    judgments[0].pop("judge_raw_response_hash")
    _write_jsonl(judgments_path, judgments)

    calls_path = run_root / "controller" / "logs" / "llm_calls.jsonl"
    calls = verifier.load_jsonl(calls_path)
    calls[0]["provider_preferences"] = {"allow_fallbacks": True}
    _write_jsonl(calls_path, calls)

    result = verifier.check_system(
        run_root,
        "controller",
        ["s1", "s2"],
        2,
        expected_answer_model="qwen/qwen3.5-9b",
        expected_answer_provider="venice",
        expected_judge_primary="google/gemma-4-31b-it:free",
        allowed_judge_fallbacks={"google/gemma-4-31b-it"},
    )
    joined = "\n".join(result["errors"])
    assert "lack raw/hash audit fields" in joined
    assert "provider policy" in joined


def test_homogeneity_gate_accepts_and_requires_a_three_provider_pool(
    tmp_path: Path,
) -> None:
    verifier, run_root = _valid_system(tmp_path)
    calls_path = run_root / "controller" / "logs" / "llm_calls.jsonl"
    calls = verifier.load_jsonl(calls_path)
    provider_policy = {
        "only": ["venice", "deepinfra", "siliconflow"],
        "allow_fallbacks": True,
    }
    calls = [
        {**calls[0], "provider": provider, "provider_preferences": provider_policy}
        for provider in ("venice", "deepinfra", "siliconflow")
    ]
    _write_jsonl(calls_path, calls)

    result = verifier.check_system(
        run_root,
        "controller",
        ["s1", "s2"],
        2,
        expected_answer_model="qwen/qwen3.5-9b",
        expected_answer_provider=None,
        expected_judge_primary="google/gemma-4-31b-it:free",
        allowed_judge_fallbacks={"google/gemma-4-31b-it"},
        allowed_answer_providers=("venice", "deepinfra", "siliconflow"),
        required_answer_providers={"venice", "deepinfra", "siliconflow"},
    )

    assert result["errors"] == []
    assert result["actual_answer_providers"] == {
        "venice": 1,
        "deepinfra": 1,
        "siliconflow": 1,
    }


def test_homogeneity_gate_allows_declared_auxiliary_call_model(tmp_path: Path) -> None:
    verifier, run_root = _valid_system(tmp_path)
    calls_path = run_root / "controller" / "logs" / "llm_calls.jsonl"
    calls = verifier.load_jsonl(calls_path)
    calls.append(
        {
            "requested_model": "qwen/extractor-model",
            "model": "qwen/extractor-model",
            "provider": "venice",
            "provider_preferences": {},
        }
    )
    _write_jsonl(calls_path, calls)

    result = verifier.check_system(
        run_root,
        "controller",
        ["s1", "s2"],
        2,
        expected_answer_model="qwen/qwen3.5-9b",
        expected_answer_provider="venice",
        expected_judge_primary="google/gemma-4-31b-it:free",
        allowed_judge_fallbacks={"google/gemma-4-31b-it"},
        allowed_auxiliary_models={"qwen/extractor-model"},
    )

    assert result["errors"] == []
    assert "qwen/extractor-model" in result["requested_call_models"]


def test_homogeneity_gate_reports_missing_id_and_seed_without_crashing(
    tmp_path: Path,
) -> None:
    verifier, run_root = _valid_system(tmp_path)
    answers_path = run_root / "controller" / "answers.jsonl"
    answers = verifier.load_jsonl(answers_path)
    answers[0]["session_id"] = None
    answers[1].pop("seed")
    _write_jsonl(answers_path, answers)

    result = verifier.check_system(
        run_root,
        "controller",
        ["s1", "s2"],
        2,
        expected_answer_model="qwen/qwen3.5-9b",
        expected_answer_provider="venice",
        expected_judge_primary="google/gemma-4-31b-it:free",
        allowed_judge_fallbacks={"google/gemma-4-31b-it"},
    )

    joined = "\n".join(result["errors"])
    assert "lack a non-empty string session_id" in joined
    assert "lack seed provenance" in joined
