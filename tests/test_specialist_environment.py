from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validation" / "validate_specialist_environment.py"
SPEC = importlib.util.spec_from_file_location("specialist_environment", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize("profile", ("ml", "adapters"))
def test_specialist_lock_is_exact_and_hashed(profile: str) -> None:
    assert MODULE.validate_lock(MODULE.LOCKS[profile]) > 0


@pytest.mark.parametrize(
    "content",
    (
        "package>=1.0\n",
        "package==1.0\n",
        "package==1.0 \\\n  --hash=sha256:not-a-hash\n",
    ),
)
def test_specialist_lock_rejects_unpinned_or_unhashed_content(tmp_path: Path, content: str) -> None:
    lock = tmp_path / "invalid.lock"
    lock.write_text(content, encoding="utf-8")
    with pytest.raises(MODULE.EnvironmentValidationError):
        MODULE.validate_lock(lock)


def test_installed_version_must_match_active_lock_pin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = tmp_path / "exact.lock"
    lock.write_text(
        "demo-package==1.2.3 \\\n    --hash=sha256:" + "0" * 64 + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE.importlib.metadata, "version", lambda name: "2.0.0")

    with pytest.raises(MODULE.EnvironmentValidationError, match="installed 2.0.0"):
        MODULE.validate_installed_versions(lock)
