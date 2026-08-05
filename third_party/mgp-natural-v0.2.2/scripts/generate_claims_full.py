from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from mgp_natural.audits.claims import evidence_commitment
from mgp_natural.util.io import read_json, sha256_file


def _evidence(repo_root: Path, paths: list[str]) -> tuple[list[dict[str, str]], str]:
    records = [
        {"path": path, "sha256": sha256_file(repo_root / path)} for path in sorted(paths)
    ]
    return records, evidence_commitment(records)


def _claim(
    repo_root: Path,
    *,
    claim_id: str,
    wording: str,
    evidence_paths: list[str],
    qualifiers: list[str],
    prohibited: list[str],
    command: str,
) -> dict[str, Any]:
    records, commitment = _evidence(repo_root, evidence_paths)
    return {
        "id": claim_id,
        "wording": wording,
        "status": "QUALIFIED_SUPPORTED",
        "evidence": records,
        "evidence_hash": commitment,
        "generation_command": command,
        "applicable_version": "0.2.0-full-private-construction",
        "allowed_qualifiers": qualifiers,
        "prohibited_stronger_wording": prohibited,
    }


def build(repo_root: Path) -> dict[str, Any]:
    reports = repo_root / "reports"
    inventory = read_json(reports / "INPUT_INVENTORY_FULL.json")
    studychat_yield = read_json(reports / "STUDYCHAT_CANDIDATE_YIELD.json")
    wiki_yield = read_json(reports / "WIKICONV_CANDIDATE_YIELD.json")
    ai = read_json(reports / "AI_ANNOTATION_AGREEMENT.json")
    claims = [
        _claim(
            repo_root,
            claim_id="MGP-FULL-C001",
            wording=(
                "The supplied private full-source run verified 16,851 StudyChat interactions, "
                "172,286 WikiConv 2003 utterances, and 3,914,519 WikiConv 2018 utterances "
                "across all seven supplied 2018 parts."
            ),
            evidence_paths=["reports/INPUT_INVENTORY_FULL.json", "reports/SOURCE_INTEGRITY.json"],
            qualifiers=["These are supplied-source counts, not public redistribution permission."],
            prohibited=["The sources are cleared for public redistribution."],
            command="make full-audit-input",
        ),
        _claim(
            repo_root,
            claim_id="MGP-FULL-C002",
            wording=(
                f"Conservative full-source construction retained {studychat_yield['candidates']} "
                f"StudyChat candidates and {wiki_yield['candidates_selected']} bounded WikiConv "
                "candidate windows before human review."
            ),
            evidence_paths=[
                "reports/STUDYCHAT_CANDIDATE_YIELD.json",
                "reports/WIKICONV_CANDIDATE_YIELD.json",
            ],
            qualifiers=[
                "Constructor decisions are provisional and the bounded WikiConv sample is not a prevalence estimate."
            ],
            prohibited=["The retained candidates are independently annotated gold."],
            command="make full-privacy-blind",
        ),
        _claim(
            repo_root,
            claim_id="MGP-FULL-C003",
            wording=(
                f"Three blind offline provisional passes covered {ai['items']} private items; "
                "the resulting machine labels require human review and are not gold."
            ),
            evidence_paths=["reports/AI_ANNOTATION_AGREEMENT.json"],
            qualifiers=["The passes use one deterministic offline controller, not independent humans."],
            prohibited=["The project completed successful human annotation or adjudication."],
            command="make annotate-ai-provisional",
        ),
        _claim(
            repo_root,
            claim_id="MGP-FULL-C004",
            wording=(
                "Legal review, manual privacy review, independent human annotation, separate "
                "human adjudication, mapping-reveal authorization, and a release decision remain pending."
            ),
            evidence_paths=["reports/FULL_VALIDATION.json", "manifests/human_approvals.json"],
            qualifiers=["The public package command remains fail-closed."],
            prohibited=["MGP-Natural is publication-ready or approved for public release."],
            command="make readiness-full",
        ),
    ]
    ledger = {
        "schema_version": "2.0",
        "benchmark_version": "0.2.0-full-private-construction",
        "claims": claims,
    }
    ledger_path = repo_root / "claims" / "claim_ledger_full.yaml"
    ledger_path.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
    summary = [
        "---",
        "ai_generated: true",
        "artifact_status: full_private_execution_summary",
        "---",
        "",
        "# MGP-Natural full private execution summary",
        "",
        f"- StudyChat source rows verified: **{inventory['studychat']['canonical_records']:,}**",
        (
            "- WikiConv 2003 utterances verified: "
            f"**{inventory['wikiconv']['year_2003']['utterance_records']:,}**"
        ),
        (
            "- WikiConv 2018 utterances verified: "
            f"**{inventory['wikiconv']['year_2018']['utterance_records']:,}**"
        ),
        f"- StudyChat construction candidates: **{studychat_yield['candidates']:,}**",
        f"- Bounded WikiConv candidate windows: **{wiki_yield['candidates_selected']:,}**",
        f"- AI-provisional private items: **{ai['items']:,}**",
        "- AI-provisional outputs are not human gold.",
        "- Legal, privacy, human annotation, adjudication, and release gates remain pending.",
    ]
    (reports / "EXECUTION_SUMMARY_FULL.md").write_text("\n".join(summary) + "\n")
    boundary = [
        "---",
        "ai_generated: true",
        "artifact_status: claim_boundary",
        "---",
        "",
        "# Claim boundary",
        "",
        "Do not claim independently annotated gold.",
        "Do not claim publication-ready status.",
        "Do not claim legal approval, privacy approval, or public redistribution rights.",
        "Do not claim state-of-the-art results, external generalization, or JMLR-ready status.",
        "",
        "Allowed statements must remain qualified as private, provisional, and human-review pending.",
    ]
    (repo_root / "paper" / "CLAIM_BOUNDARY_UPDATED.md").write_text(
        "\n".join(boundary) + "\n"
    )
    result_status = [
        "---",
        "ai_generated: true",
        "artifact_status: result_status",
        "---",
        "",
        "# Result status",
        "",
        "All machine-label analyses are exploratory AI-provisional references only.",
        "Human gold is absent and publication eligibility is false.",
    ]
    (repo_root / "paper" / "RESULT_STATUS_UPDATED.md").write_text(
        "\n".join(result_status) + "\n"
    )
    return ledger


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the full-source claim ledger")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(json.dumps(build(args.repo_root.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()

