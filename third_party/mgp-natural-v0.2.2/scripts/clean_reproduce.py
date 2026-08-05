from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.release.reproduce import run_clean_reproduction


def main() -> None:
    parser = argparse.ArgumentParser(description="Run clean-room public fixture reproduction")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(run_clean_reproduction(args.root, args.wheel, args.output))


if __name__ == "__main__":
    main()

