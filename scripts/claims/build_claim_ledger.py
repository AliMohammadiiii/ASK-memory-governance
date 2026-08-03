#!/usr/bin/env python3
"""Recompute the headline ASK claims from frozen primary artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
JSON_OUT = ROOT / "claims/claims.json"
CSV_OUT = ROOT / "claims/claims.csv"

MGP_GOLD = ROOT / ".private/benchmarks/mgp6/v4.3/hidden_gold/hidden_gold.jsonl"
MGP_SCORER = ROOT / ".private/benchmarks/mgp6/v4.3/hidden_gold/evaluate_predictions.py"
MGP_PREDICTIONS = (
    ROOT / "runs/mgp6_v43/final_hidden/live_model_controller_qwen35_9b/predictions.jsonl"
)
MGP_SPLIT_SUMMARY = ROOT / "benchmarks/mgp6/mgp6_v4_3/public/SPLIT_SUMMARY.json"
LME_CONTROLLER_JUDGMENTS = (
    ROOT / "runs_local/lme_final_controller_v12_qwen_180/controller/judgments.jsonl"
)
LME_OVERWRITE_JUDGMENTS = ROOT / "runs_local/lme_final_controller_v12_qwen_180/b4/judgments.jsonl"
LME_ACTION_LOG = ROOT / "runs_local/lme_final_controller_v12_qwen_180/controller/action_log.jsonl"
LME_MANIFEST = ROOT / "runs_local/lme_final_controller_v12_qwen_180/manifest.json"
LME_ANALYSIS = ROOT / "artifacts/analysis/lme_v12_scorecard_analysis.json"
LME_ADJACENT = ROOT / "artifacts/analysis/lme_v12_adjacent_mcnemar.json"


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def score_mgp() -> dict[str, Any]:
    if not all(path.is_file() for path in (MGP_SCORER, MGP_GOLD, MGP_PREDICTIONS)):
        return {}
    result = subprocess.run(
        [sys.executable, str(MGP_SCORER), str(MGP_GOLD), str(MGP_PREDICTIONS)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def confusion_statistics(confusion: dict[str, dict[str, int]]) -> tuple[float, float]:
    labels = ("ABSTAIN", "KEEP", "SUPERSEDE")
    matrix = [[int(confusion[row][column]) for column in labels] for row in labels]
    total = sum(sum(row) for row in matrix)
    correct = sum(matrix[index][index] for index in range(len(labels)))
    row_sums = [sum(row) for row in matrix]
    column_sums = [
        sum(matrix[row][column] for row in range(len(labels))) for column in range(len(labels))
    ]
    expected = (
        sum(row * column for row, column in zip(row_sums, column_sums, strict=True)) / total**2
    )
    kappa = (correct / total - expected) / (1.0 - expected)
    numerator = correct * total - sum(
        row * column for row, column in zip(row_sums, column_sums, strict=True)
    )
    denominator = math.sqrt(
        (total**2 - sum(column**2 for column in column_sums))
        * (total**2 - sum(row**2 for row in row_sums))
    )
    return kappa, numerator / denominator


def exact_mcnemar(b: int, c: int) -> float:
    discordant = b + c
    tail = sum(math.comb(discordant, index) for index in range(min(b, c) + 1))
    return min(1.0, 2.0 * tail / 2**discordant)


def replay_lme(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actions: Counter[str] = Counter()
    action_mismatches = 0
    score_mismatches = 0
    for row in rows:
        c = float(row["feature_c"])
        e = float(row["feature_e"])
        f = float(row["feature_f"])
        relation = float(row["feature_r"])
        rho = float(row["feature_rho"])
        s_sup = c + 0.8 * e - 0.7 * f + 1.2 * max(0.0, -relation) - 0.5 * rho
        s_abs = (1.0 - c) + f + (1.0 - abs(relation))
        if not math.isclose(s_sup, float(row["s_rev"]), abs_tol=1e-12) or not math.isclose(
            s_abs, float(row["s_abs"]), abs_tol=1e-12
        ):
            score_mismatches += 1
        if s_abs > float(row["theta_abs"]):
            replayed = "Abstain"
        elif s_sup > float(row["theta_sup"]) and relation < 0:
            replayed = "Supersede"
        else:
            replayed = "Keep"
        actions[str(row["action"])] += 1
        if replayed != row["action"]:
            action_mismatches += 1
    return {
        "n": len(rows),
        "actions": dict(actions),
        "score_mismatches": score_mismatches,
        "action_mismatches": action_mismatches,
    }


def values_equal(expected: Any, observed: Any, tolerance: float) -> bool:
    if isinstance(expected, int | float) and isinstance(observed, int | float):
        return math.isclose(float(expected), float(observed), abs_tol=tolerance, rel_tol=0.0)
    if isinstance(expected, list) and isinstance(observed, list) and len(expected) == len(observed):
        return all(values_equal(a, b, tolerance) for a, b in zip(expected, observed, strict=True))
    if (
        isinstance(expected, dict)
        and isinstance(observed, dict)
        and expected.keys() == observed.keys()
    ):
        return all(values_equal(expected[key], observed[key], tolerance) for key in expected)
    return expected == observed


def build_claims(timestamp: str | None = None) -> dict[str, Any]:
    verified_at = timestamp or datetime.now(UTC).isoformat()
    mgp = score_mgp()
    split = json.loads(MGP_SPLIT_SUMMARY.read_text()) if MGP_SPLIT_SUMMARY.is_file() else {}
    controller = load_jsonl(LME_CONTROLLER_JUDGMENTS) if LME_CONTROLLER_JUDGMENTS.is_file() else []
    overwrite = load_jsonl(LME_OVERWRITE_JUDGMENTS) if LME_OVERWRITE_JUDGMENTS.is_file() else []
    action_rows = load_jsonl(LME_ACTION_LOG) if LME_ACTION_LOG.is_file() else []
    lme_replay = replay_lme(action_rows) if action_rows else {}
    lme_analysis = json.loads(LME_ANALYSIS.read_text()) if LME_ANALYSIS.is_file() else {}
    lme_adjacent = json.loads(LME_ADJACENT.read_text()) if LME_ADJACENT.is_file() else {}
    manifest = json.loads(LME_MANIFEST.read_text()) if LME_MANIFEST.is_file() else {}

    confusion = mgp.get("confusion_matrix", {})
    kappa, mcc = confusion_statistics(confusion) if confusion else (None, None)
    controller_by_id = {row["session_id"]: bool(row["correct"]) for row in controller}
    overwrite_by_id = {row["session_id"]: bool(row["correct"]) for row in overwrite}
    paired_ids = sorted(controller_by_id.keys() & overwrite_by_id.keys())
    b = sum(controller_by_id[item] and not overwrite_by_id[item] for item in paired_ids)
    c = sum(overwrite_by_id[item] and not controller_by_id[item] for item in paired_ids)
    mcnemar_p = exact_mcnemar(b, c) if paired_ids else None

    specs: list[dict[str, Any]] = []

    def add(
        claim_id: str,
        *,
        locator: str,
        text: str,
        category: str,
        path: Path,
        expected: Any,
        observed: Any,
        method: str,
        command: str,
        tolerance: float = 0.0,
        notes: str = "",
    ) -> None:
        source_hash = sha256_file(path)
        if source_hash is None:
            status = "missing_evidence"
        else:
            status = "verified" if values_equal(expected, observed, tolerance) else "mismatch"
        specs.append(
            {
                "claim_id": claim_id,
                "manuscript_file": "paper/paper_1/main.tex",
                "locator": locator,
                "claim_text": text,
                "claim_category": category,
                "evidence_source": path.relative_to(ROOT).as_posix(),
                "source_artifact_path": path.relative_to(ROOT).as_posix(),
                "source_artifact_sha256": source_hash,
                "generating_script": "scripts/claims/build_claim_ledger.py",
                "reproduction_command": command,
                "expected_value": expected,
                "observed_value": observed,
                "tolerance": tolerance,
                "statistical_method": method,
                "configuration_id": "mgp6-v43-frozen-hidden"
                if claim_id.startswith("MGP")
                else "lme-v12-frozen",
                "status": status,
                "verification_timestamp": verified_at,
                "notes": notes,
            }
        )

    score_command = (
        ".venv/bin/python .private/benchmarks/mgp6/v4.3/hidden_gold/evaluate_predictions.py "
        ".private/benchmarks/mgp6/v4.3/hidden_gold/hidden_gold.jsonl "
        "runs/mgp6_v43/final_hidden/live_model_controller_qwen35_9b/predictions.jsonl"
    )
    split_command = ".venv/bin/python scripts/claims/build_claim_ledger.py"
    add(
        "MGP_DATASET_N",
        locator="Section 4.1",
        text="MGP-6 v4.3 contains 900 items.",
        category="dataset",
        path=MGP_SPLIT_SUMMARY,
        expected=900,
        observed=split.get("item_count"),
        method="manifest count",
        command=split_command,
    )
    add(
        "MGP_COMPONENT_N",
        locator="Section 4.1",
        text="MGP-6 v4.3 contains 100 semantic components.",
        category="dataset",
        path=MGP_SPLIT_SUMMARY,
        expected=100,
        observed=split.get("component_count"),
        method="manifest count",
        command=split_command,
    )
    add(
        "MGP_SPLITS",
        locator="Section 4.1",
        text="Train, development, and hidden contain 180, 180, and 540 items.",
        category="dataset",
        path=MGP_SPLIT_SUMMARY,
        expected={"dev": 180, "hidden": 540, "train": 180},
        observed=split.get("split_counts"),
        method="manifest count",
        command=split_command,
    )
    add(
        "MGP_HIDDEN_BALANCE",
        locator="Section 7.1",
        text="The hidden split has 180 items per action.",
        category="dataset",
        path=MGP_SPLIT_SUMMARY,
        expected={"ABSTAIN": 180, "KEEP": 180, "SUPERSEDE": 180},
        observed=(split.get("class_distribution") or {}).get("hidden"),
        method="class count",
        command=split_command,
    )
    add(
        "MGP_ACCURACY",
        locator="Abstract; Table 1",
        text="Frozen hidden action accuracy is 0.8481.",
        category="metric",
        path=MGP_PREDICTIONS,
        expected=0.8481481481481481,
        observed=mgp.get("accuracy"),
        method="accuracy",
        command=score_command,
        tolerance=1e-12,
    )
    add(
        "MGP_MACRO_F1",
        locator="Abstract; Table 1",
        text="Frozen hidden macro-F1 is 0.8479.",
        category="metric",
        path=MGP_PREDICTIONS,
        expected=0.847872957121512,
        observed=mgp.get("macro_f1"),
        method="unweighted per-action macro-F1",
        command=score_command,
        tolerance=1e-12,
    )
    add(
        "MGP_CLUSTER_CI_ACCURACY",
        locator="Table 1",
        text="Component-cluster 95% accuracy interval is [0.8037, 0.8889].",
        category="uncertainty",
        path=MGP_PREDICTIONS,
        expected=[0.8037037037037037, 0.8888888888888888],
        observed=(mgp.get("cluster_bootstrap_95_ci") or {}).get("accuracy"),
        method="5,000-replicate component bootstrap, seed 4301",
        command=score_command,
        tolerance=1e-12,
    )
    add(
        "MGP_CLUSTER_CI_F1",
        locator="Table 1",
        text="Component-cluster 95% macro-F1 interval is [0.8021, 0.8894].",
        category="uncertainty",
        path=MGP_PREDICTIONS,
        expected=[0.8020749634748688, 0.889351432442434],
        observed=(mgp.get("cluster_bootstrap_95_ci") or {}).get("macro_f1"),
        method="5,000-replicate component bootstrap, seed 4301",
        command=score_command,
        tolerance=1e-12,
    )
    add(
        "MGP_CONFUSION",
        locator="Table 2",
        text="The hidden confusion matrix is 142/30/8, 18/151/11, 6/9/165.",
        category="metric",
        path=MGP_PREDICTIONS,
        expected={
            "ABSTAIN": {"ABSTAIN": 142, "KEEP": 30, "SUPERSEDE": 8},
            "KEEP": {"ABSTAIN": 18, "KEEP": 151, "SUPERSEDE": 11},
            "SUPERSEDE": {"ABSTAIN": 6, "KEEP": 9, "SUPERSEDE": 165},
        },
        observed=confusion,
        method="confusion count",
        command=score_command,
    )
    add(
        "MGP_KAPPA",
        locator="Table 1",
        text="Hidden Cohen kappa is 0.7722.",
        category="metric",
        path=MGP_PREDICTIONS,
        expected=0.7722222222222221,
        observed=kappa,
        method="Cohen kappa from confusion matrix",
        command=score_command,
        tolerance=1e-12,
    )
    add(
        "MGP_MCC",
        locator="Table 1",
        text="Hidden multiclass MCC is 0.7728.",
        category="metric",
        path=MGP_PREDICTIONS,
        expected=0.7728426536370914,
        observed=mcc,
        method="multiclass Matthews correlation",
        command=score_command,
        tolerance=1e-12,
    )
    add(
        "MGP_FALSE_COMMIT",
        locator="Abstract; Table 2",
        text="There are 38 gold-Abstain action false commits.",
        category="operational_harm",
        path=MGP_PREDICTIONS,
        expected=38,
        observed=(
            confusion.get("ABSTAIN", {}).get("KEEP", 0)
            + confusion.get("ABSTAIN", {}).get("SUPERSEDE", 0)
        )
        if confusion
        else None,
        method="gold-Abstain confusion count",
        command=score_command,
    )
    add(
        "MGP_ABSTAIN_KEEP",
        locator="Abstract; Table 2",
        text="Thirty gold-Abstain errors preserve the compared active state but lose the refusal event.",
        category="operational_harm",
        path=MGP_PREDICTIONS,
        expected=30,
        observed=confusion.get("ABSTAIN", {}).get("KEEP") if confusion else None,
        method="gold-Abstain to Keep count",
        command=score_command,
    )
    add(
        "MGP_ABSTAIN_SUPERSEDE",
        locator="Abstract; Table 2",
        text="Eight gold-Abstain errors replace active state without sufficient evidence.",
        category="operational_harm",
        path=MGP_PREDICTIONS,
        expected=8,
        observed=confusion.get("ABSTAIN", {}).get("SUPERSEDE") if confusion else None,
        method="gold-Abstain to Supersede count",
        command=score_command,
    )

    lme_command = ".venv/bin/python scripts/claims/build_claim_ledger.py"
    add(
        "LME_CONTROLLER_CORRECT",
        locator="Abstract; Table 3",
        text="ASK-LME answers 137 of 180 items correctly.",
        category="downstream",
        path=LME_CONTROLLER_JUDGMENTS,
        expected=137,
        observed=sum(bool(row.get("correct")) for row in controller) if controller else None,
        method="judgment count",
        command=lme_command,
    )
    add(
        "LME_OVERWRITE_CORRECT",
        locator="Abstract; Table 3",
        text="Naive overwrite answers 114 of 180 items correctly.",
        category="downstream",
        path=LME_OVERWRITE_JUDGMENTS,
        expected=114,
        observed=sum(bool(row.get("correct")) for row in overwrite) if overwrite else None,
        method="judgment count",
        command=lme_command,
    )
    add(
        "LME_PAIRED_DISCORDANCE",
        locator="Section 8.1",
        text="ASK versus naive overwrite has b=31 and c=8.",
        category="statistics",
        path=LME_CONTROLLER_JUDGMENTS,
        expected={"b": 31, "c": 8, "paired_n": 180},
        observed={"b": b, "c": c, "paired_n": len(paired_ids)},
        method="paired correctness by session_id",
        command=lme_command,
    )
    add(
        "LME_MCNEMAR",
        locator="Abstract; Section 8.1",
        text="Holm-adjusted exact paired McNemar p is 2.9e-4.",
        category="statistics",
        path=LME_CONTROLLER_JUDGMENTS,
        expected=0.0002940768754342571,
        observed=mcnemar_p,
        method="two-sided exact McNemar; largest raw p in the declared Holm family, adjusted p unchanged",
        command=lme_command,
        tolerance=1e-15,
    )
    adjacent_rows = lme_adjacent.get("comparisons", [])
    add(
        "LME_ADJACENT_HOLM_FAMILY",
        locator="Section 8.1; Table 11",
        text="The four adjacent system comparisons use one Holm family of size four.",
        category="statistics",
        path=LME_ADJACENT,
        expected={
            "family_size": 4,
            "b_c": [[34, 0], [48, 11], [44, 10], [31, 8]],
            "holm": [
                4.656612873077393e-10,
                3.7248846785353784e-06,
                6.77137190674415e-06,
                0.0002940768754342571,
            ],
        },
        observed={
            "family_size": lme_adjacent.get("family_size"),
            "b_c": [[row.get("b"), row.get("c")] for row in adjacent_rows],
            "holm": [row.get("holm_adjusted_p") for row in adjacent_rows],
        },
        method="two-sided exact paired McNemar with Holm correction over four adjacent tests",
        command=".venv/bin/python scripts/analysis/build_lme_adjacent_statistics.py",
        tolerance=1e-15,
        notes="Corrects an earlier narrative family-size label of six; displayed p-values unchanged.",
    )
    add(
        "LME_ACTION_N",
        locator="Abstract; Section 8.2",
        text="The V12 action log contains 12,654 candidate-prior decisions.",
        category="execution",
        path=LME_ACTION_LOG,
        expected=12654,
        observed=lme_replay.get("n"),
        method="JSONL row count",
        command=lme_command,
    )
    add(
        "LME_ACTION_COUNTS",
        locator="Section 8.2; Table 13",
        text="The log contains 11,478 Keep, 779 Abstain, and 397 Supersede decisions.",
        category="execution",
        path=LME_ACTION_LOG,
        expected={"Abstain": 779, "Keep": 11478, "Supersede": 397},
        observed=lme_replay.get("actions"),
        method="action count",
        command=lme_command,
    )
    add(
        "LME_SCORE_REPLAY",
        locator="Abstract; Section 8.2",
        text="All logged score pairs reproduce exactly.",
        category="replay",
        path=LME_ACTION_LOG,
        expected=0,
        observed=lme_replay.get("score_mismatches"),
        method="fixed scorecard replay at 1e-12 tolerance",
        command=lme_command,
    )
    add(
        "LME_ACTION_REPLAY",
        locator="Abstract; Section 8.2",
        text="All 12,654 final policy actions reproduce exactly.",
        category="replay",
        path=LME_ACTION_LOG,
        expected=0,
        observed=lme_replay.get("action_mismatches"),
        method="ordered-rule replay",
        command=lme_command,
    )
    leave_out = (lme_analysis.get("mechanism") or {}).get("leave_one_dimension_out", {})
    add(
        "LME_FEATURE_ABLATION",
        locator="Section 8.2; Table 14",
        text="Leave-one-dimension-out action changes are 8, 0, 779, 483, and 0 for c, e, f, r, rho.",
        category="mechanism",
        path=LME_ANALYSIS,
        expected={"c": 8, "e": 0, "f": 779, "r": 483, "rho": 0},
        observed={
            key: (leave_out.get(key) or {}).get("changed") for key in ("c", "e", "f", "r", "rho")
        },
        method="deterministic counterfactual replay, not causal estimation",
        command=".venv/bin/python scripts/analysis/analyze_lme_scorecard.py",
    )
    add(
        "LME_RELATION_GUARD",
        locator="Section 8.2",
        text="Removing the relation guard changes 11,091 Keep decisions to Supersede.",
        category="mechanism",
        path=LME_ANALYSIS,
        expected=11091,
        observed=((lme_analysis.get("mechanism") or {}).get("without_relation_guard") or {}).get(
            "changed"
        ),
        method="deterministic guard-removal replay",
        command=".venv/bin/python scripts/analysis/analyze_lme_scorecard.py",
    )
    add(
        "LME_MANIFEST_ANOMALY",
        locator="Section 9",
        text="The historical V12 manifest was not finalized after resume.",
        category="provenance",
        path=LME_MANIFEST,
        expected={"attempts": 3, "exit_code": 1, "status": "running"},
        observed={
            "attempts": len(manifest.get("attempts", [])),
            "exit_code": manifest.get("exit_code"),
            "status": manifest.get("status"),
        },
        method="historical manifest inspection",
        command=lme_command,
        notes="Anomaly verification supports a limitation, not a clean provenance claim.",
    )

    return {
        "schema_version": "1.0",
        "generated_by": "scripts/claims/build_claim_ledger.py",
        "verification_timestamp": verified_at,
        "claims": specs,
    }


def write_outputs(ledger: dict[str, Any], json_out: Path, csv_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fields = list(ledger["claims"][0].keys())
    with csv_out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for claim in ledger["claims"]:
            writer.writerow(
                {
                    key: json.dumps(value, sort_keys=True)
                    if isinstance(value, dict | list)
                    else value
                    for key, value in claim.items()
                }
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path, default=JSON_OUT)
    parser.add_argument("--csv-out", type=Path, default=CSV_OUT)
    args = parser.parse_args(argv)
    ledger = build_claims()
    write_outputs(ledger, args.json_out, args.csv_out)
    counts = Counter(claim["status"] for claim in ledger["claims"])
    print(json.dumps({"claims": len(ledger["claims"]), "status": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
