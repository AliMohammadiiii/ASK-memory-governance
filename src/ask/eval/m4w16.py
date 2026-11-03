"""M4-W16 qualitative sanity checks and G3 gate utilities."""

from __future__ import annotations

import csv
import json
import math
import random
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SYSTEM_ALIASES: tuple[str, ...] = ("b1", "b2", "b3", "b4", "controller")
MGP6_TYPES: tuple[str, ...] = ("T1", "T2", "T3", "T4", "T5", "T6")
ACTIONS: tuple[str, ...] = ("KEEP", "SUPERSEDE", "ABSTAIN")
FEATURE_COLUMNS: tuple[str, ...] = (
    "feature_c",
    "feature_e",
    "feature_f",
    "feature_r",
    "feature_rho",
    "s_rev",
    "s_abs",
    "theta_sup",
    "theta_abs",
)


@dataclass(frozen=True)
class ArtifactStatus:
    missing: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.missing

    def format(self) -> str:
        lines: list[str] = []
        if self.missing:
            lines.append("Missing required M4-W16 inputs:")
            lines.extend(f"- {item}" for item in self.missing)
        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {item}" for item in self.warnings)
        return "\n".join(lines) if lines else "M4-W16 inputs are present."


def validate_artifacts(
    *,
    m4w14_root: Path,
    m4w15_root: Path,
    mgp6_input: Path,
) -> ArtifactStatus:
    missing: list[str] = []
    warnings: list[str] = []
    if not mgp6_input.exists():
        missing.append(str(mgp6_input))
    for alias in SYSTEM_ALIASES:
        report_path = m4w14_root / alias / "mgp6_report.json"
        if not report_path.exists():
            missing.append(str(report_path))
            continue
        report = _read_json(report_path)
        if int(report.get("n_scenarios") or 0) < 60:
            warnings.append(
                f"{report_path} has n_scenarios={report.get('n_scenarios')}, expected 60"
            )
    controller_log = m4w14_root / "controller" / "action_log.jsonl"
    if not controller_log.exists():
        missing.append(str(controller_log))
    sweep_reports = sorted((m4w15_root / "sweep").glob("threshold_*/report.json"))
    if len(sweep_reports) != 21:
        missing.append(
            f"{m4w15_root / 'sweep'}/threshold_*/report.json (found {len(sweep_reports)}, expected 21)"
        )
    mgp6_logs = sorted((m4w15_root / "sweep").glob("threshold_*/mgp6/controller/action_log.jsonl"))
    long_logs = sorted(
        (m4w15_root / "sweep").glob("threshold_*/longmemeval/controller/action_log.jsonl")
    )
    if len(mgp6_logs) != 21:
        missing.append(
            f"{m4w15_root / 'sweep'}/threshold_*/mgp6/controller/action_log.jsonl "
            f"(found {len(mgp6_logs)}, expected 21)"
        )
    if len(long_logs) != 21:
        missing.append(
            f"{m4w15_root / 'sweep'}/threshold_*/longmemeval/controller/action_log.jsonl "
            f"(found {len(long_logs)}, expected 21)"
        )
    return ArtifactStatus(tuple(missing), tuple(warnings))


