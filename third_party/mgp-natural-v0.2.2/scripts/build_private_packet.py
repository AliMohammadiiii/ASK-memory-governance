from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.blinding.packet import build_packet


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an allowlisted private annotation packet")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--commitment", type=Path, required=True)
    parser.add_argument(
        "--secret-file",
        type=Path,
        help="private binary secret file; omit to generate a fresh 256-bit secret",
    )
    args = parser.parse_args()
    secret = args.secret_file.read_bytes() if args.secret_file else None
    print(build_packet(args.input, args.private_dir, args.packet, args.commitment, secret))


if __name__ == "__main__":
    main()

