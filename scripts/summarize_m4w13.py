"""Summarize M4-W13 run directories with SMRR and anti-leakage telemetry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from m4w13_validation import (
    BASELINE_ALIASES,
    load_jsonl,
    validate_run_dir,
)
from m4w13_validation import (
    telemetry as run_telemetry,
)

BASELINE_TO_ALIAS = {
    "no_memory": "b1",
    "flat_vector": "b2",
    "recency": "b3",
    "naive_overwrite": "b4",
    "controller": "controller",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows, _errors = load_jsonl(path)
    return rows


def _judgment_accuracy(run_dir: Path) -> float | None:
    judgments = _iter_jsonl(run_dir / "judgments.jsonl")
    if not judgments:
        return None
    return sum(1 for row in judgments if bool(row.get("correct"))) / len(judgments)


def _report_warnings(run_dir: Path, report: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    expected_n = int(report.get("n_sessions") or 0)
    for name in ("answers.jsonl", "predictions.jsonl", "judgments.jsonl"):
        path = run_dir / name
        rows = _iter_jsonl(path)
        if len(rows) != expected_n:
            warnings.append(f"{path} has {len(rows)} rows, expected {expected_n}")
    judged_accuracy = _judgment_accuracy(run_dir)
    reported_accuracy = report.get("overall_accuracy")
    if judged_accuracy is not None and reported_accuracy is not None:
        if abs(float(reported_accuracy) - judged_accuracy) > 1e-12:
            warnings.append(
                f"{run_dir / 'report.json'} accuracy={reported_accuracy} does not "
                f"match judgments.jsonl accuracy={judged_accuracy}"
            )
    return warnings


def _select_aliases(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    if value == "all":
        return BASELINE_ALIASES
    requested = [item.strip() for item in value.split(",") if item.strip()]
    aliases: set[str] = set()
    known = set(BASELINE_ALIASES) | set(BASELINE_TO_ALIAS)
    unknown = set(requested) - known
    if unknown:
        raise SystemExit(f"unknown systems requested: {sorted(unknown)}")
    for item in requested:
        aliases.add(BASELINE_TO_ALIAS.get(item, item))
    return tuple(alias for alias in BASELINE_ALIASES if alias in aliases)


def summarize(root: Path, *, systems: str | None = None) -> dict[str, Any]:
    manifest = _load_json(root / "manifest.json") if (root / "manifest.json").exists() else {}
    selected_aliases = _select_aliases(systems)
    target_aliases = selected_aliases or tuple(manifest.get("systems") or BASELINE_ALIASES)
    expected_rows = manifest.get("limit")
    expected_rows = int(expected_rows) if expected_rows is not None else None
    rows = []
    missing = []
    warnings = []
    validation_errors = []
    for alias in target_aliases:
        run_dir = root / alias
        report_path = run_dir / "report.json"
        if not report_path.exists():
            missing.append(alias)
            continue
        report = _load_json(report_path)
        validation = validate_run_dir(
            run_dir,
            expected_rows=expected_rows,
            system=alias,
            baseline=str(report.get("baseline_name") or ""),
        )
        validation_errors.extend(validation.errors)
        warnings.extend(validation.warnings)
        rows.append(
            {
                "alias": alias,
                "baseline": report["baseline_name"],
                "complete": validation.ok,
                "n_sessions": report["n_sessions"],
                "overall_accuracy": report["overall_accuracy"],
                "overall_ci_low": report["overall_ci_low"],
                "overall_ci_high": report["overall_ci_high"],
                "wall_clock_seconds": report.get("wall_clock_seconds"),
                "judge_model_id": report["judge_model_id"],
                "validation_errors": validation.errors,
                "validation_warnings": validation.warnings,
                **run_telemetry(run_dir),
            }
        )
    manifest_systems = set(target_aliases if manifest.get("systems") else ())
    present = {row["alias"] for row in rows}
    if manifest_systems and present - manifest_systems:
        warnings.append(
            "manifest systems do not include present run directories: "
            + ", ".join(sorted(present - manifest_systems))
        )
    return {
        "manifest": manifest,
        "runs": rows,
        "missing_systems": missing,
        "warnings": warnings,
        "validation_errors": validation_errors,
    }


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# M4-W13 Run Summary",
        "",
        "| System | n | Accuracy | 95% CI | SMRR | Current-session leaks | Wall-clock |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for row in summary["runs"]:
        lines.append(
            f"| {row['alias']} `{row['baseline']}` | {row['n_sessions']} | "
            f"{_pct(row['overall_accuracy'])} | "
            f"{_pct(row['overall_ci_low'])} - {_pct(row['overall_ci_high'])} | "
            f"{_pct(row['smrr'])} | {row['current_session_leakage_count']} | "
            f"{row.get('wall_clock_seconds') or 'n/a'} |"
        )
    if summary.get("missing_systems"):
        lines.extend(
            [
                "",
                "> Missing systems: " + ", ".join(summary["missing_systems"]),
            ]
        )
    if summary.get("warnings"):
        lines.append("")
        for warning in summary["warnings"]:
            lines.append(f"> Warning: {warning}")
    if summary.get("validation_errors"):
        lines.append("")
        for error in summary["validation_errors"]:
            lines.append(f"> Validation error: {error}")
    manifest = summary.get("manifest") or {}
    if manifest.get("slice_is_synthetic"):
        lines.extend(
            [
                "",
                "> Warning: the manifest marks this slice as synthetic. These are "
                "pipeline numbers, not publication-eligible LongMemEval-S results.",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path, nargs="?", default=Path("runs/m4w13"))
    p.add_argument(
        "--systems",
        default=None,
        help="Override manifest systems for merged multi-device outputs. "
             "Accepts all, b1, controller, or comma lists such as b1,controller.",
    )
    p.add_argument("--json-out", type=Path, default=None)
    p.add_argument("--md-out", type=Path, default=None)
    p.add_argument("--require-complete", action="store_true")
    args = p.parse_args()

    summary = summarize(args.root, systems=args.systems)
    if args.json_out:
        args.json_out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    markdown = render_markdown(summary)
    if args.md_out:
        args.md_out.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    if args.require_complete and (
        summary["missing_systems"] or summary["validation_errors"] or summary["warnings"]
    ):
        reasons = []
        if summary["missing_systems"]:
            reasons.append("missing systems: " + ", ".join(summary["missing_systems"]))
        if summary["validation_errors"]:
            reasons.append("validation errors: " + "; ".join(summary["validation_errors"]))
        if summary["warnings"]:
            reasons.append("warnings: " + "; ".join(summary["warnings"]))
        raise SystemExit(
            "incomplete M4-W13 run: " + " | ".join(reasons)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
