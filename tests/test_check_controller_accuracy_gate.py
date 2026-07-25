from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/analysis/check_controller_accuracy_gate.py"


def _write_run(root: Path, *, correct: int, report_accuracy: float | None = None) -> None:
    controller = root / "controller"
    controller.mkdir(parents=True)
    with (controller / "judgments.jsonl").open("w", encoding="utf-8") as handle:
        for index in range(180):
            handle.write(
                json.dumps(
                    {
                        "competency": f"competency-{index // 30}",
                        "correct": index < correct,
                        "session_id": f"session-{index}",
                    }
                )
                + "\n"
            )
    (controller / "report.json").write_text(
        json.dumps(
            {
                "n_sessions": 180,
                "overall_accuracy": (correct / 180 if report_accuracy is None else report_accuracy),
            }
        ),
        encoding="utf-8",
    )


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--run-root", str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_accuracy_gate_passes_at_exact_153_of_180(tmp_path: Path) -> None:
    run_root = tmp_path / "passing-run"
    _write_run(run_root, correct=153)

    result = _run(run_root)

    assert result.returncode == 0, result.stderr
    assert "PASS: 153/180 (85.00%)" in result.stdout
    payload = json.loads((run_root / "controller_accuracy_gate.json").read_text())
    assert payload["passed"] is True
    assert payload["required_correct"] == 153
    assert payload["margin_correct"] == 0
    assert len(payload["by_competency"]) == 6


def test_accuracy_gate_fails_below_153_but_writes_evidence(tmp_path: Path) -> None:
    run_root = tmp_path / "failing-run"
    _write_run(run_root, correct=152)

    result = _run(run_root)

    assert result.returncode == 1, result.stderr
    assert "FAIL: 152/180 (84.44%)" in result.stdout
    payload = json.loads((run_root / "controller_accuracy_gate.json").read_text())
    assert payload["passed"] is False
    assert payload["status"] == "below_target"
    assert payload["margin_correct"] == -1


def test_accuracy_gate_rejects_report_judgment_disagreement(tmp_path: Path) -> None:
    run_root = tmp_path / "inconsistent-run"
    _write_run(run_root, correct=153, report_accuracy=0.9)

    result = _run(run_root)

    assert result.returncode == 2
    assert "report/judgment accuracy mismatch" in result.stderr
    payload = json.loads((run_root / "controller_accuracy_gate.json").read_text())
    assert payload["passed"] is False
    assert payload["status"] == "error"
    assert "report/judgment accuracy mismatch" in payload["error"]
