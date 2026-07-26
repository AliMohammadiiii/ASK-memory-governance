#!/usr/bin/env python3
"""Inter-annotator agreement for MGP-6 v2 (action labels, 3 classes).

Compares an independent annotator's labels against the gold labels (default)
or against a second annotator (--second), and reports:

- raw agreement + bootstrap 95% CI
- Cohen's kappa + bootstrap 95% CI
- Krippendorff's alpha (nominal, 2 coders)
- per-type (T1..T6) raw agreement
- confusion matrix (rows = reference, cols = annotator)
- disagreements.jsonl for the adjudication meeting (includes gold rationale)

Accepted annotation formats:
- CSV with columns  scenario_id, annotator_action   (e.g. the filled sheet
  from make_annotation_kit.py)
- JSONL with fields scenario_id, annotator_action

Usage:
    python3 compute_agreement_v2.py --gold data/mgp6_v2.jsonl \
        --annotations annotation_kit_test/annotation_sheet_filled.csv \
        --out-dir annotation_kit_test

    # annotator A vs annotator B (gold-independent):
    python3 compute_agreement_v2.py --gold data/mgp6_v2.jsonl \
        --annotations A.csv --second B.csv --out-dir agreement_ab
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ACTIONS = ("KEEP", "SUPERSEDE", "ABSTAIN")


def load_gold(path: Path) -> dict[str, dict[str, Any]]:
    rows = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                r = json.loads(line)
                rows[r["scenario_id"]] = r
    return rows


def load_labels(path: Path, field: str = "annotator_action") -> dict[str, str]:
    labels: dict[str, str] = {}
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                sid = (row.get("scenario_id") or "").strip()
                lab = (row.get(field) or "").strip().upper()
                if sid and lab:
                    labels[sid] = lab
    else:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    r = json.loads(line)
                    sid = r.get("scenario_id")
                    lab = str(r.get(field, "")).strip().upper()
                    if sid and lab:
                        labels[sid] = lab
    bad = {s: l for s, l in labels.items() if l not in ACTIONS}
    if bad:
        raise SystemExit(f"invalid labels (must be KEEP/SUPERSEDE/ABSTAIN): {bad}")
    return labels


def raw_agreement(pairs: list[tuple[str, str]]) -> float:
    return sum(a == b for a, b in pairs) / len(pairs)


def cohen_kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    po = raw_agreement(pairs)
    ref_marg = Counter(a for a, _ in pairs)
    ann_marg = Counter(b for _, b in pairs)
    pe = sum((ref_marg[c] / n) * (ann_marg[c] / n) for c in ACTIONS)
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def krippendorff_alpha(pairs: list[tuple[str, str]]) -> float:
    """Nominal alpha for 2 coders, no missing data."""
    n_units = len(pairs)
    values = [v for pair in pairs for v in pair]
    n_total = len(values)
    marg = Counter(values)
    # observed disagreement
    do = sum(a != b for a, b in pairs) * 2 / (n_units * 2)  # per-unit pairable
    # expected disagreement
    de = 0.0
    for c in ACTIONS:
        for k in ACTIONS:
            if c != k:
                de += marg[c] * marg[k]
    de /= n_total * (n_total - 1)
    if de == 0:
        return 1.0
    return 1 - do / de


def bootstrap_ci(pairs: list[tuple[str, str]], fn, n_boot: int, seed: int) -> list[float]:
    rng = random.Random(seed)
    stats = []
    n = len(pairs)
    for _ in range(n_boot):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        try:
            stats.append(fn(sample))
        except ZeroDivisionError:
            continue
    stats.sort()
    lo = stats[int(0.025 * len(stats))]
    hi = stats[int(0.975 * len(stats)) - 1]
    return [round(lo, 4), round(hi, 4)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=HERE / "data" / "mgp6_v2.jsonl")
    parser.add_argument(
        "--annotations", type=Path, required=True, help="annotator labels (CSV or JSONL)"
    )
    parser.add_argument(
        "--second",
        type=Path,
        default=None,
        help="optional second annotator file; if given, agreement is annotator-vs-annotator",
    )
    parser.add_argument("--label-field", default="annotator_action")
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    gold = load_gold(args.gold)
    ann = load_labels(args.annotations, args.label_field)

    if args.second:
        ref = load_labels(args.second, args.label_field)
        ref_name = f"annotator_B({args.second.name})"
    else:
        ref = {sid: r["gold_action"] for sid, r in gold.items()}
        ref_name = "gold"

    common = sorted(set(ann) & set(ref))
    missing = (
        sorted(set(ann) - set(ref)) + sorted((set(ref) & set(gold)) - set(ann))
        if args.second is None
        else []
    )
    if not common:
        raise SystemExit("no overlapping scenario_ids between files")
    pairs = [(ref[sid], ann[sid]) for sid in common]

    po = raw_agreement(pairs)
    kappa = cohen_kappa(pairs)
    alpha = krippendorff_alpha(pairs)

    per_type: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for sid in common:
        if sid in gold:
            per_type[gold[sid]["type"]].append((ref[sid], ann[sid]))

    confusion = {r: {c: 0 for c in ACTIONS} for r in ACTIONS}
    for a, b in pairs:
        confusion[a][b] += 1

    report = {
        "reference": ref_name,
        "annotator": str(args.annotations),
        "n_items": len(pairs),
        "n_annotated_not_in_reference": len(missing),
        "raw_agreement": {
            "value": round(po, 4),
            "ci95": bootstrap_ci(pairs, raw_agreement, args.bootstrap, args.seed),
        },
        "cohen_kappa": {
            "value": round(kappa, 4),
            "ci95": bootstrap_ci(pairs, cohen_kappa, args.bootstrap, args.seed + 1),
        },
        "krippendorff_alpha_nominal": round(alpha, 4),
        "per_type_raw_agreement": {
            t: round(raw_agreement(p), 4) for t, p in sorted(per_type.items())
        },
        "label_distribution": {
            "reference": dict(Counter(a for a, _ in pairs)),
            "annotator": dict(Counter(b for _, b in pairs)),
        },
        "confusion_matrix_ref_rows": confusion,
    }

    disagreements = []
    for sid in common:
        if ref[sid] != ann[sid]:
            g = gold.get(sid, {})
            disagreements.append(
                {
                    "scenario_id": sid,
                    "type": g.get("type"),
                    "subtype": g.get("subtype"),
                    "reference_action": ref[sid],
                    "annotator_action": ann[sid],
                    "perturbation_event": g.get("perturbation_event"),
                    "gold_rationale_notes": g.get("rationale_notes"),
                    "annotation_rule_ids": g.get("annotation_rule_ids"),
                    "adjudicated_action": "",  # fill during adjudication
                    "adjudication_notes": "",
                }
            )
    report["n_disagreements"] = len(disagreements)

    print(json.dumps(report, indent=2, sort_keys=False))

    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "agreement_report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        with (args.out_dir / "disagreements.jsonl").open("w", encoding="utf-8") as h:
            for d in disagreements:
                h.write(json.dumps(d, ensure_ascii=False) + "\n")
        print(f"\n[agreement] report -> {args.out_dir / 'agreement_report.json'}", flush=True)
        print(
            f"[agreement] {len(disagreements)} disagreements -> "
            f"{args.out_dir / 'disagreements.jsonl'} (adjudicate these)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
