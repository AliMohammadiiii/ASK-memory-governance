from __future__ import annotations

import argparse
import json
from pathlib import Path

from mgp_natural.blinding.packet import verify_packet
from mgp_natural.util.io import write_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify packet allowlist, hashes, and nested leakage"
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_packet(args.packet)
    if args.output is not None:
        write_json(args.output, report)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

