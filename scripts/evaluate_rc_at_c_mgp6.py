"""Replay MGP-6 controller action logs into an RC@C threshold sweep.

This is intentionally model-free: it uses the completed M4-W14 controller
action log, recomputes the action rule under a grid of theta_abs overrides, and
writes a coverage/correctness curve. No synthetic predictions are introduced.
"""

from __future__ import annotations

import argparse
import csv
import json
import struct
import sys
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.eval.m4w15 import compute_rc_at_c, threshold_values  # noqa: E402
from ask.eval.mgp6_schema import load_mgp6_jsonl  # noqa: E402


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _action_at_threshold(row: dict[str, Any], theta_abs: float) -> str:
    s_abs = float(row["s_abs"])
    s_rev = float(row["s_rev"])
    theta_sup = float(row["theta_sup"])
    relation_update = max(0.0, -float(row["feature_r"]))
    if s_abs > theta_abs:
        return "ABSTAIN"
    if s_rev > theta_sup and relation_update > 0.0:
        return "SUPERSEDE"
    return "KEEP"


def _threshold_predictions(
    action_rows: list[dict[str, Any]],
    gold_by_id: dict[str, str],
    theta_abs: float,
) -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": row["session_id"],
            "predicted_action": _action_at_threshold(row, theta_abs),
            "gold_action": gold_by_id[row["session_id"]],
        }
        for row in action_rows
    ]


def _default_predictions(path: Path) -> list[dict[str, Any]]:
    return _read_jsonl(path)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "threshold",
                "n_total",
                "n_committed",
                "coverage",
                "revision_correctness",
                "revision_correctness_ci_low",
                "revision_correctness_ci_high",
            ],
        )
        writer.writeheader()
        for row in rows:
            mgp6 = row["mgp6"]
            ci = mgp6["revision_correctness_ci"]
            writer.writerow(
                {
                    "threshold": row["threshold"],
                    "n_total": mgp6["n_total"],
                    "n_committed": mgp6["n_committed"],
                    "coverage": mgp6["coverage"],
                    "revision_correctness": mgp6["revision_correctness"],
                    "revision_correctness_ci_low": ci[0],
                    "revision_correctness_ci_high": ci[1],
                }
            )


def _plot_points(rows: list[dict[str, Any]]) -> list[tuple[float, float, str]]:
    points = []
    for row in rows:
        points.append(
            (
                float(row["mgp6"]["coverage"]),
                float(row["mgp6"]["revision_correctness"]),
                f"{float(row['threshold']):.2f}",
            )
        )
    return points


