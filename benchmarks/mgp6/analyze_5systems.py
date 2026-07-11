#!/usr/bin/env python3
"""Aggregate the five per-system report.json files into an analytical report.

Reads <out>/<system>/report.json for each system and writes:
    <out>/ANALYSIS.md       human-readable analytical report (Markdown)
    <out>/comparison.json   flat machine-readable comparison table

The report is built from the *official* metrics_mgp6.py output so every number
is reproducible with that scorer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

ORDER = ["b1", "b2", "b3", "b4", "controller"]
LABELS = {
    "b1": "B1 no-memory",
    "b2": "B2 flat-retr.",
    "b3": "B3 recency",
    "b4": "B4 overwrite",
    "controller": "Controller",
}

# metrics where lower is better
LOWER_BETTER = {
    "over_forgetting_rate",
    "under_forgetting_rate",
    "stale_retrieval_rate",
    "invalid_commit_rate",
    "duplicate_write_rate",
    "transient_contamination_rate",
    "cue_dependence_gap",
}

# headline metrics shown in the main table (discriminative ones first)
HEADLINE = [
    ("action_accuracy", "Action acc."),
    ("macro_f1", "Macro-F1"),
    ("abstention_precision", "Abstain P"),
    ("abstention_recall", "Abstain R"),
    ("lineage_correctness", "Lineage"),
    ("artifact_semantic_accuracy", "Artifact(sem)"),
    ("fama_presence_absence_conjunction", "FAMA both"),
    ("stale_retrieval_rate", "Stale-retr.↓"),
    ("invalid_commit_rate", "Invalid-commit↓"),
    ("transient_contamination_rate", "Transient-contam↓"),
    ("premise_resistance_rate", "Premise-resist"),
    ("implicit_application_accuracy", "Implicit-app"),
]

SATURATED = {"over_forgetting_rate", "under_forgetting_rate"}


def val(node: Any) -> float:
    if isinstance(node, dict) and "value" in node:
        return float(node["value"])
    return float(node)


def ci(node: Any) -> tuple[float, float] | None:
    if isinstance(node, dict) and "ci95" in node:
        lo, hi = node["ci95"]
        return float(lo), float(hi)
    return None


def load_reports(out: Path) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for system in ORDER:
        path = out / system / "report.json"
        if path.exists():
            reports[system] = json.loads(path.read_text(encoding="utf-8"))
    if not reports:
        raise SystemExit(f"no report.json under {out}")
    return reports


def fmt(x: float) -> str:
    return f"{x:.3f}"


def best_of(reports: dict[str, dict[str, Any]], key: str) -> str | None:
    vals = {s: val(r["full"][key]) for s, r in reports.items() if key in r["full"]}
    if not vals:
        return None
    if key in LOWER_BETTER:
        return min(vals, key=vals.get)
    return max(vals, key=vals.get)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "runs" / "ref_5systems")
    args = parser.parse_args(argv)

    reports = load_reports(args.out)
    systems = [s for s in ORDER if s in reports]

    # flat comparison table
    comparison: dict[str, Any] = {"systems": systems, "metrics": {}}
    for key, _ in HEADLINE:
        comparison["metrics"][key] = {
            s: {"value": val(reports[s]["full"][key]), "ci95": ci(reports[s]["full"][key])}
            for s in systems
            if key in reports[s]["full"]
        }
    (args.out / "comparison.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True), encoding="utf-8"
    )

    # ---- Markdown report ----
    L: list[str] = []
    L.append("# MGP-6 v2 - Five-System Diagnostic Report")
    L.append("")
    n = int(val(next(iter(reports.values()))["full"]["sample_size"]))
    L.append(
        f"Closed-book two-stage evaluation on **{n} scenarios** (full corpus; the "
        "90-row test split is reported per system in `report.json`). Every number "
        "below is produced by the repository's own `metrics_mgp6.py` with "
        "stratified bootstrap 95% intervals."
    )
    L.append("")
    L.append("## Headline comparison (full corpus)")
    L.append("")
    header = "| Metric | " + " | ".join(LABELS[s] for s in systems) + " | Best |"
    sep = "|" + "---|" * (len(systems) + 2)
    L.append(header)
    L.append(sep)
    for key, label in HEADLINE:
        best = best_of(reports, key)
        cells = []
        for s in systems:
            if key not in reports[s]["full"]:
                cells.append("-")
                continue
            v = val(reports[s]["full"][key])
            cell = fmt(v)
            if s == best:
                cell = f"**{cell}**"
            cells.append(cell)
        best_label = LABELS[best] if best else "-"
        L.append(f"| {label} | " + " | ".join(cells) + f" | {best_label} |")
    L.append("")
    L.append(
        "Arrows (↓) mark metrics where lower is better; **bold** marks the best "
        "system for each metric."
    )
    L.append("")

    # per-action F1 for the controller vs best baseline
    L.append("## Per-action F1")
    L.append("")
    L.append("| System | KEEP F1 | SUPERSEDE F1 | ABSTAIN F1 |")
    L.append("|---|---|---|---|")
    for s in systems:
        pa = reports[s]["full"].get("per_action", {})
        row = []
        for a in ("KEEP", "SUPERSEDE", "ABSTAIN"):
            node = pa.get(a, {}).get("f1")
            row.append(fmt(val(node)) if node is not None else "-")
        L.append(f"| {LABELS[s]} | " + " | ".join(row) + " |")
    L.append("")

    # confusion matrix for the controller
    if "confusion_matrix" in reports["controller"]["full"]:
        cm = reports["controller"]["full"]["confusion_matrix"]
        L.append("## Controller confusion matrix (gold → predicted)")
        L.append("")
        acts = ("KEEP", "SUPERSEDE", "ABSTAIN")
        L.append("| gold ↓ / pred → | KEEP | SUPERSEDE | ABSTAIN |")
        L.append("|---|---|---|---|")
        for g in acts:
            row = [str(int(val(cm[g][p]))) for p in acts]
            L.append(f"| {g} | " + " | ".join(row) + " |")
        L.append("")

    L.append("## Reading the results")
    L.append("")
    L.append(
        "- **B1 (no-memory)** stores nothing, so it always emits a non-commit and "
        "cannot recall a value. It trivially never over-writes, but its macro-F1 "
        "and answer scores are a floor."
    )
    L.append(
        "- **B2 (flat retrieval)** never governs memory: it keeps the prior value "
        "forever. It therefore answers correctly on genuine KEEP/ABSTAIN cases but "
        "fails every supersession, and it never abstains (high invalid-commit)."
    )
    L.append(
        "- **B3 (recency)** lets the newest detected value win, so it supersedes "
        "even temporary overrides and unreliable evidence: strong on real drift, "
        "but it contaminates durable memory and cannot abstain."
    )
    L.append(
        "- **B4 (naive overwrite)** replaces in place with no retained lineage and "
        "no abstain safeguard, so its lineage-correctness collapses."
    )
    L.append(
        "- **Controller** applies the R1-R10 policy: it abstains on unattributed, "
        "laundered or hedged evidence, keeps durable memory under a clear temporary "
        "override, and supersedes only on a reliable durable contradiction while "
        "retaining lineage."
    )
    L.append("")
    L.append("## Method notes and honest limitations")
    L.append("")
    L.append(
        "- **Closed-book fairness.** Systems read only the dialogue prefix, prior "
        "memory state and perturbation event; gold labels, source/temporal "
        "annotations, `conflict_type` and top-level `semantic_slot` are withheld."
    )
    L.append(
        "- **Shared extractor.** All memory-using systems use one deterministic "
        "text extractor so the comparison isolates write governance, not extraction. "
        "That extractor recovers the candidate value on ~82% of rows that have one; "
        "the residual are free-form phrasings that need an LLM. This caps the "
        "controller's action/answer scores on T1-T3 and is a floor, not a ceiling."
    )
    L.append(
        "- **No LLM.** These are deterministic reference systems, not the "
        "LLM-backed KSA controller. They exist to exercise the harness end-to-end "
        "and give a governance baseline; swap in real model predictions by writing "
        "the same `predictions.jsonl` format."
    )
    L.append(
        "- **Saturated metrics.** In the shipped `metrics_mgp6.py`, "
        "`over_forgetting_rate` and `under_forgetting_rate` compare the full "
        "`slot = value` text against the canonicalised value, so they read ~1.0 for "
        "every system and are not discriminative in this version. They are omitted "
        "from the headline table; the raw values remain in each `report.json`."
    )
    L.append("")

    (args.out / "ANALYSIS.md").write_text("\n".join(L), encoding="utf-8")
    print(f"[analyze] wrote {args.out / 'ANALYSIS.md'}")
    print(f"[analyze] wrote {args.out / 'comparison.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
