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
import threading
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    expected_items: int | None = None
    progress_path: Path | None = None
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


def _jsonl_record_count(path: Path) -> int:
    """Count non-empty JSONL rows without loading their content into the report."""

    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def build_tasks(
    *,
    python: str,
    input_path: Path,
    output_root: Path,
    memory_benchmarks_root: Path,
) -> list[SuiteTask]:
    """Create every supported task without executing or reading release records."""

    public_item_count = _jsonl_record_count(input_path)
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
                expected_items=public_item_count,
                progress_path=system_output / "predictions.jsonl",
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


def _attempt_report_paths(output_root: Path, attempt_id: str) -> tuple[Path, Path]:
    """Return append-only report paths for one suite invocation."""

    return (
        output_root / f"SUITE_REPORT_{attempt_id}.json",
        output_root / f"SUITE_REPORT_{attempt_id}.md",
    )


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


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "—"
    rounded = max(0, round(value))
    minutes, seconds = divmod(rounded, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:d}:{seconds:02d}"


class SuiteProgress:
    """Thread-safe terminal progress bars plus a machine-readable event log."""

    def __init__(self, *, output_root: Path, enabled: bool) -> None:
        self._lock = threading.Lock()
        self._event_path = output_root / "progress.jsonl"
        self._event_path.parent.mkdir(parents=True, exist_ok=True)
        self._enabled = enabled and sys.stderr.isatty()
        self._bars: dict[str, Any] = {}
        self._next_position = 0
        if self._enabled:
            from tqdm import tqdm

            self._tqdm = tqdm
        else:
            self._tqdm = None

    def _event(self, task: SuiteTask, *, state: str, completed: int, elapsed_s: float) -> None:
        total = task.expected_items
        eta_s = (total - completed) * elapsed_s / completed if total and completed else None
        event = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "task_id": task.task_id,
            "state": state,
            "completed": completed,
            "total": total,
            "percent": round(100 * completed / total, 2) if total else None,
            "elapsed_seconds": round(elapsed_s, 3),
            "eta_seconds": round(eta_s, 3) if eta_s is not None else None,
        }
        with self._event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    def start(self, task: SuiteTask, *, completed: int) -> None:
        with self._lock:
            if task.expected_items is not None and self._tqdm is not None:
                self._bars[task.task_id] = self._tqdm(
                    total=task.expected_items,
                    initial=completed,
                    desc=task.task_id,
                    unit="item",
                    dynamic_ncols=True,
                    position=self._next_position,
                    leave=True,
                )
                self._next_position += 1
            self._event(
                task,
                state="resuming" if completed else "started",
                completed=completed,
                elapsed_s=0.0,
            )

    def update(self, task: SuiteTask, *, completed: int, elapsed_s: float) -> None:
        with self._lock:
            bar = self._bars.get(task.task_id)
            if bar is not None:
                bar.n = min(completed, task.expected_items or completed)
                total = task.expected_items
                eta_s = (total - completed) * elapsed_s / completed if total and completed else None
                bar.set_postfix_str(f"ETA {_format_seconds(eta_s)}")
                bar.refresh()
            self._event(task, state="running", completed=completed, elapsed_s=elapsed_s)

    def finish(self, task: SuiteTask, *, completed: int, elapsed_s: float, status: str) -> None:
        with self._lock:
            bar = self._bars.get(task.task_id)
            if bar is not None:
                bar.n = min(completed, task.expected_items or completed)
                bar.set_postfix_str(status)
                bar.refresh()
                bar.close()
            self._event(task, state=status, completed=completed, elapsed_s=elapsed_s)


def _completed_items(task: SuiteTask) -> int:
    if task.progress_path is None or not task.progress_path.is_file():
        return 0
    return _jsonl_record_count(task.progress_path)


def _attempt_log_root(*, output_root: Path, task: SuiteTask) -> Path:
    """Allocate an append-only log directory for a task attempt."""

    task_log_root = output_root / "logs" / task.task_id.replace(":", "__")
    task_log_root.mkdir(parents=True, exist_ok=True)
    attempt_number = 1
    while (task_log_root / f"attempt_{attempt_number:03d}").exists():
        attempt_number += 1
    attempt_root = task_log_root / f"attempt_{attempt_number:03d}"
    attempt_root.mkdir()
    return attempt_root


def _run_task(
    task: SuiteTask,
    *,
    output_root: Path,
    progress: SuiteProgress,
    refresh_s: float,
) -> dict[str, Any]:
    log_root = _attempt_log_root(output_root=output_root, task=task)
    stdout_path, stderr_path = log_root / "stdout.log", log_root / "stderr.log"
    started = time.monotonic()
    completed_items = _completed_items(task)
    initial_completed_items = completed_items
    progress.start(task, completed=completed_items)
    returncode = 1
    try:
        with (
            stdout_path.open("w", encoding="utf-8") as stdout,
            stderr_path.open("w", encoding="utf-8") as stderr,
        ):
            process = subprocess.Popen(
                task.command, cwd=task.cwd, stdout=stdout, stderr=stderr, text=True
            )
            while process.poll() is None:
                completed_items = _completed_items(task)
                progress.update(
                    task, completed=completed_items, elapsed_s=time.monotonic() - started
                )
                time.sleep(refresh_s)
            returncode = process.wait()
    except OSError as exc:
        stderr_path.write_text(f"unable to start task: {exc}\n", encoding="utf-8")
    elapsed_s = time.monotonic() - started
    completed_items = _completed_items(task)
    status = "completed" if returncode == 0 else "failed"
    progress.finish(task, completed=completed_items, elapsed_s=elapsed_s, status=status)
    return _task_row(
        task,
        status=status,
        note=(
            f"exit={returncode}; completed={completed_items}/{task.expected_items or 'n/a'}; "
            f"resumed_from={initial_completed_items}; elapsed={_format_seconds(elapsed_s)}; "
            f"logs={log_root.relative_to(output_root)}"
        ),
        returncode=returncode,
        elapsed_seconds=round(elapsed_s, 3),
        completed_items=completed_items,
        resumed_from_items=initial_completed_items,
        expected_items=task.expected_items,
        stdout_log=str(stdout_path),
        stderr_log=str(stderr_path),
    )


