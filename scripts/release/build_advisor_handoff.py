#!/usr/bin/env python3
"""Build a sanitized, review-only snapshot for the academic advisor."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from build_final_release import (
    ROOT,
    copy_file,
    public_candidates,
    scan_public_repository,
    sha256_file,
    write_repository_file_manifest,
    write_zip,
)

OUT = ROOT / "advisor_handoff"
STAGE = ROOT / "advisor_handoff.__building__"
REPOSITORY_NAME = "ask-memory-governance-advisor"
ARCHIVE_NAME = f"{REPOSITORY_NAME}.zip"
ADVISOR_EXCLUDED_FILES = {
    "AGENTS.md",
    "BLOCKERS.md",
    "DECISION_LOG.md",
    "GIT_PUSH_GUIDE.md",
    "INIT_GIT.sh",
    "MASTER_EXECUTION_STATUS.md",
    "MGP6_Paper_Publication_Novelty_Action_Plan_FA.md",
    "PROJECT_STATE.md",
    "WORKPLAN.md",
    "research/MASTER_EXECUTION_PROMPT.md",
}


def safely_remove_generated(path: Path) -> None:
    """Remove only the two generated advisor-handoff directories."""
    allowed = {OUT.name, STAGE.name}
    if path.resolve().parent != ROOT.resolve() or path.name not in allowed:
        raise SystemExit(f"refusing to remove unexpected path: {path}")
    if path.exists():
        shutil.rmtree(path)


def source_state() -> dict[str, object]:
    """Record review provenance without embedding a machine-local path."""
    commit = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
    ).strip()
    status = subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True)
    return {
        "schema_version": "advisor-review-snapshot-1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "source_commit": commit,
        "includes_uncommitted_candidates": bool(status.strip()),
        "publication_readiness": json.loads(
            (ROOT / "reports/readiness.json").read_text(encoding="utf-8")
        )["status"],
    }


def build_snapshot() -> tuple[Path, int]:
    """Assemble and scan the review tree, then create its archive."""
    repository = STAGE / REPOSITORY_NAME
    candidates = [
        path
        for path in public_candidates(include_untracked=True)
        if path.relative_to(ROOT).as_posix() not in ADVISOR_EXCLUDED_FILES
    ]
    for source in candidates:
        copy_file(source, repository / source.relative_to(ROOT))

    paper_pdf = ROOT / "paper/paper_1/compiled/main.pdf"
    if not paper_pdf.is_file():
        raise SystemExit("compiled paper is missing; build paper/paper_1/compiled/main.pdf first")
    copy_file(paper_pdf, repository / "paper/ASK_paper.pdf")

    metadata = source_state()
    metadata_path = repository / "reports/ADVISOR_SNAPSHOT.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    write_repository_file_manifest(repository)
    scan_public_repository(repository)

    archive = STAGE / ARCHIVE_NAME
    write_zip(repository, archive, prefix=REPOSITORY_NAME)
    (STAGE / f"{ARCHIVE_NAME}.sha256").write_text(
        f"{sha256_file(archive)}  {ARCHIVE_NAME}\n", encoding="utf-8"
    )
    return archive, len([path for path in repository.rglob("*") if path.is_file()])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--replace", action="store_true", help="replace only the generated advisor handoff"
    )
    action.add_argument(
        "--clean", action="store_true", help="remove only generated advisor handoff outputs"
    )
    args = parser.parse_args()

    if args.clean:
        safely_remove_generated(STAGE)
        safely_remove_generated(OUT)
        print("removed generated advisor handoff outputs")
        return 0

    if OUT.exists() and not args.replace:
        raise SystemExit(f"{OUT} exists; pass --replace to rebuild it")
    safely_remove_generated(STAGE)
    if args.replace:
        safely_remove_generated(OUT)
    STAGE.mkdir(parents=True)

    archive, file_count = build_snapshot()
    STAGE.replace(OUT)
    final_archive = OUT / archive.name
    print(f"built {final_archive}")
    print(f"snapshot files: {file_count}")
    print(f"sha256: {sha256_file(final_archive)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
