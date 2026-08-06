from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.audits.private_permissions import audit_private_permissions_to_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit exact 0700/0600 modes under a private artifact directory"
    )
    parser.add_argument("--private-root", type=Path, default=Path(".private"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    report = audit_private_permissions_to_file(
        args.private_root,
        args.output,
        repair=args.repair,
    )
    if report["status"] not in {"PASS", "PASS_NOT_PRESENT"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

