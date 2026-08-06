from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validation" / "build_manuscripts.py"
SPEC = importlib.util.spec_from_file_location("manuscript_build", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_maintained_manuscripts_have_no_unsafe_placeholders() -> None:
    MODULE.validate_sources()


def test_thesis_avoids_optional_xepersian_localization() -> None:
    preamble = ROOT / "thesis" / "latex" / "preamble" / "commands.tex"
    source = preamble.read_text(encoding="utf-8")
    assert "localize=" not in source


@pytest.mark.parametrize(
    "placeholder",
    ("TODO", "TBD", "FILL ME", "INSERT", "XX", "[Field pending approval]", "نیازمند تأیید"),
)
def test_placeholder_validator_rejects_unsafe_tokens(tmp_path: Path, placeholder: str) -> None:
    source = tmp_path / "source.tex"
    source.write_text(f"\\title{{{placeholder}}}\n", encoding="utf-8")
    assert MODULE.placeholder_issues((source,))


def test_reference_gate_ignores_unrelated_font_warning(tmp_path: Path) -> None:
    log = tmp_path / "main.log"
    log.write_text("LaTeX Font Warning: Font shape undefined\n", encoding="utf-8")
    MODULE._check_resolved((log,))


def test_reference_gate_rejects_undefined_citation(tmp_path: Path) -> None:
    log = tmp_path / "main.log"
    log.write_text("Package natbib Warning: There were undefined citations.\n", encoding="utf-8")
    with pytest.raises(MODULE.ManuscriptBuildError, match="undefined citations"):
        MODULE._check_resolved((log,))
