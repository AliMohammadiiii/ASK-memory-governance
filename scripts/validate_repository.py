#!/usr/bin/env python3
"""Validate the repository boundary, metadata, and publishable text files."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-or-v1-[A-Za-z0-9]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{24,}"),
)
TEXT_SUFFIXES = {
    ".bib",
    ".cfg",
    ".csv",
    ".ini",
    ".j2",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".sh",
    ".sql",
    ".tex",
    ".toml",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}
REQUIRED_PATHS = (
    ".github/workflows/ci.yml",
    "CHANGELOG.md",
    "CITATION.cff",
    "CONTRIBUTING.md",
    "LICENSE",
    "LICENSE-DATA.md",
    "README.md",
    "SECURITY.md",
    "benchmarks/mgp6/data/mgp6_v2.jsonl",
    "docs/README.md",
    "pyproject.toml",
    "src/ask",
    "tests",
)
FORBIDDEN_DUPLICATES = (
    "benchmarks/mgp6/data/mgp6_v2.txt",
    "benchmarks/mgp6/annotations/model_or_mixed/mgp6_v2(1).jsonl",
    "benchmarks/mgp6/annotations/model_or_mixed/independent_annotations_test.csv",
)
HISTORICAL_ARTIFACT_ALLOWLIST = {
    "paper/paper_1/sections/08_downstream_analysis.tex.bak_v11",
}
FALLBACK_EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "final_release",
    "runs",
    "runs_local",
}


def candidate_paths(root: Path) -> list[Path]:
    """Return tracked and unignored files without traversing ignored outputs."""
    try:
        listed = subprocess.check_output(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return sorted(
            path
            for path in root.rglob("*")
            if path.is_file()
            and not any(part in FALLBACK_EXCLUDED_PARTS for part in path.relative_to(root).parts)
        )
    return sorted(
        root / raw.decode("utf-8", errors="surrogateescape") for raw in listed.split(b"\0") if raw
    )


def _assignment_from_python(path: Path, name: str) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name:
            value = ast.literal_eval(node.value)
            return str(value)
    return None


def project_versions(root: Path) -> dict[str, str | None]:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    citation = (root / "CITATION.cff").read_text(encoding="utf-8")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    citation_match = re.search(r"(?m)^version:\s*[\"']?([^\"'\s]+)", citation)
    changelog_match = re.search(r"(?m)^##\s+(\d+\.\d+\.\d+)\s+—", changelog)
    return {
        "pyproject.toml": str(pyproject["project"]["version"]),
        "CITATION.cff": citation_match.group(1) if citation_match else None,
        "CHANGELOG.md": changelog_match.group(1) if changelog_match else None,
        "src/ask/__init__.py": _assignment_from_python(root / "src/ask/__init__.py", "__version__"),
    }


def project_release_dates(root: Path) -> dict[str, str | None]:
    citation = (root / "CITATION.cff").read_text(encoding="utf-8")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    citation_match = re.search(r"(?m)^date-released:\s*(\d{4}-\d{2}-\d{2})\s*$", citation)
    changelog_match = re.search(r"(?m)^##\s+\d+\.\d+\.\d+\s+—\s+(\d{4}-\d{2}-\d{2})\s*$", changelog)
    return {
        "CITATION.cff": citation_match.group(1) if citation_match else None,
        "CHANGELOG.md": changelog_match.group(1) if changelog_match else None,
    }


def _validate_required_paths(root: Path, errors: list[str]) -> None:
    for relative in REQUIRED_PATHS:
        if not (root / relative).exists():
            errors.append(f"missing required path: {relative}")
    for relative in FORBIDDEN_DUPLICATES:
        if (root / relative).exists():
            errors.append(f"redundant canonical-data copy: {relative}")


def _validate_release_metadata(root: Path, errors: list[str]) -> None:
    try:
        versions = project_versions(root)
    except (KeyError, OSError, SyntaxError, ValueError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"cannot read release versions: {exc}")
    else:
        if None in versions.values() or len(set(versions.values())) != 1:
            rendered = ", ".join(f"{path}={version!r}" for path, version in versions.items())
            errors.append(f"release version mismatch: {rendered}")

    try:
        release_dates = project_release_dates(root)
    except OSError as exc:
        errors.append(f"cannot read release dates: {exc}")
    else:
        if None in release_dates.values() or len(set(release_dates.values())) != 1:
            rendered = ", ".join(
                f"{path}={release_date!r}" for path, release_date in release_dates.items()
            )
            errors.append(f"release date mismatch: {rendered}")


def _scan_candidate(root: Path, path: Path, errors: list[str]) -> None:
    if not path.is_file():
        return
    relative = path.relative_to(root).as_posix()
    if relative not in HISTORICAL_ARTIFACT_ALLOWLIST and (
        ".bak" in path.name or path.name == ".DS_Store"
    ):
        errors.append(f"repository pollution: {relative}")
    if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size >= 8_000_000:
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        errors.append(f"possible embedded secret: {relative}")


def validate_repository(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    _validate_required_paths(root, errors)
    _validate_release_metadata(root, errors)
    for path in candidate_paths(root):
        _scan_candidate(root, path, errors)
    return errors


def main() -> int:
    errors = validate_repository()
    if errors:
        print("Repository validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Repository structure, metadata, redundancy, and secret scan: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
