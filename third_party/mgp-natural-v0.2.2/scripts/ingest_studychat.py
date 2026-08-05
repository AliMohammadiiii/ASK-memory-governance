from __future__ import annotations

import argparse
from pathlib import Path

from mgp_natural.ingestion.studychat import acquire_authorized_huggingface


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire authorized StudyChat files; never accepts gated terms"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repo-id", default="wmcnicho/StudyChat")
    parser.add_argument("--revision")
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()
    print(
        acquire_authorized_huggingface(
            args.output_dir,
            args.repo_id,
            args.revision,
            args.local_files_only,
        )
    )


if __name__ == "__main__":
    main()

