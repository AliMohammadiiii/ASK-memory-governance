#!/usr/bin/env python3
"""Validate and compile the maintained manuscript sources in isolation."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "build" / "manuscripts"
PAPER_SOURCE = ROOT / "paper" / "paper_1"
THESIS_SOURCE = ROOT / "thesis" / "latex"
THESIS_TEMPLATE = ROOT / "thesis" / "template"

PLACEHOLDER_PATTERNS = (
    re.compile(r"\b(?:TODO|TBD|INSERT|XX)\b"),
    re.compile(r"FILL[ _-]*ME", re.IGNORECASE),
    re.compile(r"pending approval", re.IGNORECASE),
    re.compile(r"نیازمند\s+تأیید"),
    re.compile(r"پس از تأیید.+تکمیل"),
)
UNRESOLVED_PATTERNS = (
    re.compile(r"LaTeX Warning: Reference .+ undefined"),
    re.compile(r"LaTeX Warning: There were undefined references"),
    re.compile(r"Package natbib Warning: Citation .+ undefined"),
    re.compile(r"Package natbib Warning: There were undefined citations"),
    re.compile(r"Warning--I didn't find a database entry"),
)


class ManuscriptBuildError(RuntimeError):
    """Raised when a manuscript source or compilation gate fails."""


def maintained_sources() -> tuple[Path, ...]:
    paper = tuple(sorted(PAPER_SOURCE.rglob("*.tex")))
    thesis = tuple(
        path
        for path in sorted(THESIS_SOURCE.rglob("*.tex"))
        if "support" not in path.relative_to(THESIS_SOURCE).parts
    )
    return paper + thesis


def placeholder_issues(paths: Iterable[Path]) -> list[str]:
    issues: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        try:
            display_path = path.relative_to(ROOT)
        except ValueError:
            display_path = path
        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in PLACEHOLDER_PATTERNS):
                issues.append(f"{display_path}:{line_number}: unsafe placeholder")
    return issues


def validate_sources() -> None:
    required = (PAPER_SOURCE / "main.tex", THESIS_SOURCE / "main.tex")
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise ManuscriptBuildError(f"missing canonical source: {', '.join(missing)}")
    issues = placeholder_issues(maintained_sources())
    if issues:
        raise ManuscriptBuildError("unsafe manuscript placeholders:\n" + "\n".join(issues))


def _require_commands(commands: Sequence[str]) -> None:
    missing = [command for command in commands if shutil.which(command) is None]
    if missing:
        raise ManuscriptBuildError(f"missing build commands: {', '.join(missing)}")


def _run(command: Sequence[str], *, cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return
    diagnostic = "\n".join((result.stdout + result.stderr).splitlines()[-80:])
    raise ManuscriptBuildError(
        f"command failed with exit code {result.returncode}: {' '.join(command)}\n{diagnostic}"
    )


def _check_resolved(log_paths: Iterable[Path]) -> None:
    messages: list[str] = []
    for path in log_paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if any(pattern.search(line) for pattern in UNRESOLVED_PATTERNS):
                messages.append(f"{path.name}: {line.strip()}")
    if messages:
        raise ManuscriptBuildError("unresolved manuscript references:\n" + "\n".join(messages))


def _page_count(pdf: Path) -> int:
    if not pdf.is_file() or pdf.stat().st_size == 0:
        raise ManuscriptBuildError(f"expected nonempty PDF was not produced: {pdf.name}")
    result = subprocess.run(["pdfinfo", str(pdf)], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise ManuscriptBuildError(f"could not inspect generated PDF: {pdf.name}")
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, flags=re.MULTILINE)
    if match is None or int(match.group(1)) < 1:
        raise ManuscriptBuildError(f"generated PDF has no readable pages: {pdf.name}")
    return int(match.group(1))


def _publish(pdf: Path, *, name: str) -> tuple[Path, int]:
    pages = _page_count(pdf)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT_DIR / f"{name}.pdf"
    shutil.copy2(pdf, destination)
    return destination, pages


def build_paper(workspace: Path) -> tuple[Path, int]:
    _require_commands(("latexmk", "pdfinfo"))
    source = workspace / "paper"
    shutil.copytree(PAPER_SOURCE, source)
    _run(
        (
            "latexmk",
            "-pdf",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            "main.tex",
        ),
        cwd=source,
    )
    _check_resolved((source / "main.log", source / "main.blg"))
    return _publish(source / "main.pdf", name="paper")


def build_thesis(workspace: Path) -> tuple[Path, int]:
    _require_commands(("xelatex", "bibtex", "pdfinfo"))
    if not (THESIS_TEMPLATE / "tex" / "tehran-thesis.cls").is_file():
        raise ManuscriptBuildError("pinned thesis template is not initialized")
    thesis = workspace / "thesis"
    template = thesis / "template"
    shutil.copytree(THESIS_TEMPLATE, template)
    shutil.copytree(THESIS_SOURCE, thesis / "latex")
    shutil.copytree(ROOT / "docs" / "figures", workspace / "docs" / "figures")
    xelatex = (
        "xelatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "-jobname=thesis",
        "../latex/main.tex",
    )
    _run(xelatex, cwd=template)
    _run(("bibtex", "thesis"), cwd=template)
    _run(xelatex, cwd=template)
    _run(xelatex, cwd=template)
    _check_resolved((template / "thesis.log", template / "thesis.blg"))
    return _publish(template / "thesis.pdf", name="thesis")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate sources without compiling")
    parser.add_argument("--kind", choices=("paper", "thesis"))
    args = parser.parse_args()
    if not args.check and args.kind is None:
        parser.error("--kind is required unless --check is used")
    return args


def main() -> int:
    args = parse_args()
    try:
        validate_sources()
        if args.check:
            sys.stdout.write("Manuscript source validation: OK\n")
            return 0
        with tempfile.TemporaryDirectory(prefix="manuscript-build-") as directory:
            builder = build_paper if args.kind == "paper" else build_thesis
            output, pages = builder(Path(directory))
        sys.stdout.write(f"Built {output.relative_to(ROOT)} ({pages} pages)\n")
        return 0
    except ManuscriptBuildError as error:
        sys.stderr.write(f"Manuscript build failed: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
