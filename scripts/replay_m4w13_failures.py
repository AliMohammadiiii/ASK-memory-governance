"""Offline replay of the m4w13 T4-quality run through the improved pipeline.

Re-runs questions from a recorded run WITHOUT any Ollama model:

  - extraction + relation outputs come from the recorded run's cache/trace
    files (cache misses degrade to empty extraction / 'unclear' relation and
    are counted);
  - the answer LLM is a stub that always returns 'Unknown', because what this
    replay measures is everything *upstream* of the answerer:
      (a) deterministic computation-bypass answers (graded against gold with
          the repo's own token guard), and
      (b) whether the gold evidence reaches the answer prompt at all
          (evidence-coverage keys per failed question).

Usage:
  python scripts/replay_m4w13_failures.py \
      --slice data/slices/longmemeval_s_cleaned_50_seed0.jsonl \
      --run-dir /path/to/runs/m4w13_50_t4_quality/controller \
      --out runs/replay_m4w13_improvements \
      [--mode improved|baseline] [--only-failed] [--embedder-device cpu]

`--mode baseline` replays with the new flags OFF (the recorded run's
configuration) so before/after coverage can be compared on identical caches.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ask.baselines import build_session_corpus  # noqa: E402
from ask.baselines.embeddings import TurnEmbedder  # noqa: E402
from ask.data.longmemeval import load_longmemeval_s  # noqa: E402
from ask.eval.longmemeval import normalized_substring_grade  # noqa: E402
from ask.extraction import ExtractionOutput  # noqa: E402
from ask.inference.llm import LLMResponse  # noqa: E402
from ask.pipeline import ControllerOrchestrator  # noqa: E402

# Gold-evidence key strings per question, from the 2026-06-10 failure audit.
# A question's evidence "reaches the prompt" when each any-of group matches.
EVIDENCE_KEYS: dict[str, list[list[str]]] = {
    # -- the 15 graded failures of the 70% run --
    "852ce960": [["400,000"]],
    "e493bb7c": [["bedroom"]],
    "4f54b7c9": [["tea set"], ["typewriter"], ["diamond necklace"], ["music box"], ["glassware"]],
    "7024f17c": [["30-minute jog", "30 minute jog"]],
    "8cf4d046": [["3.86"]],
    "gpt4_59c863d7": [["f-15"], ["spitfire"], ["tiger"], ["b-29"], ["camaro"]],
    "10d9b85a": [["10th of april"], ["17th and 18th"]],
    "21d02d0d": [["march 26"], ["except for the run", "march 12"]],
    "f0e564bc": [["800"], ["500"]],
    "5d3d2817": [["marketing specialist"]],
    "86f00804": [["evelyn hugo", "seven husbands"]],
    "gpt4_2f584639": [["necklace"], ["photo album"]],
    "982b5123": [["three months in advance"], ["two months ago"]],
    "eac54add": [["first client"]],
    "gpt4_45189cb4": [["nba"], ["college football"], ["nfl"]],
}

FAILED_IDS = list(EVIDENCE_KEYS)


class ReplayExtractor:
    """Cache-backed extractor stub. Never calls a model.

    `model_id` matches the recorded run's extractor so the orchestrator's
    trace loader admits the recorded outputs; on a cache miss the orchestrator
    receives an empty extraction (counted via `misses`).
    """

    prompt_template = "replay/extraction-cache-only"

    def __init__(self, model_id: str = "llama3.2:3b") -> None:
        self.model_id = model_id
        self.misses = 0

    def extract(self, turn, window, *, max_new_tokens=512, temperature=0.0, seed=0):
        self.misses += 1
        return ExtractionOutput(
            items=[],
            no_extractable_content=True,
            coverage_note="replay cache miss",
        )


class ReplayClassifier:
    """Cache-backed relation classifier stub (misses → 'unclear')."""

    stage1_template = "replay/relation-cache-only"
    stage2_template = "replay/relation-cache-only"

    def __init__(self, model_id: str = "phi3.5:3.8b") -> None:
        self.model_id = model_id
        self.misses = 0

    def classify(self, candidate, prior, *, max_new_tokens=128, temperature=0.0, seed=0):
        from ask.classifier import RelationOutput

        self.misses += 1
        return RelationOutput(
            logical_relation="independent",
            temporal="unknown",
            same_subject=False,
            relation_to_prior_state="unclear",
            stage1_rationale="replay cache miss",
            stage2_rationale="replay cache miss",
        )


class UnknownLLM:
    """Answer-LLM stub: the replay never simulates the 9B answerer."""

    model_id = "replay/unknown-stub"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt, *, max_new_tokens=256, temperature=0.0, seed=0, stop=None):
        self.calls += 1
        return LLMResponse(
            text="Unknown",
            prompt_tokens=max(1, len(prompt.split())),
            completion_tokens=1,
            latency_ms=0.0,
            model_id=self.model_id,
            seed=seed,
        )


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold())


def coverage(session_id: str, prompt: str) -> tuple[int, int, list[str]]:
    """(#groups satisfied, #groups, missing-group labels) for a question."""
    groups = EVIDENCE_KEYS.get(session_id)
    if not groups:
        return 0, 0, []
    p = _norm(prompt)
    hit = 0
    missing: list[str] = []
    for group in groups:
        if any(_norm(key) in p for key in group):
            hit += 1
        else:
            missing.append("|".join(group))
    return hit, len(groups), missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slice", type=Path, required=True)
    ap.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Recorded controller run dir holding caches + traces "
        "(extraction_cache/relation_cache/extraction_trace/"
        "relation_trace .jsonl).",
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--mode", choices=("improved", "baseline"), default="improved")
    ap.add_argument(
        "--only-failed",
        action="store_true",
        help="Replay only the 15 questions the recorded run got wrong.",
    )
    ap.add_argument("--session-id", action="append", default=None)
    ap.add_argument("--embedder-device", default="cpu")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--memory-top-k", type=int, default=32)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for name in (
        "extraction_cache.jsonl",
        "relation_cache.jsonl",
        "extraction_trace.jsonl",
        "relation_trace.jsonl",
    ):
        src = args.run_dir / name
        if src.exists():
            shutil.copy(src, args.out / name)

    sessions = list(load_longmemeval_s(args.slice))
    corpus = build_session_corpus(sessions)
    judgments: dict[str, dict] = {}
    judgments_path = args.run_dir / "judgments.jsonl"
    if judgments_path.exists():
        for line in judgments_path.open():
            row = json.loads(line)
            judgments[row["session_id"]] = row

    wanted = set(args.session_id or [])
    if args.only_failed:
        wanted |= set(FAILED_IDS)
    targets = [s for s in sessions if not wanted or s.session_id in wanted]

    improved = args.mode == "improved"
    extractor = ReplayExtractor()
    classifier = ReplayClassifier()
    llm = UnknownLLM()
    embedder = TurnEmbedder(device=args.embedder_device)
    orchestrator = ControllerOrchestrator(
        llm=llm,
        extractor=extractor,
        classifier=classifier,
        corpus=corpus,
        embedder=embedder,
        k=args.k,
        seed=0,
        action_log_path=args.out / "action_log.jsonl",
        extraction_max_new_tokens=512,
        relation_max_new_tokens=128,
        progress=False,
        memory_prefilter_top_k=args.memory_top_k,
        retrieval_neighbor_window=1,
        include_assistant_context=True,
        include_raw_user_context=improved,
        retrieval_query_augmentation=improved,
        deterministic_numeric_supersede=improved,
        answer_retry_on_unknown=False,  # the stub answerer makes retries moot
        prior_top_k=3,
        prior_similarity_threshold=0.45,
        temporal_scaffold=True,
        computation_answerer=True,
    )

    rows: list[dict] = []
    for i, session in enumerate(targets, start=1):
        answer = orchestrator.answer(session)
        extras = answer.extras
        bypass = bool(extras.get("computation_bypass_used"))
        comp_answer = extras.get("computation_answer")
        was_correct = bool(judgments.get(session.session_id, {}).get("correct"))
        bypass_grade = None
        if bypass and comp_answer:
            ok, _rationale = normalized_substring_grade(
                predicted=str(comp_answer),
                gold=session.gold_answer,
                competency=session.competency,
            )
            bypass_grade = bool(ok)
        hit, total, missing = coverage(session.session_id, answer.raw_prompt or "")
        row = {
            "session_id": session.session_id,
            "competency": session.competency,
            "gold": session.gold_answer,
            "was_correct_in_recorded_run": was_correct,
            "computation_intent": extras.get("computation_intent"),
            "computation_answer": comp_answer,
            "computation_bypass_used": bypass,
            "bypass_matches_gold": bypass_grade,
            "evidence_groups_hit": hit,
            "evidence_groups_total": total,
            "evidence_missing": missing,
            "extraction_cache_hits": extras.get("extraction_cache_hits"),
            "extraction_cache_misses": extras.get("extraction_cache_misses"),
            "action_counts": extras.get("action_counts"),
            "n_retrieved": extras.get("n_retrieved"),
            "prompt_chars": len(answer.raw_prompt or ""),
        }
        rows.append(row)
        cov = f"{hit}/{total}" if total else "-"
        print(
            f"[{i:>2}/{len(targets)}] {session.session_id:<22} "
            f"{session.competency:<26} bypass={'Y' if bypass else '-'} "
            f"comp={str(comp_answer)[:28]!s:<30} grade="
            f"{'' if bypass_grade is None else ('PASS' if bypass_grade else 'FAIL'):<4} "
            f"evidence={cov} missing={missing}",
            flush=True,
        )

    report = {
        "mode": args.mode,
        "n": len(rows),
        "bypass_used": sum(1 for r in rows if r["computation_bypass_used"]),
        "bypass_pass": sum(1 for r in rows if r["bypass_matches_gold"] is True),
        "bypass_fail": sum(1 for r in rows if r["bypass_matches_gold"] is False),
        "full_evidence_coverage": sum(
            1
            for r in rows
            if r["evidence_groups_total"] and r["evidence_groups_hit"] == r["evidence_groups_total"]
        ),
        "tracked_failed_questions": sum(1 for r in rows if r["evidence_groups_total"]),
        "regression_risk": [
            r["session_id"]
            for r in rows
            if r["was_correct_in_recorded_run"] and r["bypass_matches_gold"] is False
        ],
        "rows": rows,
    }
    out_path = args.out / f"replay_report_{args.mode}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(
        f"\n[{args.mode}] bypass {report['bypass_pass']}/{report['bypass_used']} pass gold-token guard; "
        f"evidence fully present for {report['full_evidence_coverage']}/"
        f"{report['tracked_failed_questions']} previously-failed questions; "
        f"regression-risk: {report['regression_risk'] or 'none'}"
    )
    print(f"report → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
