#!/usr/bin/env python3
"""Deterministically regenerate reports/FINAL_RESULTS.{md,json} from the ledger.

Single source of truth: ``artifacts/results_ledger.json`` (READ-ONLY input; this
script never mutates it). The ledger already encodes the frozen claim policy:
only rows whose ``claim_eligibility`` is ``final_candidate`` may enter a final
MGP-6 table. LongMemEval rows retain one of the canonical non-final statuses
until the frozen homogeneous rerun (see FINAL_EVALUATION_PROTOCOL.md) lands.

This script does NOT recompute any metric. It transcribes the ledger into the two
release artifacts, applying the freeze rules:

  * MGP-6: partitioned into (a) final-table rows, (b) mapping-disclosure rows
    (external adapters), (c) bound-only / pending rows that are printed but
    flagged NOT-citable.
  * LongMemEval: every row carries its exact status. The 77.2% construction is
    annotated as selection-biased ``failure_replay_only`` evidence and paired
    with the incomplete top-up evidence that contradicts it.
  * over_forgetting_rate / under_forgetting_rate are listed under known issues
    and never surfaced as a headline metric.

Stdlib only. Deterministic: stable ordering + sorted JSON, so re-runs on an
unchanged ledger produce byte-identical output.

Usage:
    python3 scripts/analysis/build_final_results.py \
        --ledger artifacts/results_ledger.json \
        --out-dir reports
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]

# Stable display order for MGP-6 systems in the final table.
MGP6_SYSTEM_ORDER = [
    "ref_5systems/b1_no_memory",
    "ref_5systems/b2_flat_retrieval",
    "ref_5systems/b3_recency",
    "ref_5systems/b4_naive_overwrite",
    "llm_decision_zero_shot",
    "llm_decision_few6",
    "llm_controller_qwen35_9b",
    "ref_5systems/controller_rule",
]
MGP6_ABLATION_ORDER = [
    "ablation/full",
    "ablation/no_abstain",
    "ablation/no_provenance",
    "ablation/no_typing",
    "ablation/no_lineage",
]
MGP6_EXTERNAL_ORDER = [
    "external/letta_memgpt",
    "external/mem0_2.0.11",
    "external/graphiti_0.29.2",
    "external/memos",
]
LME_ORDER = [
    "v7_strat30/b1_no_memory",
    "v7_strat30/b2_flat_vector",
    "v7_strat30/b3_recency",
    "v7_strat30/b4_naive_overwrite",
    "v7_strat30/controller",
    "v8_failures_nothink_replay",
    "v8_failure_replay_adjudicated",
    "v8_topup110_modal",
    "v8_topup110_openrouter",
    "final_1.1_homogeneous_5systems",
]

FINAL_PREFIX = "final_candidate"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r.get("run_id")): r for r in rows if r.get("run_id")}


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _ordered(rows_by_id: dict[str, dict[str, Any]], order: list[str]) -> list[dict[str, Any]]:
    """Rows in the declared order first, then any remaining rows sorted by id."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for rid in order:
        if rid in rows_by_id:
            out.append(rows_by_id[rid])
            seen.add(rid)
    for rid in sorted(rows_by_id):
        if rid not in seen:
            out.append(rows_by_id[rid])
    return out


def build_json(ledger: dict[str, Any], ledger_sha: str) -> dict[str, Any]:
    mgp6 = ledger["benchmarks"]["mgp6_v2"]
    lme = ledger["benchmarks"]["longmemeval_m"]
    lme_by_id = _by_id(lme["results"])

    def is_final(row: dict[str, Any]) -> bool:
        return str(row.get("claim_eligibility", "")).startswith(FINAL_PREFIX)

    mgp6_final = [r for r in mgp6["results"] if is_final(r)]
    mgp6_nonfinal = [r for r in mgp6["results"] if not is_final(r)]

    return {
        "generated_from": {
            "ledger_path": "artifacts/results_ledger.json",
            "ledger_sha256": ledger_sha,
            "ledger_version": ledger.get("ledger_version"),
            "ledger_created": ledger.get("created"),
            "generator": "scripts/analysis/build_final_results.py",
            "note": (
                "Deterministic transcription of the ledger under the frozen claim "
                "policy. No metric is recomputed here."
            ),
        },
        "mgp6_v2": {
            "dataset": mgp6.get("dataset"),
            "final_table_rows": len(mgp6_final),
            "final_candidate": _ordered(
                _by_id(mgp6_final), MGP6_SYSTEM_ORDER + MGP6_ABLATION_ORDER + MGP6_EXTERNAL_ORDER
            ),
            "not_citable": _ordered(_by_id(mgp6_nonfinal), []),
            "known_metric_issues": mgp6.get("known_metric_issues", []),
        },
        "longmemeval_m": {
            "dataset": lme.get("dataset"),
            "has_final_candidate": any(is_final(r) for r in lme["results"]),
            "canonical_nonfinal_statuses": [
                "diagnostic_only",
                "failure_replay_only",
                "incomplete",
                "invalid",
                "externally_pending",
            ],
            "rows": _ordered(lme_by_id, LME_ORDER),
            "headline_disclosure": (
                "There is no final LongMemEval result. The 77.2% (139/180) value is "
                "a selection-biased failure-replay construction, not a complete v8 "
                "run. A non-empty top-up re-evaluated 84/110 carried-forward items: "
                "71 remained correct and 13 regressed. Combining those observations "
                "with the replay yields 96/154 raw and a full-180 raw bound of "
                "53.3%-67.8%, so this attempt cannot reproduce 77.2%. The frozen "
                "final-1.1 homogeneous run remains externally pending because the "
                "supplied OpenRouter credential returned HTTP 403 before inference."
            ),
        },
        "ssp_analysis": ledger.get("ssp_analysis"),
    }


