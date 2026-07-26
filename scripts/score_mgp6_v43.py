"""Score a public MGP-6 v4.3 train/dev prediction file.

This command deliberately requires public development labels and has no option
for hidden inputs or private gold. Hidden scoring remains a separately
authorized, local-private procedure.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ask.eval.mgp6_v43 import (  # noqa: E402
    VALID_ACTIONS,
    load_predictions,
    load_public_records,
    score_actions,
)


def _telemetry(raw_response_path: Path | None, manifest_path: Path | None) -> dict[str, Any]:
    if raw_response_path is None:
        return {"available": False}
    rows = [
        json.loads(line)
        for line in raw_response_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    latencies = [float(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None]
    payload: dict[str, Any] = {
        "available": True,
        "raw_response_count": len(rows),
        "invalid_response_count": sum(not bool(row.get("valid_action")) for row in rows),
        "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in rows),
        "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in rows),
    }
    if latencies:
        ordered = sorted(latencies)
        payload["latency_ms"] = {
            "mean": statistics.mean(latencies),
            "median": statistics.median(latencies),
            "p95": ordered[int(0.95 * (len(ordered) - 1))],
            "min": min(latencies),
            "max": max(latencies),
        }
    if manifest_path is not None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["manifest"] = {
            key: manifest.get(key)
            for key in (
                "failure_count",
                "retry_count",
                "wall_clock_seconds",
                "hidden_gold_accessed",
            )
        }
    return payload


def score_public_run(
    *,
    dataset_path: Path,
    prediction_path: Path,
    raw_response_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Strictly validate and score one public train/dev prediction set."""
    records = load_public_records(dataset_path, require_gold=True)
    predictions = load_predictions(prediction_path, (record.public_id for record in records))
    gold = {record.public_id: str(record.gold_action) for record in records}
    predicted = {prediction.public_id: prediction.action for prediction in predictions}
    result = score_actions(gold, predicted)
    non_abstained = [public_id for public_id, action in predicted.items() if action != "ABSTAIN"]
    result.update(
        {
            "prediction_counts": {
                action: sum(value == action for value in predicted.values())
                for action in VALID_ACTIONS
            },
            "gold_counts": {
                action: sum(value == action for value in gold.values()) for action in VALID_ACTIONS
            },
            "selective_accuracy": (
                sum(gold[public_id] == predicted[public_id] for public_id in non_abstained)
                / len(non_abstained)
                if non_abstained
                else None
            ),
            "abstention_precision": result["per_class"]["ABSTAIN"]["precision"],
            "abstention_recall": result["per_class"]["ABSTAIN"]["recall"],
            "component_cluster_bootstrap": {
                "available": False,
                "reason": "The component map is private and is not read by the public scorer.",
            },
            "operational": _telemetry(raw_response_path, manifest_path),
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--raw-responses", type=Path)
    parser.add_argument("--run-manifest", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = score_public_run(
        dataset_path=args.input,
        prediction_path=args.predictions,
        raw_response_path=args.raw_responses,
        manifest_path=args.run_manifest,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
