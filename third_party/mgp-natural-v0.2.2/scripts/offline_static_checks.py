from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _python_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for directory in (root / "src", root / "scripts", root / "tests"):
        result.extend(
            path
            for path in directory.rglob("*.py")
            if "__pycache__" not in path.parts and "build" not in path.parts
        )
    return sorted(result)


def _source_checks(root: Path, files: list[Path]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            if line.rstrip() != line:
                violations.append(
                    {"path": relative, "line": line_number, "code": "TRAILING_WHITESPACE"}
                )
            if "\t" in line:
                violations.append({"path": relative, "line": line_number, "code": "TAB"})
        try:
            tree = ast.parse(text, filename=relative)
        except SyntaxError as exc:
            violations.append(
                {
                    "path": relative,
                    "line": exc.lineno or 0,
                    "code": "SYNTAX_ERROR",
                    "detail": exc.msg,
                }
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                violations.append(
                    {"path": relative, "line": node.lineno, "code": "BARE_EXCEPT"}
                )
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                    violations.append(
                        {"path": relative, "line": node.lineno, "code": "DYNAMIC_EXECUTION"}
                    )
                for keyword in node.keywords:
                    if (
                        keyword.arg == "shell"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                    ):
                        violations.append(
                            {"path": relative, "line": node.lineno, "code": "SHELL_TRUE"}
                        )
            if relative.startswith("src/") and isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                if node.name.startswith("__") and node.name.endswith("__"):
                    continue
                if node.returns is None:
                    violations.append(
                        {"path": relative, "line": node.lineno, "code": "MISSING_RETURN_ANNOTATION"}
                    )
                arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                if node.args.vararg:
                    arguments.append(node.args.vararg)
                if node.args.kwarg:
                    arguments.append(node.args.kwarg)
                for argument in arguments:
                    if argument.arg in {"self", "cls"}:
                        continue
                    if argument.annotation is None:
                        violations.append(
                            {
                                "path": relative,
                                "line": node.lineno,
                                "code": "MISSING_ARGUMENT_ANNOTATION",
                                "argument": argument.arg,
                            }
                        )
    return violations


def _help_checks(root: Path) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    environment = {**os.environ, "PYTHONPATH": str(root / "src"), "TERM": "dumb"}
    for script in sorted((root / "scripts").glob("*.py")):
        if script.name in {"offline_static_checks.py"}:
            continue
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=root,
            env=environment,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if completed.returncode != 0 or "usage:" not in completed.stdout.casefold():
            failures.append(
                {
                    "script": script.relative_to(root).as_posix(),
                    "returncode": completed.returncode,
                    "output_sha256": __import__("hashlib").sha256(
                        completed.stdout.encode("utf-8")
                    ).hexdigest(),
                }
            )
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run deterministic offline syntax, annotation-shape, safety, and CLI checks"
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    files = _python_files(root)
    source_violations = _source_checks(root, files)
    help_failures = _help_checks(root)
    report = {
        "schema_version": "1.0",
        "status": "PASS" if not source_violations and not help_failures else "FAIL",
        "python": sys.version,
        "files_checked": len(files),
        "source_violations": source_violations,
        "script_help_failures": help_failures,
        "scope_note": (
            "Supplementary offline static checks; this report is not a substitute for Ruff or mypy."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()

