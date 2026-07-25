"""Render an EvalReport JSON as the per-competency markdown table.

Two modes:

    # Single baseline:
    python scripts/print_report.py runs/m1w2/no_memory/report.json \
        > NOTES/m1w2_results.md

    # Merge two baselines (M1-W3 §3.4): renders one row per
    # (baseline, competency) pair, suitable for the second row of
    # Table 4.1 in the thesis.
    python scripts/print_report.py \
        --merge runs/m1w2/no_memory/report.json \
                runs/m1w3/flat_vector/report.json \
        > NOTES/m1w3_results.md

The single-baseline output matches `EvalReport.summarize_markdown()` so the
same table format runs through every later baseline + the controller in
Month 4.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.eval.longmemeval import CompetencyRow, EvalReport  # noqa: E402


def _report_from_dict(d: dict) -> EvalReport:
    rows = [CompetencyRow(**r) for r in d.get("rows", [])]
    return EvalReport(
        baseline_name=d["baseline_name"],
        judge_model_id=d["judge_model_id"],
        n_sessions=d["n_sessions"],
        overall_accuracy=d["overall_accuracy"],
        overall_ci_low=d["overall_ci_low"],
        overall_ci_high=d["overall_ci_high"],
        rows=rows,
    )


def _format_pct(x: float, dp: int = 1) -> str:
    return f"{x * 100:.{dp}f}"


def _format_delta(x: float, dp: int = 1) -> str:
    sign = "+" if x >= 0 else ""
    return f"{sign}{x * 100:.{dp}f}"


def _render_merged_table(reports: list[tuple[Path, EvalReport]], ci_dp: int = 1) -> str:
    """Render a merged Δ-vs-baseline-1 table (M1-W3 §3.4 deliverable).

    The first report listed is the reference baseline; subsequent
    reports' rows show their accuracy plus `Δ` against the reference's
    same-competency row. Acts as the thesis Table 4.1 second-row
    progenitor.
    """
    if len(reports) < 2:
        # Degenerate to single-baseline rendering.
        return reports[0][1].summarize_markdown(ci_decimals=ci_dp)

    ref_path, ref_report = reports[0]
    ref_by_comp: dict[str, CompetencyRow] = {r.competency: r for r in ref_report.rows}

    lines: list[str] = []
    lines.append(f"# Per-competency results — merged across {len(reports)} baselines\n")
    lines.append(f"- **Reference baseline:** `{ref_report.baseline_name}` "
                 f"(`{ref_path}`); n={ref_report.n_sessions}, "
                 f"overall {_format_pct(ref_report.overall_accuracy, ci_dp)}% "
                 f"(95% CI "
                 f"{_format_pct(ref_report.overall_ci_low, ci_dp)} – "
                 f"{_format_pct(ref_report.overall_ci_high, ci_dp)})")
    for path, rep in reports[1:]:
        lines.append(
            f"- **Comparison:** `{rep.baseline_name}` (`{path}`); "
            f"n={rep.n_sessions}, "
            f"overall {_format_pct(rep.overall_accuracy, ci_dp)}% "
            f"(Δ {_format_delta(rep.overall_accuracy - ref_report.overall_accuracy, ci_dp)} pp; "
            f"95% CI {_format_pct(rep.overall_ci_low, ci_dp)} – "
            f"{_format_pct(rep.overall_ci_high, ci_dp)})"
        )
    lines.append("")
    lines.append(f"- **Judge:** `{ref_report.judge_model_id}` "
                 "(same across baselines per M1-W2 §3.0; cache hits when "
                 "answer text coincides).")
    lines.append("")

    # Build the table. One row per (competency, baseline) pair.
    header = (
        ["Competency", "Baseline", "n", "Accuracy", "Δ vs. ref", "95% CI",
         "Avg prompt tokens", "Avg latency (ms)"]
    )
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|---|---|---:|---:|---:|---|---:|---:|")

    competencies = sorted(
        {r.competency for _, rep in reports for r in rep.rows}
    )
    for comp in competencies:
        ref_row = ref_by_comp.get(comp)
        # Reference row first.
        if ref_row is not None:
            lines.append(
                f"| {comp} | {ref_report.baseline_name} | {ref_row.n} | "
                f"{_format_pct(ref_row.accuracy, ci_dp)}% | — | "
                f"{_format_pct(ref_row.accuracy_ci_low, ci_dp)} – "
                f"{_format_pct(ref_row.accuracy_ci_high, ci_dp)} | "
                f"{ref_row.mean_prompt_tokens:.0f} | "
                f"{ref_row.mean_latency_ms:.0f} |"
            )
        # Then each comparison.
        for path, rep in reports[1:]:
            row_by_comp = {r.competency: r for r in rep.rows}
            row = row_by_comp.get(comp)
            if row is None:
                lines.append(
                    f"| {comp} | {rep.baseline_name} | 0 | — | — | — | — | — |"
                )
                continue
            delta = (
                f"{_format_delta(row.accuracy - ref_row.accuracy, ci_dp)} pp"
                if ref_row is not None
                else "—"
            )
            lines.append(
                f"| {comp} | {rep.baseline_name} | {row.n} | "
                f"{_format_pct(row.accuracy, ci_dp)}% | {delta} | "
                f"{_format_pct(row.accuracy_ci_low, ci_dp)} – "
                f"{_format_pct(row.accuracy_ci_high, ci_dp)} | "
                f"{row.mean_prompt_tokens:.0f} | "
                f"{row.mean_latency_ms:.0f} |"
            )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("report_json", type=Path, nargs="?", default=None,
                   help="Single-baseline mode: path to one report.json")
    p.add_argument("--merge", nargs="+", type=Path, default=None,
                   help="Merge mode (M1-W3 §3.4): list two or more report.json paths. "
                        "First is the reference; deltas are computed against it.")
    p.add_argument("--ci-decimals", type=int, default=1)
    args = p.parse_args()

    if args.merge:
        reports = []
        for path in args.merge:
            d = json.loads(path.read_text(encoding="utf-8"))
            reports.append((path, _report_from_dict(d)))
        sys.stdout.write(_render_merged_table(reports, ci_dp=args.ci_decimals))
        # Append per-baseline meta.
        print("\n## Per-baseline run metadata\n")
        for path, rep in reports:
            d = json.loads(path.read_text(encoding="utf-8"))
            wall = d.get("wall_clock_seconds")
            slice_path = d.get("slice_path", "?")
            seed = d.get("seed", "?")
            print(f"- `{rep.baseline_name}` from `{path}`: "
                  f"wall_clock={wall:.1f}s, slice=`{slice_path}`, seed={seed}"
                  if wall is not None
                  else f"- `{rep.baseline_name}` from `{path}`: "
                       f"slice=`{slice_path}`, seed={seed}")
        return 0

    if args.report_json is None:
        p.error("either a positional report_json or --merge is required")

    d = json.loads(args.report_json.read_text(encoding="utf-8"))
    report = _report_from_dict(d)
    sys.stdout.write(report.summarize_markdown(ci_decimals=args.ci_decimals))
    if "wall_clock_seconds" in d:
        print(f"\n_Run wall-clock: {d['wall_clock_seconds']:.1f}s. "
              f"Slice: `{d.get('slice_path', '?')}`. Seed: {d.get('seed', '?')}._\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
