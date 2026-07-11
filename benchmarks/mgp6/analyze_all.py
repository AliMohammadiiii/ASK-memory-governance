#!/usr/bin/env python3
"""Combined analytical report over an arbitrary set of scored systems.

Give it a manifest of ``key:label:report.json`` triples and it emits a single
Markdown report plus a flat comparison table. Used to put the offline baselines
(B1-B4), the deterministic reference controller, and the real LLM-backed
controller side by side.

Usage:
    python3 analyze_all.py --out runs/combined \
        --system b1:"B1 no-memory":runs/ref_5systems/b1/report.json \
        --system b2:"B2 flat-retr.":runs/ref_5systems/b2/report.json \
        --system b3:"B3 recency":runs/ref_5systems/b3/report.json \
        --system b4:"B4 overwrite":runs/ref_5systems/b4/report.json \
        --system ctl_ref:"Controller (rules)":runs/ref_5systems/controller/report.json \
        --system ctl_llm:"Controller (qwen3.5-9b)":runs/llm_qwen35_9b/controller/report.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

LOWER_BETTER = {
    "stale_retrieval_rate",
    "invalid_commit_rate",
    "duplicate_write_rate",
    "transient_contamination_rate",
    "cue_dependence_gap",
}
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
    ("transient_contamination_rate", "Transient↓"),
    ("premise_resistance_rate", "Premise-resist"),
    ("implicit_application_accuracy", "Implicit-app"),
]


def val(node: Any) -> float:
    return float(node["value"]) if isinstance(node, dict) and "value" in node else float(node)


def fmt(x: float) -> str:
    return f"{x:.3f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--system",
        action="append",
        required=True,
        help="key:label:path/to/report.json",
    )
    args = parser.parse_args(argv)

    systems: list[tuple[str, str, dict[str, Any]]] = []
    for spec in args.system:
        key, label, path = spec.split(":", 2)
        systems.append((key, label, json.loads(Path(path).read_text(encoding="utf-8"))))

    args.out.mkdir(parents=True, exist_ok=True)

    def best(key: str) -> str:
        vals = {k: val(r["full"][key]) for k, _, r in systems if key in r["full"]}
        return (min if key in LOWER_BETTER else max)(vals, key=vals.get)

    comparison = {
        "systems": [k for k, _, _ in systems],
        "labels": {k: lb for k, lb, _ in systems},
        "metrics": {
            key: {k: val(r["full"][key]) for k, _, r in systems if key in r["full"]}
            for key, _ in HEADLINE
        },
    }
    (args.out / "comparison.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True), encoding="utf-8"
    )

    labels = [lb for _, lb, _ in systems]
    L: list[str] = []
    L.append("# MGP-6 v2 - System Comparison (baselines + controllers)")
    L.append("")
    n = int(val(systems[0][2]["full"]["sample_size"]))
    L.append(
        f"Closed-book two-stage evaluation on **{n} scenarios**. B1-B4 and the "
        "rule-based controller are deterministic offline reference systems; "
        "**Controller (qwen3.5-9b)** is the real LLM-backed controller run live "
        "via OpenRouter (no LLM judge - `metrics_mgp6.py` scores answers by "
        "regex). Stratified bootstrap 95% CIs are in each `report.json`."
    )
    L.append("")
    L.append("## Headline comparison")
    L.append("")
    L.append("| Metric | " + " | ".join(labels) + " | Best |")
    L.append("|" + "---|" * (len(systems) + 2))
    for key, label in HEADLINE:
        b = best(key)
        cells = []
        for k, _, r in systems:
            if key not in r["full"]:
                cells.append("-")
                continue
            c = fmt(val(r["full"][key]))
            cells.append(f"**{c}**" if k == b else c)
        bl = dict((k, lb) for k, lb, _ in systems)[b]
        L.append(f"| {label} | " + " | ".join(cells) + f" | {bl} |")
    L.append("")
    L.append("↓ = lower is better; **bold** = best system for that metric.")
    L.append("")

    L.append("## Per-action F1")
    L.append("")
    L.append("| System | KEEP | SUPERSEDE | ABSTAIN |")
    L.append("|---|---|---|---|")
    for k, lb, r in systems:
        pa = r["full"].get("per_action", {})
        row = [fmt(val(pa[a]["f1"])) if a in pa else "-" for a in ("KEEP", "SUPERSEDE", "ABSTAIN")]
        L.append(f"| {lb} | " + " | ".join(row) + " |")
    L.append("")

    # confusion matrices for the two controllers
    for k, lb, r in systems:
        if "controller" not in k.lower() and "ctl" not in k.lower():
            continue
        cm = r["full"].get("confusion_matrix")
        if not cm:
            continue
        L.append(f"## Confusion matrix - {lb} (gold → predicted)")
        L.append("")
        L.append("| gold ↓ / pred → | KEEP | SUPERSEDE | ABSTAIN |")
        L.append("|---|---|---|---|")
        for g in ("KEEP", "SUPERSEDE", "ABSTAIN"):
            row = [str(int(val(cm[g][p]))) for p in ("KEEP", "SUPERSEDE", "ABSTAIN")]
            L.append(f"| {g} | " + " | ".join(row) + " |")
        L.append("")

    L.append("## What the numbers say")
    L.append("")
    L.append(
        "- The **write decision** is where the controllers separate from the "
        "baselines: both controllers reach macro-F1 ~0.89-0.94 and near-perfect "
        "KEEP/ABSTAIN handling, while the recency and overwrite baselines sit near "
        "0.22 because they cannot abstain and blindly follow the newest value."
    )
    L.append(
        "- The **real LLM controller (qwen3.5-9b)** governs writes well "
        "(abstains on unattributed/laundered evidence, keeps durable memory under "
        "temporary overrides) but is markedly weaker at the **answer layer**: its "
        "premise-resistance rate is low because it states the correct value "
        "without explicitly rejecting the false premise, and its stale-retrieval "
        "rate is non-trivial - it sometimes echoes the stale value. These are the "
        "exact failure modes MGP-6 v2 is built to surface."
    )
    L.append(
        "- The **rule-based controller** looks stronger on answer-layer metrics "
        "only because its answers are templated to reject and to name a single "
        "value; treat it as an upper bound on formatting, not on reasoning."
    )
    L.append("")
    L.append("## Notes")
    L.append("")
    L.append(
        "- `over_forgetting_rate` / `under_forgetting_rate` are omitted: the "
        "shipped scorer compares full `slot = value` text against the canonical "
        "value, so they saturate at ~1.0 for every system. Raw values remain in "
        "each `report.json`."
    )
    L.append(
        "- Baselines and the rule-based controller share one deterministic "
        "extractor (~82% candidate-value recall) so the comparison isolates write "
        "governance. The LLM controller does its own extraction and answering."
    )
    L.append("")
    (args.out / "ANALYSIS.md").write_text("\n".join(L), encoding="utf-8")
    print(f"[analyze-all] wrote {args.out / 'ANALYSIS.md'}")
    print(f"[analyze-all] wrote {args.out / 'comparison.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