def _append_v43_score(
    rows: list[dict[str, Any]],
    *,
    task: SuiteTask,
    python: str,
    input_path: Path,
    output_root: Path,
    progress: SuiteProgress,
    refresh_s: float,
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
    score_row = _run_task(
        score_task,
        output_root=output_root,
        progress=progress,
        refresh_s=refresh_s,
    )
    metrics_path = prediction_root / "public_dev_metrics.json"
    if score_row["status"] == "completed" and metrics_path.is_file():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        score_row["metrics"] = {
            key: metrics[key]
            for key in ("n_items", "accuracy", "macro_f1", "coverage")
            if key in metrics
        }
    rows.append(score_row)


def _run_v43_task_and_score(
    task: SuiteTask,
    *,
    python: str,
    input_path: Path,
    output_root: Path,
    progress: SuiteProgress,
    refresh_s: float,
) -> list[dict[str, Any]]:
    """Run one independent public-v4.3 system and its public scorer."""

    rows = [_run_task(task, output_root=output_root, progress=progress, refresh_s=refresh_s)]
    _append_v43_score(
        rows,
        task=task,
        python=python,
        input_path=input_path,
        output_root=output_root,
        progress=progress,
        refresh_s=refresh_s,
    )
    return rows


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_PUBLIC_DEV)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=4,
        help="Maximum concurrently executing independent public v4.3 systems (1-8; default: 4).",
    )
    parser.add_argument(
        "--progress-refresh-s",
        type=float,
        default=1.0,
        help="Progress refresh interval in seconds (default: 1.0).",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable terminal progress bars; progress.jsonl is still written.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an existing run ID from validated partial public prediction files.",
    )
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
    attempt_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output_root = _require_suite_output(args.out or DEFAULT_OUTPUT_ROOT / run_id)
    memory_root = args.memory_benchmarks_root.resolve()
    if not memory_root.is_dir():
        raise SystemExit(f"memory_benchmarks root does not exist: {memory_root}")
    if not 1 <= args.max_parallel <= 8:
        raise SystemExit("--max-parallel must be between 1 and 8")
    if args.progress_refresh_s <= 0:
        raise SystemExit("--progress-refresh-s must be positive")
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
    existing_v43_predictions = {
        task.task_id: _completed_items(task)
        for task in tasks
        if task.family == "mgp6_v43_public_dev" and _completed_items(task)
    }
    if existing_v43_predictions and not args.resume:
        detail = ", ".join(
            f"{task_id}={count}" for task_id, count in sorted(existing_v43_predictions.items())
        )
        raise SystemExit(
            "existing public predictions found for this run ID; use --resume to continue safely "
            f"({detail})"
        )
    planned_rows: dict[str, list[dict[str, Any]]] = {}
    selected_v43: list[SuiteTask] = []
    selected_serial: list[SuiteTask] = []
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
            planned_rows[task.task_id] = [_task_row(task, status="planned", note=reason)]
            continue
        if task.family == "mgp6_v43_public_dev":
            selected_v43.append(task)
        else:
            # The v3.3.2 status audit depends on its preflight, and its fixture
            # Make targets share archival output roots.  Their own Makefile
            # parallelizes independent native competitors where it is safe.
            selected_serial.append(task)

    completed_rows: dict[str, list[dict[str, Any]]] = {}
    progress = SuiteProgress(output_root=output_root, enabled=not args.no_progress)
    if selected_v43:
        with ThreadPoolExecutor(max_workers=min(args.max_parallel, len(selected_v43))) as executor:
            futures = {
                executor.submit(
                    _run_v43_task_and_score,
                    task,
                    python=args.python,
                    input_path=input_path,
                    output_root=output_root,
                    progress=progress,
                    refresh_s=args.progress_refresh_s,
                ): task
                for task in selected_v43
            }
            for future in as_completed(futures):
                task = futures[future]
                completed_rows[task.task_id] = future.result()
    for task in selected_serial:
        completed_rows[task.task_id] = [
            _run_task(
                task,
                output_root=output_root,
                progress=progress,
                refresh_s=args.progress_refresh_s,
            )
        ]

    rows: list[dict[str, Any]] = []
    for task in tasks:
        rows.extend(planned_rows.get(task.task_id, completed_rows.get(task.task_id, [])))

    report = {
        "schema_version": "benchmark-suite-report-v1",
        "run_id": run_id,
        "attempt_id": attempt_id,
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
            "max_parallel": args.max_parallel,
            "progress_refresh_seconds": args.progress_refresh_s,
            "resume": args.resume,
        },
        "resumed_prediction_counts": existing_v43_predictions,
        "tasks": rows,
    }
    attempt_json, attempt_markdown = _attempt_report_paths(output_root, attempt_id)
    _write_json(attempt_json, report)
    _write_markdown(report, attempt_markdown)
    _write_json(output_root / "SUITE_REPORT.json", report)
    _write_markdown(report, output_root / "SUITE_REPORT.md")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if any(row["status"] == "failed" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
