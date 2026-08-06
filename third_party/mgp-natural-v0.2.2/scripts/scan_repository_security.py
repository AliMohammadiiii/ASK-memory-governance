from __future__ import annotations

import argparse
import json
from pathlib import Path

from mgp_natural.audits.security import repository_security_scan


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline repository security boundary checks")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args()
    report = repository_security_scan(
        args.root,
        report_path=args.output,
        inventory_path=args.inventory,
    )
    print(json.dumps(report, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

