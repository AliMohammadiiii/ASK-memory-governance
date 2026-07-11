"""Role-based + cascade eval driver against OpenAI-compatible servers.

Execution model (the project standard for high throughput):

  * Models are served behind OpenAI-compatible HTTP APIs, NOT loaded in-process.
    Each system can be split into N independent session shards
    (run_baseline --num-shards N --shard-index k).
  * Because the shard processes are thin HTTP clients (no model weights), we can
    run many of them cheaply. Concurrency ≈ shards * systems-in-flight.
  * Per-session controller logic stays sequential (correct Supersede/Abstain
    ordering); concurrency comes from independent sessions, not from reordering
    one session.

Role routing (override endpoints/models as needed):
  extraction + primary relation -> fast server
  relation escalation           -> big/quality server (cascade)
  answerer                      -> big/quality server
  judge                         -> judge model on the big/quality endpoint

Example (OpenRouter):
  OPENROUTER_API_KEY=... python scripts/run_vllm_cascade.py \
    --slice data/slices/longmemeval_m_full.jsonl \
    --out runs/lme_m_openrouter_seed0 \
    --systems controller --shards 1
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASELINES: dict[str, str] = {
    "b1": "no_memory",
    "b2": "flat_vector",
    "b3": "recency",
    "b4": "naive_overwrite",
    "controller": "controller",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _python() -> str:
    return os.environ.get("KSA_PYTHON") or sys.executable


def _base_cmd(alias: str, baseline: str, out_dir: Path, args: argparse.Namespace) -> list[str]:
    """run_baseline command for one system, role-routed to the vLLM servers."""
    cmd = [
        _python(), "scripts/run_baseline.py",
        "--baseline", baseline,
        "--slice", str(args.slice),
        "--out", str(out_dir / alias),
        "--seed", str(args.seed),
        "--n-bootstrap", str(args.n_bootstrap),
        "--openai-compatible",
        # Answerer + (default) judge -> big/quality server.
        "--openai-base-url", args.big_base_url,
        "--openai-model", args.big_model,
        "--openai-api-key-env", args.openai_api_key_env,
        "--openai-timeout-s", str(args.openai_timeout_s),
        # Answerer context window used by the controller prompt-budgeter. At the
        # old 8192 default the controller trimmed ~70% of retrieved memory items
        # before the model saw them, causing false "Unknown" answers.
        "--openai-max-model-len", str(args.openai_max_model_len),
        "--resume",
    ]
    if args.enable_thinking:
        cmd += ["--openai-enable-thinking"]
    if args.openai_chat_template_kwargs_json:
        cmd += ["--openai-chat-template-kwargs-json", args.openai_chat_template_kwargs_json]
    if args.openai_extra_body_json:
        cmd += ["--openai-extra-body-json", args.openai_extra_body_json]
    if args.openmodel_primary:
        cmd += [
            "--openmodel-primary",
            "--openmodel-base-url", args.openmodel_base_url,
            "--openmodel-api-key-env", args.openmodel_api_key_env,
            "--openmodel-timeout-s", str(args.openmodel_timeout_s),
        ]
        if args.openmodel_api_key_envs:
            cmd += ["--openmodel-api-key-envs", args.openmodel_api_key_envs]
        if args.openmodel_model:
            cmd += ["--openmodel-model", args.openmodel_model]
    if args.openai_api_key:
        cmd += ["--openai-api-key", args.openai_api_key]
    if args.sample_from is not None:
        cmd += ["--sample-from", str(args.sample_from)]
    if args.sample_to is not None:
        cmd += ["--sample-to", str(args.sample_to)]
    if args.sample_start is not None:
        cmd += ["--sample-start", str(args.sample_start)]
    if args.sample_end is not None:
        cmd += ["--sample-end", str(args.sample_end)]
    # Embedder routing:
    #   --embed-base-url set  -> shared embedding server over HTTP (scales to
    #                            many shards; the jina model lives in ONE GPU
    #                            process, not in every shard). RECOMMENDED.
    #   otherwise             -> local sentence-transformers on --embedder-device
    #                            (CPU default; jina on CPU is slow for M).
    if args.embed_base_url:
        cmd += [
            "--embedder-backend", "openai_compatible",
            "--embedder-openai-model", args.embed_model,
            "--embedder-openai-base-url", args.embed_base_url,
            "--embedder-openai-batch-size", str(args.embed_batch_size),
        ]
    else:
        cmd += ["--embedder-backend", "sentence_transformer",
                "--embedder-device", args.embedder_device]
        if args.embedder_st_model:
            cmd += ["--embedder-st-model", args.embedder_st_model, "--embedder-trust-remote-code"]
            if args.embedder_task:
                cmd += ["--embedder-task", args.embedder_task]
    if baseline != "no_memory":
        cmd += ["--k", str(args.retrieval_k)]
    # Judge: route to the big server (final-candidate quality), unless asked to
    # reuse the answerer.
    if args.judge == "big":
        cmd += [
            "--judge-backend", "openai_compatible",
            "--judge-model", args.judge_model or args.big_model,
        ]
        if args.judge_openai_chat_template_kwargs_json:
            cmd += [
                "--judge-openai-chat-template-kwargs-json",
                args.judge_openai_chat_template_kwargs_json,
            ]
        if args.judge_openai_extra_body_json:
            cmd += [
                "--judge-openai-extra-body-json",
                args.judge_openai_extra_body_json,
            ]
        for fallback_model in args.judge_openai_fallback_model or []:
            cmd += ["--judge-openai-fallback-model", fallback_model]
        if getattr(args, "judge_openai_base_url", None):
            cmd += ["--judge-openai-base-url", args.judge_openai_base_url]
        if getattr(args, "judge_openai_api_key_env", None):
            cmd += ["--judge-openai-api-key-env", args.judge_openai_api_key_env]
    else:
        cmd += ["--judge-backend", "same_as_answerer"]
    if baseline in {"recency", "naive_overwrite", "controller"}:
        # Extraction on the 4B fast server.
        cmd += [
            "--extractor-openai-model", args.fast_model,
            "--extractor-openai-base-url", args.fast_base_url,
            "--extraction-max-new-tokens", str(args.extraction_max_new_tokens),
        ]
    if baseline in {"naive_overwrite", "controller"}:
        # Primary relation on 4B; escalation to 9B (cascade).
        cmd += [
            "--classifier-openai-model", args.fast_model,
            "--classifier-openai-base-url", args.fast_base_url,
            "--relation-max-new-tokens", str(args.relation_max_new_tokens),
            "--controller-memory-top-k", str(args.controller_memory_top_k),
            "--controller-retrieval-neighbor-window", "2",
            "--controller-prior-top-k", "3",
            "--controller-prior-similarity-threshold", "0.45",
            "--controller-include-assistant-context",
            "--controller-include-raw-user-context",
            "--controller-retrieval-query-augmentation",
            "--controller-deterministic-numeric-supersede",
            "--answer-retry-on-unknown",
            "--controller-temporal-scaffold",
            "--controller-computation-answerer",
            "--controller-progress",
            # §5 fix 1 + fix 3: concurrent extraction + shared content cache.
            "--extraction-concurrency", str(getattr(args, "extraction_concurrency", 1)),
        ]
        shared_cache = getattr(args, "shared_extraction_cache", None) or (
            out_dir / "_shared_extraction_cache.jsonl"
        )
        cmd += ["--shared-extraction-cache", str(shared_cache)]
        answer_escalation_model = getattr(args, "answer_escalation_model", None)
        if answer_escalation_model:
            cmd += [
                "--answer-escalation-openai-model",
                answer_escalation_model,
                "--answer-escalation-openai-base-url",
                getattr(args, "answer_escalation_base_url", None)
                or args.big_base_url,
            ]
        if getattr(args, "v7_fixes", False):
            # §4 fixes 1/4/5/6 + §5 fixes 4/6.
            cmd += [
                "--per-competency-answer-prompt",
                "--controller-verify-computation-bypass",
                "--controller-computation-bypass-min-confidence", "0.9",
                "--controller-ordinal-list-reconstruction",
                "--answer-context-rerank",
                "--answer-context-max-tokens", str(getattr(args, "answer_context_max_tokens", 12000)),
                "--prefilter-chunk-turns",
            ]
            # Preserve the exact v7 enumerator when v8 is explicitly disabled.
            # Its strat30 replay matched gold on only 2/11 aggregate questions,
            # so the v8 profile leaves it off pending a dedicated dev-set repair.
            if not getattr(args, "v8_fixes", False):
                cmd += ["--controller-aggregation-scaffold"]
        if getattr(args, "v8_fixes", False):
            cmd += [
                "--fail-on-extraction-error",
                "--controller-history-aware-retrieval",
                "--controller-history-retrieval-k",
                str(getattr(args, "history_retrieval_k", 4)),
                "--answer-context-session-cap",
                str(getattr(args, "answer_context_session_cap", 4)),
            ]
    if (
        baseline == "controller"
        and args.escalation
        and args.big_model != args.fast_model
    ):
        cmd += [
            "--classifier-escalation-openai-model", args.big_model,
            "--classifier-escalation-openai-base-url", args.big_base_url,
            "--escalation-extraction-confidence", str(args.escalation_extraction_confidence),
            "--escalation-marker-burden", str(args.escalation_marker_burden),
            "--escalation-relations", args.escalation_relations,
        ]
    if baseline == "recency":
        cmd += ["--recency-extractor", "llm", "--recency-memory-top-k", str(args.controller_memory_top_k)]
    return cmd


def _shard_cmd(base: list[str], shard_out: Path, k: int, n: int) -> list[str]:
    cmd = list(base)
    oi = cmd.index("--out")
    cmd[oi + 1] = str(shard_out)
    cmd += ["--num-shards", str(n), "--shard-index", str(k)]
    return cmd


def _looks_like_api_key(value: str) -> bool:
    return value.lower().startswith(("sk-", "sk_"))


def _command_for_log(cmd: list[str]) -> list[str]:
    redacted = list(cmd)
    for index, token in enumerate(cmd[:-1]):
        next_index = index + 1
        if token == "--openai-api-key":
            redacted[next_index] = "<redacted>"
        elif token in {"--openai-api-key-env", "--openmodel-api-key-env", "--openmodel-api-key-envs"}:
            if _looks_like_api_key(cmd[next_index]):
                redacted[next_index] = "<redacted>"
    return redacted


def _write_command_header(log_path: Path, cmd: list[str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        if log_path.stat().st_size:
            fh.write("\n")
        fh.write("$ ")
        fh.write(shlex.join(_command_for_log(cmd)))
        fh.write("\n\n")


def _run_logged(cmd: list[str], log_path: Path) -> None:
    _write_command_header(log_path, cmd)
    with log_path.open("a", encoding="utf-8") as fh:
        subprocess.run(
            cmd,
            check=True,
            env=os.environ.copy(),
            stdout=fh,
            stderr=subprocess.STDOUT,
        )


def _run_logged_with_retries(
    cmd: list[str],
    log_path: Path,
    *,
    retries: int,
    backoff_s: float,
) -> None:
    """Run one resumable shard, preserving every attempt in an append-only log."""
    retries = max(0, int(retries))
    for attempt in range(retries + 1):
        try:
            _run_logged(cmd, log_path)
            return
        except subprocess.CalledProcessError as exc:
            if attempt >= retries:
                raise
            delay = max(0.0, float(backoff_s)) * (2**attempt)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"\n[vllm-cascade] attempt {attempt + 1} failed "
                    f"(exit={exc.returncode}); retrying in {delay:.1f}s\n"
                )
            if delay:
                time.sleep(delay)


def _run_system(alias: str, baseline: str, out_dir: Path, args: argparse.Namespace) -> None:
    base = _base_cmd(alias, baseline, out_dir, args)
    sys_out = out_dir / alias
    log_dir = args.log_dir or (out_dir / "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    n = max(1, int(args.shards))
    if args.dry_run:
        for k in range(n):
            cmd = _shard_cmd(base, sys_out / f"_shard{k}", k, n) if n > 1 else base
            log_path = log_dir / (f"{alias}_shard{k}.log" if n > 1 else f"{alias}.log")
            print(f"# log: {log_path}")
            print(shlex.join(cmd))
        return
    if n == 1:
        log_path = log_dir / f"{alias}.log"
        print(f"[vllm-cascade] {alias}: running 1 client; log={log_path}", flush=True)
        _run_logged_with_retries(
            base,
            log_path,
            retries=args.shard_retries,
            backoff_s=args.shard_retry_backoff_s,
        )
        _merge_shared_extraction_cache(alias, baseline, [sys_out], out_dir, args)
        return
    shard_dirs = [sys_out / f"_shard{k}" for k in range(n)]
    cmds = [_shard_cmd(base, shard_dirs[k], k, n) for k in range(n)]
    print(
        f"[vllm-cascade] {alias}: {n} session-shard clients -> vLLM; "
        f"logs={log_dir}/{alias}_shard*.log",
        flush=True,
    )
    failures: list[tuple[int, str]] = []
    with ThreadPoolExecutor(max_workers=n) as ex:
        futs = {
            ex.submit(
                _run_logged_with_retries,
                c,
                log_dir / f"{alias}_shard{k}.log",
                retries=args.shard_retries,
                backoff_s=args.shard_retry_backoff_s,
            ): k
            for k, c in enumerate(cmds)
        }
        for fut in as_completed(futs):
            k = futs[fut]
            try:
                fut.result()
                print(f"[vllm-cascade] {alias}: shard {k}/{n} done", flush=True)
            except subprocess.CalledProcessError as exc:
                failures.append((k, f"exit={exc.returncode}; log={log_dir / f'{alias}_shard{k}.log'}"))
            except Exception as exc:  # noqa: BLE001
                failures.append((k, f"{exc}; log={log_dir / f'{alias}_shard{k}.log'}"))
    if failures:
        raise RuntimeError(f"{alias}: {len(failures)} shard(s) failed: {failures}")
    if "src" not in sys.path:
        sys.path.insert(0, "src")
    from ksa.eval.merge import merge_run_shards
    meta = json.loads((shard_dirs[0] / "report.json").read_text(encoding="utf-8"))
    report = merge_run_shards(
        shard_dirs, sys_out,
        baseline_name=meta.get("baseline_name", baseline),
        judge_model_id=meta.get("judge_model_id", args.big_model),
        n_bootstrap=args.n_bootstrap, bootstrap_seed=args.seed,
    )
    print(f"[vllm-cascade] {alias}: merged {n} shards -> "
          f"overall={report.overall_accuracy*100:.1f}% (n={report.n_sessions})", flush=True)
    _merge_shared_extraction_cache(alias, baseline, shard_dirs, out_dir, args)


def _merge_shared_extraction_cache(
    alias: str,
    baseline: str,
    shard_dirs: list[Path],
    out_dir: Path,
    args: argparse.Namespace,
) -> None:
    """Fold this system's per-shard extraction caches into the shared cache.

    §5 fix 3: run order is controller -> b4 -> b3 -> b2 -> b1, so once the
    controller finishes we append its (content-keyed) extractions to the shared
    file and b4 reads them at startup — the repeated haystack sessions are then
    extracted once across the whole run, not once per system. Keys already encode
    the model id + prompt fingerprint, so cross-system reuse is exact.
    """
    if baseline not in {"naive_overwrite", "controller"}:
        return
    shared = args.shared_extraction_cache or (out_dir / "_shared_extraction_cache.jsonl")
    shared.parent.mkdir(parents=True, exist_ok=True)
    existing: set[str] = set()
    if shared.exists():
        for line in shared.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                existing.add(json.loads(line)["key"])
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    added = 0
    with shared.open("a", encoding="utf-8") as out:
        for shard_dir in shard_dirs:
            cache_file = shard_dir / "extraction_cache.jsonl"
            if not cache_file.exists():
                continue
            for line in cache_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    key = json.loads(line)["key"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
                if key in existing:
                    continue
                existing.add(key)
                out.write(line + "\n")
                added += 1
    print(
        f"[vllm-cascade] {alias}: shared extraction cache += {added} entries "
        f"(total {len(existing)}) -> {shared}",
        flush=True,
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--slice", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--systems", default="controller")
    p.add_argument("--shards", type=int, default=10,
                   help="Session-shard client processes per system. Higher = more "
                        "concurrent requests for vLLM to batch. Match to vLLM "
                        "--max-num-seqs.")
    p.add_argument("--shard-retries", type=int, default=2,
                   help="Retries per failed shard before aborting the system.")
    p.add_argument("--shard-retry-backoff-s", type=float, default=5.0,
                   help="Base backoff in seconds between shard attempts.")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-bootstrap", type=int, default=1000)
    p.add_argument("--log-dir", type=Path, default=None,
                   help="Directory for per-system/per-shard subprocess logs. "
                        "Defaults to OUT/logs.")
    p.add_argument("--sample-from", type=int, default=None,
                   help="1-based inclusive first sample to evaluate, passed to run_baseline.")
    p.add_argument("--sample-to", type=int, default=None,
                   help="1-based inclusive last sample to evaluate, passed to run_baseline.")
    p.add_argument("--sample-start", type=int, default=None,
                   help="Zero-based inclusive start index, passed to run_baseline.")
    p.add_argument("--sample-end", type=int, default=None,
                   help="Zero-based exclusive end index, passed to run_baseline.")
    p.add_argument(
        "--fast-base-url",
        default="https://openrouter.ai/api/v1",
    )
    p.add_argument("--fast-model", default="qwen/qwen3.5-9b")
    p.add_argument(
        "--big-base-url",
        default="https://openrouter.ai/api/v1",
    )
    p.add_argument("--big-model", default="qwen/qwen3.5-9b")
    p.add_argument("--answer-escalation-base-url", default=None,
                   help="Endpoint for the stronger Unknown-answer retry. Defaults "
                        "to --big-base-url.")
    p.add_argument("--answer-escalation-model", default=None,
                   help="Stronger model used only when the first answer is Unknown.")
    p.add_argument("--judge", choices=("big", "same_as_answerer"), default="big")
    p.add_argument("--judge-model", default="google/gemma-4-31b-it",
                   help="OpenAI-compatible judge model id.")
    p.add_argument("--judge-openai-chat-template-kwargs-json", default=None,
                   help="JSON object passed as chat_template_kwargs only for "
                        "the OpenAI-compatible judge.")
    p.add_argument(
        "--judge-openai-extra-body-json",
        default=json.dumps(
            {
                "provider": {
                    "order": ["wandb", "venice"],
                    "only": ["wandb", "venice"],
                    "allow_fallbacks": True,
                },
                "reasoning": {"enabled": False},
            },
            separators=(",", ":"),
        ),
        help="JSON object merged into OpenAI-compatible judge request bodies.",
    )
    p.add_argument(
        "--judge-openai-fallback-model",
        action="append",
        default=None,
        help="Additional OpenAI-compatible judge model id passed through to run_baseline.",
    )
    p.add_argument("--judge-openai-base-url", default=None,
                   help="Endpoint for the OpenAI-compatible judge. Defaults to --openai-base-url.")
    p.add_argument("--judge-openai-api-key-env", default=None,
                   help="Environment variable containing the OpenAI-compatible Bearer token for the judge. "
                        "Defaults to --openai-api-key-env.")
    p.add_argument("--enable-thinking", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--escalation", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--escalation-extraction-confidence", type=float, default=0.75)
    p.add_argument("--escalation-marker-burden", type=float, default=0.35)
    p.add_argument("--escalation-relations", default="contradict,supersede,unclear")
    # 12 -> 16: distributed-answer questions (counts/sums over many sessions)
    # need more dense seeds; the 32K answer window has ample headroom (v4 run
    # averaged ~15K estimated prompt tokens at k=12).
    p.add_argument("--retrieval-k", type=int, default=16)
    p.add_argument("--controller-memory-top-k", type=int, default=64)
    # --- docx v7 fixes (§4 accuracy + §5 efficiency) --------------------------
    # On by default so the acceptance run applies the fixes; --no-v7-fixes
    # reproduces the pre-v7 (v6) behavior for A/B comparison.
    p.add_argument("--v7-fixes", action=argparse.BooleanOptionalAction, default=True,
                   help="Enable the docx v7 accuracy fixes (preference prompt, "
                        "verify-computation-bypass, ordinal reconstruction, "
                        "aggregation scaffold, context rerank, prefilter chunking) "
                        "for the B4/controller answer path.")
    p.add_argument("--v8-fixes", action=argparse.BooleanOptionalAction, default=True,
                   help="Overlay query-gated lineage retrieval, session-diverse "
                        "prompt trimming, and disable the unvalidated v7 aggregate "
                        "enumerator. Use --no-v8-fixes to reproduce v7.")
    p.add_argument("--history-retrieval-k", type=int, default=4)
    p.add_argument("--answer-context-session-cap", type=int, default=4)
    p.add_argument("--extraction-concurrency", type=int, default=8,
                   help="§5 fix 1: concurrent per-turn extraction calls within one "
                        "question (B4/controller). 1 = serial.")
    p.add_argument("--shared-extraction-cache", type=Path, default=None,
                   help="§5 fix 3: content-keyed extraction cache shared across "
                        "systems/ranges. Defaults to OUT/_shared_extraction_cache.jsonl.")
    p.add_argument("--answer-context-max-tokens", type=int, default=12000,
                   help="§5 fix 4: cap the B4/controller answer context at this many "
                        "tokens (0 disables; the num_ctx guard still applies).")
    # 256/128 truncated ~7% of these structured-JSON calls mid-object
    # (finish_reason=length), silently dropping the whole turn's extraction.
    p.add_argument("--extraction-max-new-tokens", type=int, default=512)
    p.add_argument("--relation-max-new-tokens", type=int, default=256)
    # Answerer context window (qwen3.5-9b supports 32k+). 8192 forced the
    # controller to discard most retrieved memory; 16384 keeps far more.
    p.add_argument("--openai-max-model-len", type=int, default=16384)
    p.add_argument("--openai-api-key", default=None,
                   help="Bearer token sent to OpenAI-compatible clients. Prefer "
                        "--openai-api-key-env so secrets are not written to "
                        "subprocess command logs.")
    p.add_argument("--openai-api-key-env", default="OPENROUTER_API_KEY",
                   help="Environment variable containing the OpenAI-compatible "
                        "Bearer token.")
    p.add_argument("--openai-timeout-s", type=float, default=300.0,
                   help="HTTP timeout for OpenAI-compatible model calls.")
    p.add_argument("--openai-chat-template-kwargs-json", default=None,
                   help="JSON object passed through to run_baseline as "
                        "chat_template_kwargs for OpenAI-compatible requests.")
    p.add_argument(
        "--openai-extra-body-json",
        default=json.dumps(
            {
                "provider": {
                    "order": ["venice", "deepinfra", "siliconflow"],
                    "only": ["venice", "deepinfra", "siliconflow"],
                    "allow_fallbacks": True,
                }
            },
            separators=(",", ":"),
        ),
        help="JSON object merged into OpenAI-compatible request bodies.",
    )
    p.add_argument("--openmodel-primary", action=argparse.BooleanOptionalAction, default=False,
                   help="Try OpenModel Messages API before the OpenAI-compatible "
                        "endpoint for answer/extractor/classifier calls.")
    p.add_argument("--openmodel-base-url", default="https://api.openmodel.ai/v1")
    p.add_argument("--openmodel-api-key-env", default="OPENMODEL_API_KEY")
    p.add_argument("--openmodel-api-key-envs", default=None)
    p.add_argument("--openmodel-model", default=None)
    p.add_argument("--openmodel-timeout-s", type=float, default=120.0)
    p.add_argument("--embed-base-url", default=None,
                   help="Shared embedding server endpoint (e.g. "
                        "http://localhost:8100/v1 from scripts/serve_embeddings.py). "
                        "When set, shards call it over HTTP instead of loading the "
                        "embedder locally — the scalable default for many shards.")
    p.add_argument("--embed-model", default="jina",
                   help="served-name of the model on the embedding server.")
    p.add_argument("--embed-batch-size", type=int, default=4)
    p.add_argument("--embedder-device", default="cpu",
                   help="Device for the sentence-transformers retriever. Default "
                        "CPU: when vLLM owns the GPU for the two LLM servers, "
                        "loading the embedder on GPU in EVERY shard process "
                        "exhausts VRAM (OOM). The embedder runs fine on the "
                        "64-core/128GB host and keeps shards GPU-free so you can "
                        "scale --shards freely.")
    p.add_argument("--embedder-st-model", default="jinaai/jina-embeddings-v5-text-nano")
    p.add_argument("--embedder-task", default="retrieval")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    os.chdir(_repo_root())
    args.out.mkdir(parents=True, exist_ok=True)
    selected = [s.strip() for s in args.systems.split(",") if s.strip()]
    unknown = [s for s in selected if s not in BASELINES]
    if unknown:
        raise SystemExit(f"unknown systems: {unknown}")
    for alias in selected:
        _run_system(alias, BASELINES[alias], args.out, args)
    print("[vllm-cascade] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
