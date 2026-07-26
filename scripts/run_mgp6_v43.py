"""Run a resumable, public-only MGP-6 v4.3 action experiment.

The command intentionally has no hidden-gold option.  Hidden scoring is a
separate, locally private post-authorization step.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ask.eval.mgp6_v43 import (  # noqa: E402
    ADAPTER_VERSION,
    MGP6V43_SYSTEMS,
    MODEL_BACKED_SYSTEMS,
    MGP6V43Error,
    MGP6V43Prediction,
    apply_live_controller_guard,
    build_system_prompt,
    load_predictions,
    load_predictions_allow_partial,
    load_public_records,
    parse_action_response,
    rules_controller_action,
    sha256_file,
    sha256_value,
    system_allowed_actions,
    validate_system_action,
    write_prediction_resume_safe,
    write_raw_response,
)
from ask.inference.llm import LLMResponse  # noqa: E402
from ask.inference.openai_compatible import OpenAICompatibleLLM  # noqa: E402

SYSTEMS = MGP6V43_SYSTEMS
REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_HIDDEN_INPUT_ROOT = REPO_ROOT / ".private/benchmarks/mgp6/v4.3/hidden_inputs"
FINAL_HIDDEN_RUN_ROOT = REPO_ROOT / "runs/mgp6_v43/final_hidden"
DEFAULT_SYSTEM_PROMPTS = {
    "b1": Path("configs/experiments/mgp6_v43/b1_no_memory_prompt.txt"),
    "b2": Path("configs/experiments/mgp6_v43/b2_flat_retrieval_prompt.txt"),
    "b3": Path("configs/experiments/mgp6_v43/b3_recency_prompt.txt"),
    "b4": Path("configs/experiments/mgp6_v43/b4_overwrite_prompt.txt"),
    "decision_zero_shot": Path("configs/experiments/mgp6_v43/decision_system_prompt.txt"),
    "rules_controller": Path("configs/experiments/mgp6_v43/rules_controller_prompt.txt"),
    "live_model_controller": Path("configs/experiments/mgp6_v43/live_model_controller_prompt.txt"),
    "ablation_no_abstain": Path("configs/experiments/mgp6_v43/ablation_no_abstain_prompt.txt"),
    "ablation_no_provenance": Path("configs/experiments/mgp6_v43/ablation_no_provenance_prompt.txt"),
    "ablation_no_typing": Path("configs/experiments/mgp6_v43/ablation_no_typing_prompt.txt"),
    "ablation_no_lineage": Path("configs/experiments/mgp6_v43/ablation_no_lineage_prompt.txt"),
}


def _path_is_within(path: Path, root: Path) -> bool:
    """Return whether ``path`` resolves beneath ``root`` without reading it."""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _hidden_run_controls(
    *,
    system: str,
    adapter_spec: dict[str, Any],
    provider: str,
    model_id: str,
    base_url: str,
    prompt_hash: str,
    system_prompt_hash: str,
    seed: int,
    decoding: dict[str, Any],
    retry_policy: dict[str, int],
    timeout_s: float,
    concurrency: int,
    environment_lock: dict[str, str],
) -> dict[str, Any]:
    """Build the immutable, label-free control surface for a hidden run."""
    return {
        "release_version": "4.3.0-human-validated-final",
        "input_mode": "private_hidden_inputs_without_gold",
        "system": system,
        "adapter_version": ADAPTER_VERSION,
        "adapter_spec_hash": sha256_value(adapter_spec),
        "provider": provider,
        "model_id": model_id,
        "base_url": base_url,
        "prompt_hash": prompt_hash,
        "system_prompt_hash": system_prompt_hash,
        "seed": seed,
        "decoding": decoding,
        "retry_policy": retry_policy,
        "timeout_s": timeout_s,
        "concurrency": concurrency,
        "evaluator_version": "ask.eval.mgp6_v43.v1",
        "runtime_hashes": {
            "runner": sha256_file(Path(__file__)),
            "evaluator_and_adapters": sha256_file("src/ask/eval/mgp6_v43.py"),
            "public_scorer": sha256_file("scripts/score_mgp6_v43.py"),
        },
        "environment_lock": environment_lock,
    }


def _require_hidden_run_authorization(
    authorization_path: Path,
    controls: dict[str, Any],
) -> None:
    """Reject a hidden run unless its authorization binds every control exactly."""
    try:
        authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read hidden-run authorization: {authorization_path}") from exc
    if authorization.get("authorized") is not True:
        raise SystemExit("hidden run is not authorized")
    expected = authorization.get("hidden_run_controls")
    expected_hash = authorization.get("hidden_run_controls_sha256")
    if not isinstance(expected, dict) or not isinstance(expected_hash, str):
        raise SystemExit("hidden-run authorization has no valid frozen controls")
    if sha256_value(expected) != expected_hash:
        raise SystemExit("hidden-run authorization control hash is invalid")
    if expected != controls:
        raise SystemExit("hidden-run controls do not match the frozen authorization")


def _repair_instruction(allowed_actions: tuple[str, ...]) -> str:
    example = allowed_actions[0]
    return (
        "The previous response was rejected because it was not exactly one valid "
        f"MGP-6 v4.3 action. Return JSON only, with no prose: {{\"action\":\"{example}\"}}. "
        f"The action must be one of {', '.join(allowed_actions)}."
    )


def _git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _tracked_worktree_state() -> str:
    unstaged_dirty = subprocess.run(["git", "diff", "--quiet"], check=False).returncode != 0
    staged_dirty = subprocess.run(["git", "diff", "--cached", "--quiet"], check=False).returncode != 0
    return "dirty" if unstaged_dirty or staged_dirty else "clean"


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Durably replace the manifest so an interrupted run remains resumable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, indent=2, sort_keys=True))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _openrouter_reasoning_body(reasoning_effort: str | None) -> dict[str, Any] | None:
    if reasoning_effort is None:
        return None
    return {"reasoning": {"effort": reasoning_effort}}


def _raw_metadata(*, response: LLMResponse, parse_attempt: int, valid_action: bool, error: str | None = None) -> dict[str, Any]:
    metadata = dict(response.metadata)
    metadata.pop("raw_response", None)
    metadata.update(
        {
            "parse_attempt": parse_attempt,
            "valid_action": valid_action,
            "error": error,
            "latency_ms": round(float(response.latency_ms), 3),
            "prompt_tokens": int(response.prompt_tokens),
            "completion_tokens": int(response.completion_tokens),
            "model_id": response.model_id,
            "seed": response.seed,
            "temperature": response.temperature,
        }
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("benchmarks/mgp6/mgp6_v4_3/public/train.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("runs/mgp6_v43/smoke"))
    parser.add_argument("--system", choices=SYSTEMS, default="decision_zero_shot")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--seed", type=int, default=4301)
    parser.add_argument("--provider", default="fixture")
    parser.add_argument("--model-id", default="fixture/deterministic-action")
    parser.add_argument("--base-url", default="http://localhost:3001/v1")
    parser.add_argument("--api-key-env", default="OPENROUTER_API_KEY")
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--retry-max-attempts", type=int, default=3)
    parser.add_argument("--parse-retry-max-attempts", type=int, default=2)
    parser.add_argument("--reasoning-effort", choices=("none", "minimal", "low", "medium", "high"), default=None)
    parser.add_argument("--system-prompt", type=Path)
    parser.add_argument("--recency-turns", type=int, default=2)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--action", choices=("KEEP", "SUPERSEDE", "ABSTAIN"), help="Deterministic engineering fixture only.")
    parser.add_argument(
        "--hidden-input",
        action="store_true",
        help="Enable one authorized prediction-only run over ignored private hidden inputs.",
    )
    parser.add_argument(
        "--authorization",
        type=Path,
        help="Tracked FINAL_HIDDEN_RUN_AUTHORIZATION.json required with --hidden-input.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.recency_turns < 1:
        raise SystemExit("--recency-turns must be at least 1")
    if args.concurrency != 1:
        raise SystemExit(
            "--concurrency values other than 1 are not implemented; run separate output directories instead"
        )
    if args.hidden_input:
        if args.authorization is None:
            raise SystemExit("--hidden-input requires --authorization")
        if args.limit is not None or args.action is not None or args.dry_run:
            raise SystemExit("hidden runs forbid --limit, --action, and --dry-run")
        if not _path_is_within(args.input, PRIVATE_HIDDEN_INPUT_ROOT):
            raise SystemExit("hidden input must be beneath the ignored private hidden-input root")
        if not _path_is_within(args.out, FINAL_HIDDEN_RUN_ROOT):
            raise SystemExit("hidden output must be beneath runs/mgp6_v43/final_hidden")
    elif args.authorization is not None:
        raise SystemExit("--authorization is valid only with --hidden-input")
    records = load_public_records(args.input, require_gold=not args.hidden_input)
    if args.limit is not None:
        records = records[: args.limit]
    if not records:
        raise SystemExit("no public records selected")
    system_prompt_path = args.system_prompt or DEFAULT_SYSTEM_PROMPTS[args.system]
    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    allowed_actions = system_allowed_actions(args.system)
    adapter_spec = {
        "adapter_version": ADAPTER_VERSION,
        "system": args.system,
        "allowed_actions": allowed_actions,
        "recency_turns": args.recency_turns,
    }
    prompt_hash = sha256_value({"system_prompt": system_prompt, "adapter": adapter_spec})
    manifest_path = args.out / "run_manifest.json"
    previous_manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"cannot resume with invalid manifest: {manifest_path}") from exc
    effective_provider = "local-rule" if args.system == "rules_controller" and args.action is None else args.provider
    effective_model_id = "ask/rules-controller-v43" if args.system == "rules_controller" and args.action is None else args.model_id
    environment_lock = {"python": sys.version, "pyproject_sha256": sha256_file("pyproject.toml")}
    decoding = {
        "temperature": args.temperature,
        "max_new_tokens": args.max_new_tokens,
        "reasoning_effort": args.reasoning_effort,
    }
    retry_policy = {
        "transport_max_attempts": args.retry_max_attempts,
        "parse_max_attempts": args.parse_retry_max_attempts,
    }
    hidden_run_controls = _hidden_run_controls(
        system=args.system,
        adapter_spec=adapter_spec,
        provider=effective_provider,
        model_id=effective_model_id,
        base_url=args.base_url,
        prompt_hash=prompt_hash,
        system_prompt_hash=sha256_value(system_prompt),
        seed=args.seed,
        decoding=decoding,
        retry_policy=retry_policy,
        timeout_s=args.timeout_s,
        concurrency=args.concurrency,
        environment_lock=environment_lock,
    )
    if args.hidden_input:
        if not isinstance(args.authorization, Path):
            raise SystemExit("--hidden-input requires a valid --authorization path")
        _require_hidden_run_authorization(args.authorization, hidden_run_controls)
    run_config = {
        "release_version": "4.3.0-human-validated-final",
        "dataset_sha256": sha256_file(args.input),
        "system": args.system,
        "adapter_spec_hash": sha256_value(adapter_spec),
        "provider": effective_provider,
        "model_id": effective_model_id,
        "base_url": args.base_url,
        "api_key_env": args.api_key_env,
        "prompt_hash": prompt_hash,
        "system_prompt_hash": sha256_value(system_prompt),
        "seed": args.seed,
        "decoding": decoding,
        "retry_policy": retry_policy,
        "timeout_s": args.timeout_s,
        "concurrency": args.concurrency,
        "recency_turns": args.recency_turns,
        "fixture_action": args.action,
        "evaluator_version": "ask.eval.mgp6_v43.v1",
        "code_commit": _git_commit(),
        "environment_lock": environment_lock,
        "input_mode": "hidden_input" if args.hidden_input else "public_development_or_engineering",
    }
    manifest: dict[str, Any] = {
        "release_version": "4.3.0-human-validated-final",
        "dataset_path": str(args.input),
        "dataset_sha256": run_config["dataset_sha256"],
        "system": args.system,
        "adapter_version": ADAPTER_VERSION,
        "adapter_spec": adapter_spec,
        "adapter_spec_hash": run_config["adapter_spec_hash"],
        "provider": effective_provider,
        "model_id": effective_model_id,
        "prompt_hash": run_config["prompt_hash"],
        "system_prompt_path": str(system_prompt_path),
        "system_prompt_hash": run_config["system_prompt_hash"],
        "seed": args.seed,
        "decoding": run_config["decoding"],
        "retry_policy": run_config["retry_policy"],
        "timeout_s": args.timeout_s,
        "concurrency": args.concurrency,
        "evaluator_version": "ask.eval.mgp6_v43.v1",
        "code_commit": run_config["code_commit"],
        "tracked_worktree_state": _tracked_worktree_state(),
        "runtime_hashes": {
            "runner": sha256_file(Path(__file__)),
            "evaluator_and_adapters": sha256_file("src/ask/eval/mgp6_v43.py"),
        },
        "environment_lock": environment_lock,
        "run_config": run_config,
        "run_config_hash": sha256_value(run_config),
        "n_selected": len(records),
        "complete": False,
        "hidden_gold_accessed": False,
        "hidden_run_authorized": args.hidden_input,
        "failure_count": 0,
        "retry_count": 0,
        "invalid_response_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "prediction_count": 0,
    }
    if args.dry_run:
        print(
            f"[mgp6-v43] public input={args.input} n={len(records)} "
            f"system={args.system} adapter={ADAPTER_VERSION} prompt_hash={prompt_hash}"
        )
        return 0
    immutable_resume_keys = (
        "release_version",
        "dataset_sha256",
        "system",
        "adapter_spec_hash",
        "provider",
        "model_id",
        "prompt_hash",
        "seed",
        "run_config_hash",
    )
    for key in immutable_resume_keys:
        if previous_manifest and previous_manifest.get(key) != manifest[key]:
            raise SystemExit(f"cannot resume: manifest {key} does not match current run")
    predictions_path, raw_path = args.out / "predictions.jsonl", args.out / "raw_responses.jsonl"
    args.out.mkdir(parents=True, exist_ok=True)
    existing_predictions = {
        prediction.public_id: prediction
        for prediction in (load_predictions_allow_partial(predictions_path) if predictions_path.exists() else [])
    }
    if args.action is not None:
        validate_system_action(args.system, args.action)
    static_action = args.action
    llm = None
    if static_action is None and args.system in MODEL_BACKED_SYSTEMS:
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
            extra_body=_openrouter_reasoning_body(args.reasoning_effort),
        )
    started = time.perf_counter()
    failures = int(previous_manifest.get("failure_count", 0))
    retries = int(previous_manifest.get("retry_count", 0))
    prompt_tokens = int(previous_manifest.get("prompt_tokens", 0))
    completion_tokens = int(previous_manifest.get("completion_tokens", 0))
    invalid_responses = int(previous_manifest.get("invalid_response_count", 0))
    for record in records:
        if record.public_id in existing_predictions:
            continue
        prompt = build_system_prompt(
            record,
            args.system,
            system_prompt,
            recency_turns=args.recency_turns,
        )
        call_started = time.perf_counter()
        try:
            action: str | None = None
            if static_action:
                raw = static_action
                action = validate_system_action(args.system, parse_action_response(raw))
                write_raw_response(
                    raw_path,
                    public_id=record.public_id,
                    raw_response=raw,
                    metadata={
                        "latency_ms": round((time.perf_counter() - call_started) * 1000, 3),
                        "parse_attempt": 0,
                        "valid_action": True,
                        "retry_count": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "adapter_version": ADAPTER_VERSION,
                        "system": args.system,
                    },
                )
            elif args.system == "rules_controller":
                action, rule_trace = rules_controller_action(record)
                action = validate_system_action(args.system, action)
                raw = json.dumps({"action": action}, separators=(",", ":"))
                write_raw_response(
                    raw_path,
                    public_id=record.public_id,
                    raw_response=raw,
                    metadata={
                        "latency_ms": round((time.perf_counter() - call_started) * 1000, 3),
                        "parse_attempt": 0,
                        "valid_action": True,
                        "retry_count": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "adapter_version": ADAPTER_VERSION,
                        "system": args.system,
                        "rule_trace": rule_trace,
                    },
                )
            else:
                last_error: MGP6V43Error | None = None
                for parse_attempt in range(max(1, args.parse_retry_max_attempts)):
                    attempt_prompt = (
                        prompt
                        if parse_attempt == 0
                        else f"{prompt}\n\n{_repair_instruction(allowed_actions)}"
                    )
                    response = llm.generate(  # type: ignore[union-attr]
                        attempt_prompt,
                        max_new_tokens=args.max_new_tokens,
                        temperature=args.temperature,
                        seed=args.seed,
                    )
                    prompt_tokens += int(response.prompt_tokens)
                    completion_tokens += int(response.completion_tokens)
                    raw = response.text
                    try:
                        action = validate_system_action(args.system, parse_action_response(raw))
                    except MGP6V43Error as exc:
                        last_error = exc
                        invalid_responses += 1
                        write_raw_response(
                            raw_path,
                            public_id=record.public_id,
                            raw_response=raw,
                            metadata={
                                **_raw_metadata(response=response, parse_attempt=parse_attempt, valid_action=False, error=str(exc)),
                                "adapter_version": ADAPTER_VERSION,
                                "system": args.system,
                            },
                        )
                        if parse_attempt + 1 >= max(1, args.parse_retry_max_attempts):
                            raise
                        retries += 1
                        continue
                    model_action = action
                    guard_trace: dict[str, Any] | None = None
                    if args.system == "live_model_controller":
                        action, guard_trace = apply_live_controller_guard(record, action)
                    write_raw_response(
                        raw_path,
                        public_id=record.public_id,
                        raw_response=raw,
                        metadata={
                            **_raw_metadata(response=response, parse_attempt=parse_attempt, valid_action=True),
                            "adapter_version": ADAPTER_VERSION,
                            "system": args.system,
                            "model_action": model_action,
                            "guard_trace": guard_trace,
                        },
                    )
                    break
                if action is None:
                    raise MGP6V43Error("response did not yield a valid action") from last_error
            write_prediction_resume_safe(predictions_path, MGP6V43Prediction.model_validate({"public_id": record.public_id, "action": action}))
        except Exception:
            failures += 1
            manifest.update(
                {
                    "complete": False,
                    "wall_clock_seconds": round(time.perf_counter() - started, 3),
                    "failure_count": failures,
                    "retry_count": retries,
                    "invalid_response_count": invalid_responses,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "prediction_count": len(load_predictions_allow_partial(predictions_path) if predictions_path.exists() else []),
                }
            )
            _write_manifest(manifest_path, manifest)
            raise
    predictions = load_predictions(predictions_path, (record.public_id for record in records))
    manifest.update({"complete": True, "prediction_sha256": sha256_file(predictions_path), "wall_clock_seconds": round(time.perf_counter() - started, 3), "failure_count": failures, "retry_count": retries, "invalid_response_count": invalid_responses, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "prediction_count": len(predictions)})
    _write_manifest(manifest_path, manifest)
    print(f"[mgp6-v43] wrote {predictions_path} ({len(predictions)} predictions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
