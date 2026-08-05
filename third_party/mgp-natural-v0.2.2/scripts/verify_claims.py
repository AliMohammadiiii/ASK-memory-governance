from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.audits.claims import verify_claims


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify supported claim boundaries")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--documents", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(verify_claims(args.ledger, args.documents, args.output))


if __name__ == "__main__":
    main()

