"""Live rejudge persisted answers with a fresh judge backend.

Unlike ``regrade.py``, this script does not require judge-cache hits. It reads
``answers.jsonl`` from an existing run, replays those answers against the slice,
and writes a separate judged report under ``--out``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.baselines.base import BaselineAnswer  # noqa: E402
from ask.data.longmemeval import iter_longmemeval_s  # noqa: E402
from ask.eval.judge import JudgeBackendConfig, build_judge_backend  # noqa: E402
from ask.eval.longmemeval import JudgmentCache, LongMemEvalGrader, evaluate_baseline  # noqa: E402


class ReplayBaseline:
    """Baseline facade that returns persisted answers."""

    def __init__(self, baseline_name: str, by_session: dict[str, BaselineAnswer]) -> None:
        self.BASELINE_NAME = baseline_name
        self._by_session = by_session

    def answer(self, session: Any) -> BaselineAnswer:
        return self._by_session[session.session_id]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_answers(path: Path) -> dict[str, BaselineAnswer]:
    by_session = {}
    for row in _load_jsonl(path):
        row.setdefault("extras", {})
        answer = BaselineAnswer(**row)
        by_session[answer.session_id] = answer
    return by_session


def _baseline_name(run_dir: Path, answers: dict[str, BaselineAnswer]) -> str:
    report_path = run_dir / "report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            name = report.get("baseline_name")
            if isinstance(name, str) and name:
                return name
        except json.JSONDecodeError:
            pass
    if answers:
        return next(iter(answers.values())).baseline
    return "unknown"


def _write_replayed_answers(out_dir: Path, answers: list[BaselineAnswer]) -> None:
    for name in ("answers.jsonl", "predictions.jsonl"):
        with (out_dir / name).open("w", encoding="utf-8") as fh:
            for answer in answers:
                fh.write(json.dumps(answer.to_dict(), ensure_ascii=False, sort_keys=True))
                fh.write("\n")


def _build_judge(args: argparse.Namespace):
    cfg = JudgeBackendConfig(
        backend=args.judge_backend,
        model_id=args.judge_model,
        ollama_host=args.ollama_host,
        num_ctx=args.judge_num_ctx,
        timeout_s=args.judge_timeout_s,
        response_format="json" if args.judge_json_format else None,
        think=args.judge_think,
        hf_dtype=args.hf_dtype,
        hf_revision=args.hf_revision,
        hf_device_map=args.hf_device_map,
        hf_load_in_4bit=args.hf_load_in_4bit,
        hf_trust_remote_code=args.hf_trust_remote_code,
        hf_max_seq_len=args.hf_max_seq_len,
    )
    return build_judge_backend(cfg)


def rejudge(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run
    answers_path = run_dir / "answers.jsonl"
    if not answers_path.exists():
        raise SystemExit(f"missing {answers_path}")

    answers_by_session = load_answers(answers_path)
    if not answers_by_session:
        raise SystemExit(f"no answers found in {answers_path}")

    out_dir = args.out or (run_dir / "ollama_judge")
    out_dir.mkdir(parents=True, exist_ok=True)

    sessions = [s for s in iter_longmemeval_s(args.slice) if s.session_id in answers_by_session]
    if len(sessions) != len(answers_by_session):
        missing = sorted(set(answers_by_session) - {s.session_id for s in sessions})
        raise SystemExit(
            f"{len(missing)} answers are not present in slice {args.slice}: {missing[:5]}"
        )

    ordered_answers = [answers_by_session[s.session_id] for s in sessions]
    _write_replayed_answers(out_dir, ordered_answers)

    judge = _build_judge(args)
    grader = LongMemEvalGrader(
        judge_llm=judge,
        cache=JudgmentCache(out_dir / "judge_cache.jsonl"),
        seed=args.seed,
    )
    baseline = ReplayBaseline(_baseline_name(run_dir, answers_by_session), answers_by_session)
    report = evaluate_baseline(
        baseline,
        sessions,
        grader,
        n_bootstrap=args.n_bootstrap,
        bootstrap_seed=args.seed,
        judgments_path=out_dir / "judgments.jsonl",
    )

    payload = report.to_dict()
    payload.update(
        {
            "source_run": str(run_dir),
            "slice_path": str(args.slice),
            "seed": args.seed,
            "rejudge": True,
            "fallback_count": sum(1 for g in report.grades if g.used_fallback),
        }
    )
    (out_dir / "report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (out_dir / "results.md").write_text(report.summarize_markdown(), encoding="utf-8")
    return payload


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--slice", required=True, type=Path)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument(
        "--judge-backend", choices=("ollama", "hf", "huggingface", "fake"), default="ollama"
    )
    p.add_argument("--judge-model", default="phi3.5:3.8b")
    p.add_argument("--ollama-host", default="http://127.0.0.1:11434")
    p.add_argument("--judge-num-ctx", type=int, default=2048)
    p.add_argument("--judge-timeout-s", type=float, default=1800.0)
    p.add_argument("--judge-json-format", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--judge-think", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--hf-dtype", choices=("bfloat16", "float16", "float32"), default="float16")
    p.add_argument(
        "--hf-revision",
        default=None,
        help="Optional immutable Hugging Face commit revision for judge loading.",
    )
    p.add_argument("--hf-device-map", default="auto")
    p.add_argument("--hf-load-in-4bit", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--hf-trust-remote-code", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--hf-max-seq-len", type=int, default=4096)
    p.add_argument("--n-bootstrap", type=int, default=1000)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    payload = rejudge(args)
    print(
        f"[rejudge] {payload['baseline_name']} n={payload['n_sessions']} "
        f"overall={payload['overall_accuracy'] * 100:.1f}% "
        f"judge={payload['judge_model_id']}",
        flush=True,
    )
    print(f"[rejudge] wrote {args.out or (args.run / 'ollama_judge')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
