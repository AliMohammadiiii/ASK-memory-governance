#!/usr/bin/env python3
"""Check maintained Markdown and LaTeX references for missing local files."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_PREFIXES = ("artifacts/", "docs/history/", "third_party/", "thesis/template/")
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
LATEX_REFERENCE = re.compile(
    r"\\(?:input|include|includegraphics|addbibresource|bibliography)(?:\[[^\]]*\])?\{([^}]+)\}"
)


def tracked_paths(root: Path = ROOT) -> list[Path]:
    output = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    )
    paths = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8", errors="surrogateescape")
        if relative.startswith(EXCLUDED_PREFIXES):
            continue
        path = root / relative
        if path.is_file() and path.suffix.lower() in {".md", ".tex"}:
            paths.append(path)
    return sorted(paths)


def _exists_from(
    path: Path, reference: str, extensions: tuple[str, ...], main_directories: tuple[Path, ...]
) -> bool:
    clean = unquote(reference.strip().strip("<>").split("#", 1)[0])
    if not clean or clean.startswith(("#", "http://", "https://", "mailto:", "data:")):
        return True
    if any(token in clean for token in ("\\", "#", "$")) or clean.startswith("/"):
        return True
    candidates = [path.parent / clean, ROOT / clean]
    candidates.extend(directory / clean for directory in main_directories)
    for candidate in candidates:
        if candidate.exists() or any(candidate.with_suffix(ext).exists() for ext in extensions):
            return True
    return False


def validate_document_paths(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    main_output = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z", "*main.tex"])
    main_directories = tuple(
        (root / raw.decode("utf-8", errors="surrogateescape")).parent
        for raw in main_output.split(b"\0")
        if raw
    )
    for path in tracked_paths(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() == ".md":
            matches = MARKDOWN_LINK.finditer(text)
            extensions: tuple[str, ...] = ()
        else:
            matches = LATEX_REFERENCE.finditer(text)
            extensions = (".tex", ".bib", ".pdf", ".png", ".jpg", ".jpeg")
        for match in matches:
            reference = match.group(1).split(maxsplit=1)[0].strip('"')
            if not _exists_from(path, reference, extensions, main_directories):
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{relative}:{line}: missing local reference: {reference}")
    return errors


def main() -> int:
    errors = validate_document_paths()
    if errors:
        print("\n".join(errors))
        return 1
    print("PASS: maintained Markdown and LaTeX local paths resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
