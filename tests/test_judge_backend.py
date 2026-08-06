"""Tests for M4 judge backend selection."""

from __future__ import annotations

from ask.eval.judge import JudgeBackendConfig, build_judge_backend
from ask.inference.fake import FakeLLM
from ask.inference.openai_compatible import OpenAICompatibleLLM


def test_same_as_answerer_returns_answerer_instance() -> None:
    answerer = FakeLLM(model_id="answerer")
    judge = build_judge_backend(JudgeBackendConfig(), answerer=answerer)
    assert judge is answerer


def test_fake_judge_backend_allows_explicit_model_id() -> None:
    judge = build_judge_backend(
        JudgeBackendConfig(backend="fake", model_id="fake/substitute-judge"),
        answerer=FakeLLM(),
    )
    assert judge.model_id == "fake/substitute-judge"


def test_huggingface_judge_preserves_exact_revision() -> None:
    judge = build_judge_backend(
        JudgeBackendConfig(
            backend="huggingface",
            model_id="model",
            hf_revision="commit-sha",
        ),
        answerer=FakeLLM(),
    )

    assert judge.config.model_revision == "commit-sha"  # type: ignore[attr-defined]


def test_yaml_config_accepts_nested_judge_block(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "judge.yaml"
    path.write_text(
        "\n".join(
            [
                "judge:",
                "  backend: fake",
                "  model_id: fake/from-yaml",
                "  response_format: none",
                "  think: false",
                "  hf_revision: commit-sha",
            ]
        ),
        encoding="utf-8",
    )

    cfg = JudgeBackendConfig.from_yaml(path)

    assert cfg.backend == "fake"
    assert cfg.model_id == "fake/from-yaml"
    assert cfg.response_format is None
    assert cfg.think is False
    assert cfg.hf_revision == "commit-sha"


def test_openai_compatible_judge_backend_builds_json_llm(tmp_path) -> None:  # noqa: ANN001
    judge = build_judge_backend(
        JudgeBackendConfig(
            backend="openai_compatible",
            model_id="cogito-2.1:671b",
            openai_base_url="http://localhost:3001/v1",
            openai_api_key="key",
            openai_log_path=str(tmp_path / "judge_calls.jsonl"),
        ),
        answerer=FakeLLM(),
    )

    assert isinstance(judge, OpenAICompatibleLLM)
    assert judge.model_id == "cogito-2.1:671b"
    assert judge.require_json is True


def test_huggingface_judge_forwards_immutable_revision() -> None:
    revision = "c" * 40
    judge = build_judge_backend(
        JudgeBackendConfig(
            backend="huggingface",
            model_id="example/judge",
            hf_revision=revision,
        )
    )

    assert judge.config.model_revision == revision
