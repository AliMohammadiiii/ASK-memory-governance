#!/usr/bin/env python3
"""Assemble the private handoff and a separately sanitized public repository."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "final_release"
STAGE = ROOT / "final_release.__building__"
OUTER_NAME = "ask_memory_governance_final_2026-07-15.zip"

PUBLIC_EXCLUDED_PREFIXES = (
    ".git/",
    ".serena/",
    ".venv/",
    "audit_workspace/",
    "build/",
    "data/external/",
    "dist/",
    "docs/history/",
    "final_release/",
    "inputs_raw/",
    "phd_application/",
    "presentation/",
    "runs/",
    "runs_local/",
    "thesis/compiled/",
    "tmp/",
)

PUBLIC_EXCLUDED_FILES = {
    "benchmarks/mgp6/annotations/human/human_independent_annotations_test.csv",
    "benchmarks/mgp6/annotations/human/human_vs_author_disagreements.csv",
    "benchmarks/mgp6/annotations/model_or_mixed/geminiPro.csv",
    "benchmarks/mgp6/annotations/model_or_mixed/gptSolHigh.csv",
    "benchmarks/mgp6/annotations/model_or_mixed/independent_annotations_test.csv",
    "benchmarks/mgp6/annotations/model_or_mixed/kimi.csv",
    "benchmarks/mgp6/annotations/model_or_mixed/mgp6_consensus_all_test.csv",
    "benchmarks/mgp6/annotations/model_or_mixed/mgp6_disagreements_for_adjudication.csv",
    "benchmarks/mgp6/annotations/model_or_mixed/mgp6_v2(1).jsonl",
    "benchmarks/mgp6/annotations/model_or_mixed/mgp6_v2_test_blind_annotation.jsonl",
    "benchmarks/mgp6/annotations/model_or_mixed/z.csv",
}

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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_tree(source: Path, target: Path, *, exclude_parts: set[str] | None = None) -> None:
    excluded = exclude_parts or set()
    for path in sorted(source.rglob("*")):
        if not path.is_file() or any(part in excluded for part in path.relative_to(source).parts):
            continue
        copy_file(path, target / path.relative_to(source))


def public_candidates() -> list[Path]:
    listed = subprocess.check_output(
        [
            "git",
            "-C",
            str(ROOT),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ]
    )
    candidates: list[Path] = []
    for raw in listed.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", errors="surrogateescape")
        path = ROOT / rel
        if not path.is_file():
            continue
        if rel in PUBLIC_EXCLUDED_FILES:
            continue
        if rel.startswith(PUBLIC_EXCLUDED_PREFIXES):
            continue
        if "/compiled/" in f"/{rel}" or ".egg-info/" in rel:
            continue
        if "__pycache__" in path.parts or path.name == ".DS_Store":
            continue
        if path.suffix in {
            ".aux",
            ".bbl",
            ".blg",
            ".fdb_latexmk",
            ".fls",
            ".log",
            ".out",
            ".tmp",
        }:
            continue
        candidates.append(path)
    return sorted(candidates)


def build_public_repository(target: Path) -> dict[str, int]:
    candidates = public_candidates()
    for source in candidates:
        copy_file(source, target / source.relative_to(ROOT))
    write_repository_file_manifest(target)
    scan_public_repository(target)
    public_files = [path for path in target.rglob("*") if path.is_file()]
    return {
        "files": len(public_files),
        "size_bytes": sum(path.stat().st_size for path in public_files),
    }


def write_repository_file_manifest(repo: Path) -> None:
    """Hash the public snapshot while excluding the recursive manifest itself."""
    manifest = repo / "artifacts/manifests/repository_files.json"
    rows = []
    for path in sorted(repo.rglob("*")):
        if not path.is_file() or path == manifest:
            continue
        rows.append(
            {
                "path": path.relative_to(repo).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def scan_public_repository(repo: Path) -> None:
    secret_patterns = (
        re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"),
        re.compile(r"sk-[A-Za-z0-9_-]{24,}"),
    )
    forbidden_text = (str(Path.home()),)
    forbidden_names = {
        "answers.jsonl",
        "judgments.jsonl",
        "human_independent_annotations_test.csv",
        "human_vs_author_disagreements.csv",
    }
    errors: list[str] = []
    for path in sorted(repo.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo).as_posix()
        if path.name in forbidden_names or path.suffix == ".log":
            errors.append(f"forbidden public artifact: {rel}")
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 8_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in secret_patterns):
            errors.append(f"possible embedded secret: {rel}")
        if any(token in text for token in forbidden_text):
            errors.append(f"machine-local absolute path: {rel}")
    if errors:
        raise SystemExit("public repository sanitization failed:\n- " + "\n- ".join(errors))


def write_zip(source: Path, output: Path, *, prefix: str, skip: set[str] | None = None) -> None:
    skipped = skip or set()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(source).as_posix()
            if rel in skipped:
                continue
            archive.write(path, f"{prefix}/{rel}")


def assemble_results(stage: Path, public_repo: Path) -> None:
    ledger = stage / "results/ledger"
    for rel in (
        "artifacts/results_ledger.json",
        "artifacts/results_ledger.csv",
        "artifacts/analysis/mgp6_validity_audit.json",
        "artifacts/analysis/mgp6_validity_audit.md",
        "docs/audit/SCIENTIFIC_SOURCE_OF_TRUTH.md",
        "docs/audit/CLAIM_ELIGIBILITY.md",
    ):
        copy_file(ROOT / rel, ledger / Path(rel).name)

    tables = stage / "results/final_tables"
    for rel in (
        "reports/FINAL_RESULTS.md",
        "reports/FINAL_RESULTS.json",
        "reports/STATISTICAL_ANALYSIS.md",
        "reports/statistical_analysis_raw_output.txt",
        "artifacts/results/mgp6_few6_report.json",
    ):
        copy_file(ROOT / rel, tables / Path(rel).name)

    figures = stage / "results/final_figures"
    copy_tree(ROOT / "docs/figures", figures / "canonical")
    copy_tree(ROOT / "presentation/figures", figures / "defense")

    manifests = stage / "results/run_manifests"
    copy_tree(ROOT / "artifacts/manifests", manifests / "artifacts")
    copy_file(
        public_repo / "artifacts/manifests/repository_files.json",
        manifests / "artifacts/repository_files.json",
    )
    for rel in (
        "FINAL_EVALUATION_PROTOCOL.md",
        "FINAL_ANALYSIS_PLAN.md",
        "FINAL_METRIC_DEFINITIONS.md",
        "FINAL_RUN_MATRIX.yaml",
        "configs/release/final.yaml",
        "EVIDENCE_REGISTRY.yaml",
        "EXPERIMENT_REGISTRY.yaml",
    ):
        copy_file(ROOT / rel, manifests / rel)


def assemble_paper(stage: Path) -> None:
    paper = stage / "paper"
    copy_tree(ROOT / "paper/paper_1", paper / "canonical", exclude_parts={"compiled"})
    copy_file(ROOT / "paper/paper_1/compiled/main.pdf", paper / "compiled/paper.pdf")
    copy_file(ROOT / "paper/paper_1/compiled/build_log.txt", paper / "compiled/build_log.txt")
    copy_file(ROOT / "paper/VENUE_VARIANT_README.md", paper / "venue_variant/README.md")
    copy_file(
        ROOT / "paper/PUBLICATION_STRATEGY.md",
        paper / "venue_variant/PUBLICATION_STRATEGY.md",
    )
    for rel in (
        "paper/paper_1/claims_evidence_matrix.md",
        "paper/paper_1/response_to_reviewers_simulation.md",
        "paper/paper_1/artifact_appendix.md",
        "reports/REPRODUCIBILITY_CHECKLIST.md",
    ):
        copy_file(ROOT / rel, paper / "checklist" / Path(rel).name)


def assemble_thesis(stage: Path) -> None:
    thesis = stage / "thesis"
    english = thesis / "english"
    for rel in (
        "thesis/MASTERS_THESIS_ASK_MGP6.md",
        "thesis/README.md",
        "thesis/THESIS_NUMBER_AUDIT.md",
        "thesis/claims_evidence_matrix.md",
        "thesis/contribution_summary.md",
        "thesis/two_page_summary.md",
        "thesis/thesis_checklist.md",
        "thesis/references.bib",
        "thesis/references/README.md",
        "thesis/tools/build_review_docx.py",
    ):
        copy_file(ROOT / rel, english / Path(rel).name)
    copy_tree(ROOT / "thesis/frontmatter", thesis / "persian")
    copy_file(
        ROOT / "thesis/compiled/ASK_Masters_Thesis_English_Review_Draft.docx",
        thesis / "compiled/ASK_Masters_Thesis_English_Review_Draft.docx",
    )
    copy_file(
        ROOT / "thesis/compiled/ASK_Masters_Thesis_English_Review_Draft.pdf",
        thesis / "compiled/ASK_Masters_Thesis_English_Review_Draft.pdf",
    )
    copy_file(ROOT / "thesis/compiled/QA_REPORT.md", thesis / "compiled/QA_REPORT.md")
    copy_file(
        ROOT / "thesis/defense_questions.md",
        thesis / "defense_questions/defense_questions.md",
    )


def assemble_presentation(stage: Path) -> None:
    presentation = stage / "presentation"
    for name in ("defense_en.pptx", "defense_en.pdf", "defense_fa.pptx", "defense_fa.pdf"):
        copy_file(ROOT / "presentation" / name, presentation / name)
    copy_tree(ROOT / "presentation/speaker_notes", presentation / "speaker_notes")
    copy_tree(ROOT / "presentation/figures", presentation / "figures")
    copy_file(ROOT / "presentation/REHEARSAL_GUIDE.md", presentation / "REHEARSAL_GUIDE.md")


def assemble_reports_and_application(stage: Path) -> None:
    copy_tree(ROOT / "phd_application", stage / "phd_application")
    for name in (
        "FINAL_HANDOFF.md",
        "COMPLETION_MATRIX.md",
        "REMAINING_EXTERNAL_ACTIONS.md",
        "VALIDATION_REPORT.md",
    ):
        copy_file(ROOT / "reports" / name, stage / "reports" / name)


def write_release_manifest(stage: Path, public_stats: dict[str, int]) -> None:
    payload = {
        "release": "ask-memory-governance-final",
        "release_date": "2026-07-15",
        "ledger_version": "1.1",
        "ledger_sha256": sha256_file(ROOT / "artifacts/results_ledger.json"),
        "freeze_version": "final-2.0",
        "scientific_status": {
            "mgp6": "diagnostic_construct_gate_failed",
            "mgp6_confirmation_v3": "externally_pending_independent_labor",
            "longmemeval": "externally_pending",
            "longmemeval_reason": "V12 post-hoc confirmatory rerun pending external execution",
        },
        "public_repository": public_stats,
        "public_exclusions": [
            "LongMemEval data and run outputs",
            "secrets and machine-local paths",
            "private Cambridge application materials",
            "compiled personal thesis/presentation artifacts",
            "raw independent-human annotations pending written consent",
            "per-item model-annotation rationales",
        ],
        "outer_archive": OUTER_NAME,
        "generated_at_utc": dt.datetime.now(dt.UTC).isoformat(),
    }
    (stage / "RELEASE_MANIFEST.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_checksums(stage: Path) -> None:
    checksum_path = stage / "SHA256SUMS"
    rows = []
    for path in sorted(stage.rglob("*")):
        if not path.is_file() or path == checksum_path:
            continue
        rows.append(f"{sha256_file(path)}  {path.relative_to(stage).as_posix()}")
    checksum_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def safely_remove_generated(path: Path) -> None:
    if path.resolve().parent != ROOT.resolve() or path.name not in {
        "final_release",
        "final_release.__building__",
    }:
        raise SystemExit(f"refusing to remove unexpected path: {path}")
    if path.exists():
        shutil.rmtree(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace only the generated final_release directory",
    )
    args = parser.parse_args()

    if OUT.exists() and not args.replace:
        raise SystemExit(f"{OUT} exists; pass --replace to rebuild the generated release")
    safely_remove_generated(STAGE)
    if args.replace:
        safely_remove_generated(OUT)
    STAGE.mkdir(parents=True)

    public_repo = STAGE / "repository/ask-memory-governance"
    public_stats = build_public_repository(public_repo)
    write_zip(
        public_repo,
        STAGE / "repository/ask-memory-governance-final.zip",
        prefix="ask-memory-governance",
    )
    assemble_results(STAGE, public_repo)
    assemble_paper(STAGE)
    assemble_thesis(STAGE)
    assemble_presentation(STAGE)
    assemble_reports_and_application(STAGE)
    copy_file(ROOT / "reports/FINAL_HANDOFF.md", STAGE / "README.md")
    write_release_manifest(STAGE, public_stats)
    write_checksums(STAGE)

    STAGE.replace(OUT)
    outer = OUT / OUTER_NAME
    write_zip(
        OUT,
        outer,
        prefix="final_release",
        skip={OUTER_NAME, "OUTER_ZIP.sha256"},
    )
    (OUT / "OUTER_ZIP.sha256").write_text(f"{sha256_file(outer)}  {OUTER_NAME}\n", encoding="utf-8")
    print(f"built {OUT}")
    print(f"outer archive: {outer}")
    print(f"public repository files: {public_stats['files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
