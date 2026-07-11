"""Audit M4-W13 A10G sweep artifacts without launching model runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from m4w13_validation import (
    BASELINE_ALIASES,
    correctness_matrix,
    load_json,
    parse_config_slug,
    telemetry,
    validate_run_dir,
)

STAGE_EXPECTED_ROWS = {
    "pilot": 12,
    "confirm": 50,
    "final": 50,
}


def _systems_for_config(config_dir: Path, stage: str) -> list[str]:
    manifest = load_json(config_dir / "manifest.json") or {}
    systems = manifest.get("systems")
    if isinstance(systems, list) and systems:
        return [str(system) for system in systems]
    if stage == "final":
        present = [alias for alias in BASELINE_ALIASES if (config_dir / alias).exists()]
        return present or list(BASELINE_ALIASES)
    return ["controller"]


def _mean_from_report_rows(report: dict[str, Any], key: str) -> float | None:
    rows = report.get("rows") or []
    weighted = []
    for row in rows:
        if row.get(key) is None:
            continue
        weighted.append((float(row.get("n") or 0), float(row[key])))
    total_n = sum(n for n, _value in weighted)
    if total_n <= 0:
        return None
    return sum(n * value for n, value in weighted) / total_n


def audit_stage(root: Path, stage: str) -> dict[str, Any]:
    stage_dir = root / stage
    expected_rows = STAGE_EXPECTED_ROWS[stage]
    runs = []
    validation_errors: list[str] = []
    validation_warnings: list[str] = []
    controller_runs: dict[str, Path] = {}

    if not stage_dir.exists():
        return {
            "stage": stage,
            "expected_rows": expected_rows,
            "runs": [],
            "validation_errors": [f"stage directory missing: {stage_dir}"],
            "validation_warnings": [],
            "correctness": correctness_matrix({}),
        }

    for config_dir in sorted(path for path in stage_dir.iterdir() if path.is_dir()):
        try:
            config = parse_config_slug(config_dir.name)
        except ValueError:
            continue
        systems = _systems_for_config(config_dir, stage)
        system_rows = []
        complete = True
        for system in systems:
            run_dir = config_dir / system
            validation = validate_run_dir(
                run_dir,
                expected_rows=expected_rows,
                stage=stage,
                config_slug=config_dir.name,
                system=system,
            )
            validation_errors.extend(validation.errors)
            validation_warnings.extend(validation.warnings)
            complete = complete and validation.ok
            report = validation.report or {}
            row = {
                "system": system,
                "complete": validation.ok,
                "n_sessions": report.get("n_sessions"),
                "overall_accuracy": report.get("overall_accuracy"),
                "overall_ci_low": report.get("overall_ci_low"),
                "overall_ci_high": report.get("overall_ci_high"),
                "wall_clock_seconds": report.get("wall_clock_seconds"),
                "mean_prompt_tokens": _mean_from_report_rows(report, "mean_prompt_tokens"),
                "mean_latency_ms": _mean_from_report_rows(report, "mean_latency_ms"),
                "validation_errors": validation.errors,
                "validation_warnings": validation.warnings,
            }
            row.update(telemetry(run_dir))
            system_rows.append(row)
        if complete and "controller" in systems:
            controller_runs[config_dir.name] = config_dir / "controller"
        runs.append(
            {
                "config_slug": config_dir.name,
                "config": config,
                "complete": complete,
                "systems": system_rows,
            }
        )

    runs.sort(
        key=lambda row: (
            not row["complete"],
            -float((row["systems"][0] or {}).get("overall_accuracy") or 0.0)
            if row["systems"]
            else 0.0,
            float((row["systems"][0] or {}).get("wall_clock_seconds") or 10**12)
            if row["systems"]
            else 10**12,
            row["config_slug"],
        )
    )
    return {
        "stage": stage,
        "expected_rows": expected_rows,
        "runs": runs,
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "correctness": correctness_matrix(controller_runs),
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def render_stage_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# M4-W13 {str(report['stage']).title()} Audit",
        "",
        "| Config | System | Complete | n | Accuracy | Wall-clock | Prompt toks | Latency ms | Retrieved avg | Leaks |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run in report["runs"]:
        for system in run["systems"]:
            lines.append(
                f"| `{run['config_slug']}` | `{system['system']}` | {system['complete']} | "
                f"{system.get('n_sessions') or 'n/a'} | {_pct(system.get('overall_accuracy'))} | "
                f"{system.get('wall_clock_seconds') or 'n/a'} | "
                f"{system.get('mean_prompt_tokens') or 'n/a'} | "
                f"{system.get('mean_latency_ms') or 'n/a'} | "
                f"{system.get('retrieved_avg') or 'n/a'} | "
                f"{system.get('current_session_leakage_count') or 0} |"
            )

    matrix = report["correctness"]
    if matrix["configs"]:
        lines.extend(
            [
                "",
                "## Controller Correctness Matrix",
                "",
                f"- Identical correctness across configs: {matrix['identical_correctness']}",
                f"- All configs right: {', '.join(matrix['all_right']) or 'none'}",
                f"- All configs wrong: {', '.join(matrix['all_wrong']) or 'none'}",
                f"- Disagreements: {', '.join(matrix['disagreements']) or 'none'}",
                "",
                "| Session | " + " | ".join(f"`{config}`" for config in matrix["configs"]) + " |",
                "|---|" + "|".join("---:" for _ in matrix["configs"]) + "|",
            ]
        )
        for row in matrix["matrix"]:
            values = []
            for config in matrix["configs"]:
                correct = row["correct"].get(config)
                values.append("n/a" if correct is None else ("✓" if correct else "✗"))
            lines.append(f"| `{row['session_id']}` | " + " | ".join(values) + " |")

    if report["validation_errors"]:
        lines.extend(["", "## Validation Errors", ""])
        lines.extend(f"- {error}" for error in report["validation_errors"])
    if report["validation_warnings"]:
        lines.extend(["", "## Validation Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["validation_warnings"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--stages", nargs="+", choices=sorted(STAGE_EXPECTED_ROWS), default=["pilot", "confirm"])
    parser.add_argument("--fail-on-incomplete", action="store_true")
    parser.add_argument("--write-summary", action="store_true")
    args = parser.parse_args()

    reports = [audit_stage(args.root, stage) for stage in args.stages]
    for report in reports:
        markdown = render_stage_markdown(report)
        if args.write_summary:
            stage_dir = args.root / str(report["stage"])
            stage_dir.mkdir(parents=True, exist_ok=True)
            (stage_dir / f"{report['stage']}_audit_summary.json").write_text(
                json.dumps(report, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            (stage_dir / f"{report['stage']}_audit_summary.md").write_text(
                markdown,
                encoding="utf-8",
            )
        else:
            print(markdown)

    errors = [error for report in reports for error in report["validation_errors"]]
    if args.fail_on_incomplete and errors:
        raise SystemExit(
            "M4-W13 sweep validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
