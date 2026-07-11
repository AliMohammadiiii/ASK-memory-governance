"""Run the M4-W13 LongMemEval systems with local Ollama models.

Default mode runs the five required systems once, using a shared answerer so
memory-system comparisons stay controlled. The requested local model pool is
validated before any run starts; `--model-sweep` can run the same five-system
suite once per answerer model when a broader local model comparison is desired.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import threading
import urllib.request
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUESTED_OLLAMA_MODELS: tuple[str, ...] = (
    "gemma4:e4b",
    "gemma4:e2b",
    "qwen3.5:9b",
    "llama3.2:3b",
    "phi3.5:3.8b",
    "phi4:14b",
)

BASELINES: tuple[tuple[str, str], ...] = (
    ("b1", "no_memory"),
    ("b2", "flat_vector"),
    ("b3", "recency"),
    ("b4", "naive_overwrite"),
    ("controller", "controller"),
)

_ACTIVE_SCORECARD_CONFIG = Path("configs/controller_active.yaml")
_QUALITY_PRESET_NONE = "none"
_QUALITY_PRESET_MAX_A10G = "max-a10g"
_QUALITY_PRESETS = (_QUALITY_PRESET_NONE, _QUALITY_PRESET_MAX_A10G)


@dataclass(frozen=True)
class ModelRoles:
    answerer: str = "gemma4:e4b"
    judge: str = "phi4:14b"
    embedder: str = "llama3.2:3b"
    recency_extractor: str = "llama3.2:3b"
    extractor: str = "llama3.2:3b"
    classifier: str = "phi3.5:3.8b"


@dataclass
class ShardJob:
    index: int
    cmd: list[str]
    process: subprocess.Popen[str]
    log_path: Path
    log_fp: Any
    stream_thread: threading.Thread


LIGHT_MODEL_ROLES = ModelRoles(
    answerer="llama3.2:3b",
    judge="phi3.5:3.8b",
    embedder="llama3.2:3b",
    recency_extractor="llama3.2:3b",
    extractor="llama3.2:3b",
    classifier="phi3.5:3.8b",
)

T4_MODEL_ROLES = ModelRoles(
    answerer="qwen3.5:9b",
    judge="phi3.5:3.8b",
    embedder="llama3.2:3b",
    recency_extractor="llama3.2:3b",
    extractor="llama3.2:3b",
    classifier="phi3.5:3.8b",
)

# Proposal-spec'd shared 7-8B model (Llama-3-8B-Instruct) for the roles under
# test: answering, extraction, recency extraction, relation classification.
# The retrieval embedder stays a small/MiniLM model (set --embedder-backend
# sentence_transformer for the proposal MiniLM); the judge stays phi3.5 as a
# DEV judge -- a same-tier local judge is development evidence (proposal Risk
# 11), so promote_lme_to_final.py will NOT stamp FINAL on a dev judge unless
# --allow-dev-judge is passed (which caps the tier at final-candidate).
THESIS_MODEL_ROLES = ModelRoles(
    answerer="llama3:8b",
    judge="phi3.5:3.8b",
    embedder="llama3.2:3b",
    recency_extractor="llama3:8b",
    extractor="llama3:8b",
    classifier="llama3:8b",
)

# The one profile permitted (on a full, non-synthetic run) to earn
# `final-candidate`. Keep in sync with run_mgp6.SPEC_PROFILE.
SPEC_PROFILE = "thesis"


def _explicitly_set_dests(
    parser: argparse.ArgumentParser, argv: list[str]
) -> set[str]:
    """Return the dest names whose option strings appear in ``argv``.

    Used so a quality preset overrides only the knobs the user did NOT pass.
    Crucially this recognises the ``--no-...`` form of a BooleanOptionalAction
    and a value that equals the argparse default (e.g.
    ``--controller-retrieval-neighbor-window 0``). The previous sentinel checks
    (``is False`` / ``== 0``) could not tell "left at default" from "explicitly
    set to the default value", so prompt-slim flags such as
    ``--no-controller-include-assistant-context`` were silently reverted.
    """
    opt_to_dest: dict[str, str] = {}
    for action in parser._actions:
        for opt in action.option_strings:
            opt_to_dest[opt] = action.dest
    seen: set[str] = set()
    for token in argv:
        key = token.split("=", 1)[0]  # tolerate --flag=value
        dest = opt_to_dest.get(key)
        if dest is not None:
            seen.add(dest)
    return seen


def _apply_t4_quality(
    args: argparse.Namespace, explicit: set[str] | None = None
) -> None:
    """Enable the validated accuracy knobs at T4-affordable levels.

    Only knobs the user did NOT pass explicitly are overridden, so an explicit
    flag on the command line always wins — including ``--no-...`` booleans and
    values equal to the argparse default. This is what lets the prompt-slim run
    pass ``--controller-retrieval-neighbor-window 0`` and
    ``--no-controller-include-assistant-context`` under ``--quality t4`` without
    them being reverted. ``explicit`` is the dest set from
    ``_explicitly_set_dests``; when None (older callers) nothing is treated as
    explicit, matching the previous "default-only override" intent.

    The relation-classifier similarity gate (0.45) is what keeps prior-top-k=3
    from tripling per-question latency: only genuinely-related priors reach the
    2-stage relation LLM.
    """
    if args.quality != "t4":
        return
    explicit = explicit or set()

    def _unset(dest: str) -> bool:
        return dest not in explicit

    if _unset("controller_include_assistant_context"):
        args.controller_include_assistant_context = True
    if _unset("answer_retry_on_unknown"):
        args.answer_retry_on_unknown = True
    if _unset("controller_prior_top_k"):
        args.controller_prior_top_k = 3
    if _unset("controller_prior_similarity_threshold"):
        args.controller_prior_similarity_threshold = 0.45
    if _unset("k"):
        args.k = 10
    if _unset("controller_retrieval_neighbor_window"):
        args.controller_retrieval_neighbor_window = 1
    if _unset("ollama_num_ctx"):
        # The quality prompts (assistant context + k=10 + neighbor window) reach
        # ~8k tokens; 8192 leaves no generation room, so go higher.
        args.ollama_num_ctx = 16384
    if _unset("controller_temporal_scaffold"):
        args.controller_temporal_scaffold = True
    if _unset("controller_computation_answerer"):
        args.controller_computation_answerer = True
    if _unset("controller_include_raw_user_context"):
        args.controller_include_raw_user_context = True
    if _unset("controller_retrieval_query_augmentation"):
        args.controller_retrieval_query_augmentation = True
    if _unset("controller_deterministic_numeric_supersede"):
        args.controller_deterministic_numeric_supersede = True


def _model_slug(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def _installed_ollama_models(host: str) -> set[str]:
    with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return {str(m.get("name") or m.get("model")) for m in payload.get("models", [])}


def _validate_models(host: str, models: list[str]) -> None:
    installed = _installed_ollama_models(host)
    missing = sorted(set(models) - installed)
    if missing:
        raise SystemExit(
            "Ollama is reachable, but these requested models are missing: "
            + ", ".join(missing)
        )


def _select_systems(value: str) -> list[tuple[str, str]]:
    if value == "all":
        return list(BASELINES)
    requested = {item.strip() for item in value.split(",") if item.strip()}
    selected = [
        (alias, baseline)
        for alias, baseline in BASELINES
        if alias in requested or baseline in requested
    ]
    known = {item for pair in BASELINES for item in pair}
    unknown = requested - known
    if unknown:
        raise SystemExit(f"unknown systems requested: {sorted(unknown)}")
    return selected


def _is_synthetic_slice(path: Path) -> bool:
    return "synthetic" in path.name.lower()


_DATASET_LABELS: dict[str, str] = {
    "s": "LongMemEval-S cleaned",
    "m": "LongMemEval-M cleaned",
    "synthetic": "synthetic smoke",
}


def _dataset_family(path: Path, override: str = "auto") -> str:
    """Resolve the dataset family ('s' | 'm' | 'synthetic') for the manifest.

    Honors an explicit --dataset override; otherwise infers it from the slice
    filename. Mislabeling a LongMemEval-M run as -S would silently corrupt the
    thesis provenance, so this is recorded explicitly in the manifest.
    """
    if override and override != "auto":
        return override
    name = path.name.lower()
    if "synthetic" in name:
        return "synthetic"
    if (
        "longmemeval_m" in name
        or "lme_m" in name
        or "_m_" in name
        or name.endswith("_m.jsonl")
        or name.endswith("_m.json")
    ):
        return "m"
    return "s"


def _command_for(
    *,
    baseline_alias: str,
    baseline: str,
    out_dir: Path,
    args: argparse.Namespace,
    roles: ModelRoles,
) -> list[str]:
    cmd = [
        sys.executable,
        "scripts/run_baseline.py",
        "--baseline",
        baseline,
        "--slice",
        str(args.slice),
        "--out",
        str(out_dir / baseline_alias),
        "--seed",
        str(args.seed),
        "--n-bootstrap",
        str(args.n_bootstrap),
        "--ollama",
        "--ollama-host",
        args.ollama_host,
        "--ollama-timeout-s",
        str(args.ollama_timeout_s),
        "--ollama-model",
        roles.answerer,
        "--judge-backend",
        "ollama",
        "--judge-model",
        roles.judge,
        "--judge-timeout-s",
        str(args.judge_timeout_s),
        "--embedder-backend",
        args.embedder_backend,
        "--k",
        str(args.k),
        "--ollama-num-ctx",
        str(args.ollama_num_ctx),
    ]
    cmd.append("--resume" if args.resume else "--no-resume")
    if args.embedder_backend == "ollama":
        cmd.extend(
            [
                "--embedder-ollama-model",
                roles.embedder,
                "--embedder-ollama-timeout-s",
                str(args.embedder_timeout_s or args.ollama_timeout_s),
                "--embedder-ollama-batch-size",
                str(args.embedder_batch_size),
            ]
        )
    else:
        cmd.extend(["--embedder-device", args.embedder_device])
    if args.limit is not None:
        cmd.extend(["--limit", str(args.limit)])
    if args.fake_embedder:
        cmd.append("--fake-embedder")

    if baseline == "recency":
        cmd.extend(
            [
                "--recency-extractor",
                "llm",
                "--extractor-ollama-model",
                roles.recency_extractor,
            ]
        )
        # Bound per-turn LLM extraction to the top-k question-relevant haystack
        # user turns. Without this the prefilter is disabled and B3 extracts
        # EVERY haystack turn sequentially — minutes per example, appearing to
        # hang. Matches the HF/A10G run paths which always set this.
        if args.recency_memory_top_k is not None:
            cmd.extend(["--recency-memory-top-k", str(args.recency_memory_top_k)])
    if baseline in {"naive_overwrite", "controller"}:
        cmd.extend(
            [
                "--extractor-ollama-model",
                roles.extractor,
                "--classifier-ollama-model",
                roles.classifier,
            ]
        )
        if args.controller_memory_top_k is not None:
            cmd.extend(
                ["--controller-memory-top-k", str(args.controller_memory_top_k)]
            )
        if args.controller_progress:
            cmd.append("--controller-progress")
        if args.controller_include_assistant_context:
            cmd.append("--controller-include-assistant-context")
        if args.controller_include_raw_user_context:
            cmd.append("--controller-include-raw-user-context")
        if args.controller_retrieval_query_augmentation:
            cmd.append("--controller-retrieval-query-augmentation")
        if args.controller_deterministic_numeric_supersede:
            cmd.append("--controller-deterministic-numeric-supersede")
        if args.answer_retry_on_unknown:
            cmd.append("--answer-retry-on-unknown")
        else:
            cmd.append("--no-answer-retry-on-unknown")
        cmd.append(
            "--controller-temporal-scaffold"
            if args.controller_temporal_scaffold
            else "--no-controller-temporal-scaffold"
        )
        cmd.append(
            "--controller-computation-answerer"
            if args.controller_computation_answerer
            else "--no-controller-computation-answerer"
        )
        cmd.extend(["--controller-prior-top-k", str(args.controller_prior_top_k)])
        cmd.extend(
            [
                "--controller-prior-similarity-threshold",
                str(args.controller_prior_similarity_threshold),
            ]
        )
        cmd.extend(
            [
                "--controller-retrieval-neighbor-window",
                str(args.controller_retrieval_neighbor_window),
            ]
        )
    return cmd


def _run(cmd: list[str], *, dry_run: bool, env: dict[str, str]) -> None:
    printable = _shell_join(cmd)
    if dry_run:
        print(printable)
        return
    print(f"\n$ {printable}", flush=True)
    subprocess.run(cmd, check=True, env=env)


def _shell_join(cmd: list[str]) -> str:
    return shlex.join(str(part) for part in cmd)


def _shard_cmd(base_cmd: list[str], shard_out: Path, k: int, n: int) -> list[str]:
    cmd = list(base_cmd)
    oi = cmd.index("--out")
    cmd[oi + 1] = str(shard_out)
    cmd += ["--num-shards", str(n), "--shard-index", str(k)]
    return cmd


def _stream_shard_output(job: ShardJob, *, baseline_alias: str) -> None:
    assert job.process.stdout is not None
    try:
        for line in job.process.stdout:
            job.log_fp.write(line)
            print(f"[{baseline_alias}:shard{job.index}] {line}", end="", flush=True)
    finally:
        try:
            job.log_fp.flush()
        except ValueError:
            pass


def _start_shard(
    *,
    index: int,
    cmd: list[str],
    env: dict[str, str],
    log_dir: Path,
    baseline_alias: str,
) -> ShardJob:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{baseline_alias}_shard{index}.log"
    log_fp = log_path.open("w", encoding="utf-8", buffering=1)
    log_fp.write("$ " + _shell_join(cmd) + "\n\n")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        bufsize=1,
    )
    job = ShardJob(
        index=index,
        cmd=cmd,
        process=process,
        log_path=log_path,
        log_fp=log_fp,
        stream_thread=threading.Thread(target=lambda: None),
    )
    job.stream_thread = threading.Thread(
        target=_stream_shard_output,
        kwargs={"job": job, "baseline_alias": baseline_alias},
        name=f"{baseline_alias}-shard{index}",
        daemon=True,
    )
    job.stream_thread.start()
    print(
        f"[m4w13] {baseline_alias}: launched shard {index} pid={process.pid} "
        f"log={log_path}",
        flush=True,
    )
    return job


def _log_tail(path: Path, *, lines: int) -> None:
    if lines <= 0 or not path.exists():
        return
    print(f"[m4w13] tail {path} ({lines} lines):", flush=True)
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in deque(fh, maxlen=lines):
            print(f"[m4w13:tail] {line}", end="", flush=True)


def _terminate_shards(jobs: dict[int, ShardJob]) -> None:
    for job in jobs.values():
        if job.process.poll() is None:
            print(
                f"[m4w13] terminating shard {job.index} pid={job.process.pid}",
                flush=True,
            )
            job.process.terminate()
    for job in jobs.values():
        try:
            job.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            print(
                f"[m4w13] forcing shard {job.index} pid={job.process.pid} to stop",
                flush=True,
            )
            job.process.kill()
    for job in jobs.values():
        job.stream_thread.join(timeout=5)
        try:
            job.log_fp.close()
        except ValueError:
            pass


def _wait_for_shards(
    *,
    baseline_alias: str,
    jobs: dict[int, ShardJob],
    tail_lines_on_failure: int,
) -> None:
    failures: list[tuple[int, int, Path]] = []
    try:
        while jobs:
            for index, job in list(jobs.items()):
                rc = job.process.poll()
                if rc is None:
                    continue
                job.stream_thread.join(timeout=5)
                job.log_fp.close()
                del jobs[index]
                if rc == 0:
                    print(
                        f"[m4w13] {baseline_alias}: shard {index} finished",
                        flush=True,
                    )
                    continue
                failures.append((index, rc, job.log_path))
                print(
                    f"[m4w13] {baseline_alias}: shard {index} FAILED rc={rc} "
                    f"log={job.log_path}",
                    flush=True,
                )
                _log_tail(job.log_path, lines=tail_lines_on_failure)
                _terminate_shards(jobs)
                break
            if failures:
                break
            threading.Event().wait(1.0)
    except KeyboardInterrupt:
        _terminate_shards(jobs)
        raise
    if failures:
        details = ", ".join(
            f"shard {index} rc={rc} log={log_path}"
            for index, rc, log_path in failures
        )
        raise RuntimeError(f"{baseline_alias}: shard failure: {details}")


def _run_system(
    *,
    baseline_alias: str,
    baseline: str,
    out_dir: Path,
    args: argparse.Namespace,
    roles: ModelRoles,
    env: dict[str, str],
) -> None:
    """Run one system, optionally as N parallel session shards then merge.

    Each shard is an independent run_baseline process over a disjoint round-robin
    session subset (its own sqlite/caches/action log), so per-session grades are
    identical to a serial run; only wall-clock changes. Requires the Ollama
    server to allow concurrent requests (start it with OLLAMA_NUM_PARALLEL>=workers).
    """
    base = _command_for(
        baseline_alias=baseline_alias, baseline=baseline, out_dir=out_dir, args=args, roles=roles
    )
    sys_out = out_dir / baseline_alias
    n = max(1, int(args.session_workers))
    if n <= 1:
        _run(base, dry_run=args.dry_run, env=env)
        return

    shard_dirs = [sys_out / f"_shard{k}" for k in range(n)]
    cmds = [_shard_cmd(base, shard_dirs[k], k, n) for k in range(n)]
    if args.dry_run:
        for c in cmds:
            print(" ".join(c))
        return

    print(
        f"\n[m4w13] {baseline_alias}: {n} parallel session shards "
        f"(OLLAMA_NUM_PARALLEL={env.get('OLLAMA_NUM_PARALLEL', 'server-default')})",
        flush=True,
    )
    log_dir = sys_out / "_logs"
    jobs = {
        k: _start_shard(
            index=k,
            cmd=cmd,
            env=env,
            log_dir=log_dir,
            baseline_alias=baseline_alias,
        )
        for k, cmd in enumerate(cmds)
    }
    _wait_for_shards(
        baseline_alias=baseline_alias,
        jobs=jobs,
        tail_lines_on_failure=args.tail_lines_on_failure,
    )

    if "src" not in sys.path:
        sys.path.insert(0, "src")
    from ksa.eval.merge import merge_run_shards

    meta = json.loads((shard_dirs[0] / "report.json").read_text(encoding="utf-8"))
    report = merge_run_shards(
        shard_dirs,
        sys_out,
        baseline_name=meta.get("baseline_name", baseline),
        judge_model_id=meta.get("judge_model_id", roles.judge),
        n_bootstrap=args.n_bootstrap,
        bootstrap_seed=args.seed,
    )
    print(
        f"[m4w13] {baseline_alias}: merged {n} shards -> "
        f"overall={report.overall_accuracy * 100:.1f}% (n={report.n_sessions})",
        flush=True,
    )


def _write_manifest(
    *,
    root: Path,
    args: argparse.Namespace,
    roles: ModelRoles,
    model_sweep: bool,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    # Tier guard: a run may only carry `final-candidate` if it is a full run
    # (no --limit), used the proposal-spec'd `thesis` profile, AND used a real
    # (non-synthetic) slice. Any other run is `development`/`smoke` and cannot
    # be promoted by scripts/promote_lme_to_final.py. This mirrors the MGP-6
    # guard and blocks the runs/m4w14 (3B mislabel) and synthetic-slice
    # (proposal Risk 13) traps at the same time.
    synthetic = _is_synthetic_slice(args.slice)
    dataset_family = _dataset_family(args.slice, getattr(args, "dataset", "auto"))
    is_spec_full = (args.limit is None and args.model_profile == SPEC_PROFILE and not synthetic)
    if args.limit is not None:
        tier = "smoke"
        thesis_use = "no_final_claim"
    elif is_spec_full:
        tier = "final-candidate"
        thesis_use = "final_candidate_pending_review"
    else:
        tier = "development"
        reason = "synthetic_slice" if synthetic else f"{args.model_profile}_profile"
        thesis_use = f"development_{reason}_NOT_for_final"
    payload = {
        "slice": str(args.slice),
        "dataset": _DATASET_LABELS[dataset_family],
        "dataset_family": dataset_family,
        "slice_is_synthetic": synthetic,
        "requested_ollama_models": list(REQUESTED_OLLAMA_MODELS),
        "roles": asdict(roles),
        "model_profile": args.model_profile,
        "spec_profile": SPEC_PROFILE,
        "is_spec_profile": args.model_profile == SPEC_PROFILE,
        "model_sweep": model_sweep,
        "systems": [alias for alias, _baseline in _select_systems(args.systems)],
        "seed": args.seed,
        "n_bootstrap": args.n_bootstrap,
        "limit": args.limit,
        "tier": tier,
        "run_tier": tier,
        # judge tier is "dev" for a small same-family local judge (proposal Risk
        # 11); the promotion gate treats this as not-final unless acknowledged.
        "judge_tier": "ollama",
        "judge_model": roles.judge,
        "raw_turn_fallback": False,
        "complete": False,
        "thesis_use": thesis_use,
        "scorecard_config": str(_ACTIVE_SCORECARD_CONFIG),
        "scorecard_config_sha256": _sha256(_ACTIVE_SCORECARD_CONFIG),
        "fake_embedder": args.fake_embedder,
        "embedder_backend": args.embedder_backend,
        "embedder_timeout_s": args.embedder_timeout_s or args.ollama_timeout_s,
        "embedder_batch_size": args.embedder_batch_size,
        "controller_progress": args.controller_progress,
        "controller_include_assistant_context": args.controller_include_assistant_context,
        "answer_retry_on_unknown": args.answer_retry_on_unknown,
        "controller_prior_top_k": args.controller_prior_top_k,
        "controller_prior_similarity_threshold": args.controller_prior_similarity_threshold,
        "controller_retrieval_neighbor_window": args.controller_retrieval_neighbor_window,
        "controller_temporal_scaffold": args.controller_temporal_scaffold,
        "controller_computation_answerer": args.controller_computation_answerer,
        "controller_include_raw_user_context": args.controller_include_raw_user_context,
        "controller_retrieval_query_augmentation": args.controller_retrieval_query_augmentation,
        "controller_deterministic_numeric_supersede": args.controller_deterministic_numeric_supersede,
        "retrieval_k": args.k,
        "ollama_num_ctx": args.ollama_num_ctx,
        "quality": args.quality,
        "quality_preset": args.quality_preset,
        "resume": args.resume,
        "ollama_timeout_s": args.ollama_timeout_s,
        "judge_timeout_s": args.judge_timeout_s,
    }
    (root / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mark_manifest_complete(root: Path) -> None:
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["complete"] = True
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--slice", type=Path, default=Path("data/longmemeval_s_synthetic.jsonl"))
    p.add_argument("--dataset", choices=("auto", "s", "m", "synthetic"), default="auto",
                   help="Dataset family for manifest provenance. 'auto' infers S "
                        "vs M from the slice filename; set explicitly for "
                        "non-standard slice names so an M run is never labeled S.")
    p.add_argument("--out", type=Path, default=Path("runs/m4w13"))
    p.add_argument("--ollama-host", default="http://localhost:11434")
    p.add_argument("--ollama-timeout-s", type=float, default=900.0)
    p.add_argument("--judge-timeout-s", type=float, default=900.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-bootstrap", type=int, default=1000)
    p.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True,
                   help="Resume interrupted per-shard run_baseline outputs from "
                        "answers.jsonl/judgments.jsonl instead of truncating.")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--quality-preset", choices=_QUALITY_PRESETS, default=_QUALITY_PRESET_NONE,
                   help="'max-a10g' is only supported by the HF/A10G runners; "
                        "this Ollama runner rejects it to avoid ambiguous "
                        "quality numbers.")
    p.add_argument("--systems", default="all",
                   help="Comma-separated aliases/baselines to run, e.g. "
                        "'b1', 'b2', 'controller', or 'all'.")
    p.add_argument("--embedder-device", default="cpu")
    p.add_argument("--embedder-backend", choices=("sentence_transformer", "ollama"),
                   default="ollama",
                   help="Retrieval embedding backend. Default ollama avoids local HF/ST crashes.")
    p.add_argument("--embedder-model", default=None,
                   help="Ollama model tag for retrieval embeddings. Defaults to the profile embedder.")
    p.add_argument("--embedder-timeout-s", type=float, default=None,
                   help="HTTP timeout for Ollama embedding calls. Defaults to --ollama-timeout-s.")
    p.add_argument("--embedder-batch-size", type=int, default=16)
    p.add_argument("--fake-embedder", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--model-sweep", action="store_true")
    p.add_argument("--model-profile", choices=("standard", "light", "t4", "thesis"), default="standard",
                   help="Use 'light' for 3B/3.8B. Use 't4' for qwen3.5:9b "
                        "answering, llama3.2 extraction, and phi3.5 judge/classifier.")
    p.add_argument("--answerer-model", default=None)
    p.add_argument("--judge-model", default=None)
    p.add_argument("--recency-extractor-model", default=None)
    p.add_argument("--extractor-model", default=None)
    p.add_argument("--classifier-model", default=None)
    p.add_argument("--controller-progress", action=argparse.BooleanOptionalAction, default=True,
                   help="Emit heartbeat logs for B4/controller inner work. "
                        "Enabled by default for Colab visibility; pass "
                        "--no-controller-progress for quieter logs.")
    p.add_argument("--recency-memory-top-k", type=int, default=32,
                   help="Prefilter cap for B3 LLM extraction: embed all allowed "
                        "haystack user turns and only extract the top-k most "
                        "question-relevant. Without it B3 extracts every haystack "
                        "turn sequentially (minutes/example). Pass 0 or a negative "
                        "value via the underlying flag to disable; matches the "
                        "HF/A10G run paths.")
    p.add_argument("--controller-memory-top-k", type=int, default=32,
                   help="Prefilter cap for B4/controller LLM extraction, mirroring "
                        "--recency-memory-top-k.")
    p.add_argument("--controller-include-assistant-context",
                   action=argparse.BooleanOptionalAction, default=False,
                   help="Add raw assistant turns to the controller/B4 retrieval pool "
                        "so assistant-stated answers (~32%% of the LongMemEval slice) "
                        "are reachable. Default off; validated runs are unchanged.")
    p.add_argument("--answer-retry-on-unknown", action=argparse.BooleanOptionalAction,
                   default=False,
                   help="Retry B4/controller answer generation once when the first "
                        "answer is exactly 'Unknown' and retrieved evidence is non-empty.")
    p.add_argument("--controller-prior-top-k", type=int, default=1,
                   help="Semantic same-type prior candidates for B4/controller. "
                        "Default 1 preserves newest-prior behavior.")
    p.add_argument("--controller-prior-similarity-threshold", type=float, default=0.0,
                   help="Minimum cosine similarity for a semantic prior to be sent to "
                        "the relation classifier (only used when "
                        "--controller-prior-top-k > 1). Priors below it are treated as "
                        "independent without an LLM call, bounding per-question latency "
                        "on a T4. 0.0 (default) preserves current behavior.")
    p.add_argument("--controller-retrieval-neighbor-window", type=int, default=0,
                   help="For B4/controller, append active memories within +/-N turn "
                        "indices of each retrieved hit to the answer prompt.")
    p.add_argument("--controller-temporal-scaffold", action=argparse.BooleanOptionalAction,
                   default=False,
                   help="Append parsed event dates + a reference 'today' to temporal "
                        "questions (additive; never overrides the model). On in --quality t4.")
    p.add_argument("--controller-computation-answerer", action=argparse.BooleanOptionalAction,
                   default=False,
                   help="Run deterministic date/numeric/list solvers before the "
                        "controller answer LLM. On in --quality t4.")
    p.add_argument("--controller-include-raw-user-context",
                   action=argparse.BooleanOptionalAction, default=False,
                   help="Add raw USER turn chunks from the allowed memory corpus to "
                        "the retrieval pool (recall safety net for facts the "
                        "extraction prefilter never selected). On in --quality t4.")
    p.add_argument("--controller-retrieval-query-augmentation",
                   action=argparse.BooleanOptionalAction, default=False,
                   help="Additive retrieval passes for aggregation/temporal "
                        "questions (widened query, per-entity queries, calendar "
                        "window). On in --quality t4.")
    p.add_argument("--controller-deterministic-numeric-supersede",
                   action=argparse.BooleanOptionalAction, default=False,
                   help="Route same-slot numeric conflicts directly to Supersede "
                        "without the relation LLM. On in --quality t4.")
    p.add_argument("--k", type=int, default=5,
                   help="Shared retrieval top-k for the answer prompt across all "
                        "systems. Kept equal across systems for a controlled "
                        "comparison (matches the max-a10g preset philosophy).")
    p.add_argument("--ollama-num-ctx", type=int, default=8192,
                   help="Answerer context window. Must exceed the answer prompt size "
                        "or Ollama truncates the prompt and returns a single token. "
                        "The t4 quality profile raises this to 16384 because assistant "
                        "context + k=10 + neighbor window can produce ~8k-token prompts.")
    p.add_argument("--quality", choices=("none", "t4"), default="none",
                   help="'t4' enables the validated accuracy knobs at T4-affordable "
                        "levels: assistant context, answer-retry, semantic prior "
                        "top-k=3 with a 0.45 similarity gate, retrieval k=10, and a "
                        "+/-1 neighbor window. Explicit flags still override it.")
    p.add_argument("--session-workers", type=int, default=1,
                   help="Parallel session shards per system (A100 speedup). >1 runs "
                        "N independent run_baseline processes over disjoint round-robin "
                        "session subsets, then merges. Per-session grades are identical "
                        "to serial. Start Ollama with OLLAMA_NUM_PARALLEL>=N so the "
                        "server actually serves the concurrent requests.")
    p.add_argument("--tail-lines-on-failure", type=int, default=160,
                   help="When a session shard fails, print this many lines from "
                        "that shard's log and stop the remaining shards.")
    argv = sys.argv[1:]
    args = p.parse_args(argv)
    _apply_t4_quality(args, _explicitly_set_dests(p, argv))
    if args.quality_preset == _QUALITY_PRESET_MAX_A10G:
        raise SystemExit(
            "--quality-preset max-a10g is HF-only. Use "
            "scripts/run_m4w13_a10g_sweep.py or scripts/run_m4w13_hf_a100_parallel.py."
        )

    if args.model_profile == "light":
        defaults = LIGHT_MODEL_ROLES
    elif args.model_profile == "t4":
        defaults = T4_MODEL_ROLES
    elif args.model_profile == "thesis":
        defaults = THESIS_MODEL_ROLES
    else:
        defaults = ModelRoles()
    roles = ModelRoles(
        answerer=args.answerer_model or defaults.answerer,
        judge=args.judge_model or defaults.judge,
        embedder=args.embedder_model or defaults.embedder,
        recency_extractor=args.recency_extractor_model or defaults.recency_extractor,
        extractor=args.extractor_model or defaults.extractor,
        classifier=args.classifier_model or defaults.classifier,
    )
    models_to_validate = set(asdict(roles).values())
    if args.model_sweep:
        models_to_validate |= set(REQUESTED_OLLAMA_MODELS)
    if not args.dry_run:
        _validate_models(args.ollama_host, sorted(models_to_validate))
    systems = _select_systems(args.systems)

    env = dict(os.environ)
    env["PYTHONPATH"] = "src" + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("PYTHONUNBUFFERED", "1")
    if args.session_workers > 1:
        # Hint for an Ollama server started from this same environment. If the
        # server is already running, (re)start it with OLLAMA_NUM_PARALLEL set;
        # this client-side env alone does not change a running server.
        env.setdefault("OLLAMA_NUM_PARALLEL", str(args.session_workers))
        env.setdefault("OLLAMA_MAX_LOADED_MODELS", "2")

    if _is_synthetic_slice(args.slice):
        print(
            "[m4w13] WARNING: slice path looks synthetic; results are not "
            "publication-eligible LongMemEval-S numbers.",
            flush=True,
        )

    if args.model_sweep:
        for answerer in REQUESTED_OLLAMA_MODELS:
            sweep_roles = ModelRoles(
                answerer=answerer,
                judge=roles.judge,
                embedder=roles.embedder,
                recency_extractor=roles.recency_extractor,
                extractor=roles.extractor,
                classifier=roles.classifier,
            )
            sweep_root = args.out / "by_answerer" / _model_slug(answerer)
            if not args.dry_run:
                _write_manifest(root=sweep_root, args=args, roles=sweep_roles, model_sweep=True)
            for alias, baseline in systems:
                _run_system(
                    baseline_alias=alias,
                    baseline=baseline,
                    out_dir=sweep_root,
                    args=args,
                    roles=sweep_roles,
                    env=env,
                )
            if not args.dry_run:
                _mark_manifest_complete(sweep_root)
        return 0

    if not args.dry_run:
        _write_manifest(root=args.out, args=args, roles=roles, model_sweep=False)
    for alias, baseline in systems:
        _run_system(
            baseline_alias=alias,
            baseline=baseline,
            out_dir=args.out,
            args=args,
            roles=roles,
            env=env,
        )
    if not args.dry_run:
        _mark_manifest_complete(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
