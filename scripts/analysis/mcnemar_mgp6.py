#!/usr/bin/env python3
"""Pre-specified paired significance tests for MGP-6 v2 (n=180).

Skeptical-statistician analysis layer. This script is READ-ONLY with respect to
all run artifacts. It recomputes, from the per-item prediction files, the four
pre-specified pairwise comparisons of *action accuracy* on the full MGP-6 v2
corpus (n=180 paired items):

  1. rule-controller  vs  b4 (naive-overwrite)
  2. rule-controller  vs  b2 (flat-retrieval)
  3. rule-controller  vs  llm-controller (qwen3.5-9b)
  4. llm-controller    vs  zero-shot decision baseline

Action-comparison logic is replicated EXACTLY from mgp6_v2/metrics_mgp6.py:
  * predicted_action is canonicalised to one of
    {KEEP, SUPERSEDE, ABSTAIN, INVALID_COMMIT, INVALID}; anything else -> INVALID
    (metrics_mgp6.load_predictions, lines 69-74).
  * an item is "correct" iff predicted_action == gold_action
    (metrics_mgp6.action_accuracy, line 112). Gold actions are only
    KEEP/SUPERSEDE/ABSTAIN, so INVALID_COMMIT / INVALID predictions are always
    counted incorrect.
  * items are matched by scenario_id (metrics_mgp6.align / paired_mcnemar).

For each pair we report:
  * n, the 2x2 concordance/discordance table, marginal accuracies,
  * exact two-sided McNemar p-value using the SAME formula as
    metrics_mgp6.paired_mcnemar (exact binomial, p=0.5 on the discordant cells),
  * Holm-Bonferroni-corrected significance across the 4-test family,
  * effect sizes: McNemar odds ratio (b/c) and the paired risk difference,
  * risk-difference CIs: Newcombe (Wilson-based, method 10) and a paired
    item-level bootstrap (10000 reps, fixed seed), plus Wilson score CIs for
    each system's marginal accuracy.

No external dependencies (stdlib only).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Action canonicalisation (mirrors mgp6_v2/metrics_mgp6.py)
# ---------------------------------------------------------------------------
ACTIONS = ("KEEP", "SUPERSEDE", "ABSTAIN")
PREDICTION_OUTCOMES = (*ACTIONS, "INVALID_COMMIT", "INVALID")


def canonical_action(raw: Any) -> str:
    """Replicates metrics_mgp6.load_predictions action handling."""
    return raw if raw in PREDICTION_OUTCOMES else "INVALID"


def load_gold(path: Path) -> dict[str, dict[str, str]]:
    gold: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8") as fh:
        for _line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            sid = row["scenario_id"]
            gold[sid] = {
                "gold_action": row["gold_action"],
                "split": row.get("split", ""),
                "type": row.get("type", ""),
            }
    return gold


def load_predictions(path: Path) -> dict[str, str]:
    """scenario_id -> canonical predicted_action."""
    preds: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for _line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            sid = row["scenario_id"]
            preds[sid] = canonical_action(row.get("predicted_action", "INVALID"))
    return preds


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def exact_mcnemar_p(b: int, c: int) -> float:
    """Exact two-sided McNemar, identical to metrics_mgp6.paired_mcnemar.

    b = # items where A correct & B wrong; c = # items where A wrong & B correct.
    """
    discordant = b + c
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, k) for k in range(min(b, c) + 1)) / (2**discordant)
    return min(1.0, 2 * tail)


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe_paired_rd_ci(e: int, f: int, g: int, h: int) -> tuple[float, float]:
    """Newcombe (1998) method 10 CI for the difference of paired proportions.

    2x2 table:
                    B correct   B wrong
        A correct       e           f
        A wrong         g           h
    p1 = (e+f)/n (A acc), p2 = (e+g)/n (B acc), diff = p1 - p2 = (f - g)/n.
    """
    n = e + f + g + h
    if n == 0:
        return (0.0, 0.0)
    p1 = (e + f) / n
    p2 = (e + g) / n
    diff = p1 - p2
    l1, u1 = wilson_ci(e + f, n)
    l2, u2 = wilson_ci(e + g, n)
    r1 = (e + f) * (g + h) * (e + g) * (f + h)
    if r1 == 0:
        phi = 0.0
    else:
        phi = (e * h - f * g) / math.sqrt(r1)
    term_l = (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2
    term_u = (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2
    lower = diff - math.sqrt(max(0.0, term_l))
    upper = diff + math.sqrt(max(0.0, term_u))
    return (max(-1.0, lower), min(1.0, upper))


def bootstrap_rd_ci(
    correct_a: list[int], correct_b: list[int], reps: int = 10000, seed: int = 20260712
) -> tuple[float, float]:
    """Paired item-level bootstrap percentile CI for the risk difference."""
    n = len(correct_a)
    rng = random.Random(seed)
    diffs: list[float] = []
    for _ in range(reps):
        sa = 0
        sb = 0
        for _ in range(n):
            j = rng.randrange(n)
            sa += correct_a[j]
            sb += correct_b[j]
        diffs.append((sa - sb) / n)
    diffs.sort()

    def pct(q: float) -> float:
        pos = (len(diffs) - 1) * q
        lo = math.floor(pos)
        hi = math.ceil(pos)
        if lo == hi:
            return diffs[lo]
        return diffs[lo] + (diffs[hi] - diffs[lo]) * (pos - lo)

    return (pct(0.025), pct(0.975))


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (monotone-enforced)."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * pvals[idx]
        running = max(running, val)
        adj[idx] = min(1.0, running)
    return adj


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def compare(
    name_a: str,
    preds_a: dict[str, str],
    name_b: str,
    preds_b: dict[str, str],
    gold: dict[str, dict[str, str]],
) -> dict[str, Any]:
    sids = sorted(gold.keys())
    e = f = g = h = 0  # e both-correct, f A-only, g B-only, h both-wrong
    ca: list[int] = []
    cb: list[int] = []
    for sid in sids:
        ga = gold[sid]["gold_action"]
        ok_a = int(preds_a[sid] == ga)
        ok_b = int(preds_b[sid] == ga)
        ca.append(ok_a)
        cb.append(ok_b)
        if ok_a and ok_b:
            e += 1
        elif ok_a and not ok_b:
            f += 1
        elif not ok_a and ok_b:
            g += 1
        else:
            h += 1
    n = e + f + g + h
    acc_a = (e + f) / n
    acc_b = (e + g) / n
    rd = acc_a - acc_b
    p_exact = exact_mcnemar_p(f, g)
    wa = wilson_ci(e + f, n)
    wb = wilson_ci(e + g, n)
    nc = newcombe_paired_rd_ci(e, f, g, h)
    boot = bootstrap_rd_ci(ca, cb)
    if g == 0 and f == 0:
        odds = float("nan")
    elif g == 0:
        odds = float("inf")
    else:
        odds = f / g
    return {
        "name_a": name_a,
        "name_b": name_b,
        "n": n,
        "table": {"both_correct": e, "a_only_correct": f, "b_only_correct": g, "both_wrong": h},
        "n_discordant": f + g,
        "acc_a": acc_a,
        "acc_b": acc_b,
        "acc_a_correct": e + f,
        "acc_b_correct": e + g,
        "acc_a_wilson": wa,
        "acc_b_wilson": wb,
        "risk_difference": rd,
        "rd_newcombe_ci": nc,
        "rd_bootstrap_ci": boot,
        "mcnemar_exact_p": p_exact,
        "odds_ratio_b_over_c": odds,
    }


def fmt_ci(ci: tuple[float, float]) -> str:
    return f"[{ci[0]:+.4f}, {ci[1]:+.4f}]"


def fmt_ci_pos(ci: tuple[float, float]) -> str:
    return f"[{ci[0]:.4f}, {ci[1]:.4f}]"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_mgp6 = Path(__file__).resolve().parents[2].parent / "mgp6_v2"
    parser.add_argument(
        "--mgp6-root",
        type=Path,
        default=default_mgp6,
        help="root of the mgp6_v2 tree (holds data/ and runs/)",
    )
    args = parser.parse_args(argv)

    root: Path = args.mgp6_root
    gold_path = root / "data" / "mgp6_v2.jsonl"
    systems = {
        "rule_controller": root / "runs" / "ref_5systems" / "controller" / "predictions.jsonl",
        "b4_naive_overwrite": root / "runs" / "ref_5systems" / "b4" / "predictions.jsonl",
        "b2_flat_retrieval": root / "runs" / "ref_5systems" / "b2" / "predictions.jsonl",
        "llm_controller_qwen35_9b": root
        / "runs"
        / "llm_qwen35_9b"
        / "controller"
        / "predictions.jsonl",
        "zero_shot_decision": root
        / "runs"
        / "llm_decision_zero"
        / "controller"
        / "predictions.jsonl",
    }

    gold = load_gold(gold_path)
    preds = {name: load_predictions(p) for name, p in systems.items()}

    # integrity check: every system must cover exactly the gold scenario ids.
    gold_ids = set(gold)
    for name, pr in preds.items():
        if set(pr) != gold_ids:
            missing = sorted(gold_ids - set(pr))[:5]
            extra = sorted(set(pr) - gold_ids)[:5]
            print(f"FATAL: {name} id mismatch. missing={missing} extra={extra}", file=sys.stderr)
            return 2

    print("=" * 78)
    print("MGP-6 v2 pre-specified paired significance tests (n=180 full corpus)")
    print("Action-comparison logic replicated from mgp6_v2/metrics_mgp6.py")
    print("=" * 78)
    print()
    print("Per-system action accuracy (full corpus, canonicalised):")
    for name in systems:
        k = sum(int(preds[name][sid] == gold[sid]["gold_action"]) for sid in gold)
        n = len(gold)
        w = wilson_ci(k, n)
        print(f"  {name:28s} {k:3d}/{n} = {k / n:.4f}  Wilson95 {fmt_ci_pos(w)}")
    print()

    family = [
        ("rule_controller", "b4_naive_overwrite"),
        ("rule_controller", "b2_flat_retrieval"),
        ("rule_controller", "llm_controller_qwen35_9b"),
        ("llm_controller_qwen35_9b", "zero_shot_decision"),
    ]

    results = [compare(a, preds[a], b, preds[b], gold) for a, b in family]
    holm_adj = holm([r["mcnemar_exact_p"] for r in results])

    for r, padj in zip(results, holm_adj, strict=True):
        r["holm_adjusted_p"] = padj

    for i, r in enumerate(results, 1):
        print("-" * 78)
        print(f"PAIR {i}: {r['name_a']}  vs  {r['name_b']}")
        print("-" * 78)
        t = r["table"]
        print(f"  n paired items          : {r['n']}")
        print(
            f"  accuracy A ({r['name_a']}): {r['acc_a_correct']}/{r['n']} = {r['acc_a']:.4f}"
            f"  Wilson95 {fmt_ci_pos(r['acc_a_wilson'])}"
        )
        print(
            f"  accuracy B ({r['name_b']}): {r['acc_b_correct']}/{r['n']} = {r['acc_b']:.4f}"
            f"  Wilson95 {fmt_ci_pos(r['acc_b_wilson'])}"
        )
        print("  2x2 concordance table:")
        print(
            f"        both correct (e) = {t['both_correct']:3d}   A-correct/B-wrong (b) = {t['a_only_correct']:3d}"
        )
        print(
            f"        A-wrong/B-correct(c) = {t['b_only_correct']:3d}   both wrong (d)        = {t['both_wrong']:3d}"
        )
        print(
            f"  discordant pairs (b+c)  : {r['n_discordant']}  (b={t['a_only_correct']}, c={t['b_only_correct']})"
        )
        print(f"  risk difference (A - B) : {r['risk_difference']:+.4f}")
        print(f"    Newcombe95 (Wilson)   : {fmt_ci(r['rd_newcombe_ci'])}")
        print(f"    bootstrap95 (10k,seed): {fmt_ci(r['rd_bootstrap_ci'])}")
        odds = r["odds_ratio_b_over_c"]
        odds_s = (
            "inf (c=0)"
            if odds == float("inf")
            else ("undefined" if odds != odds else f"{odds:.3f}")
        )
        print(f"  McNemar odds ratio b/c  : {odds_s}")
        print(f"  McNemar exact 2-sided p : {r['mcnemar_exact_p']:.3e}")
        print(f"  Holm-adjusted p         : {r['holm_adjusted_p']:.3e}")
        sig = "SIGNIFICANT" if r["holm_adjusted_p"] < 0.05 else "not significant"
        print(f"  Family decision (alpha=0.05, Holm): {sig}")
        print()

    print("=" * 78)
    print("Holm-Bonferroni family summary (4 tests, alpha=0.05)")
    print("=" * 78)
    print(f"  {'pair':45s} {'raw p':>12s} {'Holm p':>12s}  decision")
    for r in results:
        label = f"{r['name_a']} vs {r['name_b']}"
        dec = "reject H0" if r["holm_adjusted_p"] < 0.05 else "retain H0"
        print(f"  {label:45s} {r['mcnemar_exact_p']:12.3e} {r['holm_adjusted_p']:12.3e}  {dec}")
    print()
    print("Interpretation notes:")
    print("  * H0 for each test: the two systems have equal action accuracy on the")
    print("    180 paired items (McNemar marginal homogeneity).")
    print("  * Odds ratio b/c > 1 favours system A; = inf when c=0 (B never uniquely correct).")
    print("  * All numbers are full-corpus (train+dev+test); MGP-6 v2 is an author-designed")
    print("    diagnostic slice and the rule controller encodes the labelling policy.")
    print("  * These tests establish that accuracy differences are not sampling noise;")
    print("    they do NOT establish general-capability superiority (see THREATS_TO_VALIDITY.md).")

    # machine-readable tail for downstream table generation
    print()
    print("JSON_RESULTS_BEGIN")
    print(json.dumps({"family": results, "holm": holm_adj}, indent=2))
    print("JSON_RESULTS_END")
    return 0


if __name__ == "__main__":
    sys.exit(main())
