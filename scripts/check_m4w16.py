"""Generate M4-W16 sanity-check notes, error taxonomy, and G3 decision."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.eval.m4w16 import run_m4w16, validate_artifacts  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--m4w14-root", type=Path, default=Path("runs/m4w14"))
    p.add_argument("--m4w15-root", type=Path, default=Path("runs/m4w15"))
    p.add_argument("--mgp6-input", type=Path, default=Path("data/mgp6_v1_seed0.jsonl"))
    p.add_argument("--notes-dir", type=Path, default=Path("NOTES"))
    p.add_argument("--out", type=Path, default=Path("runs/m4w16"))
    p.add_argument("--run-logreg-on-fail", action="store_true")
    p.add_argument("--check-only", action="store_true",
                   help="Validate prerequisites and print status without writing M4-W16 outputs.")
    args = p.parse_args()

    status = validate_artifacts(
        m4w14_root=args.m4w14_root,
        m4w15_root=args.m4w15_root,
        mgp6_input=args.mgp6_input,
    )
    print(status.format(), flush=True)
    if args.check_only:
        return 0 if status.ok else 2
    if not status.ok:
        raise SystemExit("M4-W16 cannot run until the real M4-W14/M4-W15 artifacts are complete.")

    result = run_m4w16(
        m4w14_root=args.m4w14_root,
        m4w15_root=args.m4w15_root,
        mgp6_input=args.mgp6_input,
        notes_dir=args.notes_dir,
        out_dir=args.out,
        run_logreg_on_fail=args.run_logreg_on_fail,
    )
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
