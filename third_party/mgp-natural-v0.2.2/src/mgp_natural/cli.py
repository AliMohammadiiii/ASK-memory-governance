"""Minimal installed CLI used by clean-room validation."""
from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.mining.studychat import mine_file
from mgp_natural.privacy.scanner import scan_jsonl


def smoke(fixture: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = output_dir / "candidates.jsonl"
    rejections = output_dir / "rejections.jsonl"
    mining_report = output_dir / "mining_report.json"
    mine_file(fixture, candidates, rejections, mining_report)
    scan_jsonl(
        candidates,
        output_dir / "privacy_findings.jsonl",
        output_dir / "privacy_report.json",
        output_dir / "privacy_queue.csv",
    )
    print("MGP_NATURAL_PUBLIC_SMOKE_PASS")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mgp-natural")
    sub = parser.add_subparsers(dest="command", required=True)
    smoke_parser = sub.add_parser("smoke", help="run deterministic public fixture pipeline")
    smoke_parser.add_argument("--fixture", type=Path, required=True)
    smoke_parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "smoke":
        smoke(args.fixture, args.output_dir)


if __name__ == "__main__":
    main()

