#!/usr/bin/env python3
"""Verify that the active ML environment matches the committed lock."""

from __future__ import annotations

import argparse
import inspect
import json
import re
from importlib import metadata
from pathlib import Path

LOCKED_DISTRIBUTIONS = (
    "accelerate",
    "faiss-cpu",
    "huggingface-hub",
    "peft",
    "safetensors",
    "sentence-transformers",
    "tokenizers",
    "torch",
    "transformers",
)


def _locked_versions(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^ ;]+)", line.strip())
        if match:
            versions[match.group(1).lower().replace("_", "-")] = match.group(2)
    return versions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--constraints",
        type=Path,
        default=Path("constraints/ml-py312.txt"),
    )
    args = parser.parse_args()

    locked = _locked_versions(args.constraints)
    observed = {name: metadata.version(name) for name in LOCKED_DISTRIBUTIONS}
    mismatches = {
        name: {"locked": locked.get(name), "observed": version}
        for name, version in observed.items()
        if locked.get(name) != version
    }

    from sentence_transformers import SentenceTransformer
    from transformers import AutoModelForCausalLM, AutoTokenizer

    revision_supported = "revision" in inspect.signature(SentenceTransformer.__init__).parameters
    payload = {
        "constraints": args.constraints.as_posix(),
        "versions": observed,
        "sentence_transformer_revision_supported": revision_supported,
        "transformers_auto_classes": [
            AutoTokenizer.__name__,
            AutoModelForCausalLM.__name__,
        ],
        "status": "PASS" if not mismatches and revision_supported else "FAIL",
        "mismatches": mismatches,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
