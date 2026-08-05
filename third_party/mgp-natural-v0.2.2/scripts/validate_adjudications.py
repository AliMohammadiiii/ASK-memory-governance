from __future__ import annotations

import argparse
import json
from pathlib import Path

from mgp_natural.adjudication.validation import validate_adjudications


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate additive adjudications")
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--adjudications", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            validate_adjudications(
                args.items,
                args.annotations,
                args.adjudications,
                args.report,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

