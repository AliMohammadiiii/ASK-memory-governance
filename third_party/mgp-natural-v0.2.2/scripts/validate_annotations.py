from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.annotation.agreement import analyze
from mgp_natural.annotation.validation import validate_annotations


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate independent annotation rows")
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--agreement", type=Path)
    parser.add_argument("--minimum", type=int, default=3)
    args = parser.parse_args()
    print(validate_annotations(args.items, args.annotations, args.report, args.minimum))
    if args.agreement:
        analyze(args.annotations, args.agreement, items_path=args.items)


if __name__ == "__main__":
    main()

