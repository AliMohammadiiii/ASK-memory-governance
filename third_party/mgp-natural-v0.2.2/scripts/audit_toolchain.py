from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any


def _module_status(name: str) -> dict[str, Any]:
    available = importlib.util.find_spec(name) is not None
    version = None
    if available:
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            version = "vendored-or-unknown"
    return {"available": available, "version": version}


def main() -> None:
    parser = argparse.ArgumentParser(description="Record quality-tool and interpreter availability")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "schema_version": "1.0",
        "status": "PASS_WITH_RECORDED_EXTERNAL_TOOLCHAIN_BLOCKERS",
        "python": {
            "executable": sys.executable,
            "version": sys.version,
            "required_project_range": ">=3.11",
            "targeted_ci_versions": ["3.11", "3.12"],
            "targeted_ci_interpreters_available_here": any(
                shutil.which(name) for name in ("python3.11", "python3.12")
            ),
        },
        "tools": {
            name: _module_status(name)
            for name in ("pytest", "ruff", "mypy", "build", "jsonschema", "yaml")
        },
        "named_targets": {
            "make lint": {
                "status": "AVAILABLE_NOT_RUN_IN_AUDIT" if importlib.util.find_spec("ruff") else "UNAVAILABLE",
                "required_module": "ruff",
            },
            "make typecheck": {
                "status": "AVAILABLE_NOT_RUN_IN_AUDIT" if importlib.util.find_spec("mypy") else "UNAVAILABLE",
                "required_module": "mypy",
            },
            "python -m build": {
                "status": "AVAILABLE_NOT_RUN_IN_AUDIT" if importlib.util.find_spec("build") else "UNAVAILABLE_FALLBACK_USED",
                "required_module": "build",
            },
        },
        "blockers": [
            "Python 3.11 and 3.12 interpreters are not installed in this runtime.",
            "Ruff, mypy, and the `build` frontend are absent from the accessible package registry.",
        ],
        "supplementary_checks": "reports/offline_static_checks.json",
        "claim_boundary": (
            "A missing tool is not recorded as a passing named-tool gate; supplementary checks are separate."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

