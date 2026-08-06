from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.splitting.continuity import build_graph_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Build authoritative continuity components")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--assignments", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.92)
    args = parser.parse_args()
    print(
        build_graph_file(
            args.input,
            args.assignments,
            args.report,
            args.near_duplicate_threshold,
        )
    )


if __name__ == "__main__":
    main()

