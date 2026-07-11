#!/usr/bin/env python3
"""Gate a LongMemEval-S (RQ2) run before it may be cited as FINAL thesis numbers.

RQ2 is exploratory (downstream QA accuracy, retrieval diagnostics, leakage); it
makes no "controller beats b4" claim, so this gate enforces DEFENSIBILITY, not a
result direction. It refuses (exit 1) unless every criterion holds:

  1. model_profile == "thesis"                  (proposal-spec'd 7-8B roles)
  2. slice sha256 == expected AND not synthetic  (no Risk-13 synthetic-slice trap)
  3. manifest.complete                           (run finished)
  4. completeness: summary.json has no missing_systems / validation_errors
  5. every requested system has report.json with the full n_sessions and a
     non-null overall_accuracy + bootstrap CI (primary metric present)
  6. judge tier: the grading judge is NOT a small same-family DEV model
     (proposal Risk 11). A dev judge can only reach `final-candidate` and only
     with --allow-dev-judge; it can NEVER be stamped `final`.

Outcomes:
  * all pass + non-dev judge          -> FINAL_OK.json,  manifest tier/thesis_use=final
  * all pass + dev judge + --allow-dev-judge
                                       -> FINAL_CANDIDATE_OK.json (NOT final)
  * otherwise                          -> exit 1, nothing written

Stdlib only; deterministic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

EXPECTED_PROFILE = "thesis"
EXPECTED_SLICE_SHA256 = "777a8d6fabfd782c05f05267d8af9e7738ad2672dc8626f872209bdc23799831"
EXPECTED_N_SESSIONS = 50
# Substrings that mark a small / same-family local judge as DEV evidence.
DEV_JUDGE_TOKENS = ("3b", "3.8b", "phi3", "phi-3", "gemma", "mini", "1.5b", "0.5b", "qwen2.5-3b", "qwen2.5:3b")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _is_dev_judge(judge: str | None) -> bool:
    if not judge:
        return True
    j = judge.lower()
    return any(tok in j for tok in DEV_JUDGE_TOKENS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-root", type=Path, required=True)
    ap.add_argument("--slice", type=Path, default=None, help="Override slice path (default: manifest.slice).")
    ap.add_argument("--expected-slice-sha", default=EXPECTED_SLICE_SHA256)
    ap.add_argument("--expected-profile", default=EXPECTED_PROFILE)
    ap.add_argument("--expected-n-sessions", type=int, default=EXPECTED_N_SESSIONS)
    ap.add_argument("--allow-dev-judge", action="store_true",
                    help="Permit a dev judge; result is capped at final-candidate, never final.")
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()

    run_root: Path = args.run_root
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append((name, bool(passed), detail))

    manifest_path = run_root / "manifest.json"
    if not manifest_path.exists():
        print(f"FATAL: {manifest_path} not found", file=sys.stderr)
        return 1
    manifest = _load(manifest_path)

    # 1. profile
    profile = manifest.get("model_profile")
    check("model_profile == thesis", profile == args.expected_profile, f"got {profile!r}")

    # 2. slice sha + not synthetic
    slice_path = args.slice or Path(manifest.get("slice", ""))
    synthetic = bool(manifest.get("slice_is_synthetic"))
    actual_sha = _sha256(slice_path) if slice_path and slice_path.exists() else "MISSING"
    check("slice sha matches & not synthetic",
          actual_sha == args.expected_slice_sha and not synthetic,
          f"sha={actual_sha[:16]}… synthetic={synthetic}")

    # 3. complete
    check("manifest.complete", bool(manifest.get("complete")), str(manifest.get("complete")))

    # 4. completeness via summary.json
    summary_path = run_root / "summary.json"
    if summary_path.exists():
        summary = _load(summary_path)
        missing = summary.get("missing_systems") or []
        verrs = summary.get("validation_errors") or []
        check("summary: no missing systems / validation errors",
              not missing and not verrs, f"missing={missing} errors={verrs}")
    else:
        check("summary: no missing systems / validation errors", False, "summary.json not found")

    # 5. per-system primary metric present + full n_sessions
    systems = manifest.get("systems") or ["b1", "b2", "b3", "b4", "controller"]
    judge_ids: set[str] = set()
    metric_ok = True
    metric_detail = []
    for alias in systems:
        rp = run_root / alias / "report.json"
        if not rp.exists():
            metric_ok = False
            metric_detail.append(f"{alias}:no-report")
            continue
        rep = _load(rp)
        n = rep.get("n_sessions")
        acc = rep.get("overall_accuracy")
        ci = (rep.get("overall_ci_low"), rep.get("overall_ci_high"))
        judge_ids.add(str(rep.get("judge_model_id")))
        ok = (n == args.expected_n_sessions and acc is not None and None not in ci)
        metric_ok = metric_ok and ok
        metric_detail.append(f"{alias}:n={n},acc={acc}")
    check(f"all systems report n={args.expected_n_sessions} + acc + CI",
          metric_ok, "; ".join(metric_detail))

    # 6. judge tier
    judge = sorted(judge_ids)[0] if judge_ids else manifest.get("judge_model")
    dev_judge = _is_dev_judge(judge)
    if dev_judge:
        check("judge tier (final requires non-dev judge)", args.allow_dev_judge,
              f"DEV judge {judge!r}; " + ("acknowledged → caps at final-candidate" if args.allow_dev_judge
                                          else "pass --allow-dev-judge for final-candidate, or upgrade judge for final"))
    else:
        check("judge tier (final requires non-dev judge)", True, f"non-dev judge {judge!r}")

    all_pass = all(p for _, p, _ in checks)
    width = max(len(n) for n, _, _ in checks)
    print("=" * (width + 30))
    print(f"LME PROMOTION GATE  ({run_root})")
    print("=" * (width + 30))
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name:<{width}}  {detail}")
    print("-" * (width + 30))
    target_tier = "final-candidate" if dev_judge else "final"
    print(f"  RESULT: {('PASS — eligible for ' + target_tier) if all_pass else 'FAIL — NOT eligible'}")
    print("=" * (width + 30))

    if not all_pass:
        return 1
    if args.check_only:
        print("[promote-lme] --check-only: not writing marker / mutating manifest.")
        return 0

    payload = {
        "promoted_at": datetime.now(UTC).isoformat(),
        "run_root": str(run_root),
        "model_profile": profile,
        "slice_sha256": actual_sha,
        "judge_model": judge,
        "judge_tier": "dev" if dev_judge else "final",
        "tier": target_tier,
        "checks": [{"name": n, "pass": p, "detail": d} for n, p, d in checks],
    }
    marker = "FINAL_CANDIDATE_OK.json" if dev_judge else "FINAL_OK.json"
    (run_root / marker).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    manifest["tier"] = target_tier
    manifest["run_tier"] = target_tier
    manifest["thesis_use"] = "final" if not dev_judge else "final_candidate_dev_judge"
    manifest["promoted_at"] = payload["promoted_at"]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[promote-lme] wrote {run_root / marker}; manifest tier -> {target_tier}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
