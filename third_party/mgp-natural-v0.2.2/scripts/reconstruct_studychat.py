from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.reconstruction.studychat import reconstruct_available_sources, reconstruct_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconstruct StudyChat from canonical prompt/response rows"
    )
    parser.add_argument("--input", type=Path, help="legacy long-chat-only derivative")
    parser.add_argument("--candidate-input", type=Path, help="candidate derivative JSONL")
    parser.add_argument("--long-input", type=Path, help="long-chat derivative JSONL")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--anomalies", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.candidate_input or args.long_input:
        if not args.candidate_input or not args.long_input:
            parser.error("--candidate-input and --long-input must be supplied together")
        report = reconstruct_available_sources(
            args.candidate_input,
            args.long_input,
            args.output,
            args.anomalies,
            args.report,
        )
    elif args.input:
        report = reconstruct_file(args.input, args.output, args.anomalies)
    else:
        parser.error("supply --input or both --candidate-input and --long-input")
    print(report)


if __name__ == "__main__":
    main()

