"""Import-order contracts for public package entrypoints."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import ksa
import ksa.controller as controller


def test_controller_public_api_exposes_active_surface_only() -> None:
    assert hasattr(controller, "decide_scorecard")
    assert hasattr(controller, "load_scorecard_config")
    assert not hasattr(controller, "decide")
    assert not hasattr(controller, "ControllerConfig")


def test_pipeline_and_naive_overwrite_public_imports_are_order_independent() -> None:
    code = (
        "from ksa.pipeline import ControllerOrchestrator; "
        "from ksa.baselines import NaiveOverwriteBaseline; "
        "assert ControllerOrchestrator.__name__ == 'ControllerOrchestrator'; "
        "assert NaiveOverwriteBaseline.__name__ == 'NaiveOverwriteBaseline'"
    )
    # The child process must resolve the SAME ksa the parent imported, whether
    # ksa is pip-installed or provided via pytest's `src` pythonpath config —
    # the contract under test is import-order independence, not installation.
    env = dict(os.environ)
    src_root = str(Path(ksa.__file__).resolve().parents[1])
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (src_root, env.get("PYTHONPATH")) if p
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
