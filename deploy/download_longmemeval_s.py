"""Download the public LongMemEval cleaned JSON (S or M) for Colab/GPU runs.

    # LongMemEval-S (default; ~115k-token haystacks)
    python deploy/download_longmemeval_s.py --dataset s

    # LongMemEval-M (~500-session haystacks) — the larger release
    python deploy/download_longmemeval_s.py --dataset m

Pass --filename to override if the upstream repo renames a file.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

# Default cleaned filenames in xiaowu0162/longmemeval-cleaned. If the upstream
# repo uses a different name for M, override with --filename.
_DEFAULT_FILENAMES = {
    "s": "longmemeval_s_cleaned.json",
    "m": "longmemeval_m_cleaned.json",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default="xiaowu0162/longmemeval-cleaned")
    p.add_argument("--dataset", choices=("s", "m"), default="s",
                   help="Which release to download (selects the default filename).")
    p.add_argument("--filename", default=None,
                   help="Override the upstream filename (defaults by --dataset).")
    p.add_argument("--out", type=Path, default=None,
                   help="Output path (defaults to /content/longmemeval/<filename>).")
    args = p.parse_args()

    filename = args.filename or _DEFAULT_FILENAMES[args.dataset]
    out = args.out or Path("/content/longmemeval") / filename

    out.parent.mkdir(parents=True, exist_ok=True)
    cached = hf_hub_download(
        repo_id=args.repo,
        repo_type="dataset",
        filename=filename,
    )
    shutil.copyfile(cached, out)
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"[download] dataset={args.dataset} wrote {out} ({size_mb:.1f} MiB)")
    print(f"[download] sha256={_sha256(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
