from __future__ import annotations

import argparse
import copy
import gzip
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

from mgp_natural.errors import ValidationError
from mgp_natural.util.io import sha256_file, write_json

SOURCE_DATE_EPOCH = "1704067200"


def _run(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env={
            **os.environ,
            "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
        },
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        digest = __import__("hashlib").sha256(completed.stdout.encode("utf-8")).hexdigest()
        tail = completed.stdout[-4000:].replace("\n", " | ")
        raise ValidationError(
            "artifact build command failed with code "
            f"{completed.returncode}; output_sha256={digest}; output_tail={tail}"
        )
    return completed.stdout


def _normalize_sdist(path: Path) -> None:
    entries: list[tuple[tarfile.TarInfo, bytes | None]] = []
    with tarfile.open(path, "r:gz") as source:
        for original in source.getmembers():
            member = copy.copy(original)
            payload: bytes | None = None
            if original.isfile():
                extracted = source.extractfile(original)
                if extracted is None:
                    raise ValidationError(f"could not read sdist member: {original.name}")
                payload = extracted.read()
            member.mtime = int(SOURCE_DATE_EPOCH)
            member.uid = 0
            member.gid = 0
            member.uname = ""
            member.gname = ""
            member.pax_headers = {}
            entries.append((member, payload))

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as target:
        for member, payload in sorted(entries, key=lambda entry: entry[0].name):
            target.addfile(member, io.BytesIO(payload) if payload is not None else None)

    compressed = io.BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=compressed,
        compresslevel=9,
        mtime=int(SOURCE_DATE_EPOCH),
    ) as handle:
        handle.write(tar_buffer.getvalue())
    path.write_bytes(compressed.getvalue())


def build_artifacts(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    missing_backend_modules = [
        module for module in ("setuptools",) if importlib.util.find_spec(module) is None
    ]
    if missing_backend_modules:
        missing = ", ".join(missing_backend_modules)
        raise ValidationError(
            "build backend dependency missing: "
            f"{missing}; run `python -m pip install -e '.[dev]'` and retry"
        )
    for path in (root / "build", root / "dist", root / "src/mgp_natural.egg-info"):
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    (root / "dist").mkdir(parents=True, exist_ok=True)

    frontend_failure: str | None = None
    if importlib.util.find_spec("build") is not None:
        try:
            backend = "python-build"
            _run([sys.executable, "-m", "build", "--no-isolation"], root)
        except ValidationError as exc:
            frontend_failure = str(exc)
            backend = "setuptools-pep517-hook-fallback-after-build-frontend-failure"
    else:
        backend = "offline-setuptools-pep517-hook-fallback"

    if backend != "python-build":
        for path in (root / "build", root / "dist", root / "src/mgp_natural.egg-info"):
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        (root / "dist").mkdir(parents=True, exist_ok=True)
        wheel_command = (
            "from pathlib import Path; "
            "from setuptools import build_meta; "
            "print(build_meta.build_wheel(str(Path('dist').resolve())))"
        )
        _run([sys.executable, "-c", wheel_command], root)
        sdist_command = (
            "from pathlib import Path; "
            "from setuptools import build_meta; "
            "print(build_meta.build_sdist(str(Path('dist').resolve())))"
        )
        _run([sys.executable, "-c", sdist_command], root)

    artifacts = sorted((root / "dist").iterdir())
    wheels = [path for path in artifacts if path.suffix == ".whl"]
    source_distributions = [path for path in artifacts if path.name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(source_distributions) != 1:
        raise ValidationError("build must produce exactly one wheel and one source distribution")
    _normalize_sdist(source_distributions[0])
    report = {
        "schema_version": "1.0",
        "status": "PASS",
        "backend": backend,
        "python": sys.version,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "sdist_normalized_for_reproducibility": True,
        "artifacts": [
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in artifacts
            if path.is_file()
        ],
        "limitations": (
            []
            if backend == "python-build"
            else [
                "The local setuptools PEP 517 hooks were invoked without network access.",
                *(
                    [f"The build frontend failed before fallback: {frontend_failure}"]
                    if frontend_failure
                    else []
                ),
            ]
        ),
    }
    write_json(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build wheel and source distribution fail-closed")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_artifacts(args.root, args.output), sort_keys=True))


if __name__ == "__main__":
    main()

