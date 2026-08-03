#!/usr/bin/env python3
"""Verify current files against the additive LongMemEval V12 audit manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "artifacts/manifests/lme_v12_derived_manifest.json"
RUN_ROOT = ROOT / "runs_local/lme_final_controller_v12_qwen_180"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify() -> dict[str, object]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    mismatches = []
    for relative, expected in manifest["output_sha256"].items():
        path = RUN_ROOT / relative
        observed = _sha256(path) if path.is_file() else None
        if observed != expected:
            mismatches.append({"path": relative, "expected": expected, "observed": observed})
    parent = ROOT / manifest["parent_manifest_path"]
    observed_parent = _sha256(parent) if parent.is_file() else None
    if observed_parent != manifest["parent_manifest_sha256"]:
        mismatches.append(
            {
                "path": manifest["parent_manifest_path"],
                "expected": manifest["parent_manifest_sha256"],
                "observed": observed_parent,
            }
        )
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "manifest_status": manifest["status"],
        "mismatches": mismatches,
    }


def main() -> int:
    report = verify()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
