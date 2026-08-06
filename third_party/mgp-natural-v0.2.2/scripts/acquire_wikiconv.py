from __future__ import annotations

import argparse
import json
from pathlib import Path

from mgp_natural.ingestion.wikiconv import (
    DownloadSpec,
    resumable_download,
    write_official_source_manifest,
    write_runtime_acquisition_attempt,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record official WikiConv sources or download a pinned artifact"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--access-date", default="2026-08-04")
    parser.add_argument("--attempt-report", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    write_official_source_manifest(args.manifest, args.access_date)
    if args.attempt_report is not None:
        write_runtime_acquisition_attempt(args.attempt_report, args.access_date)
    if args.spec is not None:
        if args.output_dir is None:
            parser.error("--output-dir is required with --spec")
        value = json.loads(args.spec.read_text(encoding="utf-8"))
        print(resumable_download(DownloadSpec(**value), args.output_dir))


if __name__ == "__main__":
    main()

