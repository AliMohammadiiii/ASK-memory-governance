from __future__ import annotations

import argparse
import json
from pathlib import Path

from mgp_natural.util.io import write_json

PRIVATE_CLASSES = (
    ".private/full",
    ".private/source",
    ".private/audit",
    ".private/derived",
    ".private/mappings",
    ".private/packets",
    ".private/annotations",
    ".private/adjudications",
    ".private/gold",
    ".private/scores",
    "data/raw",
    "data/interim",
)


def aggregate(root: Path) -> dict[str, object]:
    root = root.resolve()
    classes = []
    for relative in PRIVATE_CLASSES:
        directory = root / relative
        files = [path for path in directory.rglob("*") if path.is_file() and not path.is_symlink()] if directory.exists() else []
        directories = [path for path in directory.rglob("*") if path.is_dir() and not path.is_symlink()] if directory.exists() else []
        classes.append(
            {
                "class": relative,
                "present": directory.exists(),
                "files": len(files),
                "directories_below_class_root": len(directories),
                "bytes": sum(path.stat().st_size for path in files),
            }
        )
    return {
        "schema_version": "1.0",
        "status": "PRIVATE_AGGREGATE_INVENTORY_PATHS_WITHHELD",
        "public_package_exclusion_required": True,
        "classes": classes,
        "additional_private_material": [
            "unreleased split manifests and source locators",
            "blinding secrets and source-to-blind mappings",
            "individual annotations, adjudications, and unreleased gold",
        ],
        "path_disclosure": "Only predeclared private classes and aggregate counts are reported.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate aggregate private-file inventory")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = aggregate(args.root)
    write_json(args.output, report)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

