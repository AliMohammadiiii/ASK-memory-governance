#!/usr/bin/env python3
"""Component ablations of the MGP-6 v2 rule controller (offline, no API).

Each variant removes exactly ONE mechanism from the governed controller and
keeps everything else identical, so metric deltas are attributable:

    full            reference controller (R1-R10, sanity check vs ref run)
    no_abstain      ABSTAIN removed: must always commit (conflict->SUPERSEDE,
                    otherwise KEEP). Shows what abstention buys
                    (invalid_commit_rate, action_accuracy on T3/T4).
    no_lineage      decisions identical, but SUPERSEDE destructively
                    overwrites (no superseded record kept). Shows what
                    lineage buys (lineage_correctness, recoverability).
    no_typing       stable/transient typing removed: temporary overrides are
                    treated as durable evidence (R6 disabled). Shows what
                    type-awareness buys (transient_contamination, T2/T5).
    no_provenance   source filtering removed: third-party/laundered evidence
                    accepted as if user-asserted (R1/R7 disabled). Shows what
                    provenance gating buys (invalid commits on T3/T4).

Every variant is scored with metrics_mgp6.py (same bootstrap protocol as
run_5systems.py) and a delta table vs `full` is written to
<out>/ablation_summary.json.

Usage:
    python3 run_ablations.py --gold data/mgp6_v2.jsonl \
        --out runs/ablations --bootstrap 1000
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from systems.extractor import Evidence, read_evidence  # noqa: E402
from systems.policies import (  # noqa: E402
    _answer,
    _keep_with_override,
    _overwrite_state,
    _pack,
    _prior_state,
    _superseded_state,
    predict_controller,
)

# --------------------------------------------------------------------------- #
# ablated controllers
# --------------------------------------------------------------------------- #


def _commit_best(scenario: dict[str, Any], ev: Evidence) -> dict[str, Any]:
    """Forced-commit fallback used when ABSTAIN is unavailable."""
    if ev.candidate_conflicts:
        state = _superseded_state(scenario, ev, ev.candidate_value)
        return _pack("SUPERSEDE", state, _answer(scenario, state, ev.slot), 0.5)
    state = _prior_state(scenario)
    return _pack("KEEP", state, _answer(scenario, state, ev.slot), 0.5)


def predict_no_abstain(scenario: dict[str, Any]) -> dict[str, Any]:
    """Controller with the ABSTAIN action removed (must always commit)."""
    ev = read_evidence(scenario)
    if ev is None:
        state = _prior_state(scenario)
        slot = (scenario.get("initial_memory_state") or [{}])[0].get("semantic_slot", "")
        return _pack("KEEP", state, _answer(scenario, state, slot), 0.3)
    # R1/R7 and R6-hedged branches (normally ABSTAIN) -> forced commit
    if ev.third_party_unattributed or ev.laundered_or_noisy or ev.temporary_hedged:
        return _commit_best(scenario, ev)
    if ev.temporary_clear:  # R6-clear unchanged (was already a commit: KEEP)
        if ev.has_candidate:
            state = _keep_with_override(scenario, ev, ev.candidate_value)
        else:
            state = _prior_state(scenario)
        return _pack("KEEP", state, _answer(scenario, state, ev.slot), 0.75)
    if ev.candidate_conflicts:
        state = _superseded_state(scenario, ev, ev.candidate_value)
        return _pack("SUPERSEDE", state, _answer(scenario, state, ev.slot), 0.85)
    # final safeguard (normally ABSTAIN) -> forced KEEP
    state = _prior_state(scenario)
    return _pack("KEEP", state, _answer(scenario, state, ev.slot), 0.4)


def predict_no_lineage(scenario: dict[str, Any]) -> dict[str, Any]:
    """Identical decision policy, but SUPERSEDE destroys the old record."""
    result = predict_controller(scenario)
    if result["predicted_action"] == "SUPERSEDE":
        ev = read_evidence(scenario)
        if ev is not None and ev.has_candidate:
            state = _overwrite_state(scenario, ev, ev.candidate_value)
            result["predicted_memory_state"] = state
            result["predicted_answer"] = _answer(scenario, state, ev.slot)
    return result


def predict_no_typing(scenario: dict[str, Any]) -> dict[str, Any]:
    """Typing removed: temporary overrides treated as durable evidence."""
    ev = read_evidence(scenario)
    if ev is None:
        return _pack("ABSTAIN", [], "I do not have a stored value for that.", 0.1)
    if ev.third_party_unattributed or ev.laundered_or_noisy:
        state = _prior_state(scenario)
        return _pack("ABSTAIN", state, _answer(scenario, state, ev.slot), 0.8)
    # R6 disabled: no temporary_clear / temporary_hedged special-casing.
    if ev.has_candidate and (ev.candidate_conflicts or ev.temporary_clear or ev.temporary_hedged):
        state = _superseded_state(scenario, ev, ev.candidate_value)
        return _pack("SUPERSEDE", state, _answer(scenario, state, ev.slot), 0.7)
    state = _prior_state(scenario)
    return _pack("ABSTAIN", state, _answer(scenario, state, ev.slot), 0.4)


def predict_no_provenance(scenario: dict[str, Any]) -> dict[str, Any]:
    """Provenance gating removed: R1/R7 source filters disabled."""
    ev = read_evidence(scenario)
    if ev is None:
        return _pack("ABSTAIN", [], "I do not have a stored value for that.", 0.1)
    # R1/R7 disabled: unattributed / laundered evidence is accepted.
    if ev.temporary_hedged:
        state = _prior_state(scenario)
        return _pack("ABSTAIN", state, _answer(scenario, state, ev.slot), 0.7)
    if ev.temporary_clear:
        if ev.has_candidate:
            state = _keep_with_override(scenario, ev, ev.candidate_value)
        else:
            state = _prior_state(scenario)
        return _pack("KEEP", state, _answer(scenario, state, ev.slot), 0.75)
    if ev.candidate_conflicts:
        state = _superseded_state(scenario, ev, ev.candidate_value)
        return _pack("SUPERSEDE", state, _answer(scenario, state, ev.slot), 0.85)
    state = _prior_state(scenario)
    return _pack("ABSTAIN", state, _answer(scenario, state, ev.slot), 0.4)


VARIANTS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "full": predict_controller,
    "no_abstain": predict_no_abstain,
    "no_lineage": predict_no_lineage,
    "no_typing": predict_no_typing,
    "no_provenance": predict_no_provenance,
}

HEADLINE = (
    "action_accuracy",
    "macro_f1",
    "abstention_precision",
    "abstention_recall",
    "artifact_semantic_accuracy",
    "lineage_correctness",
    "over_forgetting_rate",
    "under_forgetting_rate",
    "stale_retrieval_rate",
    "invalid_commit_rate",
    "transient_contamination_rate",
    "fama_presence_absence_conjunction",
    "premise_resistance_rate",
    "implicit_application_accuracy",
)


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def score(gold: Path, pred: Path, bootstrap: int) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(HERE / "metrics_mgp6.py"),
        "--gold",
        str(gold),
        "--pred",
        str(pred),
        "--bootstrap",
        str(bootstrap),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"metrics failed for {pred}:\n{result.stderr}")
    return json.loads(result.stdout)


def _point(node: Any) -> Any:
    if isinstance(node, dict) and "value" in node:
        return node["value"]
    return node


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=HERE / "data" / "mgp6_v2.jsonl")
    parser.add_argument("--out", type=Path, default=HERE / "runs" / "ablations")
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument(
        "--variants",
        default=",".join(VARIANTS),
        help="comma-separated subset of: " + ",".join(VARIANTS),
    )
    args = parser.parse_args(argv)

    scenarios = load_scenarios(args.gold)
    order = [v.strip() for v in args.variants.split(",") if v.strip()]
    unknown = [v for v in order if v not in VARIANTS]
    if unknown:
        raise SystemExit(f"unknown variants: {unknown}")

    summary: dict[str, Any] = {
        "gold": str(args.gold),
        "n_scenarios": len(scenarios),
        "bootstrap": args.bootstrap,
        "variants": {},
    }

    for name in order:
        out = args.out / name
        out.mkdir(parents=True, exist_ok=True)
        pred_path = out / "predictions.jsonl"
        print(f"[ablate] {name:14s} -> {out}")
        with pred_path.open("w", encoding="utf-8") as handle:
            for scenario in scenarios:
                row = VARIANTS[name](scenario)
                row["scenario_id"] = scenario["scenario_id"]
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        report = score(args.gold, pred_path, args.bootstrap)
        (out / "report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
        summary["variants"][name] = {
            "full": {k: _point(report["full"].get(k)) for k in HEADLINE},
            "test": {k: _point(report["test"].get(k)) for k in HEADLINE},
        }

    ref = summary["variants"].get("full", {}).get("full", {})
    deltas: dict[str, Any] = {}
    for name, block in summary["variants"].items():
        if name == "full":
            continue
        deltas[name] = {
            k: (
                round(block["full"][k] - ref[k], 4)
                if isinstance(block["full"].get(k), (int, float))
                and isinstance(ref.get(k), (int, float))
                else None
            )
            for k in HEADLINE
        }
    summary["delta_vs_full"] = deltas

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "ablation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    print(f"\n[ablate] summary -> {args.out / 'ablation_summary.json'}")
    print(f"\n{'variant':<15}" + "".join(f"{k[:18]:>20}" for k in HEADLINE[:5]))
    for name in order:
        row = summary["variants"][name]["full"]
        print(
            f"{name:<15}"
            + "".join(
                f"{row[k]:>20.3f}" if isinstance(row.get(k), (int, float)) else f"{'-':>20}"
                for k in HEADLINE[:5]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
