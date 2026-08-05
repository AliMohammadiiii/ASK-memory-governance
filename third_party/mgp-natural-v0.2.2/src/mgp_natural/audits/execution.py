"""Generate a consolidated, machine-readable execution summary."""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from mgp_natural.errors import ValidationError
from mgp_natural.util.io import read_json, write_json


def _load(root: Path, relative: str) -> dict[str, Any]:
    value = read_json(root / relative)
    if not isinstance(value, dict):
        raise ValidationError(f"expected JSON object: {relative}")
    return cast(dict[str, Any], value)


def build_execution_summary(root: Path) -> dict[str, Any]:
    root = root.resolve()
    scope = _load(root, "reports/STUDYCHAT_INPUT_SCOPE.json")
    inventory = _load(root, "reports/input_manifest.json")
    reconstruction = _load(root, "reports/studychat_reconstruction.json")
    studychat_yield = _load(root, "reports/studychat_candidate_yield.json")
    wikiconv_yield = _load(root, "reports/wikiconv_fixture_candidate_yield.json")
    wikiconv_acquisition = _load(root, "reports/WIKICONV_ACQUISITION_ATTEMPT.json")
    continuity = _load(root, "reports/studychat_continuity.json")
    split = _load(root, "reports/studychat_split_audit.json")
    privacy = _load(root, "reports/PII_SCAN.json")
    licenses = _load(root, "reports/LICENSE_BLOCKERS.json")
    packet = _load(root, "reports/private_packet_verification.json")
    tests = _load(root, "reports/pytest_results.json")
    static = _load(root, "reports/offline_static_checks.json")
    toolchain = _load(root, "reports/ENVIRONMENT_TOOLCHAIN.json")
    build = _load(root, "reports/build_artifacts.json")
    build_reproducibility = _load(root, "reports/build_reproducibility.json")
    clean = _load(root, "reports/clean_reproduction.json")
    permissions = _load(root, "reports/private_permissions.json")
    security = _load(root, "reports/security_scan.json")
    readiness = _load(root, "reports/readiness.json")
    claims = yaml.safe_load((root / "claims/claim_ledger.yaml").read_text(encoding="utf-8"))
    allowed = [
        {"id": claim["id"], "wording": claim["wording"], "status": claim["status"]}
        for claim in claims.get("claims", [])
        if claim.get("status") in {"SUPPORTED", "QUALIFIED_SUPPORTED"}
    ]
    prohibited = [
        {"id": claim["id"], "wording": claim["wording"], "status": claim["status"]}
        for claim in claims.get("claims", [])
        if str(claim.get("status", "")).startswith("PROHIBITED")
    ]
    return {
        "schema_version": "1.0",
        "verdict": readiness["verdict"],
        "publication_eligible": readiness["publication_eligible"],
        "studychat_input": {
            "classification": scope["classification"],
            "archive": inventory["source_facts"]["outer_archive"],
            "observed_available": scope["observed_available"],
            "metadata_only_expected_full_source": scope["metadata_only_expected_full_source"],
            "full_release_gate": scope["full_release_gate"],
        },
        "observed_reconstruction": {
            "interactions": reconstruction["canonical_interactions"],
            "chats": reconstruction["canonical_chats"],
            "users": reconstruction["canonical_users"],
            "anomalies": reconstruction["anomaly_count"],
            "anomaly_codes": reconstruction["anomaly_codes"],
            "messages_used_for_reconstruction": reconstruction["messages_used_for_reconstruction"],
        },
        "candidate_counts": {
            "STUDYCHAT": {
                "natural_provisional_candidates": studychat_yield["candidates"],
                "scopes": studychat_yield["scope_counts"],
                "constructor_actions": studychat_yield["action_counts_provisional_only"],
                "construction_status": "PROVISIONAL_CANDIDATE_NOT_GOLD",
                "rejected": studychat_yield["rejected"],
                "rejection_reasons": studychat_yield["rejection_reasons"],
            },
            "WIKICONV": {
                "natural_candidates": 0,
                "natural_acquisition_status": wikiconv_acquisition["status"],
                "synthetic_fixture_candidates": wikiconv_yield["candidates"],
                "synthetic_fixture_scopes": wikiconv_yield["scope_counts"],
                "construction_status": "SYNTHETIC_FIXTURE_ONLY_NOT_NATURAL_BENCHMARK_DATA",
            },
        },
        "continuity": {
            "items": continuity["items"],
            "components": continuity["components"],
            "component_sizes": continuity["component_sizes"],
            "largest_component_size": continuity["largest_component_size"],
            "largest_component_share": continuity["largest_component_share"],
            "exact_text_duplicate_pairs": continuity["exact_text_duplicate_pairs"],
            "near_duplicate_edges": continuity["near_duplicate_edges"],
        },
        "splits": {
            "status": split["status"],
            "passed": split["split_audit_passed"],
            "counts": split["split_counts"],
            "empty_splits": split["empty_splits"],
            "crossing_components": split["crossing_components"],
        },
        "privacy": privacy,
        "private_packet": packet,
        "license_and_redistribution": licenses,
        "annotation_readiness": {
            "packet_structurally_verified": packet["status"] == "VERIFIED",
            "independent_annotation_exists": False,
            "independent_adjudication_exists": False,
            "manual_privacy_review_complete": False,
            "protocol_human_approved": False,
        },
        "engineering_validation": {
            "tests": tests,
            "supplementary_static_checks": static,
            "named_toolchain": toolchain,
            "build": build,
            "build_reproducibility": build_reproducibility,
            "clean_reproduction": clean,
            "private_permissions": permissions,
            "security_scan": security,
        },
        "readiness": readiness,
        "allowed_claims": allowed,
        "prohibited_claims": prohibited,
        "remaining_human_actions": readiness["blocked"]["tmlr_human"],
        "reproduction_commands": [
            "make install",
            "make check",
            "make reproduce",
            "make readiness",
            "make package-public  # expected to fail while gates are unresolved",
        ],
    }


