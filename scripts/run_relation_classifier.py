#!/usr/bin/env python3
"""Run the two-stage relation classifier over a labelled dev set."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.classifier import CandidateMemory, PriorMemory, RelationClassifier  # noqa: E402
from ask.classifier.metrics import (  # noqa: E402
    LABELS,
    add_bootstrap_f1_cis,
    confusion_counts,
    per_label_metrics,
)
from ask.inference.llm import StructuredLLM  # noqa: E402
from ask.inference.ollama import OllamaLLM  # noqa: E402


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _candidate_from_row(row: dict) -> CandidateMemory:
    label = row["gold_label"]
    return CandidateMemory(
        text=row.get("extractor_item_text") or row.get("expected_extraction", ""),
        type_guess=label["type"],
        source_turn=row.get("content"),
        session_id=row.get("session_id"),
        turn_id=row.get("turn_id"),
        timestamp=row.get("timestamp"),
    )


def _prior_from_row(row: dict, prior_text: str) -> PriorMemory:
    if row.get("prior_memory"):
        return PriorMemory.model_validate(row["prior_memory"])

    return PriorMemory(
        text=prior_text,
        type=row["gold_label"]["type"],
        memory_id="canonical-coffee-prior",
        timestamp=None,
    )


def _write_confusion(path: Path, gold: list[str], predicted: list[str]) -> None:
    counts = confusion_counts(gold, predicted)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["gold\\predicted", *LABELS])
        for gold_label in LABELS:
            writer.writerow([gold_label, *[counts[(gold_label, pred)] for pred in LABELS]])


def _fmt_float(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"


def _write_pr_table(path: Path, gold: list[str], predicted: list[str], n_bootstrap: int) -> None:
    rows = add_bootstrap_f1_cis(
        per_label_metrics(gold, predicted),
        gold,
        predicted,
        n_bootstrap=n_bootstrap,
        seed=0,
    )
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "label",
                "support",
                "predicted",
                "true_positive",
                "precision",
                "recall",
                "f1",
                "f1_ci_low",
                "f1_ci_high",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.label,
                    row.support,
                    row.predicted,
                    row.true_positive,
                    _fmt_float(row.precision),
                    _fmt_float(row.recall),
                    _fmt_float(row.f1),
                    _fmt_float(row.f1_ci_low),
                    _fmt_float(row.f1_ci_high),
                ]
            )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--stage1-prompt", type=Path, default=Path("prompts/relation_stage1_v0.j2"))
    p.add_argument("--stage2-prompt", type=Path, default=Path("prompts/relation_stage2_v0.j2"))
    p.add_argument("--ollama-model", default="phi3.5:3.8b")
    p.add_argument("--ollama-host", default="http://localhost:11434")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-new-tokens", type=int, default=96)
    p.add_argument("--num-ctx", type=int, default=4096)
    p.add_argument("--n-bootstrap", type=int, default=1000)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument(
        "--resume",
        action="store_true",
        help="Append missing rows when predictions.jsonl already exists.",
    )
    p.add_argument(
        "--prior-text",
        default="User prefers coffee in the morning.",
        help="Canonical retrieved prior memory used by the synthetic dev set.",
    )
    args = p.parse_args()

    rows = _read_jsonl(args.input)
    if args.limit is not None:
        rows = rows[: args.limit]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = args.out_dir / "predictions.jsonl"
    trace_path = args.out_dir / "trace.jsonl"
    completed: set[str] = set()
    if args.resume and predictions_path.exists():
        for line in predictions_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                completed.add(json.loads(line)["turn_id"])
    else:
        predictions_path.write_text("", encoding="utf-8")
        trace_path.write_text("", encoding="utf-8")

    llm = StructuredLLM(
        OllamaLLM(
            model_id=args.ollama_model,
            host=args.ollama_host,
            num_ctx=args.num_ctx,
        )
    )
    classifier = RelationClassifier.from_template_files(
        llm,
        args.stage1_prompt,
        args.stage2_prompt,
        log_path=trace_path,
    )

    existing_predictions: list[dict] = []
    if completed:
        existing_predictions = [
            json.loads(line)
            for line in predictions_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    gold: list[str] = [r["gold_relation"] for r in existing_predictions]
    predicted: list[str] = [
        r["prediction"]["relation_to_prior_state"] for r in existing_predictions
    ]
    with predictions_path.open("a", encoding="utf-8") as fh:
        for i, row in enumerate(rows, start=1):
            if row["turn_id"] in completed:
                print(f"[{i}/{len(rows)}] {row['turn_id']} skipped (resume)", flush=True)
                continue
            candidate = _candidate_from_row(row)
            prior = _prior_from_row(row, args.prior_text)
            out = classifier.classify(
                candidate,
                prior,
                max_new_tokens=args.max_new_tokens,
                temperature=args.temperature,
                seed=args.seed,
            )
            gold_label = row["gold_label"]["relation_to_prior_state"]
            pred_label = out.relation_to_prior_state
            gold.append(gold_label)
            predicted.append(pred_label)
            record = {
                "turn_id": row["turn_id"],
                "session_id": row["session_id"],
                "candidate": candidate.model_dump(),
                "prior": prior.model_dump(),
                "gold_relation": gold_label,
                "prediction": out.model_dump(),
                "model_id": args.ollama_model,
                "temperature": args.temperature,
                "seed": args.seed,
            }
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
            print(
                f"[{i}/{len(rows)}] {row['turn_id']} gold={gold_label} pred={pred_label}",
                flush=True,
            )

    _write_confusion(args.out_dir / "confusion.csv", gold, predicted)
    _write_pr_table(args.out_dir / "pr_table.csv", gold, predicted, args.n_bootstrap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