def build_md(data: dict[str, Any]) -> str:
    g = data["generated_from"]
    lines: list[str] = []
    lines.append("# FINAL RESULTS (auto-generated)")
    lines.append("")
    lines.append(
        "> Generated by `scripts/analysis/build_final_results.py` from "
        "`artifacts/results_ledger.json`. Do not edit by hand; edit the ledger "
        "and regenerate. Regeneration is deterministic."
    )
    lines.append("")
    lines.append(f"- Ledger version: `{g['ledger_version']}`  created `{g['ledger_created']}`")
    lines.append(f"- Ledger sha256: `{g['ledger_sha256']}`")
    lines.append("")

    # ---- MGP-6 --------------------------------------------------------- #
    m = data["mgp6_v2"]
    ds = m.get("dataset") or {}
    lines.append("## MGP-6 v2 (final-candidate; author-designed diagnostic slice)")
    lines.append("")
    lines.append(f"- n_examples: {ds.get('n_examples')}  |  gold actions: {ds.get('gold_actions')}")
    lines.append(
        "- Annotation: one independent human annotator (Cohen's kappa ~0.98) PLUS a "
        "four-model audit panel. Never describe as multi-annotator human IAA."
    )
    lines.append("")
    lines.append("### Systems and ablations")
    lines.append("")
    lines.append("| Run | n | action_acc | macro_F1 | invalid_commit | claim_eligibility |")
    lines.append("|---|---|---|---|---|---|")
    for r in m["final_candidate"]:
        lines.append(
            "| {rid} | {n} | {acc} | {f1} | {ic} | {ce} |".format(
                rid=r.get("run_id"),
                n=_fmt(r.get("n")),
                acc=_fmt(r.get("action_accuracy")),
                f1=_fmt(r.get("macro_f1")),
                ic=_fmt(r.get("invalid_commit_rate")),
                ce=r.get("claim_eligibility"),
            )
        )
    lines.append("")
    if m["not_citable"]:
        lines.append("### NOT citable (excluded from final tables)")
        lines.append("")
        lines.append("| Run | reason / status | claim_eligibility |")
        lines.append("|---|---|---|")
        for r in m["not_citable"]:
            reason = r.get("note") or r.get("mapping_disclosure") or "see ledger"
            lines.append(f"| {r.get('run_id')} | {reason} | {r.get('claim_eligibility')} |")
        lines.append("")
    lines.append("### Known metric issues")
    lines.append("")
    for issue in m["known_metric_issues"]:
        lines.append(f"- {issue}")
    lines.append("")

    # ---- LongMemEval -------------------------------------------------- #
    l = data["longmemeval_m"]
    lds = l.get("dataset") or {}
    lines.append("## LongMemEval-M (no final-candidate result)")
    lines.append("")
    lines.append(f"- slice: {lds.get('slice')}")
    lines.append(f"- {l['headline_disclosure']}")
    lines.append("")
    lines.append("| Run | status / n | correct | accuracy / bound | claim_eligibility |")
    lines.append("|---|---|---|---|---|")
    for r in l["rows"]:
        status_n = r.get("status") or r.get("n") or r.get("n_observed") or "-"
        accuracy = r.get("accuracy")
        if accuracy is None:
            accuracy = r.get("combined_with_replay") or r.get("note") or "-"
        lines.append(
            "| {rid} | {n} | {c} | {acc} | {ce} |".format(
                rid=r.get("run_id"),
                n=_fmt(status_n),
                c=_fmt(r.get("correct", r.get("correct_observed"))),
                acc=_fmt(accuracy),
                ce=r.get("claim_eligibility"),
            )
        )
    lines.append("")
    ssp = data.get("ssp_analysis") or {}
    if ssp:
        lines.append("### Single-session-preference (open failure)")
        lines.append("")
        lines.append(f"- {ssp.get('headline')}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", type=Path, default=REPO / "artifacts" / "results_ledger.json")
    ap.add_argument("--out-dir", type=Path, default=REPO / "reports")
    args = ap.parse_args(argv)

    ledger_path: Path = args.ledger
    if not ledger_path.exists():
        print(f"FATAL: ledger not found: {ledger_path}")
        return 1
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger_sha = _sha256(ledger_path)

    data = build_json(ledger, ledger_sha)
    md = build_md(data)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "FINAL_RESULTS.json"
    md_path = out_dir / "FINAL_RESULTS.md"

    # Atomic writes: tmp then replace.
    tmp_json = json_path.with_suffix(".json.tmp")
    tmp_md = md_path.with_suffix(".md.tmp")
    tmp_json.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_md.write_text(md, encoding="utf-8")
    tmp_json.replace(json_path)
    tmp_md.replace(md_path)

    print(f"[build-final-results] wrote {md_path}")
    print(f"[build-final-results] wrote {json_path}")
    print(
        f"[build-final-results] MGP-6 final rows={data['mgp6_v2']['final_table_rows']} "
        f"not-citable={len(data['mgp6_v2']['not_citable'])} "
        f"LME rows={len(data['longmemeval_m']['rows'])} "
        f"(final_candidate={data['longmemeval_m']['has_final_candidate']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
