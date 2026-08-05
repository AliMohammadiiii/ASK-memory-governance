from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.splitting.split import build_splits


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assign authoritative continuity components to group-disjoint splits"
    )
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--components", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1729)
    args = parser.parse_args()
    print(build_splits(args.items, args.components, args.manifest, args.report, args.seed))


if __name__ == "__main__":
    main()

