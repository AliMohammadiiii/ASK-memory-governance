#!/usr/bin/env python3
"""Evaluate mandatory JMLR and TMLR gates without inferring human approval."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATES = ROOT / "readiness/gates.yaml"
DEFAULT_JSON = ROOT / "reports/readiness.json"
DEFAULT_MD = ROOT / "reports/GO_NO_GO.md"
HUMAN_AUTHORITIES = {
    "human",
    "human_legal",
    "independent_human",
    "independent_human_and_machine",
    "independent_human_or_external_execution",
    "machine_and_human",
    "scientific_review",
}


def evaluate(gates: dict[str, Any]) -> dict[str, Any]:
    tmlr = gates["tmlr"]
    jmlr = gates["jmlr"]
    for group in (tmlr, jmlr):
        for gate_id, gate in group.items():
            if gate.get("authority") in HUMAN_AUTHORITIES and gate.get("passed") not in {
                True,
                False,
            }:
                raise ValueError(f"human gate {gate_id} must be explicitly true or false")
    tmlr_go = all(bool(gate["passed"]) for gate in tmlr.values())
    jmlr_go = tmlr_go and all(bool(gate["passed"]) for gate in jmlr.values())
    if jmlr_go:
        status = "JMLR_GO"
    elif tmlr_go:
        status = "TMLR_GO_ONLY"
    else:
        status = "NO_GO"
    blockers = []
    for venue, group in (("TMLR", tmlr), ("JMLR", jmlr)):
        for gate_id, gate in group.items():
            if not gate["passed"]:
                blockers.append(
                    {
                        "venue": venue,
                        "gate_id": gate_id,
                        "authority": gate["authority"],
                        "evidence": gate["evidence"],
                    }
                )
    return {
        "schema_version": "1.0",
        "evaluated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "tmlr_go": tmlr_go,
        "jmlr_go": jmlr_go,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "gates": {"tmlr": tmlr, "jmlr": jmlr},
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Publication GO / NO-GO", "", f"Final status: **{report['status']}**", ""]
    lines.extend(
        [
            "## Blocking gates",
            "",
            "| Venue | Gate | Authority | Resolution evidence |",
            "|---|---|---|---|",
        ]
    )
    for blocker in report["blockers"]:
        lines.append(
            f"| {blocker['venue']} | `{blocker['gate_id']}` | "
            f"`{blocker['authority']}` | `{blocker['evidence']}` |"
        )
    lines.extend(
        [
            "",
            "A template or empty directory does not satisfy a gate. Human gates require an explicit",
            "recorded decision or independent contribution. Machine gates require a successful",
            "validation artifact from the authoritative command.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gates", type=Path, default=DEFAULT_GATES)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    args = parser.parse_args(argv)
    gates = yaml.safe_load(args.gates.read_text(encoding="utf-8"))
    report = evaluate(gates)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.md_out.write_text(render_markdown(report), encoding="utf-8")
    print(report["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