def write_execution_summary(root: Path, output: Path) -> dict[str, Any]:
    report = build_execution_summary(root)
    write_json(output, report)
    return report


def render_execution_summary(report: dict[str, Any]) -> str:
    study = report["studychat_input"]
    reconstruction = report["observed_reconstruction"]
    candidates = report["candidate_counts"]
    continuity = report["continuity"]
    splits = report["splits"]
    privacy = report["privacy"]
    engineering = report["engineering_validation"]
    lines = [
        "# MGP-Natural Execution Summary",
        "",
        f"**Verdict: `{report['verdict']}`. Publication eligible: `{str(report['publication_eligible']).lower()}`.**",
        "",
        "## Input and reconstruction",
        "",
        f"- StudyChat input classification: `{study['classification']}`.",
        f"- Available derivative: {study['observed_available']['candidate_rows']:,} candidate rows and {study['observed_available']['long_chat_records']:,} sampled long chats.",
        f"- Canonical reconstruction: {reconstruction['interactions']:,} interactions, {reconstruction['chats']:,} chats, {reconstruction['users']:,} pseudonymous users.",
        f"- Recorded anomalies: {reconstruction['anomalies']:,}; cumulative `messages` were not used as canonical reconstruction.",
        "",
        "## Candidate construction",
        "",
        f"- StudyChat: {candidates['STUDYCHAT']['natural_provisional_candidates']} provisional natural candidates, {candidates['STUDYCHAT']['rejected']:,} reason-coded rejections, no gold.",
        f"- WikiConv: {candidates['WIKICONV']['natural_candidates']} natural candidates acquired; {candidates['WIKICONV']['synthetic_fixture_candidates']} synthetic interface-test candidates only.",
        "",
        "## Continuity and splits",
        "",
        f"- Components: {continuity['components']} over {continuity['items']} items; largest share {continuity['largest_component_share']:.3f}.",
        f"- Split status: `{splits['status']}`; counts {splits['counts']}.",
        "",
        "## Privacy and annotation",
        "",
        f"- Automated findings: {privacy['findings']} across {privacy['records_with_findings']} of {privacy['records_scanned']} records; manual queue rows: {privacy['manual_queue_rows']}.",
        "- Automated scanning does not guarantee anonymity; no manual privacy approval, independent annotation, or adjudication exists.",
        "",
        "## Engineering validation",
        "",
        f"- Tests: {engineering['tests'].get('tests', 0)} passed with {engineering['tests'].get('failures', 0)} failures, {engineering['tests'].get('errors', 0)} errors, and {engineering['tests'].get('skipped', 0)} skipped.",
        f"- Supplementary static checks: `{engineering['supplementary_static_checks']['status']}`.",
        f"- Private permissions: `{engineering['private_permissions']['status']}`; security scan: `{engineering['security_scan']['status']}`.",
        f"- Build: `{engineering['build']['status']}`; two-run build reproducibility: `{engineering['build_reproducibility']['status']}`; clean reproduction: `{engineering['clean_reproduction']['status']}`.",
        "- Ruff, mypy, Python 3.11/3.12, the `build` frontend, and external scanners were unavailable and are not counted as passing named-tool results.",
        "",
        "## Readiness",
        "",
        f"- Blocking TMLR machine gates: {', '.join(report['readiness']['blocked']['tmlr_machine'])}.",
        f"- Pending TMLR human gates: {', '.join(report['readiness']['blocked']['tmlr_human'])}.",
        f"- Pending additional JMLR gates: {', '.join(report['readiness']['blocked']['jmlr_additional'])}.",
        "",
        "Public packaging remains blocked by design.",
        "",
    ]
    return "\n".join(lines)

