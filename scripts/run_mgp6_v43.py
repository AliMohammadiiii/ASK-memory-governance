"""Run a resumable, public-only MGP-6 v4.3 action experiment.

The command intentionally has no hidden-gold option.  Hidden scoring is a
separate, locally private post-authorization step.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ask.eval.mgp6_v43 import (  # noqa: E402
    MGP6V43Prediction,
    build_decision_prompt,
    load_predictions,
    load_public_records,
    parse_action_response,
    sha256_file,
    sha256_value,
    write_prediction_resume_safe,
    write_raw_response,
)
from ask.inference.openai_compatible import OpenAICompatibleLLM  # noqa: E402

SYSTEMS = ("b1", "b2", "b3", "b4", "decision_zero_shot", "rules_controller", "live_model_controller")
DEFAULT_SYSTEM_PROMPT = Path("configs/experiments/mgp6_v43/decision_system_prompt.txt")


def _git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("benchmarks/mgp6/mgp6_v4_3/public/train.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("runs/mgp6_v43/smoke"))
    parser.add_argument("--system", choices=SYSTEMS, default="rules_controller")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--seed", type=int, default=4301)
    parser.add_argument("--provider", default="fixture")
    parser.add_argument("--model-id", default="fixture/deterministic-action")
    parser.add_argument("--base-url", default="http://localhost:3001/v1")
    parser.add_argument("--api-key-env", default="OPENROUTER_API_KEY")
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--retry-max-attempts", type=int, default=3)
    parser.add_argument("--system-prompt", type=Path, default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--action", choices=("KEEP", "SUPERSEDE", "ABSTAIN"), help="Deterministic engineering fixture only.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    records = load_public_records(args.input)
    if args.limit is not None:
        records = records[: args.limit]
    if not records:
        raise SystemExit("no public records selected")
    args.out.mkdir(parents=True, exist_ok=True)
    system_prompt = args.system_prompt.read_text(encoding="utf-8")
    prompt_hash = sha256_value({"system": system_prompt, "format": "v1"})
    manifest: dict[str, Any] = {
        "release_version": "4.3.0-human-validated-final",
        "dataset_path": str(args.input),
        "dataset_sha256": sha256_file(args.input),
        "system": args.system,
        "provider": args.provider,
        "model_id": args.model_id,
        "prompt_hash": prompt_hash,
        "system_prompt_path": str(args.system_prompt),
        "system_prompt_hash": sha256_value(system_prompt),
        "seed": args.seed,
        "decoding": {"temperature": args.temperature, "max_new_tokens": args.max_new_tokens},
        "retry_policy": {"max_attempts": args.retry_max_attempts},
        "timeout_s": args.timeout_s,
        "concurrency": args.concurrency,
        "evaluator_version": "ask.eval.mgp6_v43.v1",
        "code_commit": _git_commit(),
        "environment_lock": {"python": sys.version, "pyproject_sha256": sha256_file("pyproject.toml")},
        "n_selected": len(records),
        "complete": False,
        "hidden_gold_accessed": False,
    }
    (args.out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    if args.dry_run:
        print(f"[mgp6-v43] public input={args.input} n={len(records)} prompt_hash={prompt_hash}")
        return 0

    static_action = args.action
    llm = None
    if static_action is None:
        if args.provider == "fixture":
            raise SystemExit("a real system requires a non-fixture provider, or --action for an engineering fixture")
        llm = OpenAICompatibleLLM(
            model_id=args.model_id,
            base_url=args.base_url,
            api_key_env=args.api_key_env,
            timeout_s=args.timeout_s,
            require_json=True,
            retry_max_attempts=args.retry_max_attempts,
            response_format="json_object",
            include_raw_response=True,
        )
    predictions_path, raw_path = args.out / "predictions.jsonl", args.out / "raw_responses.jsonl"
    started = time.perf_counter()
    failures = retries = prompt_tokens = completion_tokens = 0
    for record in records:
        prompt = build_decision_prompt(record, system_prompt)
        call_started = time.perf_counter()
        try:
            raw = static_action if static_action else llm.generate(prompt, max_new_tokens=args.max_new_tokens, temperature=args.temperature, seed=args.seed).text  # type: ignore[union-attr]
            action = parse_action_response(raw)
            write_prediction_resume_safe(predictions_path, MGP6V43Prediction(public_id=record.public_id, action=action))
            write_raw_response(raw_path, public_id=record.public_id, raw_response=raw, metadata={"latency_ms": round((time.perf_counter() - call_started) * 1000, 3), "retry_count": 0, "prompt_tokens": None, "completion_tokens": None})
        except Exception:
            failures += 1
            raise
    predictions = load_predictions(predictions_path, (record.public_id for record in records))
    manifest.update({"complete": True, "prediction_sha256": sha256_file(predictions_path), "wall_clock_seconds": round(time.perf_counter() - started, 3), "failure_count": failures, "retry_count": retries, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "prediction_count": len(predictions)})
    (args.out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[mgp6-v43] wrote {predictions_path} ({len(predictions)} predictions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
