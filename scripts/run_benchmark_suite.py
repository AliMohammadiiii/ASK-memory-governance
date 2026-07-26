#!/usr/bin/env python3
"""Run or audit the public MGP-6 v4.3 and archived memory-benchmark suites.

The command is deliberately conservative:

* MGP-6 v4.3 runs are confined to its tracked public train/dev release.
* A v4.3 hidden run is never a suite task.
* The sibling ``memory_benchmarks`` workspace is an archived MGP-6 v3.3.2
  harness.  Its fixture is private and test-only, so execution requires two
  explicit opt-ins and is always reported as non-scientific fixture evidence.
* All new logs and reports are written beneath this repository's ignored
  ``runs/`` directory.  The archived workspace is not modified by an audit.

Use ``--run-offline`` for the local v4.3 rules controller plus archival
readiness/status audit.  Add ``--execute-models`` only after exporting a
fresh, non-exposed ``OPENROUTER_API_KEY`` in the shell.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    # Keep this script directly runnable from a clean checkout, matching the
    # existing scripts/ command-line convention without requiring installation.
    sys.path.insert(0, str(SRC_ROOT))

from ask.eval.mgp6_v43 import MGP6V43_RUNNABLE_SYSTEMS, MGP6V43_SUCCESSOR_SYSTEMS  # noqa: E402

DEFAULT_PUBLIC_DEV = REPO_ROOT / "benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "runs/benchmark_suite"
DEFAULT_MEMORY_BENCHMARKS_ROOT = REPO_ROOT.parent / "memory_benchmarks"
MODEL_ID = "qwen/qwen3.5-9b"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class SuiteTask:
    """One bounded command in the benchmark suite."""

    task_id: str
    family: str
    classification: str
    command: tuple[str, ...]
    cwd: Path
    requires_model: bool = False
    requires_external_fixture_opt_in: bool = False
    description: str = ""


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _require_public_v43_input(path: Path) -> Path:
    public_root = REPO_ROOT / "benchmarks/mgp6/mgp6_v4_3/public"
    resolved = path.resolve()
    if not _is_within(resolved, public_root) or resolved.name not in {"train.jsonl", "dev.jsonl"}:
        raise ValueError(
            "MGP-6 v4.3 suite input must be the tracked public train.jsonl or dev.jsonl"
        )
    return resolved


def _require_suite_output(path: Path) -> Path:
    resolved = path.resolve()
    if not _is_within(resolved, REPO_ROOT / "runs"):
        raise ValueError("suite output must be beneath this repository's ignored runs/ directory")
    return resolved


def _v43_run_command(
    *, python: str, system: str, input_path: Path, output: Path
) -> tuple[str, ...]:
    command = [
        python,
        "scripts/run_mgp6_v43.py",
        "--input",
        str(input_path),
        "--out",
        str(output),
        "--system",
        system,
        "--seed",
        "4301",
        "--max-new-tokens",
        "128",
    ]
    if system != "rules_controller":
        command.extend(
            [
                "--provider",
                "openrouter",
                "--base-url",
                OPENROUTER_BASE_URL,
                "--api-key-env",
                "OPENROUTER_API_KEY",
                "--model-id",
                MODEL_ID,
                "--reasoning-effort",
                "none",
            ]
        )
    return tuple(command)


def _v43_score_command(*, python: str, input_path: Path, output: Path) -> tuple[str, ...]:
    return (
        python,
        "scripts/score_mgp6_v43.py",
        "--input",
        str(input_path),
        "--predictions",
        str(output / "predictions.jsonl"),
        "--raw-responses",
        str(output / "raw_responses.jsonl"),
        "--run-manifest",
        str(output / "run_manifest.json"),
        "--out",
        str(output / "public_dev_metrics.json"),
    )


def build_tasks(
    *,
    python: str,
    input_path: Path,
    output_root: Path,
    memory_benchmarks_root: Path,
) -> list[SuiteTask]:
    """Create every supported task without executing or reading release records."""

    tasks: list[SuiteTask] = []
    for system in MGP6V43_RUNNABLE_SYSTEMS:
        system_output = output_root / "mgp6_v43_public_dev" / system
        tasks.append(
            SuiteTask(
                task_id=f"v43:{system}",
                family="mgp6_v43_public_dev",
                classification=(
                    "post-final public-dev candidate"
                    if system in MGP6V43_SUCCESSOR_SYSTEMS
                    else "public development experiment"
                ),
                command=_v43_run_command(
                    python=python, system=system, input_path=input_path, output=system_output
                ),
                cwd=REPO_ROOT,
                requires_model=system != "rules_controller",
                description="Generate public-only predictions; the scorer is scheduled after success.",
            )
        )

    harness = memory_benchmarks_root / "harnesses/mgp6_v3_3_2"
    external_python = memory_benchmarks_root / "environments/mgp6-v3.3.2/bin/python"
    preflight_output = output_root / "memory_benchmarks_v332" / "PREFLIGHT.json"
    tasks.extend(
        [
            SuiteTask(
                task_id="v332:archival-preflight",
                family="memory_benchmarks_v332",
                classification="archival readiness audit; no model calls",
                command=(
                    str(external_python),
                    str(harness / "scripts/preflight.py"),
                    "--output",
                    str(preflight_output),
                ),
                cwd=memory_benchmarks_root,
                description="Reads registry and availability checks only; writes audit output in this repo.",
            ),
            SuiteTask(
                task_id="v332:archival-status",
                family="memory_benchmarks_v332",
                classification="archival status audit; no model calls",
                command=(
                    str(external_python),
                    str(harness / "scripts/summarize_benchmark_suite.py"),
                    "--preflight",
                    str(preflight_output),
                    "--run-root",
                    str(memory_benchmarks_root / "runs/mgp6_v3_3_2"),
                    "--output",
                    str(output_root / "memory_benchmarks_v332" / "BENCHMARK_SUITE_STATUS.json"),
                ),
                cwd=memory_benchmarks_root,
                description="Summarizes existing archived evidence without changing it.",
            ),
            SuiteTask(
                task_id="v332:core-fixture-suite",
                family="memory_benchmarks_v332",
                classification="private test-only fixture; never scientific",
                command=("make", "mgp6-run-ready-suite", f"OPENROUTER_MODEL={MODEL_ID}"),
                cwd=memory_benchmarks_root,
                requires_model=True,
                requires_external_fixture_opt_in=True,
                description="Official archived core-suite entry point; may resume historical fixture outputs.",
            ),
            SuiteTask(
                task_id="v332:native-memory-fixture-suite",
                family="memory_benchmarks_v332",
                classification="private test-only fixture; never scientific",
                command=("make", "mgp6-external-fixture-all", f"OPENROUTER_MODEL={MODEL_ID}"),
                cwd=memory_benchmarks_root,
                requires_model=True,
                requires_external_fixture_opt_in=True,
                description="Official Mem0/Letta/Graphiti/MemOS fixture entry point; may resume archives.",
            ),
        ]
    )
    return tasks


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Benchmark suite report",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- MGP-6 v4.3 input: `{report['public_v43_input']}`",
        "- v4.3 hidden input/gold: **not accessible to this suite**",
        "- Archived v3.3.2 fixture results: **test-only, not scientific evidence**",
        "",
        "| Task | Classification | Status | Note |",
        "|---|---|---|---|",
    ]
    for row in report["tasks"]:
        note = str(row.get("note", "")).replace("|", "\\|")
        lines.append(
            f"| `{row['task_id']}` | {row['classification']} | {row['status']} | {note or '—'} |"
        )
    lines.extend(
        [
            "",
            "Model tasks require a newly rotated `OPENROUTER_API_KEY` in the environment; keys are never accepted as command-line arguments or written to this report.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _task_row(task: SuiteTask, *, status: str, note: str = "", **extra: Any) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "family": task.family,
        "classification": task.classification,
        "status": status,
        "note": note,
        "command": list(task.command),
        "cwd": str(task.cwd),
        **extra,
    }


def _run_task(task: SuiteTask, *, output_root: Path) -> dict[str, Any]:
    log_root = output_root / "logs" / task.task_id.replace(":", "__")
    log_root.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        task.command,
        cwd=task.cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    (log_root / "stdout.log").write_text(completed.stdout, encoding="utf-8")
    (log_root / "stderr.log").write_text(completed.stderr, encoding="utf-8")
    return _task_row(
        task,
        status="completed" if completed.returncode == 0 else "failed",
        note=f"exit={completed.returncode}; logs={log_root.relative_to(output_root)}",
        returncode=completed.returncode,
        stdout_log=str(log_root / "stdout.log"),
        stderr_log=str(log_root / "stderr.log"),
    )


def _append_v43_score(
    rows: list[dict[str, Any]], *, task: SuiteTask, python: str, input_path: Path, output_root: Path
) -> None:
    if rows[-1]["status"] != "completed":
        return
    system = task.task_id.split(":", maxsplit=1)[1]
    prediction_root = output_root / "mgp6_v43_public_dev" / system
    score_task = SuiteTask(
        task_id=f"v43-score:{system}",
        family="mgp6_v43_public_dev",
        classification=task.classification,
        command=_v43_score_command(python=python, input_path=input_path, output=prediction_root),
        cwd=REPO_ROOT,
        description="Scores public dev labels only.",
    )
    score_row = _run_task(score_task, output_root=output_root)
    metrics_path = prediction_root / "public_dev_metrics.json"
    if score_row["status"] == "completed" and metrics_path.is_file():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        score_row["metrics"] = {
            key: metrics[key]
            for key in ("n_items", "accuracy", "macro_f1", "coverage")
            if key in metrics
        }
    rows.append(score_row)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_PUBLIC_DEV)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--memory-benchmarks-root", type=Path, default=DEFAULT_MEMORY_BENCHMARKS_ROOT
    )
    parser.add_argument(
        "--run-offline",
        action="store_true",
        help="Run only the local v4.3 rules controller and v3.3.2 archival audits.",
    )
    parser.add_argument(
        "--execute-models",
        action="store_true",
        help="Execute public v4.3 model systems with OPENROUTER_API_KEY.",
    )
    parser.add_argument(
        "--execute-external-fixtures",
        action="store_true",
        help="Run archived v3.3.2 fixture suites after both safety opt-ins.",
    )
    parser.add_argument(
        "--allow-test-only-external-fixture",
        action="store_true",
        help="Acknowledge that v3.3.2 fixture data are private and non-scientific.",
    )
    parser.add_argument(
        "--allow-archive-resume",
        action="store_true",
        help="Acknowledge that archived v3.3.2 Make targets can resume prior outputs.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        input_path = _require_public_v43_input(args.input)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_root = _require_suite_output(args.out or DEFAULT_OUTPUT_ROOT / run_id)
    memory_root = args.memory_benchmarks_root.resolve()
    if not memory_root.is_dir():
        raise SystemExit(f"memory_benchmarks root does not exist: {memory_root}")
    if args.execute_external_fixtures and not (
        args.allow_test_only_external_fixture and args.allow_archive_resume
    ):
        raise SystemExit(
            "--execute-external-fixtures requires --allow-test-only-external-fixture and --allow-archive-resume"
        )
    if (args.execute_models or args.execute_external_fixtures) and not os.environ.get(
        "OPENROUTER_API_KEY"
    ):
        raise SystemExit("model execution requires OPENROUTER_API_KEY to be exported in the shell")

    tasks = build_tasks(
        python=args.python,
        input_path=input_path,
        output_root=output_root,
        memory_benchmarks_root=memory_root,
    )
    rows: list[dict[str, Any]] = []
    for task in tasks:
        if task.family == "mgp6_v43_public_dev":
            selected = args.run_offline and task.task_id == "v43:rules_controller"
            selected = selected or (args.execute_models and task.requires_model)
        elif task.requires_external_fixture_opt_in:
            selected = args.execute_external_fixtures
        else:
            selected = args.run_offline

        if not selected:
            reason = "planned"
            if task.requires_model:
                reason = "model execution not requested"
            elif task.requires_external_fixture_opt_in:
                reason = "archived private test-only fixture execution not requested"
            rows.append(_task_row(task, status="planned", note=reason))
            continue
        row = _run_task(task, output_root=output_root)
        rows.append(row)
        if task.family == "mgp6_v43_public_dev":
            _append_v43_score(
                rows, task=task, python=args.python, input_path=input_path, output_root=output_root
            )

    report = {
        "schema_version": "benchmark-suite-report-v1",
        "run_id": run_id,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "public_v43_input": str(input_path),
        "v43_hidden_access": False,
        "memory_benchmarks_root": str(memory_root),
        "memory_benchmarks_fixture_classification": "private test-only archival fixture",
        "controls": {
            "run_offline": args.run_offline,
            "execute_models": args.execute_models,
            "execute_external_fixtures": args.execute_external_fixtures,
            "allow_test_only_external_fixture": args.allow_test_only_external_fixture,
            "allow_archive_resume": args.allow_archive_resume,
            "model_id": MODEL_ID,
        },
        "tasks": rows,
    }
    _write_json(output_root / "SUITE_REPORT.json", report)
    _write_markdown(report, output_root / "SUITE_REPORT.md")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if any(row["status"] == "failed" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
