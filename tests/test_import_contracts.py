"""Import-order contracts for public package entrypoints."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import ask
import ask.controller as controller


def test_controller_public_api_exposes_active_surface_only() -> None:
    assert hasattr(controller, "decide_scorecard")
    assert hasattr(controller, "load_scorecard_config")
    assert not hasattr(controller, "decide")
    assert not hasattr(controller, "ControllerConfig")


def test_pipeline_and_naive_overwrite_public_imports_are_order_independent() -> None:
    code = (
        "from ask.pipeline import ControllerOrchestrator; "
        "from ask.baselines import NaiveOverwriteBaseline; "
        "assert ControllerOrchestrator.__name__ == 'ControllerOrchestrator'; "
        "assert NaiveOverwriteBaseline.__name__ == 'NaiveOverwriteBaseline'"
    )
    # The child process must resolve the SAME ask the parent imported, whether
    # ask is pip-installed or provided via pytest's `src` pythonpath config —
    # the contract under test is import-order independence, not installation.
    env = dict(os.environ)
    src_root = str(Path(ask.__file__).resolve().parents[1])
    env["PYTHONPATH"] = os.pathsep.join(p for p in (src_root, env.get("PYTHONPATH")) if p)
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr


def test_package_import_is_silent_and_does_not_create_files(tmp_path: Path) -> None:
    env = dict(os.environ)
    src_root = str(Path(ask.__file__).resolve().parents[1])
    env["PYTHONPATH"] = os.pathsep.join(p for p in (src_root, env.get("PYTHONPATH")) if p)
    code = (
        "import logging; "
        "root = logging.getLogger(); "
        "handlers = tuple(root.handlers); level = root.level; "
        "import ask; "
        "assert tuple(root.handlers) == handlers; assert root.level == level"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
    assert list(tmp_path.iterdir()) == []
