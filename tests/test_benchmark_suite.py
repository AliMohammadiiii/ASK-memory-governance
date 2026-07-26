"""Safety and planning tests for the cross-benchmark suite runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from ask.eval.mgp6_v43 import MGP6V43_RUNNABLE_SYSTEMS
from scripts import run_benchmark_suite

ROOT = Path(__file__).resolve().parents[1]


def test_public_input_guard_rejects_private_and_hidden_paths() -> None:
    public_dev = ROOT / "benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl"
    assert run_benchmark_suite._require_public_v43_input(public_dev) == public_dev.resolve()
    with pytest.raises(ValueError, match="tracked public"):
        run_benchmark_suite._require_public_v43_input(
            ROOT / ".private/benchmarks/mgp6/v4.3/hidden_inputs/items.jsonl"
        )


def test_suite_output_guard_requires_ignored_runs_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ignored runs"):
        run_benchmark_suite._require_suite_output(tmp_path / "report")
    assert (
        run_benchmark_suite._require_suite_output(ROOT / "runs/benchmark_suite/test")
        == (ROOT / "runs/benchmark_suite/test").resolve()
    )


def test_task_plan_covers_every_v43_system_and_never_contains_hidden_flags(tmp_path: Path) -> None:
    tasks = run_benchmark_suite.build_tasks(
        python="python",
        input_path=ROOT / "benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl",
        output_root=ROOT / "runs/benchmark_suite/test-plan",
        memory_benchmarks_root=ROOT.parent / "memory_benchmarks",
    )
    v43 = [task for task in tasks if task.family == "mgp6_v43_public_dev"]
    assert {task.task_id.removeprefix("v43:") for task in v43} == set(MGP6V43_RUNNABLE_SYSTEMS)
    assert all("--hidden-input" not in task.command for task in v43)
    assert all("hidden_gold" not in " ".join(task.command) for task in tasks)
    assert any(task.task_id == "v332:archival-preflight" for task in tasks)


def test_external_fixture_requires_two_explicit_acknowledgements() -> None:
    with pytest.raises(SystemExit, match="allow-test-only-external-fixture"):
        run_benchmark_suite.main(
            [
                "--execute-external-fixtures",
                "--memory-benchmarks-root",
                str(ROOT.parent / "memory_benchmarks"),
            ]
        )


def test_parallelism_is_bounded_and_defaults_to_four_workers() -> None:
    assert run_benchmark_suite.parse_args([]).max_parallel == 4
    with pytest.raises(SystemExit, match="between 1 and 8"):
        run_benchmark_suite.main(["--max-parallel", "9"])
