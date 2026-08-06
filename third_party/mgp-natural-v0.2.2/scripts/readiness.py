from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.audits.readiness import from_status_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate machine-readable and human-readable readiness reports")
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--go-no-go", type=Path)
    parser.add_argument("--remaining-actions", type=Path)
    args = parser.parse_args()
    print(
        from_status_file(
            args.status,
            args.output,
            go_no_go_path=args.go_no_go,
            remaining_actions_path=args.remaining_actions,
        )
    )


if __name__ == "__main__":
    main()

