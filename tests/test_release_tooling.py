from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, relative_path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_metadata_versions_are_consistent() -> None:
    validator = _load_module("validate_repository", "scripts/validate_repository.py")
    versions = validator.project_versions(ROOT)
    assert len(set(versions.values())) == 1
    assert next(iter(versions.values())) == "0.2.0"


def test_repository_release_dates_are_consistent() -> None:
    validator = _load_module("validate_repository_dates", "scripts/validate_repository.py")
    release_dates = validator.project_release_dates(ROOT)
    assert set(release_dates.values()) == {"2026-07-13"}


def test_repository_validator_accepts_current_tree() -> None:
    validator = _load_module("validate_repository_current", "scripts/validate_repository.py")
    assert validator.validate_repository(ROOT) == []


def test_repository_validator_fallback_excludes_local_environments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validator = _load_module("validate_repository_fallback", "scripts/validate_repository.py")
    (tmp_path / "README.md").write_text("public", encoding="utf-8")
    (tmp_path / ".venv/lib").mkdir(parents=True)
    (tmp_path / ".venv/lib/private.txt").write_text("local", encoding="utf-8")
    monkeypatch.setattr(
        validator.subprocess,
        "check_output",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError),
    )
    assert validator.candidate_paths(tmp_path) == [tmp_path / "README.md"]


def test_public_release_candidates_are_tracked_only(monkeypatch: pytest.MonkeyPatch) -> None:
    release = _load_module("build_final_release", "scripts/release/build_final_release.py")
    captured: list[str] = []

    def fake_check_output(command: list[str], **_: object) -> bytes:
        captured.extend(command)
        return b"README.md\0"

    monkeypatch.setattr(release.subprocess, "check_output", fake_check_output)
    assert release.public_candidates() == [ROOT / "README.md"]
    assert "--cached" in captured
    assert "--others" not in captured


def test_advisor_candidates_can_include_untracked_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = _load_module("build_final_release_advisor", "scripts/release/build_final_release.py")
    captured: list[str] = []

    def fake_check_output(command: list[str], **_: object) -> bytes:
        captured.extend(command)
        return b"README.md\0"

    monkeypatch.setattr(release.subprocess, "check_output", fake_check_output)
    assert release.public_candidates(include_untracked=True) == [ROOT / "README.md"]
    assert "--others" in captured
    assert "--exclude-standard" in captured


def test_advisor_cleaner_rejects_paths_outside_generated_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "scripts/release"))
    advisor = _load_module(
        "build_advisor_handoff_cleaner", "scripts/release/build_advisor_handoff.py"
    )
    with pytest.raises(SystemExit, match="refusing to remove"):
        advisor.safely_remove_generated(tmp_path)


def test_embedding_server_defaults_to_local_and_does_not_trust_remote_code() -> None:
    server = _load_module("serve_embeddings_defaults", "scripts/serve_embeddings.py")
    args = server.build_parser().parse_args([])
    assert args.host == "127.0.0.1"
    assert args.revision is None
    assert args.trust_remote_code is False


def test_public_release_excludes_private_and_local_path_records() -> None:
    release = _load_module(
        "build_final_release_boundaries", "scripts/release/build_final_release.py"
    )
    assert ".private/" in release.PUBLIC_EXCLUDED_PREFIXES
    assert "artifacts/mgp6_v43_integration/" in release.PUBLIC_EXCLUDED_PREFIXES


def test_secret_pattern_requires_a_token_boundary() -> None:
    validator = _load_module(
        "validate_repository_secret_boundary", "scripts/validate_repository.py"
    )
    assert all(
        not pattern.search("ask-memory-governance-advisor") for pattern in validator.SECRET_PATTERNS
    )
    assert any(pattern.search("token=sk-" + "a" * 32) for pattern in validator.SECRET_PATTERNS)


def test_release_builder_fails_closed_on_dirty_worktree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = _load_module("build_final_release_dirty", "scripts/release/build_final_release.py")
    monkeypatch.setattr(
        release.subprocess,
        "check_output",
        lambda *_args, **_kwargs: " M README.md\n",
    )
    with pytest.raises(SystemExit, match="clean worktree"):
        release.ensure_clean_worktree(allow_dirty=False)


def test_release_builder_can_explicitly_allow_local_dirty_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = _load_module(
        "build_final_release_allow_dirty", "scripts/release/build_final_release.py"
    )

    def unexpected_call(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("git status should not run when dirty validation is explicit")

    monkeypatch.setattr(release.subprocess, "check_output", unexpected_call)
    release.ensure_clean_worktree(allow_dirty=True)