def run_m4w16(
    *,
    m4w14_root: Path,
    m4w15_root: Path,
    mgp6_input: Path,
    notes_dir: Path,
    out_dir: Path,
    run_logreg_on_fail: bool = False,
) -> dict[str, Any]:
    status = validate_artifacts(m4w14_root=m4w14_root, m4w15_root=m4w15_root, mgp6_input=mgp6_input)
    if not status.ok:
        raise FileNotFoundError(status.format())

    notes_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    scenarios = _load_scenarios(mgp6_input)
    reports = {
        alias: _read_json(m4w14_root / alias / "mgp6_report.json") for alias in SYSTEM_ALIASES
    }
    controller_report = reports["controller"]
    controller_logs = _logs_by_session(_read_jsonl(m4w14_root / "controller" / "action_log.jsonl"))

    qualitative_md = render_qualitative_markdown(
        controller_report=controller_report,
        controller_logs=controller_logs,
        scenarios=scenarios,
    )
    (notes_dir / "m4w16_qualitative.md").write_text(qualitative_md, encoding="utf-8")

    pattern_audit = audit_patterns(reports)
    threshold_md = render_threshold_validation_markdown(
        controller_report, controller_logs, pattern_audit
    )
    (notes_dir / "m4w16_threshold_validation.md").write_text(threshold_md, encoding="utf-8")
    (out_dir / "pattern_audit.json").write_text(
        json.dumps(pattern_audit, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    taxonomy_rows = build_error_taxonomy(
        controller_report=controller_report,
        controller_logs=controller_logs,
        scenarios=scenarios,
    )
    write_error_taxonomy(out_dir / "error_taxonomy.csv", taxonomy_rows)

    g3 = decide_g3(reports)
    logreg = None
    if g3["decision"] == "FAIL" and run_logreg_on_fail:
        logreg = logistic_regression_comparator(controller_report, controller_logs)
        (out_dir / "logreg_comparator.json").write_text(
            json.dumps(logreg, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    g3_md = render_g3_markdown(g3, pattern_audit, logreg=logreg)
    (notes_dir / "G3_gate_decision.md").write_text(g3_md, encoding="utf-8")
    return {
        "qualitative_path": str(notes_dir / "m4w16_qualitative.md"),
        "threshold_validation_path": str(notes_dir / "m4w16_threshold_validation.md"),
        "gate_decision_path": str(notes_dir / "G3_gate_decision.md"),
        "taxonomy_path": str(out_dir / "error_taxonomy.csv"),
        "pattern_audit_path": str(out_dir / "pattern_audit.json"),
        "g3": g3,
        "n_taxonomy_rows": len(taxonomy_rows),
    }


def render_qualitative_markdown(
    *,
    controller_report: dict[str, Any],
    controller_logs: dict[str, list[dict[str, Any]]],
    scenarios: dict[str, dict[str, Any]],
    n_each: int = 10,
) -> str:
    predictions = list(controller_report.get("predictions") or [])
    wins = [row for row in predictions if bool(row.get("correct_action"))]
    losses = [row for row in predictions if not bool(row.get("correct_action"))]
    selected_wins = wins[:n_each]
    selected_losses = losses[:n_each]

    lines = [
        "# M4-W16 Qualitative Sanity Checks",
        "",
        "Source: controller MGP-6 predictions and controller `action_log.jsonl` rows generated by real Ollama runs.",
        "",
        f"- Wins selected: {len(selected_wins)} / {n_each}",
        f"- Losses selected: {len(selected_losses)} / {n_each}",
    ]
    if len(selected_wins) < n_each or len(selected_losses) < n_each:
        lines.append(
            "- Coverage warning: fewer than 10 wins or losses were available in the controller report."
        )
    lines.extend(["", "## Controller Wins"])
    for idx, row in enumerate(selected_wins, start=1):
        lines.extend(_walkthrough_lines(idx, row, controller_logs, scenarios, outcome="win"))
    lines.extend(["", "## Controller Losses"])
    for idx, row in enumerate(selected_losses, start=1):
        lines.extend(_walkthrough_lines(idx, row, controller_logs, scenarios, outcome="loss"))
    return "\n".join(lines) + "\n"


def audit_patterns(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    controller = reports["controller"]
    predictions = list(controller.get("predictions") or [])
    by_type: dict[str, list[dict[str, Any]]] = {scenario_type: [] for scenario_type in MGP6_TYPES}
    for row in predictions:
        by_type.setdefault(str(row.get("scenario_type")), []).append(row)

    t5_t6: dict[str, Any] = {}
    for scenario_type in ("T5", "T6"):
        rows = by_type.get(scenario_type, [])
        abstains = sum(1 for row in rows if _action(row.get("predicted_action")) == "ABSTAIN")
        t5_t6[scenario_type] = {
            "n": len(rows),
            "abstain": abstains,
            "always_abstain": bool(rows) and abstains == len(rows),
        }

    t4_scores = {}
    for alias, report in reports.items():
        score = ((report.get("per_type") or {}).get("T4") or {}).get("action_accuracy")
        t4_scores[alias] = score
    max_t4 = max((score for score in t4_scores.values() if score is not None), default=None)
    t4_winners = [
        alias
        for alias, score in t4_scores.items()
        if score is not None and max_t4 is not None and math.isclose(float(score), float(max_t4))
    ]
    baseline_always_win_t4 = [
        alias
        for alias, score in t4_scores.items()
        if alias != "controller" and score is not None and math.isclose(float(score), 1.0)
    ]

    threshold_ordering = controller.get("threshold_ordering") or {}
    per_type_accuracy = {
        scenario_type: ((controller.get("per_type") or {}).get(scenario_type) or {}).get(
            "action_accuracy"
        )
        for scenario_type in MGP6_TYPES
    }
    return {
        "controller_t5_t6_abstain": t5_t6,
        "t4_action_accuracy_by_system": t4_scores,
        "t4_winners": t4_winners,
        "baseline_always_win_t4": baseline_always_win_t4,
        "threshold_ordering": threshold_ordering,
        "controller_per_type_accuracy": per_type_accuracy,
        "suspicious": {
            "controller_always_abstains_on_t5_or_t6": any(
                item["always_abstain"] for item in t5_t6.values()
            ),
            "baseline_always_wins_t4": bool(baseline_always_win_t4),
            "threshold_ordering_refuted": threshold_ordering.get("confirmed") is False,
        },
    }


def render_threshold_validation_markdown(
    controller_report: dict[str, Any],
    controller_logs: dict[str, list[dict[str, Any]]],
    pattern_audit: dict[str, Any],
) -> str:
    ordering = controller_report.get("threshold_ordering") or {}
    empirical = ordering.get("mean_theta_sup_by_candidate_type") or {}
    fitted = _fitted_thresholds_from_logs(controller_logs)
    confirmed = _ordered(empirical)

    lines = [
        "# M4-W16 Threshold Validation",
        "",
        "Hypothesis: `theta_sup[stable_pref] > theta_sup[episodic_fact] > theta_sup[transient_pref]`.",
        "",
        "## M4-W14 Breakdown",
        "",
        "| Candidate type | Mean theta_sup | Errors | n |",
        "|---|---:|---:|---:|",
    ]
    errors = ordering.get("errors_by_candidate_type") or {}
    totals = ordering.get("n_by_candidate_type") or {}
    for memory_type in ("stable_pref", "episodic_fact", "transient_pref"):
        lines.append(
            f"| `{memory_type}` | {_fmt_float(empirical.get(memory_type))} | "
            f"{errors.get(memory_type, 0)} | {totals.get(memory_type, 0)} |"
        )
    lines.extend(
        [
            "",
            "## Action Log Thresholds",
            "",
            "| Candidate type | Unique theta_sup values | Min | Max | n decisions |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for memory_type in ("stable_pref", "episodic_fact", "transient_pref"):
        item = fitted.get(memory_type, {})
        unique = ", ".join(_fmt_float(v) for v in item.get("unique", [])) or "n/a"
        lines.append(
            f"| `{memory_type}` | {unique} | {_fmt_float(item.get('min'))} | "
            f"{_fmt_float(item.get('max'))} | {item.get('n', 0)} |"
        )
    lines.extend(
        [
            "",
            f"Conclusion: {'validated' if confirmed else 'refuted_or_insufficient'} "
            f"(`threshold_ordering.empirical_status={ordering.get('empirical_status')}`).",
            "",
            "## Pattern Audit",
            "",
            f"- Controller T5/T6 abstain check: {pattern_audit['controller_t5_t6_abstain']}",
            f"- T4 winners: {pattern_audit['t4_winners']}",
            f"- Suspicious flags: {pattern_audit['suspicious']}",
        ]
    )
    return "\n".join(lines) + "\n"


def decide_g3(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    controller = reports["controller"]
    naive = reports["b4"]
    rows = []
    passing_types = []
    for scenario_type in MGP6_TYPES:
        controller_score = ((controller.get("per_type") or {}).get(scenario_type) or {}).get(
            "action_accuracy"
        )
        naive_score = ((naive.get("per_type") or {}).get(scenario_type) or {}).get(
            "action_accuracy"
        )
        delta = (
            None
            if controller_score is None or naive_score is None
            else float(controller_score) - float(naive_score)
        )
        passes = delta is not None and delta >= 0.0
        if passes:
            passing_types.append(scenario_type)
        rows.append(
            {
                "type": scenario_type,
                "controller": controller_score,
                "naive_overwrite": naive_score,
                "delta": delta,
                "passes": passes,
            }
        )
    decision = "PASS" if passing_types else "FAIL"
    return {
        "decision": decision,
        "pass_condition": "controller >= naive-overwrite on revision correctness for at least one MGP-6 type",
        "passing_types": passing_types,
        "per_type": rows,
    }


def render_g3_markdown(
    g3: dict[str, Any],
    pattern_audit: dict[str, Any],
    *,
    logreg: dict[str, Any] | None = None,
) -> str:
    lines = [
        "# G3 Gate Decision",
        "",
        f"Decision: **{g3['decision']}**",
        "",
        f"Pass rule: {g3['pass_condition']}.",
        "",
        "| MGP-6 type | Controller | Naive overwrite | Delta | Passes |",
        "|---|---:|---:|---:|---|",
    ]
    for row in g3["per_type"]:
        lines.append(
            f"| {row['type']} | {_fmt_pct(row['controller'])} | {_fmt_pct(row['naive_overwrite'])} | "
            f"{_fmt_signed_pct(row['delta'])} | {'yes' if row['passes'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            f"Passing types: {', '.join(g3['passing_types']) if g3['passing_types'] else 'none'}.",
            "",
            "## Pattern Audit Summary",
            "",
            f"- T5/T6 abstain: {pattern_audit['controller_t5_t6_abstain']}",
            f"- T4 winners: {pattern_audit['t4_winners']}",
            f"- Suspicious flags: {pattern_audit['suspicious']}",
        ]
    )
    if g3["decision"] == "FAIL":
        lines.extend(
            [
                "",
                "## Fail Action",
                "",
                "G3 failed. Re-examine feature weights, try logistic regression over the same features, "
                "or cut one ablation before retuning the controller.",
            ]
        )
        if logreg is None:
            lines.append("Logistic-regression comparator was not run in this invocation.")
        else:
            lines.append(
                f"Logistic-regression comparator overall accuracy: {_fmt_pct(logreg['overall_accuracy'])} "
                f"over n={logreg['n']}."
            )
    else:
        lines.extend(
            [
                "",
                "## Closeout",
                "",
                "G3 passes. The Month 4 closeout tag can be created after the artifacts are reviewed.",
            ]
        )
    return "\n".join(lines) + "\n"


def build_error_taxonomy(
    *,
    controller_report: dict[str, Any],
    controller_logs: dict[str, list[dict[str, Any]]],
    scenarios: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for pred in controller_report.get("predictions") or []:
        if bool(pred.get("correct_action")) and bool(pred.get("state_correct")):
            continue
        scenario_id = str(pred["scenario_id"])
        scenario = scenarios.get(scenario_id, {})
        logs = controller_logs.get(scenario_id, [])
        primary_log = logs[0] if logs else {}
        label, evidence = _classify_error(pred, logs, scenario)
        rows.append(
            {
                "scenario_id": scenario_id,
                "scenario_type": pred.get("scenario_type"),
                "gold_action": pred.get("gold_action"),
                "predicted_action": pred.get("predicted_action"),
                "state_correct": pred.get("state_correct"),
                "taxonomy": label,
                "evidence": evidence,
                "candidate_text": primary_log.get("candidate_text"),
                "candidate_type": primary_log.get("candidate_type"),
                "feature_r": primary_log.get("feature_r"),
                "s_rev": primary_log.get("s_rev"),
                "s_abs": primary_log.get("s_abs"),
                "theta_sup": primary_log.get("theta_sup"),
                "theta_abs": primary_log.get("theta_abs"),
                "rationale": primary_log.get("rationale"),
                "rationale_notes": scenario.get("rationale_notes"),
            }
        )
    return rows


def write_error_taxonomy(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "scenario_id",
        "scenario_type",
        "gold_action",
        "predicted_action",
        "state_correct",
        "taxonomy",
        "evidence",
        "candidate_text",
        "candidate_type",
        "feature_r",
        "s_rev",
        "s_abs",
        "theta_sup",
        "theta_abs",
        "rationale",
        "rationale_notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def logistic_regression_comparator(
    controller_report: dict[str, Any],
    controller_logs: dict[str, list[dict[str, Any]]],
    *,
    seed: int = 0,
    folds: int = 5,
    epochs: int = 350,
    lr: float = 0.15,
    l2: float = 0.001,
) -> dict[str, Any]:
    examples = []
    for pred in controller_report.get("predictions") or []:
        logs = controller_logs.get(str(pred["scenario_id"]), [])
        if not logs:
            continue
        row = logs[0]
        if any(row.get(column) is None for column in FEATURE_COLUMNS):
            continue
        examples.append(
            {
                "scenario_id": pred["scenario_id"],
                "scenario_type": pred["scenario_type"],
                "x": [float(row[column]) for column in FEATURE_COLUMNS],
                "y": _action(pred["gold_action"]),
            }
        )
    if len(examples) < folds:
        return {"n": len(examples), "overall_accuracy": 0.0, "error": "not_enough_examples"}

    rng = random.Random(seed)
    indices = list(range(len(examples)))
    rng.shuffle(indices)
    predictions: list[tuple[str, str, str]] = []
    for fold in range(folds):
        test_indices = [idx for pos, idx in enumerate(indices) if pos % folds == fold]
        train_indices = [idx for idx in indices if idx not in test_indices]
        train = [examples[idx] for idx in train_indices]
        test = [examples[idx] for idx in test_indices]
        model = _fit_softmax(
            [item["x"] for item in train],
            [item["y"] for item in train],
            epochs=epochs,
            lr=lr,
            l2=l2,
        )
        for item in test:
            pred_action = _predict_softmax(model, item["x"])
            predictions.append((item["scenario_type"], item["y"], pred_action))

    correct = sum(1 for _typ, gold, pred in predictions if gold == pred)
    per_type: dict[str, dict[str, Any]] = {}
    for scenario_type in MGP6_TYPES:
        subset = [(gold, pred) for typ, gold, pred in predictions if typ == scenario_type]
        per_type[scenario_type] = {
            "n": len(subset),
            "accuracy": 0.0
            if not subset
            else sum(1 for gold, pred in subset if gold == pred) / len(subset),
        }
    return {
        "n": len(predictions),
        "overall_accuracy": 0.0 if not predictions else correct / len(predictions),
        "per_type": per_type,
        "features": list(FEATURE_COLUMNS),
        "folds": folds,
    }


def _walkthrough_lines(
    idx: int,
    row: dict[str, Any],
    logs_by_session: dict[str, list[dict[str, Any]]],
    scenarios: dict[str, dict[str, Any]],
    *,
    outcome: str,
) -> list[str]:
    scenario_id = str(row["scenario_id"])
    scenario = scenarios.get(scenario_id, {})
    logs = logs_by_session.get(scenario_id, [])
    checks = [_score_check(log) for log in logs]
    legible = all(_rationale_legible(log) for log in logs) if logs else False
    score_ok = all(item["matches"] for item in checks) if checks else False
    lines = [
        "",
        f"### {outcome.title()} {idx}: `{scenario_id}` ({row.get('scenario_type')})",
        "",
        f"- Gold/predicted: `{row.get('gold_action')}` / `{row.get('predicted_action')}`; "
        f"state_correct={row.get('state_correct')}.",
        f"- Perturbation: {scenario.get('perturbation_event', 'n/a')}",
        f"- Rationale note: {scenario.get('rationale_notes', 'n/a')}",
        f"- Checks: rationale_legible={'yes' if legible else 'no'}; "
        f"score_action_consistent={'yes' if score_ok else 'no'}.",
    ]
    if not logs:
        lines.append("- No action_log rows found for this scenario.")
        return lines
    for log, check in zip(logs, checks, strict=True):
        lines.append(
            "- Log row: "
            f"action=`{_action(log.get('action'))}`, candidate_type=`{log.get('candidate_type')}`, "
            f"candidate={log.get('candidate_text')!r}, "
            f"S_rev={_fmt_float(log.get('s_rev'))}, S_abs={_fmt_float(log.get('s_abs'))}, "
            f"theta_sup={_fmt_float(log.get('theta_sup'))}, theta_abs={_fmt_float(log.get('theta_abs'))}, "
            f"feature_r={_fmt_float(log.get('feature_r'))}, inferred=`{check['inferred']}`."
        )
        lines.append(f"  Rationale: {log.get('rationale')}")
    return lines


def _classify_error(
    pred: dict[str, Any],
    logs: list[dict[str, Any]],
    scenario: dict[str, Any],
) -> tuple[str, str]:
    if not logs:
        return (
            "extraction_error",
            "no action_log row; likely no candidate made it into the decision path",
        )
    primary = logs[0]
    candidate_text = str(primary.get("candidate_text") or "")
    if not candidate_text or candidate_text.startswith("(no extractable"):
        return "extraction_error", "extractor emitted no usable memory candidate"
    initial_type = None
    if scenario.get("initial_memory_state"):
        initial_type = scenario["initial_memory_state"][0].get("type")
    if (
        primary.get("candidate_type") not in {initial_type, None}
        and pred.get("gold_action") == "SUPERSEDE"
    ):
        return (
            "extraction_error",
            "candidate type differs from the memory slot needed for supersession",
        )

    gold = _action(pred.get("gold_action"))
    predicted = _action(pred.get("predicted_action"))
    any_negative_relation = any(float(log.get("feature_r") or 0.0) < 0.0 for log in logs)
    any_high_abs = any(_float(log.get("s_abs")) > _float(log.get("theta_abs")) for log in logs)
    any_sup_ready = any(
        _float(log.get("s_rev")) > _float(log.get("theta_sup"))
        and float(log.get("feature_r") or 0.0) < 0.0
        for log in logs
    )
    if gold == "SUPERSEDE" and not any_negative_relation:
        return (
            "classifier_error",
            "gold requires supersession but relation feature is not contradictory",
        )
    if gold == "SUPERSEDE" and predicted == "ABSTAIN" and any_high_abs:
        return "action_error", "relation supports supersession but abstain score crossed theta_abs"
    if gold == "SUPERSEDE" and not any_sup_ready:
        return "action_error", "relation is contradictory but S_rev did not clear theta_sup"
    if gold == "ABSTAIN" and predicted != "ABSTAIN":
        if any_high_abs:
            return "action_error", "abstain score cleared theta_abs but committed action was chosen"
        return "extraction_error", "ambiguous/noisy scenario produced a committed candidate"
    if gold == "KEEP" and predicted == "SUPERSEDE":
        if any_negative_relation:
            return "classifier_error", "keep case was treated as contradiction"
        return "action_error", "policy committed supersession without a contradictory relation"
    if gold == "KEEP" and predicted == "ABSTAIN":
        return "action_error", "keep case was blocked by abstain threshold"
    return (
        "action_error",
        "extractor/classifier evidence was not enough to justify the final action",
    )


def _score_check(log: dict[str, Any]) -> dict[str, Any]:
    inferred = _infer_action_from_scores(log)
    return {"inferred": inferred, "matches": inferred == _action(log.get("action"))}


def _infer_action_from_scores(log: dict[str, Any]) -> str:
    if _float(log.get("s_abs")) > _float(log.get("theta_abs")):
        return "ABSTAIN"
    if (
        _float(log.get("s_rev")) > _float(log.get("theta_sup"))
        and _float(log.get("feature_r")) < 0.0
    ):
        return "SUPERSEDE"
    return "KEEP"


def _rationale_legible(log: dict[str, Any]) -> bool:
    rationale = str(log.get("rationale") or "")
    if not rationale:
        return False
    action = _action(log.get("action")).lower()
    return "S_rev" in rationale and "S_abs" in rationale and action in rationale.lower()


def _fitted_thresholds_from_logs(
    logs_by_session: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[float]] = {}
    for logs in logs_by_session.values():
        for row in logs:
            memory_type = row.get("candidate_type")
            theta = row.get("theta_sup")
            if memory_type is None or theta is None:
                continue
            buckets.setdefault(str(memory_type), []).append(float(theta))
    out: dict[str, dict[str, Any]] = {}
    for memory_type, values in sorted(buckets.items()):
        out[memory_type] = {
            "n": len(values),
            "min": min(values),
            "max": max(values),
            "unique": sorted(set(values)),
        }
    return out


def _ordered(values: dict[str, Any]) -> bool:
    try:
        return (
            float(values["stable_pref"])
            > float(values["episodic_fact"])
            > float(values["transient_pref"])
        )
    except (KeyError, TypeError, ValueError):
        return False


def _fit_softmax(
    raw_x: list[list[float]],
    y: list[str],
    *,
    epochs: int,
    lr: float,
    l2: float,
) -> dict[str, Any]:
    means, scales = _standardizer(raw_x)
    x = [[*_standardize(row, means, scales), 1.0] for row in raw_x]
    labels = list(ACTIONS)
    label_to_idx = {label: idx for idx, label in enumerate(labels)}
    width = len(x[0])
    weights = [[0.0 for _ in range(width)] for _ in labels]
    for _epoch in range(epochs):
        grad = [[0.0 for _ in range(width)] for _ in labels]
        for row, gold in zip(x, y, strict=True):
            probs = _softmax(
                [
                    sum(w * v for w, v in zip(weights[k], row, strict=True))
                    for k in range(len(labels))
                ]
            )
            gold_idx = label_to_idx[gold]
            for k in range(len(labels)):
                diff = probs[k] - (1.0 if k == gold_idx else 0.0)
                for j, value in enumerate(row):
                    grad[k][j] += diff * value / len(x)
        for k in range(len(labels)):
            for j in range(width - 1):
                grad[k][j] += l2 * weights[k][j]
            for j in range(width):
                weights[k][j] -= lr * grad[k][j]
    return {"weights": weights, "means": means, "scales": scales, "labels": labels}


def _predict_softmax(model: dict[str, Any], raw_x: list[float]) -> str:
    x = [*_standardize(raw_x, model["means"], model["scales"]), 1.0]
    scores = [sum(w * v for w, v in zip(row, x, strict=True)) for row in model["weights"]]
    return str(model["labels"][max(range(len(scores)), key=lambda idx: scores[idx])])


def _standardizer(rows: list[list[float]]) -> tuple[list[float], list[float]]:
    width = len(rows[0])
    means = [sum(row[j] for row in rows) / len(rows) for j in range(width)]
    scales = []
    for j in range(width):
        variance = sum((row[j] - means[j]) ** 2 for row in rows) / len(rows)
        scales.append(math.sqrt(variance) or 1.0)
    return means, scales


def _standardize(row: list[float], means: list[float], scales: list[float]) -> list[float]:
    return [(value - mean) / scale for value, mean, scale in zip(row, means, scales, strict=True)]


def _softmax(scores: list[float]) -> list[float]:
    offset = max(scores)
    exps = [math.exp(score - offset) for score in scores]
    total = sum(exps)
    return [value / total for value in exps]


def _load_scenarios(path: Path) -> dict[str, dict[str, Any]]:
    return {row["scenario_id"]: row for row in _read_jsonl(path)}


def _logs_by_session(rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row.get("session_id")), []).append(row)
    return out


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _action(value: Any) -> str:
    text = str(value or "").strip().upper()
    mapping = {
        "KEEP": "KEEP",
        "KEPT": "KEEP",
        "SUPERSEDE": "SUPERSEDE",
        "SUPERSEDED": "SUPERSEDE",
        "ABSTAIN": "ABSTAIN",
        "ABSTAINED": "ABSTAIN",
    }
    return mapping.get(text, text)


def _float(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _fmt_float(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _fmt_signed_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:+.1f} pp"
