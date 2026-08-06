"""Clean-room public validation using only rights-cleared synthetic fixtures."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from mgp_natural.errors import ValidationError
from mgp_natural.util.io import sha256_file, write_json


def _run(command: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "TERM": "dumb", "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
    )
    if completed.returncode != 0:
        output_hash = hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest()
        raise ValidationError(
            f"clean reproduction command failed with code {completed.returncode}; "
            f"output_sha256={output_hash}"
        )
    return completed.stdout


def _directory_manifest(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _scan_for_private_leaks(root: Path, forbidden_fragments: list[str]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if any(fragment in relative for fragment in (".private", "data/raw", "source_locator")):
            violations.append({"path": relative, "kind": "FORBIDDEN_PATH"})
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for fragment in forbidden_fragments:
            if fragment and fragment in text:
                violations.append(
                    {
                        "path": relative,
                        "kind": "FORBIDDEN_CONTENT_HASH_"
                        + hashlib.sha256(fragment.encode("utf-8")).hexdigest()[:12],
                    }
                )
    return violations


def run_clean_reproduction(project_root: Path, wheel: Path, output_path: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    wheel = wheel.resolve()
    if not wheel.is_file():
        raise ValidationError(f"wheel does not exist: {wheel}")
    fixture = project_root / "data/fixtures/studychat_candidate_fixture.jsonl"
    if not fixture.is_file():
        raise ValidationError("synthetic StudyChat fixture is missing")

    with tempfile.TemporaryDirectory(prefix="mgp-clean-") as temporary_name:
        temporary = Path(temporary_name)
        environment = temporary / "venv"
        _run([sys.executable, "-m", "venv", str(environment)])
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        pip = [str(python), "-m", "pip"]
        install_output = _run(
            [
                *pip,
                "install",
                "--no-deps",
                "--disable-pip-version-check",
                str(wheel),
            ]
        )

        working_fixture = temporary / "fixture.jsonl"
        shutil.copy2(fixture, working_fixture)
        manifests: list[list[dict[str, Any]]] = []
        stdout_hashes: list[str] = []
        leak_violations: list[dict[str, str]] = []
        for repetition in (1, 2):
            output_directory = temporary / f"out-{repetition}"
            command = [
                str(python),
                "-m",
                "mgp_natural.cli",
                "smoke",
                "--fixture",
                str(working_fixture),
                "--output-dir",
                str(output_directory),
            ]
            stdout = _run(command)
            stdout_hashes.append(hashlib.sha256(stdout.encode("utf-8")).hexdigest())
            manifests.append(_directory_manifest(output_directory))
            leak_violations.extend(
                _scan_for_private_leaks(
                    output_directory,
                    [str(project_root), str(project_root / ".private")],
                )
            )

        version_output = _run(
            [
                str(python),
                "-c",
                (
                    "import importlib.metadata as m, json, platform, sys; "
                    "print(json.dumps({'python': sys.version, "
                    "'platform': platform.platform(), "
                    "'mgp_natural': m.version('mgp-natural'), "
                    "'pip': m.version('pip')}, sort_keys=True))"
                ),
            ]
        ).strip()
        deterministic = manifests[0] == manifests[1] and stdout_hashes[0] == stdout_hashes[1]
        status = "PASS" if deterministic and not leak_violations else "FAIL"
        report = {
            "schema_version": "1.0",
            "status": status,
            "wheel_sha256": sha256_file(wheel),
            "fixture_sha256": sha256_file(fixture),
            "dependency_install_mode": "WHEEL_NO_DEPS_OFFLINE_PUBLIC_SMOKE",
            "install_stdout_sha256": hashlib.sha256(
                install_output.encode("utf-8")
            ).hexdigest(),
            "environment": json.loads(version_output),
            "deterministic_repetition_count": 2,
            "deterministic_outputs": deterministic,
            "stdout_hashes": stdout_hashes,
            "generated_manifest": manifests[0],
            "private_path_or_content_leaks": leak_violations,
            "raw_or_private_inputs_required": False,
            "fixture_rights_status": "SYNTHETIC_REPOSITORY_FIXTURE",
            "limitations": [
                "Declared third-party runtime dependencies were not resolved from the network; "
                "the installed public smoke path is dependency-free and was installed with --no-deps."
            ],
        }
        write_json(output_path, report)
        if status != "PASS":
            raise ValidationError("clean reproduction failed deterministic or leakage checks")
        return report

