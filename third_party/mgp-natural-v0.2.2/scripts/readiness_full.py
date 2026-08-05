from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from mgp_natural.util.io import read_json, write_json


def _pass(path: Path, field: str = "status", accepted: set[str] | None = None) -> bool:
    if not path.is_file():
        return False
    value = read_json(path)
    observed = value.get(field)
    return observed in (accepted or {"PASS", "VALID", "VERIFIED"})


def _exists_all(paths: list[Path]) -> bool:
    return all(path.is_file() for path in paths)


def build(repo_root: Path) -> dict[str, Any]:
    reports = repo_root / "reports"
    inventory = read_json(reports / "INPUT_INVENTORY_FULL.json") if (reports / "INPUT_INVENTORY_FULL.json").is_file() else {}
    split = read_json(reports / "SPLIT_AUDIT_FULL.json") if (reports / "SPLIT_AUDIT_FULL.json").is_file() else {}
    full_validation = read_json(reports / "FULL_VALIDATION.json") if (reports / "FULL_VALIDATION.json").is_file() else {}
    machine_gates = {
        "full_input_inventory": _pass(reports / "SOURCE_INTEGRITY.json"),
        "studychat_full_reconstruction": _exists_all(
            [
                reports / "STUDYCHAT_FULL_RECONSTRUCTION.json",
                reports / "STUDYCHAT_CANDIDATE_YIELD.json",
            ]
        ),
        "wikiconv_full_streaming_and_candidate_construction": _exists_all(
            [
                reports / "WIKICONV_2003_RECONSTRUCTION.json",
                reports / "WIKICONV_2018_RECONSTRUCTION.json",
                reports / "WIKICONV_CANDIDATE_YIELD.json",
            ]
        ),
        "automated_privacy_processing": _exists_all(
            [
                reports / "PII_SCAN_FULL.json",
                reports / "MANUAL_PRIVACY_REVIEW_QUEUE.csv",
            ]
        ),
        "blinding_and_leakage_scan": _pass(
            reports / "FULL_PRIVATE_PACKET_VERIFICATION.json",
            accepted={"VERIFIED"},
        ),
        "AI_provisional_annotation": _exists_all(
            [
                reports / "AI_ANNOTATION_AGREEMENT.json",
                repo_root
                / "data"
                / "derived"
                / "ai_provisional"
                / "consensus.ai_provisional.jsonl",
            ]
        ),
        "separate_track_continuity_splits": bool(split.get("all_track_splits_valid")),
        "tests": _pass(reports / "pytest_results.json"),
        "ruff": _pass(reports / "ruff.json"),
        "mypy": _pass(reports / "mypy.json"),
        "build": _pass(reports / "build_artifacts.json"),
        "claim_verification": _pass(
            repo_root / "claims" / "mismatch_report_full.json"
        ),
        "full_validation": full_validation.get("status")
        == "PASS_MACHINE_VALIDATION_HUMAN_GATES_PENDING",
        "paper_and_docs": _exists_all(
            [
                repo_root / "paper" / "main_anonymous.tex",
                repo_root / "paper" / "AI_USE_STATEMENT.md",
                repo_root / "docs" / "AI_ANNOTATION_PROTOCOL.md",
            ]
        ),
    }
    human_gates = {
        "human_legal_and_redistribution_approval": False,
        "manual_privacy_review": False,
        "annotation_protocol_human_approval": False,
        "independent_human_annotation": False,
        "independent_human_adjudication": False,
        "mapping_reveal_authorization": False,
        "authorship_confirmation": False,
        "current_venue_compliance_human_review": False,
        "public_release_decision": False,
    }
    source_completeness = {
        "studychat": inventory.get("studychat", {}).get("canonical_records") == 16851,
        "wikiconv_2003": inventory.get("wikiconv", {})
        .get("year_2003", {})
        .get("utterance_records")
        == 172286,
        "wikiconv_2018": inventory.get("wikiconv", {})
        .get("year_2018", {})
        .get("utterance_records")
        == 3914519,
    }
    all_machine = all(machine_gates.values())
    all_human = all(human_gates.values())
    result = {
        "schema_version": "2.0",
        "run_id": "full-natural-20260804-v2",
        "final_verdict": "NO_GO_FOR_PUBLICATION_AND_PUBLIC_RELEASE",
        "engineering_status": (
            "PRIVATE_AI_PROVISIONAL_RESOURCE_MACHINE_COMPLETE"
            if all_machine
            else "NO_GO_MACHINE_GATES_REMAIN"
        ),
        "publication_eligible": False,
        "public_release_ready": False,
        "human_gold_items": 0,
        "source_completeness": source_completeness,
        "machine_gates": machine_gates,
        "human_gates": human_gates,
        "all_machine_gates_pass": all_machine,
        "all_human_gates_pass": all_human,
        "private_AI_provisional_resource": all_machine,
        "tmlr_ready": False,
        "jmlr_ready": False,
    }
    write_json(reports / "readiness_full.json", result)
    go_no_go = [
        "---",
        "ai_generated: true",
        "artifact_status: readiness_decision",
        "---",
        "",
        "# Go / no-go",
        "",
        "## NO_GO_FOR_PUBLICATION_AND_PUBLIC_RELEASE",
        "",
        f"Machine gates complete: **{all_machine}**",
        "",
        "Human legal, privacy, annotation, adjudication, authorship, venue, and release gates remain pending.",
    ]
    (reports / "GO_NO_GO_FULL.md").write_text("\n".join(go_no_go) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate full-source readiness status")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(json.dumps(build(args.repo_root.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()

