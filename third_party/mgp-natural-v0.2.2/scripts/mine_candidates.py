from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.mining.studychat import mine_file, mine_reconstructed_chats
from mgp_natural.mining.wikiconv import mine_reconstructed
from mgp_natural.util.io import iter_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mine provisional MGP construction candidates")
    parser.add_argument("--track", choices=["studychat", "wikiconv"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-format", choices=["auto", "flat_rows", "reconstructed_chats"], default="auto")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--rejections", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.track == "wikiconv":
        print(mine_reconstructed(args.input, args.candidates, args.report))
        return
    if not args.rejections:
        parser.error("--rejections is required for StudyChat")
    input_format = args.input_format
    if input_format == "auto":
        first = next(iter_jsonl(args.input), None)
        input_format = "reconstructed_chats" if first and "interactions" in first else "flat_rows"
    if input_format == "reconstructed_chats":
        report = mine_reconstructed_chats(
            args.input, args.candidates, args.rejections, args.report
        )
    else:
        report = mine_file(args.input, args.candidates, args.rejections, args.report)
    print(report)


if __name__ == "__main__":
    main()

