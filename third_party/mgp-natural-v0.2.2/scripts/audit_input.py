from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.ingestion.studychat import write_audit_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and safely extract a StudyChat archive")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--extract-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_audit_report(args.archive, args.extract_dir, args.output)


if __name__ == "__main__":
    main()

