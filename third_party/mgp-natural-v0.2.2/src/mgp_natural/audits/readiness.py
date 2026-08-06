"""Machine-readable readiness gates with explicit evidence and human blockers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mgp_natural.util.io import atomic_write_text, read_json, write_json

TMLR_MACHINE_GATES = (
    "input_scope_audited",
    "source_manifests_pinned",
    "reconstruction_validated",
    "schemas_validated",
    "candidate_semantics_validated",
    "privacy_scan_completed",
    "private_packet_verified",
    "prohibited_key_scan_passed",
    "continuity_graph_generated",
    "split_audit_passed",
    "scorer_validated",
    "clean_reproduction_passed",
    "claim_verification_passed",
    "package_boundary_passed",
    "venue_requirements_recorded",
)
TMLR_HUMAN_GATES = (
    "legal_and_redistribution_approval",
    "manual_privacy_review",
    "protocol_approval",
    "independent_annotation",
    "independent_adjudication",
    "mapping_reveal_authorization",
    "authorship_confirmation",
    "venue_compliance_review",
    "release_decision",
)
JMLR_ADDITIONAL_GATES = (
    "sufficient_natural_gold",
    "trajectory_evaluation",
    "multiple_model_families",
    "multiple_judge_or_human_validation",
    "robustness_analysis",
    "cross_storage_or_native_system_evidence",
    "calibration_analysis",
    "generalizable_ml_lessons",
    "scientific_breadth_review",
)
PRIVATE_PILOT_MACHINE_GATES = (
    "input_scope_audited",
    "reconstruction_validated",
    "schemas_validated",
    "candidate_semantics_validated",
    "privacy_scan_completed",
    "private_packet_verified",
    "prohibited_key_scan_passed",
    "continuity_graph_generated",
    "scorer_validated",
)
PRIVATE_PILOT_HUMAN_GATES = ("manual_privacy_review", "protocol_approval")


def _gate_record(value: Any, *, owner: str) -> dict[str, Any]:
    if isinstance(value, bool):
        return {
            "passed": value,
            "status": "PASS" if value else "BLOCKED",
            "owner": owner,
            "evidence": [],
            "blocker": None if value else "No passing evidence recorded.",
        }
    if isinstance(value, dict):
        passed = bool(value.get("passed", False))
        evidence = value.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        return {
            "passed": passed,
            "status": str(value.get("status", "PASS" if passed else "BLOCKED")),
            "owner": str(value.get("owner", owner)),
            "evidence": list(evidence) if isinstance(evidence, list) else [],
            "blocker": value.get("blocker") if not passed else None,
            "notes": value.get("notes"),
        }
    return {
        "passed": False,
        "status": "BLOCKED",
        "owner": owner,
        "evidence": [],
        "blocker": "Gate entry is absent or malformed.",
    }


def _gate_map(names: tuple[str, ...], values: dict[str, Any], *, owner: str) -> dict[str, Any]:
    return {name: _gate_record(values.get(name), owner=owner) for name in names}


def generate_readiness(
    machine_status: dict[str, Any],
    human_status: dict[str, Any],
    jmlr_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    machine = _gate_map(TMLR_MACHINE_GATES, machine_status, owner="machine")
    human = _gate_map(TMLR_HUMAN_GATES, human_status, owner="human")
    jmlr_values = human_status if jmlr_status is None else jmlr_status
    jmlr = _gate_map(JMLR_ADDITIONAL_GATES, jmlr_values, owner="mixed_human_machine")

    machine_complete = all(record["passed"] for record in machine.values())
    human_complete = all(record["passed"] for record in human.values())
    private_machine_complete = all(machine[name]["passed"] for name in PRIVATE_PILOT_MACHINE_GATES)
    private_human_complete = all(human[name]["passed"] for name in PRIVATE_PILOT_HUMAN_GATES)
    jmlr_complete = all(record["passed"] for record in jmlr.values())

    if machine_complete and human_complete:
        verdict = "PUBLIC_RELEASE_READY"
    elif machine_complete:
        verdict = "MACHINE_READY_HUMAN_GATES_PENDING"
    elif private_machine_complete and private_human_complete:
        verdict = "PRIVATE_PILOT_READY"
    else:
        verdict = "NO_GO"

    blocked_machine = [name for name, record in machine.items() if not record["passed"]]
    blocked_human = [name for name, record in human.items() if not record["passed"]]
    blocked_jmlr = [name for name, record in jmlr.items() if not record["passed"]]
    return {
        "schema_version": "1.0",
        "verdict": verdict,
        "publication_eligible": verdict == "PUBLIC_RELEASE_READY",
        "tmlr_machine_gates": machine,
        "tmlr_human_gates": human,
        "jmlr_additional_gates": jmlr,
        "tmlr_machine_complete": machine_complete,
        "tmlr_human_complete": human_complete,
        "private_pilot_machine_complete": private_machine_complete,
        "private_pilot_human_complete": private_human_complete,
        "jmlr_ready": machine_complete and human_complete and jmlr_complete,
        "blocked": {
            "tmlr_machine": blocked_machine,
            "tmlr_human": blocked_human,
            "jmlr_additional": blocked_jmlr,
        },
    }


def _display_name(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()


def render_go_no_go(report: dict[str, Any]) -> str:
    verdict = str(report["verdict"])
    lines = [
        "# MGP-Natural Go/No-Go Decision",
        "",
        f"**Final machine-generated verdict: `{verdict}`.**",
        "",
        "This verdict is fail-closed. It does not constitute legal, privacy, scientific, venue, or release approval.",
        "",
        "## Blocking TMLR machine gates",
        "",
    ]
    machine = report["tmlr_machine_gates"]
    blocked_machine = report["blocked"]["tmlr_machine"]
    if blocked_machine:
        for gate in blocked_machine:
            record = machine[gate]
            lines.append(
                f"- `{gate}` — `{record['status']}`: {record.get('blocker') or 'No passing evidence recorded.'}"
            )
    else:
        lines.append("- None.")

    lines.extend(["", "## Pending TMLR human gates", ""])
    for gate in report["blocked"]["tmlr_human"]:
        lines.append(f"- `{gate}` — {_display_name(gate)} requires a recorded human decision.")

    lines.extend(
        [
            "",
            "## Readiness interpretation",
            "",
            f"- TMLR machine gates complete: `{str(report['tmlr_machine_complete']).lower()}`.",
            f"- TMLR human gates complete: `{str(report['tmlr_human_complete']).lower()}`.",
            f"- Private pilot machine gates complete: `{str(report['private_pilot_machine_complete']).lower()}`.",
            f"- Private pilot human gates complete: `{str(report['private_pilot_human_complete']).lower()}`.",
            f"- JMLR additional gates complete: `{str(not report['blocked']['jmlr_additional']).lower()}`.",
            f"- Publication eligible: `{str(report['publication_eligible']).lower()}`.",
            "",
            "`make package-public` must remain blocked until recorded human approvals, independent gold, and valid splits exist.",
            "",
        ]
    )
    return "\n".join(lines)


def render_remaining_actions(report: dict[str, Any]) -> str:
    lines = [
        "# Remaining External and Human Actions",
        "",
        "The repository completed the locally available construction and validation work. The following actions must not be inferred, automated, or performed without the stated authority.",
        "",
        "## Source and machine-coverage blockers",
        "",
    ]
    for gate in report["blocked"]["tmlr_machine"]:
        record = report["tmlr_machine_gates"][gate]
        lines.append(f"- `{gate}`: {record.get('blocker') or 'No passing evidence recorded.'}")

    lines.extend(["", "## Required human actions", ""])
    human_actions = {
        "legal_and_redistribution_approval": "Counsel or an authorized institutional reviewer must decide the exact StudyChat, WikiConv, annotation, paper, code, attribution, ShareAlike, modification-notice, and deleted-content release terms.",
        "manual_privacy_review": "Authorized reviewers must inspect every natural item and redaction, resolve the manual queue, and exclude items whose privacy-safe form destroys the task.",
        "protocol_approval": "A responsible investigator must approve and timestamp the annotation, adjudication, exclusion, continuation-threshold, and amendment protocols before natural annotation starts.",
        "independent_annotation": "At least three independent qualified annotators per valid item must submit immutable blind decisions; constructors must not annotate their own provisional labels.",
        "independent_adjudication": "A separate adjudicator must add final resolutions without mutating source annotations.",
        "mapping_reveal_authorization": "An authorized human must approve any source-mapping reveal after annotation, privacy, split, and adjudication checks pass.",
        "authorship_confirmation": "All contributors must confirm authorship, conflicts, funding, and contribution statements under the selected venue rules.",
        "venue_compliance_review": "A human owner must re-check current official venue requirements at submission time and approve the final manuscript and artifacts.",
        "release_decision": "An authorized human must record an explicit go/no-go release decision; no tool command may infer approval.",
    }
    for gate in report["blocked"]["tmlr_human"]:
        lines.append(f"- `{gate}`: {human_actions[gate]}")

    lines.extend(["", "## Additional JMLR evidence", ""])
    for gate in report["blocked"]["jmlr_additional"]:
        lines.append(f"- `{gate}`: produce and review the corresponding natural-data scientific evidence.")

    lines.extend(
        [
            "",
            "## Explicitly unauthorized actions",
            "",
            "Do not accept gated terms, distribute annotation packets, collect human annotations, reveal private mappings, publish data, push to a remote, create a DOI, call paid APIs, or declare legal/privacy/release approval without explicit authorization.",
            "",
        ]
    )
    return "\n".join(lines)


def from_status_file(
    status_path: Path,
    output_path: Path,
    go_no_go_path: Path | None = None,
    remaining_actions_path: Path | None = None,
) -> dict[str, Any]:
    status = read_json(status_path)
    report = generate_readiness(
        status.get("machine", {}),
        status.get("human", {}),
        status.get("jmlr", {}),
    )
    report["status_manifest"] = status_path.as_posix()
    write_json(output_path, report)
    if go_no_go_path is not None:
        atomic_write_text(go_no_go_path, render_go_no_go(report))
    if remaining_actions_path is not None:
        atomic_write_text(remaining_actions_path, render_remaining_actions(report))
    return report

