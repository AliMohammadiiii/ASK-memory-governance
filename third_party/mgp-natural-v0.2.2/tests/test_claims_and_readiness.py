from __future__ import annotations

import json
from pathlib import Path

import pytest

from mgp_natural.audits.claims import verify_claims
from mgp_natural.audits.readiness import (
    JMLR_ADDITIONAL_GATES,
    TMLR_HUMAN_GATES,
    TMLR_MACHINE_GATES,
    generate_readiness,
)
from mgp_natural.errors import ValidationError


def test_readiness_fail_closed() -> None:
    report = generate_readiness({}, {})
    assert report["verdict"] == "NO_GO"
    assert report["tmlr_machine_complete"] is False
    assert report["jmlr_ready"] is False


def test_machine_ready_human_pending() -> None:
    machine = {gate: True for gate in TMLR_MACHINE_GATES}
    report = generate_readiness(machine, {})
    assert report["verdict"] == "MACHINE_READY_HUMAN_GATES_PENDING"


def test_public_ready_only_with_all_human_gates() -> None:
    machine = {gate: True for gate in TMLR_MACHINE_GATES}
    human = {gate: True for gate in TMLR_HUMAN_GATES}
    report = generate_readiness(machine, human)
    assert report["verdict"] == "PUBLIC_RELEASE_READY"
    assert report["jmlr_ready"] is False
    human.update({gate: True for gate in JMLR_ADDITIONAL_GATES})
    assert generate_readiness(machine, human)["jmlr_ready"] is True


def test_claim_verifier_rejects_unqualified_prohibited_claim(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}", encoding="utf-8")
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(
        "claims:\n  - id: C1\n    wording: qualified\n    status: SUPPORTED\n"
        f"    evidence: {evidence.as_posix()}\n    evidence_hash: {'0' * 64}\n",
        encoding="utf-8",
    )
    document = tmp_path / "paper.md"
    document.write_text("This is the first benchmark.", encoding="utf-8")
    with pytest.raises(ValidationError, match="claim verification failed"):
        verify_claims(ledger, [document], tmp_path / "out.json")


def test_readiness_markdown_reports_are_fail_closed() -> None:
    from mgp_natural.audits.readiness import render_go_no_go, render_remaining_actions

    report = generate_readiness({}, {})
    decision = render_go_no_go(report)
    actions = render_remaining_actions(report)
    assert "`NO_GO`" in decision
    assert "Publication eligible: `false`" in decision
    assert "legal_and_redistribution_approval" in actions
    assert "Do not accept gated terms" in actions


def test_execution_summary_preserves_no_go_boundaries(tmp_path: Path) -> None:
    from mgp_natural.audits.execution import build_execution_summary

    reports = tmp_path / "reports"
    reports.mkdir()

    def write(name: str, value: object) -> None:
        (reports / name).write_text(json.dumps(value), encoding="utf-8")

    write(
        "STUDYCHAT_INPUT_SCOPE.json",
        {
            "classification": "SAMPLE_DERIVATIVE",
            "observed_available": {"candidate_rows": 1, "long_chat_records": 1},
            "metadata_only_expected_full_source": True,
            "full_release_gate": "BLOCKED",
        },
    )
    write("input_manifest.json", {"source_facts": {"outer_archive": "fixture.zip"}})
    write(
        "studychat_reconstruction.json",
        {
            "canonical_interactions": 1,
            "canonical_chats": 1,
            "canonical_users": 1,
            "anomaly_count": 0,
            "anomaly_codes": [],
            "messages_used_for_reconstruction": False,
        },
    )
    write(
        "studychat_candidate_yield.json",
        {
            "candidates": 0,
            "scope_counts": {},
            "action_counts_provisional_only": {},
            "rejected": 1,
            "rejection_reasons": {},
        },
    )
    write("wikiconv_fixture_candidate_yield.json", {"candidates": 1, "scope_counts": {}})
    write("WIKICONV_ACQUISITION_ATTEMPT.json", {"status": "NOT_ACQUIRED"})
    write(
        "studychat_continuity.json",
        {
            "items": 0,
            "components": 0,
            "component_sizes": [],
            "largest_component_size": 0,
            "largest_component_share": 0.0,
            "exact_text_duplicate_pairs": 0,
            "near_duplicate_edges": 0,
        },
    )
    write(
        "studychat_split_audit.json",
        {
            "status": "BLOCKED",
            "split_audit_passed": False,
            "split_counts": {},
            "empty_splits": ["dev", "test"],
            "crossing_components": 0,
        },
    )
    write("PII_SCAN.json", {})
    write("LICENSE_BLOCKERS.json", {})
    write("private_packet_verification.json", {"status": "VERIFIED"})
    write("pytest_results.json", {})
    write("offline_static_checks.json", {})
    write("ENVIRONMENT_TOOLCHAIN.json", {})
    write("build_artifacts.json", {})
    write("build_reproducibility.json", {})
    write("clean_reproduction.json", {})
    write("private_permissions.json", {})
    write("security_scan.json", {})
    write(
        "readiness.json",
        {
            "verdict": "NO_GO",
            "publication_eligible": False,
            "blocked": {"tmlr_human": [], "tmlr_machine": [], "jmlr_additional": []},
        },
    )
    claims = tmp_path / "claims"
    claims.mkdir()
    (claims / "claim_ledger.yaml").write_text("claims: []\n", encoding="utf-8")

    report = build_execution_summary(tmp_path)
    assert report["verdict"] == "NO_GO"
    assert report["studychat_input"]["classification"] == "SAMPLE_DERIVATIVE"
    assert report["candidate_counts"]["WIKICONV"]["natural_candidates"] == 0
    assert report["splits"]["passed"] is False
    assert report["publication_eligible"] is False
