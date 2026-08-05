from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.annotation.agreement import analyze


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze validated independent annotations")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--items", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(analyze(args.annotations, args.output, items_path=args.items))


if __name__ == "__main__":
    main()

