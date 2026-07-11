"""Validation and audit helpers for M4-W13 run artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASELINE_ALIASES: tuple[str, ...] = ("b1", "b2", "b3", "b4", "controller")
ACTION_LOG_BASELINES = {"recency", "naive_overwrite", "controller"}
ACTION_LOG_ALIASES = {"b3", "b4", "controller"}
REQUIRED_JSONL_FILES: tuple[str, ...] = (
    "answers.jsonl",
    "predictions.jsonl",
    "judgments.jsonl",
)
OUTPUT_ARTIFACT_FILES: tuple[str, ...] = (
    "answers.jsonl",
    "predictions.jsonl",
    "judgments.jsonl",
    "action_log.jsonl",
    "extraction_trace.jsonl",
    "relation_trace.jsonl",
    "report.json",
    "results.md",
)


@dataclass
class RunValidation:
    run_dir: Path
    expected_rows: int | None
    report: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def context_prefix(
    *,
    stage: str | None = None,
    config_slug: str | None = None,
    system: str | None = None,
) -> str:
    parts = []
    if stage:
        parts.append(f"stage={stage}")
    if config_slug:
        parts.append(f"config={config_slug}")
    if system:
        parts.append(f"system={system}")
    return " ".join(parts) if parts else "run"


def format_issue(
    message: str,
    *,
    path: Path | None = None,
    stage: str | None = None,
    config_slug: str | None = None,
    system: str | None = None,
) -> str:
    prefix = context_prefix(stage=stage, config_slug=config_slug, system=system)
    if path is not None:
        return f"{prefix}: {path}: {message}"
    return f"{prefix}: {message}"


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    if not path.exists():
        return rows, errors
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_no}: invalid JSON: {exc.msg}")
                continue
            if not isinstance(row, dict):
                errors.append(f"line {line_no}: expected JSON object")
                continue
            rows.append(row)
    return rows, errors


def jsonl_count(path: Path) -> int:
    rows, _errors = load_jsonl(path)
    return len(rows)


def action_log_required(alias: str | None, baseline: str | None) -> bool:
    return (alias in ACTION_LOG_ALIASES) or (baseline in ACTION_LOG_BASELINES)


def required_jsonl_files(
    alias: str | None,
    baseline: str | None,
    *,
    require_action_log: bool | None = None,
) -> tuple[str, ...]:
    names = list(REQUIRED_JSONL_FILES)
    should_require_action = (
        action_log_required(alias, baseline)
        if require_action_log is None
        else require_action_log
    )
    if should_require_action:
        names.append("action_log.jsonl")
    return tuple(names)


def has_output_artifacts(run_dir: Path) -> bool:
    return any((run_dir / name).exists() for name in OUTPUT_ARTIFACT_FILES)


def telemetry(run_dir: Path) -> dict[str, Any]:
    answers, _errors = load_jsonl(run_dir / "predictions.jsonl")
    if not answers:
        answers, _errors = load_jsonl(run_dir / "answers.jsonl")

    stale = 0
    retrieved = 0
    leakage = 0
    prompt_tokens: list[float] = []
    latencies: list[float] = []
    for answer in answers:
        extras = answer.get("extras") or {}
        retrieval_session_ids = extras.get("retrieval_session_ids") or []
        if extras.get("smrr_status") == "not_computed_longmemeval_lacks_gold_supersession":
            pass
        else:
            retrieved += int(extras.get("smrr_denominator", len(retrieval_session_ids)))
            stale += int(extras.get("stale_retrieval_count", 0))
        if "current_session_leakage_count" in extras:
            leakage += int(extras.get("current_session_leakage_count") or 0)
        else:
            leakage += sum(1 for sid in retrieval_session_ids if sid == answer.get("session_id"))
        if answer.get("prompt_tokens") is not None:
            prompt_tokens.append(float(answer["prompt_tokens"]))
        if answer.get("latency_ms") is not None:
            latencies.append(float(answer["latency_ms"]))

    n_predictions = len(answers)
    return {
        "n_predictions": n_predictions,
        "retrieved_items": retrieved,
        "retrieved_avg": None if n_predictions == 0 else retrieved / n_predictions,
        "stale_retrieval_count": stale,
        "smrr": None if retrieved == 0 else stale / retrieved,
        "current_session_leakage_count": leakage,
        "mean_prompt_tokens": None if not prompt_tokens else sum(prompt_tokens) / len(prompt_tokens),
        "mean_latency_ms": None if not latencies else sum(latencies) / len(latencies),
    }


def validate_run_dir(
    run_dir: Path,
    *,
    expected_rows: int | None = None,
    stage: str | None = None,
    config_slug: str | None = None,
    system: str | None = None,
    baseline: str | None = None,
    require_action_log: bool | None = None,
) -> RunValidation:
    result = RunValidation(run_dir=run_dir, expected_rows=expected_rows)
    report_path = run_dir / "report.json"
    report = load_json(report_path)
    if report is None:
        result.errors.append(
            format_issue(
                "missing or invalid report.json",
                path=report_path,
                stage=stage,
                config_slug=config_slug,
                system=system,
            )
        )
        report = {}
    else:
        result.report = report

    inferred_baseline = baseline or str(report.get("baseline_name") or "")
    report_rows = int(report.get("n_sessions") or 0)
    row_target = expected_rows if expected_rows is not None else report_rows
    result.expected_rows = row_target

    if report and report_rows <= 0:
        result.errors.append(
            format_issue(
                f"report n_sessions must be positive, got {report_rows}",
                path=report_path,
                stage=stage,
                config_slug=config_slug,
                system=system,
            )
        )
    if report and row_target is not None and report_rows != row_target:
        result.errors.append(
            format_issue(
                f"report n_sessions {report_rows} != expected {row_target}",
                path=report_path,
                stage=stage,
                config_slug=config_slug,
                system=system,
            )
        )

    for name in required_jsonl_files(
        system,
        inferred_baseline,
        require_action_log=require_action_log,
    ):
        path = run_dir / name
        if not path.exists():
            result.errors.append(
                format_issue(
                    "required output file is missing",
                    path=path,
                    stage=stage,
                    config_slug=config_slug,
                    system=system,
                )
            )
            continue
        rows, row_errors = load_jsonl(path)
        for row_error in row_errors:
            result.errors.append(
                format_issue(
                    row_error,
                    path=path,
                    stage=stage,
                    config_slug=config_slug,
                    system=system,
                )
            )
        if not rows:
            result.errors.append(
                format_issue(
                    "required output file is empty",
                    path=path,
                    stage=stage,
                    config_slug=config_slug,
                    system=system,
                )
            )
        if name != "action_log.jsonl" and row_target is not None and len(rows) != row_target:
            result.errors.append(
                format_issue(
                    f"row count {len(rows)} != expected {row_target}",
                    path=path,
                    stage=stage,
                    config_slug=config_slug,
                    system=system,
                )
            )

    judgments, _errors = load_jsonl(run_dir / "judgments.jsonl")
    if judgments and report.get("overall_accuracy") is not None:
        judged_accuracy = sum(1 for row in judgments if bool(row.get("correct"))) / len(judgments)
        if abs(float(report["overall_accuracy"]) - judged_accuracy) > 1e-12:
            result.errors.append(
                format_issue(
                    f"report accuracy {report['overall_accuracy']} != judgments accuracy {judged_accuracy}",
                    path=report_path,
                    stage=stage,
                    config_slug=config_slug,
                    system=system,
                )
            )

    answers, _answer_errors = load_jsonl(run_dir / "answers.jsonl")
    predictions, _prediction_errors = load_jsonl(run_dir / "predictions.jsonl")
    if answers and predictions:
        answer_ids = [str(row.get("session_id")) for row in answers]
        prediction_ids = [str(row.get("session_id")) for row in predictions]
        if answer_ids != prediction_ids:
            result.errors.append(
                format_issue(
                    "answers.jsonl and predictions.jsonl session order differs",
                    stage=stage,
                    config_slug=config_slug,
                    system=system,
                )
            )

    run_telemetry = telemetry(run_dir)
    if run_telemetry["current_session_leakage_count"]:
        result.warnings.append(
            format_issue(
                f"current-session leakage count {run_telemetry['current_session_leakage_count']}",
                stage=stage,
                config_slug=config_slug,
                system=system,
            )
        )
    return result


_CONFIG_RE = re.compile(
    r"^tk(?P<top_k>\d+)-rk(?P<retrieval_k>\d+)-w(?P<neighbor_window>\d+)-"
    r"t(?P<extraction_tokens>\d+)-(?P<relation_tokens>\d+)$"
)


def parse_config_slug(slug: str) -> dict[str, int]:
    match = _CONFIG_RE.match(slug)
    if not match:
        raise ValueError(f"invalid M4-W13 config slug: {slug!r}")
    return {key: int(value) for key, value in match.groupdict().items()}


def correctness_matrix(config_runs: dict[str, Path]) -> dict[str, Any]:
    per_config: dict[str, dict[str, bool]] = {}
    questions: set[str] = set()
    for config, run_dir in sorted(config_runs.items()):
        judgments, _errors = load_jsonl(run_dir / "judgments.jsonl")
        rows = {str(row.get("session_id")): bool(row.get("correct")) for row in judgments}
        per_config[config] = rows
        questions.update(rows)

    matrix = []
    all_right = []
    all_wrong = []
    disagreements = []
    for session_id in sorted(questions):
        row = {
            config: values.get(session_id)
            for config, values in sorted(per_config.items())
        }
        present = [value for value in row.values() if value is not None]
        matrix.append({"session_id": session_id, "correct": row})
        if present and all(present):
            all_right.append(session_id)
        elif present and not any(present):
            all_wrong.append(session_id)
        elif len(set(present)) > 1:
            disagreements.append(session_id)

    return {
        "configs": sorted(per_config),
        "matrix": matrix,
        "all_right": all_right,
        "all_wrong": all_wrong,
        "disagreements": disagreements,
        "identical_correctness": not disagreements,
    }
