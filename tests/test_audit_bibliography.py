from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/release/audit_bibliography.py"
SPEC = importlib.util.spec_from_file_location("audit_bibliography", SCRIPT)
assert SPEC and SPEC.loader
audit_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit_module
SPEC.loader.exec_module(audit_module)


def test_project_paper_bibliography_passes() -> None:
    assert audit_module.audit(
        ROOT / "paper/paper_1/references.bib",
        ROOT / "paper/paper_1/main.tex",
    ) == []


def test_audit_rejects_truncated_author_and_missing_citation(tmp_path: Path) -> None:
    bib = tmp_path / "references.bib"
    tex = tmp_path / "main.tex"
    bib.write_text(
        """@article{bad,
  title = {Example},
  author = {Example, Alice and others},
  year = {2026},
  url = {https://example.org}
}
""",
        encoding="utf-8",
    )
    tex.write_text(r"\citep{missing}" + "\n", encoding="utf-8")

    errors = audit_module.audit(bib, tex)

    assert any("truncated metadata" in error for error in errors)
    assert any("missing from bibliography: missing" in error for error in errors)
    assert any("uncited bibliography entry: bad" in error for error in errors)
