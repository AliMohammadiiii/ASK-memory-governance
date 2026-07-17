#!/usr/bin/env python3
"""Audit a BibTeX file and the recursively included LaTeX citation graph."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BIB = ROOT / "paper/paper_1/references.bib"
DEFAULT_TEX = ROOT / "paper/paper_1/main.tex"
PLACEHOLDER_PATTERNS = (
    re.compile(r"\band\s+others\b", re.IGNORECASE),
    re.compile(r"\bMemTensor\b", re.IGNORECASE),
    re.compile(r"\b(?:unknown|anonymous|authors?|tbd|todo)\b", re.IGNORECASE),
)
BODY_PLACEHOLDER = re.compile(r"(?:not\s+verified|\b(?:tbd|todo)\b)", re.IGNORECASE)


@dataclass(frozen=True)
class BibEntry:
    kind: str
    key: str
    body: str


def parse_entries(text: str) -> list[BibEntry]:
    entries: list[BibEntry] = []
    index = 0
    while True:
        match = re.search(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text[index:])
        if match is None:
            break
        start = index + match.start()
        body_start = index + match.end()
        depth = 1
        cursor = body_start
        while cursor < len(text) and depth:
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
            cursor += 1
        if depth:
            raise ValueError(f"unclosed BibTeX entry beginning at byte {start}")
        entries.append(BibEntry(match.group(1).lower(), match.group(2), text[body_start : cursor - 1]))
        index = cursor
    return entries


def field_value(entry: BibEntry, name: str) -> str | None:
    match = re.search(rf"(?im)^\s*{re.escape(name)}\s*=\s*", entry.body)
    if match is None:
        return None
    cursor = match.end()
    if cursor >= len(entry.body):
        return None
    opener = entry.body[cursor]
    if opener not in {'{', '"'}:
        end = entry.body.find(",", cursor)
        return entry.body[cursor : end if end >= 0 else None].strip()
    closer = "}" if opener == "{" else '"'
    depth = 1
    cursor += 1
    start = cursor
    while cursor < len(entry.body):
        char = entry.body[cursor]
        if opener == "{" and char == "{":
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return entry.body[start:cursor].strip()
        cursor += 1
    return None


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def latex_sources(entrypoint: Path) -> list[Path]:
    entrypoint = entrypoint.resolve()
    latex_root = entrypoint.parent
    pending = [entrypoint]
    seen: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        if not path.is_file():
            raise FileNotFoundError(path)
        seen.add(path)
        text = path.read_text(encoding="utf-8")
        for raw in re.findall(r"\\(?:input|include)\{([^}]+)\}", text):
            candidates = [latex_root / raw, path.parent / raw]
            normalized = [
                candidate if candidate.suffix else candidate.with_suffix(".tex")
                for candidate in candidates
            ]
            child = next((candidate for candidate in normalized if candidate.is_file()), normalized[0])
            pending.append(child.resolve())
    return sorted(seen)


def cited_keys(paths: list[Path]) -> set[str]:
    keys: set[str] = set()
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for group in re.findall(r"\\cite\w*\s*(?:\[[^]]*\]\s*)*\{([^}]+)\}", text):
            keys.update(key.strip() for key in group.split(",") if key.strip())
    return keys


def audit(bib_path: Path, tex_entrypoint: Path | None) -> list[str]:
    entries = parse_entries(bib_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    keys: set[str] = set()
    titles: dict[str, str] = {}
    for entry in entries:
        if entry.key in keys:
            errors.append(f"duplicate key: {entry.key}")
        keys.add(entry.key)
        required = ("author", "title", "year")
        for field in required:
            if not field_value(entry, field):
                errors.append(f"{entry.key}: missing {field}")
        if not (field_value(entry, "doi") or field_value(entry, "url")):
            errors.append(f"{entry.key}: missing DOI or stable URL")
        author = field_value(entry, "author") or ""
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern.search(author):
                errors.append(f"{entry.key}: placeholder or truncated metadata ({pattern.pattern})")
                break
        if BODY_PLACEHOLDER.search(entry.body):
            errors.append(f"{entry.key}: placeholder note in metadata")
        title = field_value(entry, "title")
        if title:
            normalized = normalize_title(title)
            if normalized in titles:
                errors.append(f"duplicate title: {titles[normalized]} and {entry.key}")
            else:
                titles[normalized] = entry.key

    if tex_entrypoint is not None:
        citations = cited_keys(latex_sources(tex_entrypoint))
        for key in sorted(citations - keys):
            errors.append(f"cited key missing from bibliography: {key}")
        for key in sorted(keys - citations):
            errors.append(f"uncited bibliography entry: {key}")
    if not entries:
        errors.append("bibliography contains no entries")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bib", type=Path, default=DEFAULT_BIB)
    parser.add_argument("--tex", type=Path, default=DEFAULT_TEX)
    parser.add_argument("--no-citation-check", action="store_true")
    args = parser.parse_args(argv)
    errors = audit(args.bib.resolve(), None if args.no_citation_check else args.tex.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {args.bib} passed metadata, duplicate, and citation checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
