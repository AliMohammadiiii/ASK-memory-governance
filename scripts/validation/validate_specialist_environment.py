#!/usr/bin/env python3
"""Validate exact specialist locks and their import contracts."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCKS = {
    "ml": ROOT / "constraints" / "maintained-ml-py312.lock",
    "adapters": ROOT / "constraints" / "maintained-adapters-py312.lock",
}
IMPORTS = {
    "ml": (
        "accelerate",
        "faiss",
        "huggingface_hub",
        "ijson",
        "numpy",
        "peft",
        "pydantic",
        "safetensors",
        "sentence_transformers",
        "tokenizers",
        "torch",
        "transformers",
    ),
    "adapters": (
        "chonkie",
        "graphiti_core",
        "langchain_text_splitters",
        "letta_client",
        "mem0",
        "memos",
        "qdrant_client",
        "sentence_transformers",
    ),
}
EXACT_REQUIREMENT = re.compile(r"^[A-Za-z0-9_.-]+==[^\s;\\]+(?:\s+;\s+.+)?\s+\\$")
HASH = re.compile(r"^\s+--hash=sha256:[0-9a-f]{64}(?:\s+\\)?$")


class EnvironmentValidationError(RuntimeError):
    """Raised when a specialist environment contract is incomplete."""


def validate_lock(path: Path) -> int:
    try:
        display_path = path.relative_to(ROOT)
    except ValueError:
        display_path = path
    if not path.is_file():
        raise EnvironmentValidationError(f"missing exact lock: {display_path}")
    package_count = 0
    current: str | None = None
    current_has_hash = False
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line or line.startswith("#"):
            continue
        if line[0].isspace():
            if current is None or not HASH.fullmatch(line):
                raise EnvironmentValidationError(
                    f"{display_path}:{line_number}: invalid hash continuation"
                )
            current_has_hash = True
            continue
        if current is not None and not current_has_hash:
            raise EnvironmentValidationError(f"{current}: requirement has no distribution hash")
        if not EXACT_REQUIREMENT.fullmatch(line):
            raise EnvironmentValidationError(
                f"{display_path}:{line_number}: requirement is not exactly pinned"
            )
        current = f"{display_path}:{line_number}"
        current_has_hash = False
        package_count += 1
    if current is None:
        raise EnvironmentValidationError(f"empty exact lock: {display_path}")
    if not current_has_hash:
        raise EnvironmentValidationError(f"{current}: requirement has no distribution hash")
    return package_count


def validate_python_version() -> None:
    if sys.version_info[:2] != (3, 12):
        raise EnvironmentValidationError("specialist environments require CPython 3.12")


def validate_imports(profile: str) -> None:
    importlib.import_module("ask")
    failures: list[str] = []
    for module_name in IMPORTS[profile]:
        try:
            importlib.import_module(module_name)
        except ImportError as error:
            failures.append(f"{module_name}: {error}")
    if failures:
        raise EnvironmentValidationError("failed import contracts:\n" + "\n".join(failures))


def validate_installed_versions(path: Path) -> None:
    try:
        from packaging.requirements import Requirement
        from packaging.utils import canonicalize_name
    except ImportError as error:
        raise EnvironmentValidationError(
            "installed-version validation requires the packaging distribution"
        ) from error

    expected: dict[str, Requirement] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or line[0].isspace():
            continue
        requirement = Requirement(line.removesuffix("\\").rstrip())
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        normalized_name = canonicalize_name(requirement.name)
        previous = expected.get(normalized_name)
        if previous is not None and previous.specifier != requirement.specifier:
            raise EnvironmentValidationError(
                f"active lock contains conflicting pins for {requirement.name}"
            )
        expected[normalized_name] = requirement

    failures: list[str] = []
    for requirement in expected.values():
        try:
            installed = importlib.metadata.version(requirement.name)
        except importlib.metadata.PackageNotFoundError:
            failures.append(f"{requirement.name}: not installed")
            continue
        if installed not in requirement.specifier:
            failures.append(
                f"{requirement.name}: installed {installed}, expected {requirement.specifier}"
            )
    if failures:
        raise EnvironmentValidationError(
            "installed versions do not match lock:\n" + "\n".join(failures)
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, choices=tuple(LOCKS))
    parser.add_argument("--lock-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        count = validate_lock(LOCKS[args.profile])
        if not args.lock_only:
            validate_python_version()
            validate_installed_versions(LOCKS[args.profile])
            validate_imports(args.profile)
    except EnvironmentValidationError as error:
        sys.stderr.write(f"Specialist environment validation failed: {error}\n")
        return 1
    mode = "lock" if args.lock_only else "environment"
    sys.stdout.write(f"Specialist {args.profile} {mode}: OK ({count} exact packages)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
