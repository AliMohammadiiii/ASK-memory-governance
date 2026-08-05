from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mgp_natural.errors import GateBlockedError
from mgp_natural.release.package import BLOCK_MESSAGE, package_public, verify_boundary
from mgp_natural.util.io import write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail-closed public package builder")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--approvals", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--boundary-only", action="store_true")
    args = parser.parse_args()
    excluded = {args.output.resolve(), args.inventory.resolve()}
    if args.boundary_only:
        report = verify_boundary(
            args.root,
            exclude=excluded,
            inventory_path=args.inventory,
        )
        if args.report:
            write_json(args.report, report)
        print(report)
        return
    try:
        report = package_public(args.root, args.approvals, args.output, args.inventory)
        if args.report:
            write_json(args.report, report)
        print(report)
    except GateBlockedError:
        args.output.unlink(missing_ok=True)
        if args.report:
            write_json(
                args.report,
                {
                    "schema_version": "1.0",
                    "status": BLOCK_MESSAGE,
                    "package_created": False,
                },
            )
        print(BLOCK_MESSAGE)
        sys.exit(3)


if __name__ == "__main__":
    main()

