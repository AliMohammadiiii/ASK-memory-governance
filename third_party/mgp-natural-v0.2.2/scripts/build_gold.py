from __future__ import annotations

import argparse
import json
from pathlib import Path

from mgp_natural.adjudication.gold import build_gold


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build independently adjudicated gold after explicit approvals"
    )
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path, required=True)
    parser.add_argument("--approvals", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "gold_rows": build_gold(args.items, args.adjudications, args.approvals, args.output)
    }
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

