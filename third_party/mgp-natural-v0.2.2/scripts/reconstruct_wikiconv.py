from __future__ import annotations

import argparse
import json
from pathlib import Path

from mgp_natural.reconstruction.wikiconv import reconstruct_actions


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstruct WikiConv actions and lineage")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reconstruct_actions(args.input, args.output), sort_keys=True))


if __name__ == "__main__":
    main()

