#!/usr/bin/env python3
"""Explicitly refresh modular LaTeX chapters from retained Markdown sources.

The maintained LaTeX project is authoritative. Run this converter only when a
reviewed Markdown change is intentionally being transferred into that project.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
THESIS = ROOT / "thesis"
LATEX = THESIS / "latex"
TEMPLATE = THESIS / "template"
MASTER = THESIS / "MASTERS_THESIS_ASK_MGP6.md"
PANDOC = shutil.which("pandoc")

CHAPTERS = {
    "1. Introduction and Research Questions": "01_introduction",
    "2. Background and Related Work": "02_related_work",
    "3. Problem Formulation": "03_problem_formulation",
    "4. ASK Architecture and Implementation": "04_ask_architecture",
    "5. MGP-6 v2: The Diagnostic Instrument": "05_mgp6_v2",
    "6. Experimental Methodology": "06_methodology",
    "7. Results": "07_results",
    "8. Error Analysis and Discussion": "08_discussion",
    "9. Validity, Ethics, and Limitations": "09_validity_limitations",
    "10. Conclusion and Future Work": "10_conclusion",
}

APPENDICES = {
    "Appendix A. Data and Record Schemas": "a_data_record_schemas",
    "Appendix B. Prompt Contracts (pointer)": "b_prompt_contracts",
    "Appendix C. Metric Definitions": "c_metric_definitions",
    "Appendix D. Annotation Manual and Adjudication (pointer)": "d_annotation_manual",
    "Appendix E. Reproducibility Commands": "e_reproducibility",
    "Appendix F. Artifact Manifest and Claim-Eligibility Vocabulary": "f_artifact_manifest",
}


def pandoc(markdown: str) -> str:
    """Convert Markdown to TeX without resolving citations or altering facts."""
    if PANDOC is None:
        raise RuntimeError("pandoc is required to generate thesis/latex sources")
    # The retained thesis uses LaTeX delimiters for mathematics. Pandoc's
    # Markdown reader treats them as literal text unless the tex_math_dollars
    # extension is used, so normalize them before conversion.
    markdown = re.sub(r"\\\((.+?)\\\)", r"$\1$", markdown, flags=re.DOTALL)
    markdown = re.sub(r"\\\[\s*(.+?)\s*\\\]", r"$$\n\1\n$$", markdown, flags=re.DOTALL)
    result = subprocess.run(
        [PANDOC, "--from=markdown", "--to=latex", "--natbib", "--shift-heading-level-by=-1"],
        input=markdown,
        text=True,
        check=True,
        capture_output=True,
    )
    # Markdown links to repo-level figures are relative to thesis/.  The TeX
    # build runs from thesis/template/ so they need one extra parent segment.
    latex = result.stdout.replace("{../docs/", "{../../docs/").replace("[keepaspectratio]", "")
    # The current bidi/graphicx combination rejects Pandoc's accessibility
    # alt key. Captions are retained, so this does not remove thesis content.
    latex = re.sub(r",alt=\{[^{}]*\}", "", latex)
    # Pandoc can retain Unicode mathematical symbols inside code listings and
    # prose.  Map the symbols seen in the source corpus to TeX math commands so
    # they render with the selected thesis fonts.
    return latex.replace("θ", r"\ensuremath{\theta}").replace("∈", r"\ensuremath{\in}")


def h1_blocks(markdown: str) -> dict[str, str]:
    """Return H1 title -> body, retaining the source order in Python dicts."""
    matches = list(re.finditer(r"^# (.+?)\s*$", markdown, flags=re.MULTILINE))
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        blocks[match.group(1)] = markdown[match.end() : end].lstrip()
    return blocks


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def extract_section(markdown: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, markdown, flags=re.MULTILINE | re.DOTALL)
    if not match:
        raise RuntimeError(f"Could not find '{heading}' in {MASTER}")
    return match.group(1).strip()


def persian_toc_sections(latex: str) -> str:
    """Keep Persian section titles legible when the English TOC is read."""
    return re.sub(r"\\section\{([^{}]+)\}", r"\\section{\\rl{\1}}", latex)


def build_master() -> None:
    text = MASTER.read_text(encoding="utf-8")
    blocks = h1_blocks(text)
    for title, stem in CHAPTERS.items():
        write(LATEX / "chapters" / f"{stem}.tex", pandoc(blocks[title]))
    for title, stem in APPENDICES.items():
        write(LATEX / "appendices" / f"{stem}.tex", pandoc(blocks[title]))

    write(
        LATEX / "frontmatter" / "abstract_en.tex",
        pandoc(
            extract_section(
                blocks["Auditable Governance of Long-Term Memory in Language Agents"], "Abstract"
            )
        ),
    )
    write(
        LATEX / "frontmatter" / "abstract_fa.tex",
        pandoc(
            (THESIS / "frontmatter" / "abstract_fa.md")
            .read_text(encoding="utf-8")
            .split("\n", 2)[2]
        ),
    )
    write(
        LATEX / "appendices" / "g_extended_summary_fa.tex",
        persian_toc_sections(
            pandoc(
                (THESIS / "frontmatter" / "extended_summary_fa.md")
                .read_text(encoding="utf-8")
                .split("\n", 2)[2]
            )
        ),
    )
    write(
        LATEX / "appendices" / "h_terminology_fa.tex",
        pandoc(
            (THESIS / "frontmatter" / "terminology_fa.md")
            .read_text(encoding="utf-8")
            .split("\n", 2)[2]
        ),
    )


def main() -> None:
    build_master()
    shutil.copy2(THESIS / "references.bib", LATEX / "references.bib")


if __name__ == "__main__":
    main()
