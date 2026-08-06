#!/usr/bin/env python3
"""Run the public verification path in a fresh venv from a clean Git tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "reports/clean_reproduction.json"
DEFAULT_MD = ROOT / "reports/CLEAN_REPRODUCTION.md"
DEFAULT_ARTIFACT = ROOT / "artifacts/reproduction/preflight-current/manifest.json"


def _sanitize_text(value: str) -> str:
    """Remove machine-local paths and checkout identity from public receipts."""
    sanitized = value.replace(str(ROOT), "$REPO")
    temporary_prefix = r"/(?:private/)?var/folders/[^/\s]+/[^/\s]+/T/"
    sanitized = re.sub(
        temporary_prefix + r"ask-repro-[^/\s\"]+",
        "$REPRO_TMP",
        sanitized,
    )
    sanitized = re.sub(
        temporary_prefix + r"pip-ephem-wheel-cache-[^/\s\"]+",
        "$PIP_EPHEMERAL_CACHE",
        sanitized,
    )
    return re.sub(
        r"-e git\+\S+#egg=ask_memory_governance",
        "-e $REPRO_SOURCE#egg=ask_memory_governance",
        sanitized,
    )


def _sanitize_value(value: object) -> object:
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_value(item) for key, item in value.items()}
    return value


def _run(command: list[str], *, cwd: Path = ROOT) -> dict[str, object]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    combined = result.stdout + result.stderr
    return {
        "command": _sanitize_value(command),
        "exit_code": result.returncode,
        "output_sha256": hashlib.sha256(combined.encode()).hexdigest(),
        "output_tail": _sanitize_text(combined[-4000:]),
    }


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def _write_outputs(
    report: dict[str, object], *, json_out: Path, md_out: Path, artifact_out: Path
) -> None:
    report = _sanitize_value(report)
    if not isinstance(report, dict):
        raise TypeError("sanitized reproduction report must remain a mapping")
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(payload, encoding="utf-8")
    categories = {
        "reproduced_from_raw_public_inputs": report.get("status") == "PASS",
        "replayed_from_preserved_private_outputs": False,
        "requires_paid_api": False,
        "not_redistributable": ["hidden MGP-6 gold", "LongMemEval source data", "raw V12 run"],
        "historical_only": ["LongMemEval V12 historical execution provenance"],
        "failed_or_blocked": report.get("status") != "PASS",
    }
    md = "\n".join(
        [
            "# Clean reproduction",
            "",
            f"Status: **{report['status']}**",
            "",
            "This report concerns a fresh-environment reproduction of the public deterministic path.",
            "Cached prediction replay and private evidence verification are separate activities.",
            "",
            "## Evidence classes",
            "",
            *[f"- `{key}`: `{value}`" for key, value in categories.items()],
            "",
            f"Git head: `{report['git_head']}`",
            f"Reason: {report.get('reason', 'all declared public commands completed')}",
            "",
        ]
    )
    md_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.write_text(md, encoding="utf-8")
    artifact = {
        "schema_version": "1.0",
        "run_id": "preflight-current",
        "status": report["status"],
        "git_head": report["git_head"],
        "git_tree": report["git_tree"],
        "report_path": json_out.relative_to(ROOT).as_posix(),
        "report_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "complete_logs_preserved": bool(report.get("commands")),
        "claim_scope": "public deterministic path only",
    }
    artifact_out.parent.mkdir(parents=True, exist_ok=True)
    artifact_out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--artifact-out", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()
    report: dict[str, object] = {
        "schema_version": "1.0",
        "started_at": datetime.now(UTC).isoformat(),
        "git_head": _git("rev-parse", "HEAD"),
        "git_tree": _git("rev-parse", "HEAD^{tree}"),
        "commands": [],
        "network_note": "pip package acquisition may use the configured index; research inference is never called",
    }
    status = _git("status", "--porcelain=v1", "--untracked-files=normal")
    if status:
        report.update(
            {
                "status": "BLOCKED_DIRTY_WORKTREE",
                "passed": False,
                "reason": "clean reproduction requires a frozen clean commit",
            }
        )
        _write_outputs(
            report, json_out=args.out, md_out=args.md_out, artifact_out=args.artifact_out
        )
        print(report["status"])
        return 1

    with tempfile.TemporaryDirectory(prefix="ask-repro-") as temporary:
        venv = Path(temporary) / "venv"
        python = venv / "bin/python"
        commands = [
            ["python3.12", "-m", "venv", str(venv)],
            [str(python), "-m", "pip", "install", "--upgrade", "pip"],
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--constraint",
                str(ROOT / "constraints/repro-py312.txt"),
                "-e",
                ".[dev]",
            ],
            ["make", "reproduce-public", f"PYTHON={python}"],
            [str(python), "-m", "pip", "freeze", "--all"],
        ]
        records: list[dict[str, object]] = []
        for command in commands:
            record = _run(command)
            records.append(record)
            if record["exit_code"] != 0:
                break
        report["commands"] = records
        passed = len(records) == len(commands) and all(row["exit_code"] == 0 for row in records)
        report.update(
            {
                "status": "PASS" if passed else "FAIL",
                "passed": passed,
                "completed_at": datetime.now(UTC).isoformat(),
            }
        )
    _write_outputs(report, json_out=args.out, md_out=args.md_out, artifact_out=args.artifact_out)
    print(report["status"])
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
