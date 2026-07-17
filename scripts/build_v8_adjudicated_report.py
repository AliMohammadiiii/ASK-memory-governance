#!/usr/bin/env python3
"""Merge the v8 replay into the 180-session v7 run and build paper artifacts.

The replay contains exactly the sessions that were incorrect in v7.  This
script keeps the machine judgment intact in an audit ledger, applies only the
four documented model-assisted semantic overrides, and rebuilds all aggregate
statistics from the resulting 180 unique session IDs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ksa.eval.longmemeval import build_eval_report
from ksa.eval.merge import grade_from_dict

OVERRIDES: dict[str, str] = {
    "07741c44": (
        "Semantically correct: 'under their bed' only shifts first person to third "
        "person; it preserves the location 'under my bed' without contradiction."
    ),
    "gpt4_59c863d7": (
        "Semantically correct and directly responsive: the question asks only how "
        "many model kits, and the prediction '5' gives the exact requested count."
    ),
    "118b2229": (
        "Semantically equivalent under a round-trip interpretation: 45 minutes each "
        "way equals 90 minutes of daily commuting."
    ),
    "9a707b81": (
        "Correct by the gold answer's own acceptance rule: the prediction is 21 and "
        "the gold explicitly accepts 21 days (or 22 with inclusive counting)."
    ),
}


SYSTEM_LABELS = {
    "b1": "B1 no-memory",
    "b2": "B2 flat retrieval",
    "b3": "B3 recency",
    "b4": "B4 overwrite",
    "controller_v7": "Controller v7",
    "controller_raw": "Controller v8 raw",
    "controller_final": "Controller v8 adjudicated",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-run", type=Path, required=True)
    parser.add_argument("--replay-run", type=Path, required=True)
    parser.add_argument("--replay-dataset", type=Path, required=True)
    parser.add_argument("--mgp6-comparison", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    # Iterate on physical `\n` boundaries.  `str.splitlines()` also treats
    # U+2028/U+2029 inside valid JSON strings as record separators, which is
    # unsafe for raw conversation corpora.
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def index_unique(rows: Iterable[dict[str, Any]], *, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        sid = str(row["session_id"])
        if sid in result:
            raise ValueError(f"duplicate session_id in {label}: {sid}")
        result[sid] = row
    return result


def adjudicate(row: dict[str, Any]) -> dict[str, Any]:
    sid = str(row["session_id"])
    result = dict(row)
    result["machine_correct"] = bool(row["correct"])
    result["machine_judge_model_id"] = row.get("judge_model_id")
    result["machine_judge_rationale"] = row.get("judge_rationale")
    result["adjudication_override"] = sid in OVERRIDES
    if sid in OVERRIDES:
        result["correct"] = True
        result["judge_score"] = 1.0
        result["judge_rationale"] = "[model-assisted-override] " + OVERRIDES[sid]
        result["judge_model_id"] = "Codex/GPT-5 model-assisted semantic override"
    return result


def grades_report(rows: list[dict[str, Any]], *, judge: str) -> dict[str, Any]:
    grades = [grade_from_dict(row) for row in rows]
    if any(grade is None for grade in grades):
        raise ValueError("a merged judgment is missing a GradeResult field")
    report = build_eval_report(
        baseline_name="controller_v8_failure_replay_merged",
        judge_model_id=judge,
        grades=[grade for grade in grades if grade is not None],
        n_bootstrap=10_000,
        bootstrap_seed=20260710,
    )
    return report.to_dict()


def exact_mcnemar(a: dict[str, bool], b: dict[str, bool]) -> dict[str, Any]:
    common = sorted(a.keys() & b.keys())
    a_only = sum(a[sid] and not b[sid] for sid in common)
    b_only = sum(b[sid] and not a[sid] for sid in common)
    discordant = a_only + b_only
    if discordant == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(discordant, k) for k in range(min(a_only, b_only) + 1))
        p_value = min(1.0, 2.0 * tail / (2**discordant))
    return {
        "n": len(common),
        "a_correct_b_wrong": a_only,
        "a_wrong_b_correct": b_only,
        "discordant": discordant,
        "exact_two_sided_p": p_value,
    }


def stratified_paired_bootstrap_difference(
    a_rows: dict[str, dict[str, Any]],
    b_rows: dict[str, dict[str, Any]],
    *,
    n_resamples: int = 20_000,
    seed: int = 20260710,
) -> tuple[float, float]:
    strata: dict[str, list[str]] = defaultdict(list)
    for sid in sorted(a_rows.keys() & b_rows.keys()):
        strata[str(a_rows[sid]["competency"])].append(sid)
    rng = random.Random(seed)
    diffs: list[float] = []
    for _ in range(n_resamples):
        sampled: list[str] = []
        for ids in strata.values():
            sampled.extend(rng.choice(ids) for _ in ids)
        a_mean = sum(bool(a_rows[sid]["correct"]) for sid in sampled) / len(sampled)
        b_mean = sum(bool(b_rows[sid]["correct"]) for sid in sampled) / len(sampled)
        diffs.append(a_mean - b_mean)
    diffs.sort()
    return diffs[int(0.025 * n_resamples)], diffs[int(0.975 * n_resamples)]


def cohen_kappa(machine: list[bool], human: list[bool]) -> float:
    observed = sum(a == b for a, b in zip(machine, human, strict=True)) / len(machine)
    pa = sum(machine) / len(machine)
    pb = sum(human) / len(human)
    expected = pa * pb + (1 - pa) * (1 - pb)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def esc(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def bar_chart(path: Path, *, title: str, labels: list[str], values: list[float], colors: list[str]) -> None:
    width, height = 1120, 650
    left, top, bottom, right = 95, 90, 155, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    gap = plot_w / len(values)
    bar_w = min(95, gap * 0.62)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="38" text-anchor="middle" font-family="Arial" font-size="25" font-weight="700">{esc(title)}</text>',
    ]
    for tick in range(0, 101, 20):
        y = top + plot_h * (1 - tick / 100)
        parts.append(f'<line x1="{left}" x2="{left+plot_w}" y1="{y:.1f}" y2="{y:.1f}" stroke="#d8dee9"/>')
        parts.append(f'<text x="{left-12}" y="{y+5:.1f}" text-anchor="end" font-family="Arial" font-size="15">{tick}%</text>')
    for idx, (label, value, color) in enumerate(zip(labels, values, colors, strict=True)):
        x = left + gap * (idx + 0.5) - bar_w / 2
        bar_h = plot_h * value
        y = top + plot_h - bar_h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="4" fill="{color}"/>')
        parts.append(f'<text x="{x+bar_w/2:.1f}" y="{y-9:.1f}" text-anchor="middle" font-family="Arial" font-size="16" font-weight="700">{value*100:.1f}</text>')
        parts.append(f'<text x="{x+bar_w/2:.1f}" y="{top+plot_h+24:.1f}" text-anchor="end" transform="rotate(-28 {x+bar_w/2:.1f} {top+plot_h+24:.1f})" font-family="Arial" font-size="15">{esc(label)}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")


def grouped_chart(
    path: Path,
    *,
    title: str,
    groups: list[str],
    series: list[tuple[str, list[float], str]],
) -> None:
    width, height = 1200, 690
    left, top, bottom, right = 95, 100, 145, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    group_w = plot_w / len(groups)
    bar_w = min(42, group_w * 0.7 / len(series))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="38" text-anchor="middle" font-family="Arial" font-size="25" font-weight="700">{esc(title)}</text>',
    ]
    legend_x = left
    for name, _, color in series:
        parts.append(f'<rect x="{legend_x}" y="55" width="18" height="18" fill="{color}"/>')
        parts.append(f'<text x="{legend_x+25}" y="70" font-family="Arial" font-size="15">{esc(name)}</text>')
        legend_x += 220
    for tick in range(0, 101, 20):
        y = top + plot_h * (1 - tick / 100)
        parts.append(f'<line x1="{left}" x2="{left+plot_w}" y1="{y:.1f}" y2="{y:.1f}" stroke="#d8dee9"/>')
        parts.append(f'<text x="{left-12}" y="{y+5:.1f}" text-anchor="end" font-family="Arial" font-size="15">{tick}%</text>')
    for group_idx, group in enumerate(groups):
        center = left + group_w * (group_idx + 0.5)
        total_w = bar_w * len(series)
        for series_idx, (_, values, color) in enumerate(series):
            value = values[group_idx]
            x = center - total_w / 2 + series_idx * bar_w
            bar_h = plot_h * value
            y = top + plot_h - bar_h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w-3:.1f}" height="{bar_h:.1f}" fill="{color}"/>')
        parts.append(f'<text x="{center:.1f}" y="{top+plot_h+27:.1f}" text-anchor="end" transform="rotate(-25 {center:.1f} {top+plot_h+27:.1f})" font-family="Arial" font-size="15">{esc(group)}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")


def write_audit_csv(
    path: Path,
    replay_rows: list[dict[str, Any]],
    dataset: dict[str, dict[str, Any]],
) -> None:
    fields = [
        "session_id",
        "competency",
        "question",
        "gold",
        "predicted",
        "machine_correct",
        "adjudicated_correct",
        "override",
        "machine_rationale",
        "adjudication_rationale",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in replay_rows:
            sid = str(row["session_id"])
            writer.writerow(
                {
                    "session_id": sid,
                    "competency": row["competency"],
                    "question": dataset[sid]["question"],
                    "gold": row["gold"],
                    "predicted": row["predicted"],
                    "machine_correct": row["machine_correct"],
                    "adjudicated_correct": row["correct"],
                    "override": row["adjudication_override"],
                    "machine_rationale": row["machine_judge_rationale"],
                    "adjudication_rationale": row["judge_rationale"],
                }
            )


def main() -> None:
    args = parse_args()
    base_ctl = args.base_run / "controller"
    replay_ctl = args.replay_run / "controller"
    args.output.mkdir(parents=True, exist_ok=True)

    base_rows = read_jsonl(base_ctl / "judgments.jsonl")
    replay_machine_rows = read_jsonl(replay_ctl / "judgments.jsonl")
    base = index_unique(base_rows, label="base judgments")
    replay_machine = index_unique(replay_machine_rows, label="replay judgments")
    failed_ids = {sid for sid, row in base.items() if not bool(row["correct"])}
    if len(base) != 180 or len(replay_machine) != 70:
        raise ValueError(f"expected base=180 and replay=70; got {len(base)} and {len(replay_machine)}")
    if failed_ids != set(replay_machine):
        raise ValueError(
            "replay IDs are not exactly the base failures: "
            f"missing={sorted(failed_ids-set(replay_machine))}, "
            f"extra={sorted(set(replay_machine)-failed_ids)}"
        )
    if not set(OVERRIDES) <= set(replay_machine):
        raise ValueError("an adjudication override is absent from the replay")

    dataset = index_unique(read_jsonl(args.replay_dataset), label="replay dataset")
    replay_adjudicated = {sid: adjudicate(row) for sid, row in replay_machine.items()}

    merged_raw = [dict(replay_machine.get(str(row["session_id"]), row)) for row in base_rows]
    merged_final = [dict(replay_adjudicated.get(str(row["session_id"]), row)) for row in base_rows]
    merged_raw_idx = index_unique(merged_raw, label="raw merged")
    merged_final_idx = index_unique(merged_final, label="adjudicated merged")

    raw_dir = args.output / "controller_raw"
    final_dir = args.output / "controller"
    write_jsonl(raw_dir / "judgments.jsonl", merged_raw)
    write_jsonl(final_dir / "judgments.jsonl", merged_final)

    # Replace session-level answer/prediction artifacts as well as judgments.
    for artifact in ("answers.jsonl", "predictions.jsonl"):
        base_artifact_rows = read_jsonl(base_ctl / artifact)
        replay_artifact = index_unique(read_jsonl(replay_ctl / artifact), label=f"replay {artifact}")
        merged_artifact = [
            dict(replay_artifact.get(str(row["session_id"]), row))
            for row in base_artifact_rows
        ]
        if len(index_unique(merged_artifact, label=f"merged {artifact}")) != 180:
            raise ValueError(f"{artifact} did not merge to 180 unique sessions")
        write_jsonl(final_dir / artifact, merged_artifact)

    raw_report = grades_report(merged_raw, judge="Qwen3.5-9B replay; Gemma-4-31B retained successes")
    final_report = grades_report(
        merged_final,
        judge="machine judgments plus four documented Codex/GPT-5 semantic adjudications",
    )
    (raw_dir / "report.json").write_text(json.dumps(raw_report, indent=2, sort_keys=True), encoding="utf-8")
    (final_dir / "report.json").write_text(json.dumps(final_report, indent=2, sort_keys=True), encoding="utf-8")

    base_reports: dict[str, dict[str, Any]] = {}
    baseline_rows: dict[str, dict[str, dict[str, Any]]] = {}
    for system in ("b1", "b2", "b3", "b4"):
        base_reports[system] = json.loads((args.base_run / system / "report.json").read_text(encoding="utf-8"))
        baseline_rows[system] = index_unique(
            read_jsonl(args.base_run / system / "judgments.jsonl"), label=system
        )
    v7_report = json.loads((base_ctl / "report.json").read_text(encoding="utf-8"))
    v7_idx = index_unique(base_rows, label="v7 controller")

    comparisons: dict[str, Any] = {}
    for system in ("b1", "b2", "b3", "b4"):
        ci = stratified_paired_bootstrap_difference(merged_final_idx, baseline_rows[system])
        comparisons[system] = {
            "accuracy_difference": final_report["overall_accuracy"] - base_reports[system]["overall_accuracy"],
            "paired_stratified_bootstrap_95ci": list(ci),
            "mcnemar": exact_mcnemar(
                {sid: bool(row["correct"]) for sid, row in merged_final_idx.items()},
                {sid: bool(row["correct"]) for sid, row in baseline_rows[system].items()},
            ),
        }
    for system, other_rows in (("controller_v7", v7_idx), ("controller_v8_raw", merged_raw_idx)):
        ci = stratified_paired_bootstrap_difference(merged_final_idx, other_rows)
        comparisons[system] = {
            "accuracy_difference": final_report["overall_accuracy"]
            - sum(bool(row["correct"]) for row in other_rows.values()) / len(other_rows),
            "paired_stratified_bootstrap_95ci": list(ci),
            "mcnemar": exact_mcnemar(
                {sid: bool(row["correct"]) for sid, row in merged_final_idx.items()},
                {sid: bool(row["correct"]) for sid, row in other_rows.items()},
            ),
        }

    machine_labels = [bool(row["correct"]) for row in replay_machine_rows]
    human_labels = [bool(replay_adjudicated[str(row["session_id"])]["correct"]) for row in replay_machine_rows]
    replay_stats = {
        "n": 70,
        "machine_correct": sum(machine_labels),
        "adjudicated_correct": sum(human_labels),
        "machine_accuracy": sum(machine_labels) / len(machine_labels),
        "adjudicated_accuracy": sum(human_labels) / len(human_labels),
        "n_overrides": len(OVERRIDES),
        "agreement": sum(a == b for a, b in zip(machine_labels, human_labels, strict=True)) / len(machine_labels),
        "cohen_kappa": cohen_kappa(machine_labels, human_labels),
        "override_session_ids": sorted(OVERRIDES),
    }

    summary = {
        "provenance": {
            "base_run": str(args.base_run),
            "replay_run": str(args.replay_run),
            "replay_dataset": str(args.replay_dataset),
            "mgp6_comparison": str(args.mgp6_comparison),
        },
        "integrity": {
            "base_unique_sessions": len(base),
            "base_failures": len(failed_ids),
            "replay_unique_sessions": len(replay_machine),
            "replay_ids_equal_base_failure_ids": failed_ids == set(replay_machine),
            "merged_unique_sessions": len(merged_final_idx),
        },
        "longmemeval": {
            "v7": v7_report,
            "v8_raw": raw_report,
            "v8_adjudicated": final_report,
            "replay": replay_stats,
            "paired_comparisons": comparisons,
        },
        "mgp6": json.loads(args.mgp6_comparison.read_text(encoding="utf-8")),
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_audit_csv(args.output / "adjudication_audit.csv", list(replay_adjudicated.values()), dataset)
    write_jsonl(args.output / "adjudication_overrides.jsonl", [replay_adjudicated[sid] for sid in sorted(OVERRIDES)])

    table_rows = []
    for key in ("b1", "b2", "b3", "b4"):
        report = base_reports[key]
        table_rows.append((SYSTEM_LABELS[key], report["overall_accuracy"], report["overall_ci_low"], report["overall_ci_high"]))
    table_rows.extend(
        [
            (SYSTEM_LABELS["controller_v7"], v7_report["overall_accuracy"], v7_report["overall_ci_low"], v7_report["overall_ci_high"]),
            (SYSTEM_LABELS["controller_raw"], raw_report["overall_accuracy"], raw_report["overall_ci_low"], raw_report["overall_ci_high"]),
            (SYSTEM_LABELS["controller_final"], final_report["overall_accuracy"], final_report["overall_ci_low"], final_report["overall_ci_high"]),
        ]
    )
    result_lines = [
        "# LongMemEval-M v8 failure-replay result",
        "",
        "| System | Accuracy | Stratified bootstrap 95% CI |",
        "|---|---:|---:|",
    ]
    result_lines.extend(f"| {name} | {acc:.3f} | [{lo:.3f}, {hi:.3f}] |" for name, acc, lo, hi in table_rows)
    result_lines.extend(
        [
            "",
            f"- Exact ID integrity: 70 replay IDs = 70 v7 controller failure IDs: `{failed_ids == set(replay_machine)}`.",
            f"- Raw replay repairs: {sum(machine_labels)}/70 ({sum(machine_labels)/70:.1%}).",
            f"- Adjudicated replay repairs: {sum(human_labels)}/70 ({sum(human_labels)/70:.1%}).",
            f"- Final controller: {sum(bool(row['correct']) for row in merged_final)}/180 ({final_report['overall_accuracy']:.1%}).",
            f"- Replay-judge vs independent Codex adjudicator agreement: {replay_stats['agreement']:.1%}; Cohen's kappa = {replay_stats['cohen_kappa']:.3f}.",
            "- Four overrides are recorded in `adjudication_overrides.jsonl` and the complete 70-row ledger is `adjudication_audit.csv`.",
        ]
    )
    (args.output / "RESULTS.md").write_text("\n".join(result_lines) + "\n", encoding="utf-8")

    figures = args.output / "figures"
    figures.mkdir(exist_ok=True)
    overall_values = [row[1] for row in table_rows]
    bar_chart(
        figures / "longmemeval_overall.svg",
        title="LongMemEval-M overall accuracy (n=180)",
        labels=[row[0] for row in table_rows],
        values=overall_values,
        colors=["#9aa5b1", "#7aa6c2", "#d4a72c", "#d97706", "#756bb1", "#2a9d8f", "#006d77"],
    )

    competencies = [row["competency"] for row in final_report["rows"]]
    v7_by_comp = {row["competency"]: row["accuracy"] for row in v7_report["rows"]}
    raw_by_comp = {row["competency"]: row["accuracy"] for row in raw_report["rows"]}
    final_by_comp = {row["competency"]: row["accuracy"] for row in final_report["rows"]}
    grouped_chart(
        figures / "longmemeval_by_competency.svg",
        title="LongMemEval-M controller accuracy by competency",
        groups=competencies,
        series=[
            ("v7", [v7_by_comp[c] for c in competencies], "#756bb1"),
            ("v8 raw", [raw_by_comp[c] for c in competencies], "#2a9d8f"),
            ("v8 adjudicated", [final_by_comp[c] for c in competencies], "#006d77"),
        ],
    )

    replay_by_comp: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in replay_adjudicated.values():
        replay_by_comp[str(row["competency"])].append(row)
    repair_groups = sorted(replay_by_comp)
    repair_rates = [
        sum(bool(row["correct"]) for row in replay_by_comp[group]) / len(replay_by_comp[group])
        for group in repair_groups
    ]
    residual_rates = [
        sum(not bool(row["correct"]) for row in replay_by_comp[group]) / 41
        for group in repair_groups
    ]
    grouped_chart(
        figures / "replay_repair_and_residuals.svg",
        title="Replay repair rate and share of 41 residual errors",
        groups=repair_groups,
        series=[
            ("Repair rate within replay stratum", repair_rates, "#2a9d8f"),
            ("Share of all residual errors", residual_rates, "#e76f51"),
        ],
    )

    mgp = summary["mgp6"]["metrics"]
    mgp_metrics = [
        ("Action accuracy", "action_accuracy"),
        ("Macro-F1", "macro_f1"),
        ("Lineage", "lineage_correctness"),
        ("Artifact semantic", "artifact_semantic_accuracy"),
        ("FAMA both", "fama_presence_absence_conjunction"),
    ]
    grouped_chart(
        figures / "mgp6_governance.svg",
        title="MGP-6 v2 governance metrics (n=180)",
        groups=[label for label, _ in mgp_metrics],
        series=[
            ("B4 overwrite", [mgp[key]["b4"] for _, key in mgp_metrics], "#d97706"),
            ("Rule controller", [mgp[key]["ctl_ref"] for _, key in mgp_metrics], "#4c78a8"),
            ("Qwen controller", [mgp[key]["ctl_llm"] for _, key in mgp_metrics], "#006d77"),
        ],
    )

    manifest = {
        "artifact_version": "v8-failure-replay-adjudicated-1",
        "generated_by": "scripts/build_v8_adjudicated_report.py",
        "counts": summary["integrity"],
        "overrides": OVERRIDES,
        "outputs": [
            "RESULTS.md",
            "FINAL_REPORT_FA.md",
            "PAPER_RESULTS_EN.md",
            "summary.json",
            "adjudication_audit.csv",
            "adjudication_overrides.jsonl",
            "controller/judgments.jsonl",
            "controller/answers.jsonl",
            "controller/predictions.jsonl",
            "controller/report.json",
            "controller_raw/judgments.jsonl",
            "controller_raw/report.json",
            "figures/longmemeval_overall.svg",
            "figures/longmemeval_overall.png",
            "figures/longmemeval_overall.pdf",
            "figures/longmemeval_by_competency.svg",
            "figures/longmemeval_by_competency.png",
            "figures/longmemeval_by_competency.pdf",
            "figures/replay_repair_and_residuals.svg",
            "figures/replay_repair_and_residuals.png",
            "figures/replay_repair_and_residuals.pdf",
            "figures/mgp6_governance.svg",
            "figures/mgp6_governance.png",
            "figures/mgp6_governance.pdf",
        ],
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
