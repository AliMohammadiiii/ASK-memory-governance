"""M4-W15 RC@C and main-table aggregation utilities."""

from __future__ import annotations

import csv
import json
import random
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SYSTEM_ALIASES: tuple[str, ...] = ("b1", "b2", "b3", "b4", "controller")
SYSTEM_LABELS: dict[str, str] = {
    "b1": "B1",
    "b2": "B2",
    "b3": "B3",
    "b4": "B4",
    "controller": "Controller",
}
LONGMEMEVAL_COMPETENCIES: tuple[str, ...] = (
    "multi-session",
    "single-session-preference",
    "single-session-user",
    "single-session-assistant",
    "temporal-reasoning",
    "knowledge-update",
    "abstention",
)
MGP6_TYPES: tuple[str, ...] = ("T1", "T2", "T3", "T4", "T5", "T6")
MISSING = "MISSING"


@dataclass(frozen=True)
class PrerequisiteStatus:
    """Completeness check for the M4-W15 inputs."""

    missing: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.missing

    def format(self) -> str:
        if self.ok and not self.warnings:
            return "M4-W13 and M4-W14 prerequisites are present."
        lines: list[str] = []
        if self.missing:
            lines.append("Missing prerequisite artifacts:")
            lines.extend(f"- {item}" for item in self.missing)
        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {item}" for item in self.warnings)
        return "\n".join(lines)


def threshold_values() -> list[float]:
    """The M4-W15 theta_abs grid: 0.00, 0.05, ..., 1.00."""

    return [idx / 20 for idx in range(21)]


def threshold_dir_name(theta: float) -> str:
    return f"threshold_{theta:.2f}"


def validate_prerequisites(
    m4w13_root: Path,
    m4w14_root: Path,
    *,
    expected_mgp6_n: int = 60,
) -> PrerequisiteStatus:
    missing: list[str] = []
    warnings: list[str] = []
    manifest_path = m4w13_root / "manifest.json"
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        if manifest.get("slice_is_synthetic"):
            warnings.append(f"{manifest_path} marks the LongMemEval slice as synthetic")
    for alias in SYSTEM_ALIASES:
        long_report = m4w13_root / alias / "report.json"
        if not long_report.exists():
            missing.append(str(long_report))
        else:
            report = _read_json(long_report)
            if int(report.get("n_sessions") or 0) <= 0:
                warnings.append(f"{long_report} has n_sessions <= 0")
        mgp6_report = m4w14_root / alias / "mgp6_report.json"
        if not mgp6_report.exists():
            missing.append(str(mgp6_report))
        else:
            report = _read_json(mgp6_report)
            n_scenarios = int(report.get("n_scenarios") or 0)
            if n_scenarios < expected_mgp6_n:
                warnings.append(
                    f"{mgp6_report} has n_scenarios={n_scenarios}, expected {expected_mgp6_n}"
                )
    return PrerequisiteStatus(tuple(missing), tuple(warnings))


def compute_rc_at_c(
    predictions: Iterable[dict[str, Any]],
    *,
    n_bootstrap: int = 1000,
    seed: int = 0,
) -> dict[str, Any]:
    """Compute revision correctness at coverage over non-abstain decisions."""

    rows = list(predictions)
    committed = [row for row in rows if _prediction_action(row) != "ABSTAIN"]
    corrects = [_prediction_correct(row) for row in committed]
    coverage = 0.0 if not rows else len(committed) / len(rows)
    revision_correctness = 0.0 if not committed else sum(corrects) / len(committed)
    ci_low, ci_high = _bootstrap_mean_ci(corrects, n_bootstrap=n_bootstrap, seed=seed)
    return {
        "n_total": len(rows),
        "n_committed": len(committed),
        "coverage": coverage,
        "revision_correctness": revision_correctness,
        "revision_correctness_ci": [ci_low, ci_high],
    }


