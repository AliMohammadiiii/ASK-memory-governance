from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.scoring.metrics import score_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score complete predictions against validated, track-separated gold"
    )
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-provisional-smoke", action="store_true")
    parser.add_argument("--bootstrap-iterations", type=int, default=1000)
    parser.add_argument("--bootstrap-seed", type=int, default=1729)
    args = parser.parse_args()
    print(
        score_files(
            args.gold,
            args.predictions,
            args.output,
            args.allow_provisional_smoke,
            args.bootstrap_iterations,
            args.bootstrap_seed,
        )
    )


if __name__ == "__main__":
    main()

