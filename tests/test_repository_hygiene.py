from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, relative_path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prompt_registry_is_complete_and_hashes_match() -> None:
    validator = _load_module(
        "validate_prompt_registry", "scripts/validation/validate_prompt_registry.py"
    )
    assert validator.validate_registry() == []


def test_document_paths_resolve() -> None:
    validator = _load_module(
        "validate_document_paths", "scripts/validation/validate_document_paths.py"
    )
    assert validator.validate_document_paths() == []


def test_authored_prose_has_no_strong_leakage() -> None:
    validator = _load_module(
        "validate_prose_hygiene", "scripts/validation/validate_prose_hygiene.py"
    )
    assert validator.inspect_prose()["violations"] == []