def _write_png(path: Path, points: list[tuple[float, float, str]]) -> None:
    width, height = 900, 620
    margin_left, margin_right, margin_top, margin_bottom = 90, 40, 45, 85
    pixels = bytearray([255, 255, 255] * width * height)

    def put(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            idx = (y * width + x) * 3
            pixels[idx : idx + 3] = bytes(color)

    def line(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            put(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius**2:
                    put(x, y, color)

    def sx(value: float) -> int:
        span = width - margin_left - margin_right
        return margin_left + round(max(0.0, min(1.0, value)) * span)

    def sy(value: float) -> int:
        span = height - margin_top - margin_bottom
        return height - margin_bottom - round(max(0.0, min(1.0, value)) * span)

    axis = (40, 40, 40)
    grid = (220, 220, 220)
    curve = (20, 95, 170)
    for tick in [i / 10 for i in range(11)]:
        x = sx(tick)
        y = sy(tick)
        line(x, margin_top, x, height - margin_bottom, grid)
        line(margin_left, y, width - margin_right, y, grid)
    line(margin_left, margin_top, margin_left, height - margin_bottom, axis)
    line(margin_left, height - margin_bottom, width - margin_right, height - margin_bottom, axis)

    coords = [(sx(x), sy(y)) for x, y, _label in points]
    for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
        line(x0, y0, x1, y1, curve)
    for x, y in coords:
        circle(x, y, 5, curve)

    raw = b"".join(
        b"\x00" + bytes(pixels[y * width * 3 : (y + 1) * width * 3]) for y in range(height)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _write_pdf(path: Path, points: list[tuple[float, float, str]]) -> None:
    width, height = 612, 420
    left, right, top, bottom = 70, 35, 35, 65

    def sx(value: float) -> float:
        return left + max(0.0, min(1.0, value)) * (width - left - right)

    def sy(value: float) -> float:
        return bottom + max(0.0, min(1.0, value)) * (height - top - bottom)

    commands = [
        "0.95 0.95 0.95 rg",
        f"{left} {bottom} {width - left - right} {height - top - bottom} re f",
        "0 0 0 RG 1 w",
        f"{left} {bottom} m {left} {height - top} l S",
        f"{left} {bottom} m {width - right} {bottom} l S",
        "0.08 0.37 0.67 RG 1.5 w",
    ]
    coords = [(sx(x), sy(y)) for x, y, _label in points]
    if coords:
        x0, y0 = coords[0]
        commands.append(f"{x0:.2f} {y0:.2f} m")
        for x, y in coords[1:]:
            commands.append(f"{x:.2f} {y:.2f} l")
        commands.append("S")
    for x, y in coords:
        commands.append(f"{x - 2.5:.2f} {y - 2.5:.2f} 5 5 re f")
    commands.extend(
        [
            "0 0 0 rg BT /F1 12 Tf 70 395 Td (M4-W15 MGP-6 RC@C Sweep) Tj ET",
            "BT /F1 10 Tf 235 22 Td (Coverage) Tj ET",
            "BT /F1 10 Tf 10 220 Td (Revision correctness) Tj ET",
        ]
    )
    stream = "\n".join(commands).encode("ascii")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
            f"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{idx} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode(
            "ascii"
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mgp6", type=Path, default=Path("data/mgp6_v1_seed0.jsonl"))
    parser.add_argument("--run-root", type=Path, default=Path("runs/m4w14"))
    parser.add_argument("--out", type=Path, default=Path("runs/m4w15"))
    parser.add_argument("--n-bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    scenarios = {row.scenario_id: row for row in load_mgp6_jsonl(args.mgp6)}
    gold_by_id = {scenario_id: row.gold_action for scenario_id, row in scenarios.items()}
    action_rows = _read_jsonl(args.run_root / "controller" / "action_log.jsonl")
    if len(action_rows) != len(scenarios):
        raise SystemExit(
            f"expected one controller action row per scenario; got {len(action_rows)} "
            f"for {len(scenarios)} scenarios"
        )

    source_manifest_path = args.run_root / "manifest.json"
    source_manifest: dict[str, Any] = {}
    if source_manifest_path.exists():
        source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_sanity_ok = source_manifest.get("sanity_ok") is True
    rechecked_sanity_path = args.run_root / "sanity_report_rechecked.json"
    if rechecked_sanity_path.exists():
        rechecked_sanity = json.loads(rechecked_sanity_path.read_text(encoding="utf-8"))
        source_sanity_ok = source_sanity_ok or rechecked_sanity.get("ok") is True
    source_tier = str(source_manifest.get("tier") or source_manifest.get("run_tier") or "unknown")
    source_is_final_candidate = (
        source_tier in {"final-candidate", "final"}
        and source_manifest.get("model_profile") == "thesis"
        and source_manifest.get("complete") is True
        and source_sanity_ok
    )
    tier = "final-candidate" if source_is_final_candidate else "development"
    thesis_use = (
        "final_candidate_pending_review"
        if source_is_final_candidate
        else f"development_replay_of_{source_tier}_source_NOT_for_final"
    )

    reports = []
    for theta in threshold_values():
        predictions = _threshold_predictions(action_rows, gold_by_id, theta)
        reports.append(
            {
                "threshold": round(theta, 2),
                "mgp6": compute_rc_at_c(
                    predictions,
                    n_bootstrap=args.n_bootstrap,
                    seed=args.seed + int(theta * 100),
                ),
            }
        )

    default_predictions = _default_predictions(args.run_root / "controller" / "predictions.jsonl")
    default_point = compute_rc_at_c(
        default_predictions,
        n_bootstrap=args.n_bootstrap,
        seed=args.seed,
    )

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "rc_at_c_report.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "source": "replayed_real_m4w14_controller_action_log",
                "mgp6": str(args.mgp6),
                "run_root": str(args.run_root),
                "n_bootstrap": args.n_bootstrap,
                "default_operating_point": default_point,
                "threshold_reports": reports,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _write_csv(args.out / "rc_at_c_sweep.csv", reports)
    points = _plot_points(reports)
    _write_png(args.out / "rc_at_c_curve.png", points)
    _write_pdf(args.out / "rc_at_c_curve.pdf", points)
    (args.out / "manifest.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "tier": tier,
                "run_tier": tier,
                "complete": True,
                "thesis_use": thesis_use,
                "source_run": str(args.run_root),
                "source_tier": source_tier,
                "input": str(args.mgp6),
                "method": "action_log_replay_threshold_sweep",
                "raw_turn_fallback": False,
                "judge_tier": "direct_label_state_comparison",
                "outputs": [
                    "rc_at_c_report.json",
                    "rc_at_c_sweep.csv",
                    "rc_at_c_curve.png",
                    "rc_at_c_curve.pdf",
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(f"[rc_at_c] wrote {args.out / 'rc_at_c_sweep.csv'}")
    print(f"[rc_at_c] wrote {args.out / 'rc_at_c_curve.png'}")
    print(f"[rc_at_c] wrote {args.out / 'rc_at_c_curve.pdf'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
