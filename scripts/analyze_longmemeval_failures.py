"""Classify LongMemEval run failures into actionable buckets."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

CATEGORY_RETRIEVAL_MISS = "retrieval_miss"
CATEGORY_EXTRACTION_MISS = "extraction_miss"
CATEGORY_ANSWER_GENERATION_MISS = "answer_generation_miss"
CATEGORY_SPECIFICITY_MISS = "answer_specificity_or_formatting_miss"
CATEGORY_BLANK_OR_REFUSAL = "blank_or_refusal"
CATEGORY_JUDGE_GUARD_ISSUE = "judge_guard_issue"

REFUSAL_MARKERS = (
    "i don't know",
    "i do not know",
    "unknown",
    "not sure",
    "cannot answer",
    "can't answer",
    "no information",
    "not mentioned",
    "not provided",
)

STOPWORDS = {
    "a", "an", "the", "is", "was", "were", "to", "of", "and", "or", "in", "on",
    "for", "with", "that", "this", "they", "them", "their", "user", "assistant",
}

TOKEN_RE = re.compile(r"\w+")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text) if token.lower() not in STOPWORDS}


def _covers_gold(text: str, gold: str) -> bool:
    gold_tokens = _tokens(gold)
    if not gold_tokens:
        return False
    return gold_tokens <= _tokens(text)


def _gold_coverage(text: str, gold: str) -> float:
    gold_tokens = _tokens(gold)
    if not gold_tokens:
        return 0.0
    return len(gold_tokens & _tokens(text)) / len(gold_tokens)


def _looks_like_refusal(text: str) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in REFUSAL_MARKERS)


def _retrieved_block(raw_prompt: str) -> str:
    start_marker = "----- RETRIEVED MEMORY"
    end_marker = "----- DIALOG -----"
    start = raw_prompt.find(start_marker)
    if start < 0:
        return raw_prompt
    end = raw_prompt.find(end_marker, start)
    return raw_prompt[start:end] if end >= 0 else raw_prompt[start:]


def classify_failure(answer: dict[str, Any], judgment: dict[str, Any]) -> str | None:
    if bool(judgment.get("correct")):
        return None
    text = str(answer.get("text") or "")
    gold = str(judgment.get("gold") or "")
    extras = answer.get("extras") or {}
    if not text.strip():
        return CATEGORY_BLANK_OR_REFUSAL
    if _covers_gold(text, gold):
        return CATEGORY_JUDGE_GUARD_ISSUE

    action_counts = extras.get("action_counts") or {}
    total_actions = sum(int(v) for v in action_counts.values()) if isinstance(action_counts, dict) else 0
    n_retrieved = int(extras.get("n_retrieved") or 0)
    if total_actions == 0 and answer.get("baseline") in {"controller", "naive_overwrite", "recency"}:
        return CATEGORY_EXTRACTION_MISS
    if n_retrieved == 0:
        return CATEGORY_RETRIEVAL_MISS

    retrieved = _retrieved_block(str(answer.get("raw_prompt") or ""))
    if _looks_like_refusal(text):
        if not _covers_gold(retrieved, gold):
            return CATEGORY_RETRIEVAL_MISS
        return CATEGORY_BLANK_OR_REFUSAL
    prediction_gold_coverage = _gold_coverage(text, gold)
    retrieved_gold_coverage = _gold_coverage(retrieved, gold)
    if _covers_gold(retrieved, gold):
        if 0.0 < prediction_gold_coverage < 1.0:
            return CATEGORY_SPECIFICITY_MISS
        return CATEGORY_ANSWER_GENERATION_MISS
    if prediction_gold_coverage > 0.0:
        return CATEGORY_SPECIFICITY_MISS
    if retrieved_gold_coverage < 1.0:
        return CATEGORY_RETRIEVAL_MISS
    return CATEGORY_ANSWER_GENERATION_MISS


def analyze_run(run_dir: Path) -> dict[str, Any]:
    answers = {row["session_id"]: row for row in _load_jsonl(run_dir / "answers.jsonl")}
    judgments = {row["session_id"]: row for row in _load_jsonl(run_dir / "judgments.jsonl")}
    rows = []
    counts: Counter[str] = Counter()
    for session_id in sorted(set(answers) & set(judgments)):
        answer = answers[session_id]
        judgment = judgments[session_id]
        category = classify_failure(answer, judgment)
        if category is None:
            continue
        counts[category] += 1
        rows.append(
            {
                "session_id": session_id,
                "competency": judgment.get("competency"),
                "category": category,
                "predicted": answer.get("text"),
                "gold": judgment.get("gold"),
                "prediction_gold_coverage": _gold_coverage(
                    str(answer.get("text") or ""),
                    str(judgment.get("gold") or ""),
                ),
                "retrieved_gold_coverage": _gold_coverage(
                    _retrieved_block(str(answer.get("raw_prompt") or "")),
                    str(judgment.get("gold") or ""),
                ),
                "judge_rationale": judgment.get("judge_rationale"),
            }
        )
    return {
        "run": str(run_dir),
        "n_answers": len(answers),
        "n_judgments": len(judgments),
        "n_failures": len(rows),
        "counts": dict(sorted(counts.items())),
        "failures": rows,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# LongMemEval Failure Analysis",
        "",
        f"- **Run:** `{report['run']}`",
        f"- **Failures:** {report['n_failures']}",
        "",
        "| Category | Count |",
        "|---|---:|",
    ]
    for category, count in report["counts"].items():
        lines.append(f"| {category} | {count} |")
    lines.extend(
        [
            "",
            "| Session | Competency | Category | Gold | Predicted |",
            "|---|---|---|---|---|",
        ]
    )
    for row in report["failures"]:
        gold = str(row.get("gold") or "").replace("|", "\\|")
        predicted = str(row.get("predicted") or "").replace("|", "\\|")
        lines.append(
            f"| `{row['session_id']}` | {row.get('competency')} | {row['category']} | "
            f"{gold[:120]} | {predicted[:120]} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--slice", type=Path, default=None,
                   help="Accepted for workflow symmetry; current analysis uses persisted outputs.")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    out_dir = args.out or (args.run / "failure_analysis")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = analyze_run(args.run)
    (out_dir / "analysis.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (out_dir / "analysis.md").write_text(_render_markdown(report), encoding="utf-8")
    print(f"[failure-analysis] failures={report['n_failures']} wrote {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