def assemble_threshold_report(
    threshold_dir: Path,
    *,
    threshold: float | None = None,
    n_bootstrap: int = 1000,
    seed: int = 0,
) -> dict[str, Any]:
    """Write ``threshold_dir/report.json`` from the MGP-6 and LongMemEval outputs."""

    threshold = _infer_threshold(threshold_dir) if threshold is None else threshold
    mgp6_report_path = _first_existing(
        (
            threshold_dir / "mgp6" / "controller" / "mgp6_report.json",
            threshold_dir / "controller" / "mgp6_report.json",
            threshold_dir / "mgp6_report.json",
        )
    )
    long_report_path = _first_existing(
        (
            threshold_dir / "longmemeval" / "controller" / "report.json",
            threshold_dir / "longmemeval" / "report.json",
            threshold_dir / "report.longmemeval.json",
        ),
        required=False,
    )
    assert mgp6_report_path is not None
    mgp6_report = _read_json(mgp6_report_path)
    predictions = _load_mgp6_predictions(threshold_dir, mgp6_report)
    rc_at_c = compute_rc_at_c(predictions, n_bootstrap=n_bootstrap, seed=seed)

    payload: dict[str, Any] = {
        "threshold": threshold,
        "mgp6": {
            "report_path": str(mgp6_report_path),
            "action_accuracy": mgp6_report.get("action_accuracy"),
            "action_accuracy_ci": mgp6_report.get("action_accuracy_ci"),
            **rc_at_c,
        },
    }
    if long_report_path is not None:
        long_report = _read_json(long_report_path)
        payload["longmemeval"] = {
            "report_path": str(long_report_path),
            "overall_accuracy": long_report.get("overall_accuracy"),
            "overall_ci": [
                long_report.get("overall_ci_low"),
                long_report.get("overall_ci_high"),
            ],
            "n_sessions": long_report.get("n_sessions"),
        }
    threshold_dir.mkdir(parents=True, exist_ok=True)
    (threshold_dir / "report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return payload


def load_threshold_reports(sweep_dir: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in sorted(sweep_dir.glob("threshold_*/report.json")):
        reports.append(_read_json(path))
    return sorted(reports, key=lambda row: float(row["threshold"]))


def plot_rc_curve(
    reports: list[dict[str, Any]],
    *,
    png_path: Path,
    pdf_path: Path,
) -> None:
    if not reports:
        raise ValueError("no threshold reports to plot")
    import matplotlib.pyplot as plt

    xs = [float(row["mgp6"]["coverage"]) for row in reports]
    ys = [float(row["mgp6"]["revision_correctness"]) for row in reports]
    labels = [float(row["threshold"]) for row in reports]

    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.plot(xs, ys, marker="o", linewidth=1.8)
    for x, y, theta in zip(xs, ys, labels, strict=True):
        if theta in {0.0, 0.5, 1.0}:
            ax.annotate(
                f"{theta:.2f}", (x, y), textcoords="offset points", xytext=(4, 5), fontsize=8
            )
    ax.set_xlabel("Coverage (non-abstain fraction)")
    ax.set_ylabel("Revision correctness on committed set")
    ax.set_title("M4-W15 RC@C Sweep")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(png_path, dpi=180)
    fig.savefig(pdf_path)
    plt.close(fig)


def build_main_table(
    *,
    m4w13_root: Path,
    m4w14_root: Path,
    markdown_path: Path,
    csv_path: Path,
    n_bootstrap: int = 1000,
    seed: int = 0,
) -> list[dict[str, str]]:
    rows = collect_main_table_rows(
        m4w13_root=m4w13_root,
        m4w14_root=m4w14_root,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_main_table_markdown(rows), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def collect_main_table_rows(
    *,
    m4w13_root: Path,
    m4w14_root: Path,
    n_bootstrap: int = 1000,
    seed: int = 0,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for idx, alias in enumerate(SYSTEM_ALIASES):
        row: dict[str, str] = {"System": SYSTEM_LABELS[alias]}
        row.update(_longmemeval_cells(m4w13_root / alias / "report.json"))
        row["SMRR"] = _format_cell(
            *_smrr_cell(m4w13_root / alias, n_bootstrap=n_bootstrap, seed=seed + idx)
        )
        row.update(_mgp6_cells(m4w14_root / alias / "mgp6_report.json"))
        rows.append(row)
    return rows


def render_main_table_markdown(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "# M4-W15 Main Results Table\n\nNo rows.\n"
    headers = list(rows[0])
    lines = [
        "# M4-W15 Main Results Table",
        "",
        "Cells are point estimates with 95% bootstrap CIs where available. "
        "SMRR is lower-is-better; all other cells are accuracy/rate percentages.",
        "",
        "|" + "|".join(headers) + "|",
        "|" + "|".join(["---"] + ["---:" for _ in headers[1:]]) + "|",
    ]
    for row in rows:
        lines.append("|" + "|".join(row.get(header, MISSING) for header in headers) + "|")
    return "\n".join(lines) + "\n"


def _longmemeval_cells(report_path: Path) -> dict[str, str]:
    cells = {f"LME {name}": MISSING for name in LONGMEMEVAL_COMPETENCIES}
    if not report_path.exists():
        return cells
    report = _read_json(report_path)
    by_name = {row["competency"]: row for row in report.get("rows", [])}
    for name in LONGMEMEVAL_COMPETENCIES:
        item = by_name.get(name)
        if item is None:
            continue
        cells[f"LME {name}"] = _format_cell(
            item.get("accuracy"),
            item.get("accuracy_ci_low"),
            item.get("accuracy_ci_high"),
        )
    return cells


def _mgp6_cells(report_path: Path) -> dict[str, str]:
    cells = {f"MGP-6 {name}": MISSING for name in MGP6_TYPES}
    cells.update(
        {
            "Revision correctness": MISSING,
            "Over-forgetting": MISSING,
            "Under-forgetting": MISSING,
        }
    )
    if not report_path.exists():
        return cells
    report = _read_json(report_path)
    per_type = report.get("per_type") or {}
    for name in MGP6_TYPES:
        item = per_type.get(name)
        if item is None:
            continue
        ci = item.get("action_accuracy_ci") or [None, None]
        cells[f"MGP-6 {name}"] = _format_cell(item.get("action_accuracy"), ci[0], ci[1])
    action_ci = report.get("action_accuracy_ci") or [None, None]
    over_ci = report.get("over_forgetting_ci") or [None, None]
    under_ci = report.get("under_forgetting_ci") or [None, None]
    cells["Revision correctness"] = _format_cell(
        report.get("action_accuracy"), action_ci[0], action_ci[1]
    )
    cells["Over-forgetting"] = _format_cell(
        report.get("over_forgetting_rate"), over_ci[0], over_ci[1]
    )
    cells["Under-forgetting"] = _format_cell(
        report.get("under_forgetting_rate"), under_ci[0], under_ci[1]
    )
    return cells


def _smrr_cell(
    run_dir: Path, *, n_bootstrap: int, seed: int
) -> tuple[float | None, float | None, float | None]:
    rows = _read_jsonl(run_dir / "predictions.jsonl")
    if not rows:
        rows = _read_jsonl(run_dir / "answers.jsonl")
    pairs: list[tuple[int, int]] = []
    for row in rows:
        extras = row.get("extras") or {}
        if extras.get("smrr_status") == "not_computed_longmemeval_lacks_gold_supersession":
            continue
        denominator = int(
            extras.get("smrr_denominator", len(extras.get("retrieval_session_ids") or [])) or 0
        )
        stale = int(extras.get("stale_retrieval_count") or 0)
        pairs.append((stale, denominator))
    denominator_total = sum(denominator for _stale, denominator in pairs)
    if denominator_total == 0:
        return None, None, None
    point = sum(stale for stale, _denominator in pairs) / denominator_total
    low, high = _bootstrap_ratio_ci(pairs, n_bootstrap=n_bootstrap, seed=seed)
    return point, low, high


def _load_mgp6_predictions(threshold_dir: Path, report: dict[str, Any]) -> list[dict[str, Any]]:
    path = _first_existing(
        (
            threshold_dir / "mgp6" / "controller" / "predictions.jsonl",
            threshold_dir / "controller" / "predictions.jsonl",
            threshold_dir / "predictions.jsonl",
        ),
        required=False,
    )
    if path is not None:
        return _read_jsonl(path)
    return list(report.get("predictions") or [])


def _prediction_action(row: dict[str, Any]) -> str:
    return str(row.get("predicted_action") or "").upper()


def _prediction_correct(row: dict[str, Any]) -> bool:
    if "correct_action" in row:
        return bool(row["correct_action"])
    return _prediction_action(row) == str(row.get("gold_action") or "").upper()


def _format_cell(
    value: Any,
    ci_low: Any = None,
    ci_high: Any = None,
    *,
    decimals: int = 1,
) -> str:
    if value is None:
        return MISSING
    value_f = float(value)
    low_f = value_f if ci_low is None else float(ci_low)
    high_f = value_f if ci_high is None else float(ci_high)
    return (
        f"{value_f * 100:.{decimals}f}% [{low_f * 100:.{decimals}f}%, {high_f * 100:.{decimals}f}%]"
    )


def _bootstrap_mean_ci(values: list[bool], *, n_bootstrap: int, seed: int) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        value = float(values[0])
        return value, value
    rng = random.Random(seed)
    means = []
    for _ in range(n_bootstrap):
        sample = [values[rng.randrange(len(values))] for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()
    return _percentile_bounds(means)


def _bootstrap_ratio_ci(
    pairs: list[tuple[int, int]],
    *,
    n_bootstrap: int,
    seed: int,
) -> tuple[float, float]:
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(n_bootstrap):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        denominator = sum(item[1] for item in sample)
        values.append(0.0 if denominator == 0 else sum(item[0] for item in sample) / denominator)
    values.sort()
    return _percentile_bounds(values)


def _percentile_bounds(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    lo_idx = max(0, min(len(values) - 1, int(0.025 * len(values))))
    hi_idx = max(0, min(len(values) - 1, int(0.975 * len(values)) - 1))
    return values[lo_idx], values[hi_idx]


def _infer_threshold(threshold_dir: Path) -> float:
    prefix = "threshold_"
    name = threshold_dir.name
    if not name.startswith(prefix):
        raise ValueError(f"cannot infer threshold from directory name: {threshold_dir}")
    return float(name[len(prefix) :])


def _first_existing(paths: Iterable[Path], *, required: bool = True) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    if required:
        joined = ", ".join(str(path) for path in paths)
        raise FileNotFoundError(f"none of these paths exist: {joined}")
    return None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
