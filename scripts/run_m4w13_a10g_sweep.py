"""A10G-budgeted M4-W13 controller tuning workflow.

Stages:
  pilot   - run six fixed controller configs on 12 sessions.
  confirm - run the top two pilot configs on 50 sessions.
  final   - run all five systems with the best confirmed config.

The script delegates actual evaluation to the resumable HF parallel runner but
keeps max-workers at 1 so an A10G only hosts one Transformers process at a time.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from m4w13_validation import (
    BASELINE_ALIASES,
    correctness_matrix,
    telemetry,
    validate_run_dir,
)
from m4w13_validation import (
    parse_config_slug as _parse_config_slug_values,
)
from run_m4w13_hf import (  # noqa: E402
    _MAX_A10G_MODEL,
    _QUALITY_PRESET_MAX_A10G,
    _QUALITY_PRESET_NONE,
    _QUALITY_PRESETS,
    _preferred_python,
)


@dataclass(frozen=True)
class SweepConfig:
    top_k: int
    retrieval_k: int
    neighbor_window: int
    extraction_tokens: int
    relation_tokens: int


PILOT_CONFIGS: tuple[SweepConfig, ...] = (
    SweepConfig(8, 5, 2, 128, 64),
    SweepConfig(16, 5, 2, 128, 64),
    SweepConfig(16, 8, 2, 128, 64),
    SweepConfig(16, 8, 0, 128, 64),
    SweepConfig(16, 8, 2, 192, 96),
    SweepConfig(24, 8, 2, 192, 96),
)

MAX_A10G_CONFIG = SweepConfig(64, 12, 2, 256, 128)


@dataclass(frozen=True)
class StageRun:
    stage: str
    config: SweepConfig
    out_dir: Path
    command: list[str]


def config_slug(config: SweepConfig) -> str:
    return (
        f"tk{config.top_k:02d}-rk{config.retrieval_k:02d}-"
        f"w{config.neighbor_window:02d}-t{config.extraction_tokens}-{config.relation_tokens}"
    )


def parse_config_slug(slug: str) -> SweepConfig:
    values = _parse_config_slug_values(slug)
    return SweepConfig(**values)


def _expected_stage_rows(stage: str, args: argparse.Namespace) -> int:
    return args.pilot_limit if stage == "pilot" else args.confirm_limit


def _shell_join(cmd: list[str]) -> str:
    return shlex.join(str(part) for part in cmd)


def _runner_command(
    args: argparse.Namespace,
    *,
    config: SweepConfig,
    out_dir: Path,
    systems: str,
    limit: int,
    zip_results: bool,
) -> list[str]:
    cmd = [
        _preferred_python(),
        "scripts/run_m4w13_hf_a100_parallel.py",
        "--slice",
        str(args.slice),
        "--out",
        str(out_dir),
        "--systems",
        systems,
        "--limit",
        str(limit),
        "--max-workers",
        "1",
        "--status-s",
        str(args.status_s),
        "--hf-model",
        args.hf_model,
        "--hf-dtype",
        args.hf_dtype,
        "--judge-backend",
        args.judge_backend,
        "--embedder-backend",
        args.embedder_backend,
        "--embedder-device",
        args.embedder_device,
        "--retrieval-k",
        str(config.retrieval_k),
        "--controller-memory-top-k",
        str(config.top_k),
        "--recency-memory-top-k",
        str(config.top_k),
        "--controller-retrieval-neighbor-window",
        str(config.neighbor_window),
        "--extraction-max-new-tokens",
        str(config.extraction_tokens),
        "--relation-max-new-tokens",
        str(config.relation_tokens),
        "--no-require-a100",
        "--resume" if args.resume else "--no-resume",
    ]
    if args.quality_preset != _QUALITY_PRESET_NONE:
        cmd.extend(["--quality-preset", args.quality_preset])
    if args.answer_retry_on_unknown:
        cmd.append("--answer-retry-on-unknown")
    else:
        cmd.append("--no-answer-retry-on-unknown")
    cmd.extend(["--controller-prior-top-k", str(args.controller_prior_top_k)])
    if args.controller_include_assistant_context:
        cmd.append("--controller-include-assistant-context")
    if args.judge_model:
        cmd.extend(["--judge-model", args.judge_model])
    if args.extractor_model:
        cmd.extend(["--extractor-model", args.extractor_model])
    if args.classifier_model:
        cmd.extend(["--classifier-model", args.classifier_model])
    if args.hf_load_in_4bit:
        cmd.append("--hf-load-in-4bit")
    if args.hf_trust_remote_code:
        cmd.append("--hf-trust-remote-code")
    if args.no_prefetch:
        cmd.append("--no-prefetch")
    if args.clean_incomplete:
        cmd.append("--clean-incomplete")
    if not zip_results or args.no_zip:
        cmd.append("--no-zip")
    return cmd


def _load_report(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _score_config(
    root: Path,
    stage: str,
    config: SweepConfig,
    *,
    expected_rows: int | None,
) -> tuple[float, float, int] | None:
    slug = config_slug(config)
    run_dir = root / stage / slug / "controller"
    validation = validate_run_dir(
        run_dir,
        expected_rows=expected_rows,
        stage=stage,
        config_slug=slug,
        system="controller",
        baseline="controller",
    )
    if not validation.ok or validation.report is None:
        return None
    report = validation.report
    return (
        float(report.get("overall_accuracy") or 0.0),
        float(report.get("wall_clock_seconds") or 10**12),
        int(report.get("n_sessions") or 0),
    )


def select_top_configs(
    root: Path,
    stage: str,
    n: int,
    *,
    expected_rows: int | None = None,
) -> list[SweepConfig]:
    scored: list[tuple[float, float, int, SweepConfig]] = []
    invalid: list[str] = []
    for config in PILOT_CONFIGS:
        score = _score_config(root, stage, config, expected_rows=expected_rows)
        if score is None:
            slug = config_slug(config)
            validation = validate_run_dir(
                root / stage / slug / "controller",
                expected_rows=expected_rows,
                stage=stage,
                config_slug=slug,
                system="controller",
                baseline="controller",
            )
            invalid.extend(validation.errors)
            continue
        accuracy, wall_clock, rows = score
        scored.append((accuracy, wall_clock, rows, config))
    if not scored:
        detail = "\n".join(f"  - {error}" for error in invalid[:12])
        suffix = f"\nInvalid candidates:\n{detail}" if detail else ""
        raise SystemExit(
            f"no valid complete {stage} controller reports found under {root / stage}{suffix}"
        )
    scored.sort(key=lambda row: (-row[0], row[1], -row[2], config_slug(row[3])))
    return [row[3] for row in scored[:n]]


def build_stage_runs(args: argparse.Namespace) -> list[StageRun]:
    if args.quality_preset == _QUALITY_PRESET_MAX_A10G:
        configs = [MAX_A10G_CONFIG]
        systems = "all" if args.stage == "final" else "controller"
        limit = args.pilot_limit if args.stage == "pilot" else args.confirm_limit
        zip_results = args.stage == "final"
    elif args.stage == "pilot":
        configs = list(PILOT_CONFIGS)
        systems = "controller"
        limit = args.pilot_limit
        zip_results = False
    elif args.stage == "confirm":
        configs = select_top_configs(args.out, "pilot", 2, expected_rows=args.pilot_limit)
        systems = "controller"
        limit = args.confirm_limit
        zip_results = False
    else:
        configs = select_top_configs(args.out, "confirm", 1, expected_rows=args.confirm_limit)
        systems = "all"
        limit = args.confirm_limit
        zip_results = True

    runs = []
    for config in configs:
        out_dir = args.out / args.stage / config_slug(config)
        runs.append(
            StageRun(
                stage=args.stage,
                config=config,
                out_dir=out_dir,
                command=_runner_command(
                    args,
                    config=config,
                    out_dir=out_dir,
                    systems=systems,
                    limit=limit,
                    zip_results=zip_results,
                ),
            )
        )
    return runs


def _write_config_manifest(run: StageRun) -> None:
    run.out_dir.mkdir(parents=True, exist_ok=True)
    tier = "pilot" if run.stage in {"pilot", "confirm"} else "final-candidate"
    payload = {
        "stage": run.stage,
        "tier": tier,
        "run_tier": tier,
        "judge_tier": "same_as_answerer",
        "raw_turn_fallback": True,
        "quality_preset": _quality_preset_from_command(run.command),
        "complete": False,
        "thesis_use": "no_final_claim" if tier == "pilot" else "final_candidate_pending_review",
        "config": asdict(run.config),
        "config_slug": config_slug(run.config),
        "command": run.command,
    }
    (run.out_dir / "sweep_config.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _quality_preset_from_command(cmd: list[str]) -> str:
    try:
        return str(cmd[cmd.index("--quality-preset") + 1])
    except (ValueError, IndexError):
        return _QUALITY_PRESET_NONE


def _systems_for_run(run: StageRun) -> list[str]:
    try:
        raw = run.command[run.command.index("--systems") + 1]
    except (ValueError, IndexError):
        raw = "controller"
    if raw == "all":
        return list(BASELINE_ALIASES)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _stage_summary(
    root: Path,
    stage: str,
    runs: list[StageRun],
    *,
    expected_rows: int,
) -> dict[str, Any]:
    rows = []
    validation_errors: list[str] = []
    validation_warnings: list[str] = []
    controller_runs: dict[str, Path] = {}
    for run in runs:
        slug = config_slug(run.config)
        systems = _systems_for_run(run)
        system_validations = [
            validate_run_dir(
                run.out_dir / system,
                expected_rows=expected_rows,
                stage=stage,
                config_slug=slug,
                system=system,
            )
            for system in systems
        ]
        for validation in system_validations:
            validation_errors.extend(validation.errors)
            validation_warnings.extend(validation.warnings)
        controller_validation = next(
            (
                validation
                for validation, system in zip(system_validations, systems)
                if system == "controller"
            ),
            system_validations[0] if system_validations else None,
        )
        report = controller_validation.report if controller_validation else None
        complete = all(validation.ok for validation in system_validations) and bool(
            system_validations
        )
        if complete and "controller" in systems:
            controller_runs[slug] = run.out_dir / "controller"
        if report is None:
            rows.append(
                {
                    "stage": stage,
                    "config_slug": slug,
                    "config": asdict(run.config),
                    "complete": False,
                    "systems": systems,
                    "validation_errors": [
                        error for validation in system_validations for error in validation.errors
                    ],
                }
            )
            continue
        run_telemetry = telemetry(run.out_dir / "controller")
        rows.append(
            {
                "stage": stage,
                "config_slug": slug,
                "config": asdict(run.config),
                "complete": complete,
                "systems": systems,
                "n_sessions": report.get("n_sessions"),
                "overall_accuracy": report.get("overall_accuracy"),
                "overall_ci_low": report.get("overall_ci_low"),
                "overall_ci_high": report.get("overall_ci_high"),
                "wall_clock_seconds": report.get("wall_clock_seconds"),
                "judge_model_id": report.get("judge_model_id"),
                "n_predictions": run_telemetry.get("n_predictions"),
                "retrieved_avg": run_telemetry.get("retrieved_avg"),
                "current_session_leakage_count": run_telemetry.get("current_session_leakage_count"),
                "validation_errors": [
                    error for validation in system_validations for error in validation.errors
                ],
                "validation_warnings": [
                    warning for validation in system_validations for warning in validation.warnings
                ],
            }
        )
    rows.sort(
        key=lambda row: (
            not row.get("complete", False),
            -float(row.get("overall_accuracy") or 0.0),
            float(row.get("wall_clock_seconds") or 10**12),
            str(row["config_slug"]),
        )
    )
    matrix = (
        correctness_matrix(controller_runs)
        if controller_runs
        else {
            "configs": [],
            "matrix": [],
            "all_right": [],
            "all_wrong": [],
            "disagreements": [],
            "identical_correctness": True,
        }
    )
    summary = {
        "stage": stage,
        "expected_rows": expected_rows,
        "runs": rows,
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "correctness": matrix,
    }
    stage_dir = root / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / f"{stage}_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        f"# A10G {stage.title()} Summary",
        "",
        "| Config | Complete | n | Accuracy | 95% CI | Retrieved avg | Leaks | Wall-clock |",
        "|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for row in rows:
        acc = row.get("overall_accuracy")
        lo = row.get("overall_ci_low")
        hi = row.get("overall_ci_high")
        lines.append(
            f"| `{row['config_slug']}` | {row.get('complete', False)} | "
            f"{row.get('n_sessions', 'n/a')} | "
            f"{acc * 100:.1f}%"
            if isinstance(acc, float)
            else f"| `{row['config_slug']}` | {row.get('complete', False)} | n/a | n/a"
        )
        if isinstance(acc, float):
            lines[-1] += (
                f" | {float(lo) * 100:.1f}% - {float(hi) * 100:.1f}% | "
                f"{row.get('retrieved_avg', 'n/a')} | "
                f"{row.get('current_session_leakage_count', 'n/a')} | "
                f"{row.get('wall_clock_seconds', 'n/a')} |"
            )
        else:
            lines[-1] += " | n/a | n/a | n/a | n/a |"
    if matrix["configs"]:
        lines.extend(
            [
                "",
                "## Correctness Matrix",
                "",
                f"- Identical correctness across controller configs: {matrix['identical_correctness']}",
                f"- All configs right: {', '.join(matrix['all_right']) or 'none'}",
                f"- All configs wrong: {', '.join(matrix['all_wrong']) or 'none'}",
                f"- Disagreements: {', '.join(matrix['disagreements']) or 'none'}",
                "",
                "| Session | " + " | ".join(f"`{config}`" for config in matrix["configs"]) + " |",
                "|---|" + "|".join("---:" for _ in matrix["configs"]) + "|",
            ]
        )
        for matrix_row in matrix["matrix"]:
            cells = []
            for config in matrix["configs"]:
                value = matrix_row["correct"].get(config)
                cells.append("n/a" if value is None else ("✓" if value else "✗"))
            lines.append(f"| `{matrix_row['session_id']}` | " + " | ".join(cells) + " |")
    if validation_errors:
        lines.extend(["", "## Validation Errors", ""])
        lines.extend(f"- {error}" for error in validation_errors)
    if validation_warnings:
        lines.extend(["", "## Validation Warnings", ""])
        lines.extend(f"- {warning}" for warning in validation_warnings)
    (stage_dir / f"{stage}_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--slice", type=Path, default=Path("/content/longmemeval/longmemeval_s_cleaned.json")
    )
    p.add_argument("--out", type=Path, default=Path("runs/m4w13_a10g_sweep"))
    p.add_argument("--stage", choices=("pilot", "confirm", "final"), required=True)
    p.add_argument("--pilot-limit", type=int, default=12)
    p.add_argument("--confirm-limit", type=int, default=50)
    p.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--status-s", type=float, default=30.0)
    p.add_argument(
        "--quality-preset",
        choices=_QUALITY_PRESETS,
        default=_QUALITY_PRESET_NONE,
        help="Lock an accuracy-first runtime profile. 'max-a10g' "
        "runs a single fixed controller quality config and "
        "passes the preset through to the HF runner.",
    )
    p.add_argument("--hf-model", default="Qwen/Qwen2.5-3B-Instruct")
    p.add_argument("--hf-dtype", choices=("bfloat16", "float16", "float32"), default="float16")
    p.add_argument(
        "--judge-backend",
        choices=("same_as_answerer", "hf", "huggingface", "ollama", "fake"),
        default="same_as_answerer",
    )
    p.add_argument("--judge-model", default=None)
    p.add_argument("--extractor-model", default=None)
    p.add_argument("--classifier-model", default=None)
    p.add_argument("--hf-load-in-4bit", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--hf-trust-remote-code", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument(
        "--embedder-backend",
        choices=("sentence_transformer", "ollama"),
        default="sentence_transformer",
    )
    p.add_argument("--embedder-device", default="auto")
    p.add_argument(
        "--controller-include-assistant-context",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument(
        "--answer-retry-on-unknown", action=argparse.BooleanOptionalAction, default=False
    )
    p.add_argument("--controller-prior-top-k", type=int, default=1)
    p.add_argument("--no-prefetch", action="store_true")
    p.add_argument(
        "--clean-incomplete",
        action="store_true",
        help="Archive incomplete run directories before rerunning. "
        "Without this, stale zero-line or mismatched artifacts fail fast.",
    )
    p.add_argument("--no-zip", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if args.quality_preset == _QUALITY_PRESET_MAX_A10G:
        args.hf_model = _MAX_A10G_MODEL
        args.hf_dtype = "float16"
        args.hf_load_in_4bit = False
        args.controller_include_assistant_context = True
        args.answer_retry_on_unknown = True
        args.controller_prior_top_k = 3

    runs = build_stage_runs(args)
    for run in runs:
        if args.dry_run:
            print(_shell_join(run.command))
            continue
        _write_config_manifest(run)
        print(f"[a10g-sweep] {run.stage} {config_slug(run.config)}", flush=True)
        print("$ " + _shell_join(run.command), flush=True)
        subprocess.run(run.command, check=True)
    if not args.dry_run:
        summary = _stage_summary(
            args.out,
            args.stage,
            runs,
            expected_rows=_expected_stage_rows(args.stage, args),
        )
        if summary["validation_errors"]:
            raise SystemExit(
                "stage validation failed:\n"
                + "\n".join(f"  - {error}" for error in summary["validation_errors"])
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
