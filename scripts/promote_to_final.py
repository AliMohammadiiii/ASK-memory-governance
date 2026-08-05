#!/usr/bin/env python3
"""Gate an MGP-6 run before it may be cited as FINAL thesis numbers.

This is the last line of defence against the runs/m4w14 class of failure: a run
that *looks* complete (manifest.complete == true, a results table rendered) but
is not defensible -- wrong model tier, broken extraction, or a controller edge
that is not statistically distinguishable from the naive-overwrite baseline.

The script refuses (exit code 1) unless EVERY criterion below passes. Only on a
full pass does it write ``<run-root>/FINAL_OK.json`` and rewrite the run
manifest's ``tier``/``thesis_use`` to ``final``. The thesis result tables should
read only from runs that carry ``FINAL_OK.json``.

Criteria (all must hold):
  1. model_profile == "thesis"            (proposal-spec'd 7-8B model)
  2. dataset sha256 == expected MGP-6 sha (default: the v1 seed-0 slice)
  3. manifest.complete and sanity_ok      (run finished, no bug-signature)
  4. extraction recall >= SPEC floor       for controller AND b4
  5. T1 extraction recall >= SPEC floor    for controller AND b4
  6. controller beats b4 on action accuracy with a paired bootstrap 95% CI on
     the per-scenario difference whose lower bound is > 0
  7. superseded recoverability: controller == 1.0 (n_revisions>0) and
     b4 == 0.0 (n_revisions>0)

Stdlib only; no third-party imports, deterministic (fixed bootstrap seed).

Usage:
    python scripts/promote_to_final.py --run-root runs/m4w14_thesis \\
        --mgp6 data/mgp6_v1_seed0.jsonl
    # add --check-only to validate without writing FINAL_OK / mutating manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

# Proposal-spec'd profile and dataset; keep in sync with run_mgp6.SPEC_PROFILE
# and configs/eval_mgp6_final.yaml.
EXPECTED_PROFILE = "thesis"
EXPECTED_DATASET_SHA256 = "12e17af530067f0ec1cefa1131898e2c8bd2414ef20cfc4c37fb936148e65701"
# Fallback floors if the sanity report predates the threshold block.
DEFAULT_SPEC_MIN_EXTRACTION_RECALL = 0.90
DEFAULT_SPEC_MIN_T1_RECALL = 0.90
UPDATING_FOR_RECALL = ("controller", "b4", "naive_overwrite")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _predictions(run_root: Path, alias: str) -> dict[str, str]:
    rows = _load_jsonl(run_root / alias / "predictions.jsonl")
    return {r["scenario_id"]: r.get("predicted_action") for r in rows}


def _paired_bootstrap(controller_ok: list[int], b4_ok: list[int], n_boot: int, seed: int):
    diff = [c - b for c, b in zip(controller_ok, b4_ok, strict=True)]
    n = len(diff)
    rng = random.Random(seed)
    boots = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        boots.append(sum(diff[i] for i in idx) / n)
    boots.sort()
    lo = boots[int(0.025 * n_boot)]
    hi = boots[int(0.975 * n_boot)]
    return sum(diff) / n, lo, hi


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--run-root",
        type=Path,
        required=True,
        help="MGP-6 run dir (has manifest.json, b4/, controller/).",
    )
    ap.add_argument(
        "--mgp6", type=Path, default=Path("data/mgp6_v1_seed0.jsonl"), help="Gold dataset."
    )
    ap.add_argument(
        "--recoverability-report",
        type=Path,
        default=None,
        help="Path to recoverability_report.json (default: <run-root>/recoverability_report.json).",
    )
    ap.add_argument("--expected-dataset-sha", default=EXPECTED_DATASET_SHA256)
    ap.add_argument("--expected-profile", default=EXPECTED_PROFILE)
    ap.add_argument("--n-bootstrap", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument(
        "--check-only",
        action="store_true",
        help="Validate without writing FINAL_OK or mutating manifest.",
    )
    args = ap.parse_args()

    run_root: Path = args.run_root
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append((name, bool(passed), detail))

    # --- load manifest + sanity ---
    manifest_path = run_root / "manifest.json"
    sanity_path = run_root / "sanity_report.json"
    if not manifest_path.exists():
        print(f"FATAL: {manifest_path} not found", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sanity = json.loads(sanity_path.read_text(encoding="utf-8")) if sanity_path.exists() else {}

    # 1. profile
    profile = manifest.get("model_profile")
    check("model_profile == thesis", profile == args.expected_profile, f"got {profile!r}")

    # 2. dataset sha
    ds_path = Path(manifest.get("input", args.mgp6))
    if not ds_path.is_absolute() and not ds_path.exists():
        ds_path = args.mgp6
    actual_sha = _sha256(ds_path) if ds_path.exists() else "MISSING"
    check(
        "dataset sha256 matches",
        actual_sha == args.expected_dataset_sha,
        f"{actual_sha[:16]}… vs expected {args.expected_dataset_sha[:16]}…",
    )

    # 3. complete + sanity_ok
    check("manifest.complete", bool(manifest.get("complete")), str(manifest.get("complete")))
    check(
        "sanity_ok",
        bool(manifest.get("sanity_ok")) and bool(sanity.get("ok", manifest.get("sanity_ok"))),
        f"manifest={manifest.get('sanity_ok')} sanity={sanity.get('ok')}",
    )

    # 3b. full run, not a smoke/limited run. The runner stamps tier=smoke /
    # thesis_use=no_final_claim whenever --limit is set; a limited run must
    # never promote even if its (partial) extraction looks healthy.
    limit = manifest.get("limit")
    tier = manifest.get("tier")
    check(
        "full run (not smoke/limited)",
        limit is None and tier in ("final-candidate", "final"),
        f"limit={limit} tier={tier}",
    )

    # thresholds (prefer those recorded by the run; fall back to defaults)
    thr = sanity.get("thresholds", {})
    min_rec = thr.get("spec_min_extraction_recall", DEFAULT_SPEC_MIN_EXTRACTION_RECALL)
    min_t1 = thr.get("spec_min_t1_recall", DEFAULT_SPEC_MIN_T1_RECALL)
    per_system = sanity.get("per_system", {})

    # 4 + 5. extraction recall (overall and T1) for controller and b4
    for alias in ("controller", "b4"):
        ps = per_system.get(alias, {})
        rec = ps.get("extraction_recall")
        t1 = ps.get("t1_extraction_recall")
        check(
            f"{alias} extraction_recall >= {min_rec:.2f}",
            rec is not None and rec >= min_rec,
            f"got {rec}",
        )
        check(
            f"{alias} T1 extraction_recall >= {min_t1:.2f}",
            t1 is not None and t1 >= min_t1,
            f"got {t1}",
        )

    # 6. paired bootstrap controller - b4
    gold = {r["scenario_id"]: r["gold_action"] for r in _load_jsonl(args.mgp6)}
    cp = _predictions(run_root, "controller")
    bp = _predictions(run_root, "b4")
    sids = list(gold)
    c_ok = [1 if cp.get(s) == gold[s] else 0 for s in sids]
    b_ok = [1 if bp.get(s) == gold[s] else 0 for s in sids]
    obs, lo, hi = _paired_bootstrap(c_ok, b_ok, args.n_bootstrap, args.seed)
    check(
        "controller > b4 (paired bootstrap CI lower > 0)",
        lo > 0,
        f"diff={obs:+.3f} 95%CI=[{lo:+.3f},{hi:+.3f}]",
    )

    # 7. recoverability: controller 1.0, b4 0.0 (both with revisions)
    rec_path = args.recoverability_report or (run_root / "recoverability_report.json")
    rec_ok_ctrl = rec_ok_b4 = False
    rec_detail = f"{rec_path} not found"
    if rec_path.exists():
        rrep = json.loads(rec_path.read_text(encoding="utf-8"))
        by_sys = {s["system"]: s for s in rrep.get("systems", [])}
        c = by_sys.get("controller", {})
        b = by_sys.get("b4", by_sys.get("naive_overwrite", {}))
        rec_ok_ctrl = c.get("superseded_recoverability") == 1.0 and (c.get("n_revisions") or 0) > 0
        rec_ok_b4 = b.get("superseded_recoverability") == 0.0 and (b.get("n_revisions") or 0) > 0
        rec_detail = (
            f"controller={c.get('superseded_recoverability')} (n={c.get('n_revisions')}), "
            f"b4={b.get('superseded_recoverability')} (n={b.get('n_revisions')})"
        )
    check("recoverability controller==1.0 & b4==0.0", rec_ok_ctrl and rec_ok_b4, rec_detail)

    # --- report ---
    all_pass = all(p for _, p, _ in checks)
    width = max(len(n) for n, _, _ in checks)
    print("=" * (width + 30))
    print(f"PROMOTION GATE  ({run_root})")
    print("=" * (width + 30))
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name:<{width}}  {detail}")
    print("-" * (width + 30))
    print(
        f"  RESULT: {'PASS — eligible for FINAL' if all_pass else 'FAIL — NOT eligible for FINAL'}"
    )
    print("=" * (width + 30))

    if not all_pass:
        return 1
    if args.check_only:
        print("[promote] --check-only: not writing FINAL_OK or mutating manifest.")
        return 0

    final_ok = {
        "promoted_at": datetime.now(UTC).isoformat(),
        "run_root": str(run_root),
        "model_profile": profile,
        "dataset_sha256": actual_sha,
        "paired_diff": obs,
        "paired_ci_95": [lo, hi],
        "recoverability": rec_detail,
        "checks": [{"name": n, "pass": p, "detail": d} for n, p, d in checks],
    }
    (run_root / "FINAL_OK.json").write_text(
        json.dumps(final_ok, indent=2, sort_keys=True), encoding="utf-8"
    )
    manifest["tier"] = "final"
    manifest["run_tier"] = "final"
    manifest["thesis_use"] = "final"
    manifest["promoted_at"] = final_ok["promoted_at"]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[promote] wrote {run_root / 'FINAL_OK.json'} and updated manifest tier -> final")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
