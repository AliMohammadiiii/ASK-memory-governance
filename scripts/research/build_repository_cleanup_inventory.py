#!/usr/bin/env python3
"""Build deterministic repository-cleanup inventories without reading ignored private data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import mimetypes
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports/repository_cleanup"
BASELINE_EXCLUSIONS = {
    "scripts/research/build_repository_cleanup_inventory.py",
}
TEXT_SUFFIXES = {
    ".bib",
    ".cfg",
    ".cff",
    ".csv",
    ".ini",
    ".j2",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".rst",
    ".sh",
    ".sql",
    ".tex",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PATH_TOKEN = re.compile(r"(?<![\w.-])(?:\.\.?/)?[\w.@()+-]+(?:/[\w.@ ()+-]+)+")

INVENTORY_COLUMNS = [
    "path",
    "file_type",
    "size_bytes",
    "sha256",
    "git_tracked",
    "last_git_modification_commit",
    "likely_category",
]

DISPOSITION_COLUMNS = [
    "original_path",
    "sha256",
    "size_bytes",
    "category",
    "scientific_role",
    "referenced_by",
    "duplicate_of",
    "status",
    "proposed_action",
    "destination",
    "risk_level",
    "reason",
    "validation_required",
    "final_action",
]


def _git_lines(*args: str, nul: bool = False) -> list[str]:
    raw = subprocess.check_output(["git", "-C", str(ROOT), *args])
    separator = b"\0" if nul else b"\n"
    return [part.decode("utf-8", errors="surrogateescape") for part in raw.split(separator) if part]


def tracked_paths() -> list[str]:
    """Return all paths in the Git index."""
    return sorted(_git_lines("ls-files", "-z", nul=True))


def candidate_paths(*, baseline: bool) -> list[str]:
    """Return tracked and non-ignored untracked paths, excluding audit self-output."""
    paths = _git_lines(
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
        nul=True,
    )
    excluded = set(BASELINE_EXCLUSIONS) if baseline else set()
    return sorted(
        path
        for path in paths
        if path not in excluded and not path.startswith("reports/repository_cleanup/")
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def last_git_commit(relative: str, *, tracked: bool) -> str:
    if not tracked:
        return ""
    result = subprocess.run(
        ["git", "-C", str(ROOT), "log", "-1", "--format=%H", "--", relative],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def file_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or path.suffix.lower().lstrip(".") or "unknown"


def category(relative: str) -> str:
    first = relative.split("/", 1)[0]
    if relative.startswith(("build/", "dist/")) or "__pycache__" in relative:
        return "generated_build_output"
    if ".bak" in Path(relative).name:
        return "backup"
    if relative.startswith("docs/history/"):
        return "historical_documentation"
    if relative.startswith("artifacts/"):
        return "research_artifact"
    if relative.startswith("benchmarks/"):
        return "benchmark"
    if relative.startswith("src/"):
        return "package_source"
    if relative.startswith("tests/"):
        return "test_source"
    if relative.startswith("scripts/"):
        return "research_tooling"
    if relative.startswith(("paper/", "thesis/", "publication/")):
        return "manuscript_source"
    if relative.startswith(("claims/", "release/", "releases/")):
        return "release_evidence"
    if relative.startswith(("configs/", "experiments/", "prompts/")):
        return "experiment_definition"
    if first.startswith("."):
        return "repository_configuration"
    return "project_documentation_or_data"


def scientific_role(relative: str) -> str:
    if relative.startswith("artifacts/manifests/"):
        return "provenance manifest"
    if relative.startswith("artifacts/"):
        return "reported or derived research evidence"
    if relative.startswith("benchmarks/"):
        return "benchmark source, fixture, or protocol"
    if relative.startswith(("claims/", "experiments/")):
        return "claim or experiment provenance"
    if relative.startswith(("paper/", "thesis/")):
        return "scientific manuscript"
    if relative.startswith(("configs/", "prompts/")):
        return "experiment configuration or prompt"
    if relative.startswith("docs/history/"):
        return "historical research record"
    if relative.startswith("reports/"):
        return "derived analysis or audit"
    if relative.startswith(("src/", "scripts/", "tests/")):
        return "software or verification"
    return "repository support"


def _normalize_reference(source: str, token: str, candidates: set[str]) -> str | None:
    cleaned = token.strip("`'\"<>[]{}(),.;:").replace("\\", "/")
    while cleaned.startswith("../"):
        cleaned = cleaned[3:]
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    if cleaned in candidates:
        return cleaned
    resolved = (Path(source).parent / cleaned).as_posix()
    normalized = Path(resolved).as_posix()
    while normalized.startswith("../"):
        normalized = normalized[3:]
    return normalized if normalized in candidates else None


def references(paths: list[str]) -> dict[str, list[str]]:
    candidate_set = set(paths)
    reverse: dict[str, set[str]] = defaultdict(set)
    for source in paths:
        path = ROOT / source
        if (
            not path.is_file()
            or path.suffix.lower() not in TEXT_SUFFIXES
            or path.stat().st_size >= 8_000_000
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in PATH_TOKEN.findall(text):
            target = _normalize_reference(source, token, candidate_set)
            if target and target != source:
                reverse[target].add(source)
    return {target: sorted(sources) for target, sources in reverse.items()}


def proposed_disposition(
    relative: str,
    *,
    tracked: bool,
    duplicate_of: str,
) -> tuple[str, str, str, str, str, str]:
    name = Path(relative).name
    if relative.startswith(("build/", "dist/")) or "__pycache__" in relative:
        return (
            "generated",
            "DELETE_GENERATED",
            "",
            "low",
            "regenerable build or interpreter output",
            "quality gates and package build",
        )
    if name.endswith((".pyc", ".pyo")):
        return (
            "generated",
            "DELETE_GENERATED",
            "",
            "low",
            "regenerable Python bytecode",
            "quality gates",
        )
    if ".bak" in name:
        return (
            "historical_candidate",
            "ARCHIVE",
            "docs/history/",
            "medium",
            "ambiguous backup name; preserve content under a semantic historical path",
            "hash comparison and reference scan",
        )
    if relative.startswith(("artifacts/", "claims/", "experiments/", "docs/history/")):
        return (
            "retained_evidence",
            "RETAIN_AUDIT_EVIDENCE",
            relative,
            "high",
            "scientific evidence or historical provenance",
            "hash and claim-ledger verification",
        )
    if duplicate_of:
        return (
            "exact_byte_duplicate",
            "MANUAL_REVIEW_REQUIRED",
            "",
            "medium",
            "byte-identical content can still have a distinct scientific or packaging role",
            "reference, provenance, and release-role review",
        )
    if not tracked:
        return (
            "working_tree_candidate",
            "MANUAL_REVIEW_REQUIRED",
            "",
            "medium",
            "non-ignored untracked input or active work; ownership must be preserved",
            "owner and public/private boundary review",
        )
    return (
        "active",
        "KEEP",
        relative,
        "low",
        "canonical tracked source or documentation",
        "repository quality gates",
    )


def build_rows(*, baseline: bool) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    tracked = set(tracked_paths())
    candidates = candidate_paths(baseline=baseline)
    metadata: list[dict[str, object]] = []
    hashes: dict[str, list[str]] = defaultdict(list)
    for relative in candidates:
        path = ROOT / relative
        if not path.is_file():
            continue
        digest = sha256_file(path)
        hashes[digest].append(relative)
        is_tracked = relative in tracked
        metadata.append(
            {
                "path": relative,
                "file_type": file_type(path),
                "size_bytes": path.stat().st_size,
                "sha256": digest,
                "git_tracked": str(is_tracked).lower(),
                "last_git_modification_commit": last_git_commit(relative, tracked=is_tracked),
                "likely_category": category(relative),
            }
        )

    duplicate_of: dict[str, str] = {}
    for same_hash in hashes.values():
        if len(same_hash) < 2:
            continue
        canonical = sorted(same_hash)[0]
        for relative in sorted(same_hash)[1:]:
            duplicate_of[relative] = canonical

    reverse_references = references([str(row["path"]) for row in metadata])
    dispositions: list[dict[str, object]] = []
    for row in metadata:
        relative = str(row["path"])
        is_tracked = row["git_tracked"] == "true"
        duplicate = duplicate_of.get(relative, "")
        status, action, destination, risk, reason, validation = proposed_disposition(
            relative, tracked=is_tracked, duplicate_of=duplicate
        )
        dispositions.append(
            {
                "original_path": relative,
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
                "category": row["likely_category"],
                "scientific_role": scientific_role(relative),
                "referenced_by": ";".join(reverse_references.get(relative, [])),
                "duplicate_of": duplicate,
                "status": status,
                "proposed_action": action,
                "destination": destination,
                "risk_level": risk,
                "reason": reason,
                "validation_required": validation,
                "final_action": "PENDING",
            }
        )
    return metadata, dispositions


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def migration_destinations() -> dict[str, tuple[str, str]]:
    path = REPORT_DIR / "MIGRATION_MAP.csv"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["old_path"]: (row["new_path"], row["action"]) for row in csv.DictReader(handle)}


def finalize_dispositions(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    migrations = migration_destinations()
    for row in rows:
        relative = str(row["original_path"])
        proposed = str(row["proposed_action"])
        if proposed == "RETAIN_FROZEN_EVIDENCE":
            proposed = "RETAIN_AUDIT_EVIDENCE"
            row["proposed_action"] = proposed
        if relative in migrations:
            destination, action = migrations[relative]
            row["destination"] = destination
            row["final_action"] = action
        elif relative == "benchmarks/mgp6.zip":
            row["destination"] = "system Trash (recoverable)"
            row["final_action"] = "REMOVE_GENERATED_DUPLICATE"
        elif relative.startswith("tmp/"):
            row["final_action"] = "KEEP_LOCAL_IGNORED"
        elif relative.startswith("thesis/latex/compiled/"):
            row["final_action"] = "DELETE_GENERATED_AFTER_VALIDATION"
        elif str(row["status"]) == "exact_byte_duplicate":
            row["final_action"] = "KEEP_DISTINCT_ROLE"
        elif str(row["status"]) == "working_tree_candidate":
            row["final_action"] = "KEEP_USER_OWNED_INPUT"
        elif proposed == "MANUAL_REVIEW_REQUIRED":
            row["final_action"] = "KEEP_AFTER_ROLE_REVIEW"
        else:
            row["final_action"] = proposed
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true", help="exclude cleanup self-output")
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    args = parser.parse_args()

    inventory, dispositions = build_rows(baseline=args.baseline)
    output_dir = args.output_dir.resolve()
    inventory_name = "baseline_inventory.csv" if args.baseline else "final_inventory.csv"
    disposition_path = output_dir / "FILE_DISPOSITION.csv"
    if not args.baseline and disposition_path.is_file():
        dispositions = finalize_dispositions(read_csv(disposition_path))
    write_csv(output_dir / inventory_name, INVENTORY_COLUMNS, inventory)
    write_csv(disposition_path, DISPOSITION_COLUMNS, dispositions)
    print(
        f"wrote {len(inventory)} inventory rows and {len(dispositions)} dispositions to "
        f"{output_dir.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
