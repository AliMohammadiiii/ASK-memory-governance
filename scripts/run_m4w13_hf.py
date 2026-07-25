"""Run M4-W13 systems with an in-process HuggingFace Transformers model.

This is the fast Colab path for controller debugging: it avoids Ollama HTTP
calls and model swapping by sharing one HF model instance across answerer,
extractor, classifier, and (by default) judge roles inside each baseline
process. Scores from the default same-model judge are useful for iteration, but
are not directly comparable to the Ollama phi3.5 judge reports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

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
_QUALITY_PRESET_MAX_A100_40GB = "max-a100-40gb"
_QUALITY_PRESETS = (
    _QUALITY_PRESET_NONE,
    _QUALITY_PRESET_MAX_A10G,
    _QUALITY_PRESET_MAX_A100_40GB,
)
_MAX_A10G_MODEL = "Qwen/Qwen2.5-7B-Instruct"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _preferred_python() -> str:
    override = os.environ.get("ASK_PYTHON")
    if override:
        return override
    for rel_path in (".venv/bin/python", "venv/bin/python"):
        candidate = _repo_root() / rel_path
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _required_modules(
    args: argparse.Namespace,
    systems: list[tuple[str, str]],
    *,
    include_prefetch: bool = False,
) -> list[str]:
    modules = ["torch", "transformers"]
    if include_prefetch:
        modules.append("huggingface_hub")
    if args.embedder_backend == "sentence_transformer" and not args.fake_embedder:
        modules.append("sentence_transformers")
    if any(baseline != "no_memory" for _alias, baseline in systems):
        modules.append("faiss")
    return sorted(set(modules))


def _check_python_environment(
    args: argparse.Namespace,
    systems: list[tuple[str, str]],
    *,
    include_prefetch: bool = False,
) -> None:
    if getattr(args, "dry_run", False):
        return
    modules = _required_modules(args, systems, include_prefetch=include_prefetch)
    code = (
        "import importlib.util, json, sys\n"
        "modules = json.loads(sys.argv[1])\n"
        "missing = [name for name in modules if importlib.util.find_spec(name) is None]\n"
        "print(json.dumps(missing))\n"
        "raise SystemExit(1 if missing else 0)\n"
    )
    python = _preferred_python()
    result = subprocess.run(
        [python, "-c", code, json.dumps(modules)],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        missing = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"could not verify Python environment with {python}: "
            f"rc={result.returncode} stderr={result.stderr.strip()}"
        ) from exc
    if result.returncode != 0 or missing:
        raise SystemExit(
            f"Python environment {python} is missing required modules: {', '.join(missing)}. "
            "Run deploy/colab_prepare.sh from the repo root, or set ASK_PYTHON to the prepared "
            "virtualenv interpreter."
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


def _apply_quality_preset(args: argparse.Namespace) -> None:
    preset = getattr(args, "quality_preset", _QUALITY_PRESET_NONE)
    if preset == _QUALITY_PRESET_NONE:
        return
    if preset not in {_QUALITY_PRESET_MAX_A10G, _QUALITY_PRESET_MAX_A100_40GB}:
        raise SystemExit(f"unknown quality preset {preset!r}")
    args.hf_model = _MAX_A10G_MODEL
    args.hf_dtype = "float16"
    args.hf_load_in_4bit = False
    if hasattr(args, "hf_max_seq_len"):
        args.hf_max_seq_len = max(int(args.hf_max_seq_len), 8192)
    args.retrieval_k = 12
    args.controller_memory_top_k = 64
    args.controller_raw_turn_fallback = True
    args.controller_include_raw_user_context = True
    args.controller_include_assistant_context = True
    args.controller_retrieval_query_augmentation = True
    args.controller_retrieval_neighbor_window = 2
    args.controller_deterministic_numeric_supersede = True
    args.extraction_max_new_tokens = 256
    args.relation_max_new_tokens = 128
    args.answer_retry_on_unknown = True
    args.controller_prior_top_k = 3
    args.controller_prior_similarity_threshold = 0.45
    args.controller_temporal_scaffold = True
    args.controller_computation_answerer = True
    if hasattr(args, "recency_memory_top_k"):
        args.recency_memory_top_k = 64
    if hasattr(args, "recency_raw_turn_fallback"):
        args.recency_raw_turn_fallback = True
    if preset == _QUALITY_PRESET_MAX_A10G and hasattr(args, "session_workers"):
        args.session_workers = 1
    if preset == _QUALITY_PRESET_MAX_A10G and hasattr(args, "max_workers"):
        args.max_workers = 1


_DATASET_LABELS: dict[str, str] = {
    "s": "LongMemEval-S cleaned",
    "m": "LongMemEval-M cleaned",
    "synthetic": "synthetic smoke",
}


def _dataset_family(path: Path) -> str:
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
) -> list[str]:
    cmd = [
        _preferred_python(),
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
        "--hf",
        "--hf-model",
        args.hf_model,
        "--hf-dtype",
        args.hf_dtype,
        "--hf-device-map",
        args.hf_device_map,
        "--hf-max-seq-len",
        str(args.hf_max_seq_len),
        "--embedder-backend",
        args.embedder_backend,
    ]
    if getattr(args, "quality_preset", _QUALITY_PRESET_NONE) != _QUALITY_PRESET_NONE:
        cmd.extend(["--quality-preset", args.quality_preset])
    if args.hf_load_in_4bit:
        cmd.append("--hf-load-in-4bit")
    if args.hf_trust_remote_code:
        cmd.append("--hf-trust-remote-code")
    _enable_thinking = getattr(args, "hf_enable_thinking", None)
    if _enable_thinking is True:
        cmd.append("--hf-enable-thinking")
    elif _enable_thinking is False:
        cmd.append("--no-hf-enable-thinking")
    cmd.append("--resume" if args.resume else "--no-resume")
    if args.limit is not None:
        cmd.extend(["--limit", str(args.limit)])
    if args.embedder_backend == "sentence_transformer":
        cmd.extend(["--embedder-device", args.embedder_device])
        if getattr(args, "embedder_st_model", None):
            cmd.extend(["--embedder-st-model", args.embedder_st_model])
        if getattr(args, "embedder_trust_remote_code", False):
            cmd.append("--embedder-trust-remote-code")
        if getattr(args, "embedder_task", None):
            cmd.extend(["--embedder-task", args.embedder_task])
        if getattr(args, "embedder_prompt_name", None):
            cmd.extend(["--embedder-prompt-name", args.embedder_prompt_name])
    elif args.embedder_backend == "ollama":
        cmd.extend(
            [
                "--embedder-ollama-model",
                args.embedder_ollama_model,
                "--embedder-ollama-host",
                args.ollama_host,
                "--embedder-ollama-timeout-s",
                str(args.embedder_timeout_s),
                "--embedder-ollama-batch-size",
                str(args.embedder_batch_size),
            ]
        )
    if args.fake_embedder:
        cmd.append("--fake-embedder")

    if baseline != "no_memory":
        cmd.extend(["--k", str(args.retrieval_k)])

    if args.judge_backend == "same_as_answerer":
        cmd.extend(["--judge-backend", "same_as_answerer"])
    else:
        if not args.judge_model and args.judge_backend != "fake":
            raise SystemExit(f"--judge-backend {args.judge_backend} requires --judge-model")
        cmd.extend(["--judge-backend", args.judge_backend])
        if args.judge_model:
            cmd.extend(["--judge-model", args.judge_model])
        if args.judge_backend == "ollama":
            cmd.extend(
                [
                    "--ollama-host",
                    args.ollama_host,
                    "--judge-timeout-s",
                    str(args.judge_timeout_s),
                ]
            )

    if baseline == "recency":
        cmd.extend(["--recency-extractor", "llm"])
        cmd.extend(["--extraction-max-new-tokens", str(args.extraction_max_new_tokens)])
        if args.recency_memory_top_k is not None:
            cmd.extend(["--recency-memory-top-k", str(args.recency_memory_top_k)])
        if args.recency_raw_turn_fallback:
            cmd.append("--recency-raw-turn-fallback")
        else:
            cmd.append("--no-recency-raw-turn-fallback")
        if args.recency_progress:
            cmd.append("--recency-progress")
        if args.extractor_model:
            cmd.extend(["--extractor-hf-model", args.extractor_model])
    if baseline in {"naive_overwrite", "controller"}:
        if args.extractor_model:
            cmd.extend(["--extractor-hf-model", args.extractor_model])
        if args.classifier_model:
            cmd.extend(["--classifier-hf-model", args.classifier_model])
        cmd.extend(["--extraction-max-new-tokens", str(args.extraction_max_new_tokens)])
        cmd.extend(["--relation-max-new-tokens", str(args.relation_max_new_tokens)])
        if args.controller_memory_top_k is not None:
            cmd.extend(["--controller-memory-top-k", str(args.controller_memory_top_k)])
        if args.controller_raw_turn_fallback:
            cmd.append("--controller-raw-turn-fallback")
        else:
            cmd.append("--no-controller-raw-turn-fallback")
        cmd.extend([
            "--controller-retrieval-neighbor-window",
            str(args.controller_retrieval_neighbor_window),
        ])
        if getattr(args, "controller_include_assistant_context", False):
            cmd.append("--controller-include-assistant-context")
        if getattr(args, "controller_include_raw_user_context", False):
            cmd.append("--controller-include-raw-user-context")
        if getattr(args, "controller_retrieval_query_augmentation", False):
            cmd.append("--controller-retrieval-query-augmentation")
        if getattr(args, "controller_deterministic_numeric_supersede", False):
            cmd.append("--controller-deterministic-numeric-supersede")
        if getattr(args, "answer_retry_on_unknown", False):
            cmd.append("--answer-retry-on-unknown")
        else:
            cmd.append("--no-answer-retry-on-unknown")
        cmd.extend([
            "--controller-prior-top-k",
            str(getattr(args, "controller_prior_top_k", 1)),
        ])
        cmd.extend([
            "--controller-prior-similarity-threshold",
            str(getattr(args, "controller_prior_similarity_threshold", 0.0)),
        ])
        cmd.append(
            "--controller-temporal-scaffold"
            if getattr(args, "controller_temporal_scaffold", False)
            else "--no-controller-temporal-scaffold"
        )
        cmd.append(
            "--controller-computation-answerer"
            if getattr(args, "controller_computation_answerer", False)
            else "--no-controller-computation-answerer"
        )
        if args.controller_progress:
            cmd.append("--controller-progress")
    return cmd


def _run(cmd: list[str], *, dry_run: bool, env: dict[str, str]) -> None:
    printable = " ".join(cmd)
    if dry_run:
        print(printable)
        return
    print(f"\n$ {printable}", flush=True)
    subprocess.run(cmd, check=True, env=env)


def _shard_cmd(base_cmd: list[str], shard_out: Path, k: int, n: int) -> list[str]:
    cmd = list(base_cmd)
    oi = cmd.index("--out")
    cmd[oi + 1] = str(shard_out)
    cmd += ["--num-shards", str(n), "--shard-index", str(k)]
    return cmd


def _run_system(
    *, baseline_alias: str, baseline: str, out_dir: Path, args: argparse.Namespace, env: dict
) -> None:
    """Run one HF system, optionally as N parallel session shards then merge.

    NOTE: each shard is a separate process that loads its OWN copy of the HF
    model into GPU memory. On a single A100 (80 GB) an 8B fp16 model is ~16 GB,
    so 2-3 shards is the practical ceiling (use --hf-load-in-4bit for more).
    Per-session grades are identical to a serial run; only wall-clock changes.
    """
    base = _command_for(baseline_alias=baseline_alias, baseline=baseline, out_dir=out_dir, args=args)
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

    print(f"\n[m4w13-hf] {baseline_alias}: {n} parallel session shards (own model copy each)", flush=True)
    failures: list[tuple[int, str]] = []
    with ThreadPoolExecutor(max_workers=n) as ex:
        futs = {ex.submit(subprocess.run, c, check=True, env=env): k for k, c in enumerate(cmds)}
        for fut in as_completed(futs):
            k = futs[fut]
            try:
                fut.result()
            except Exception as exc:  # noqa: BLE001
                failures.append((k, str(exc)))
    if failures:
        raise RuntimeError(f"{baseline_alias}: {len(failures)} shard(s) failed: {failures}")

    if "src" not in sys.path:
        sys.path.insert(0, "src")
    from ask.eval.merge import merge_run_shards

    meta = json.loads((shard_dirs[0] / "report.json").read_text(encoding="utf-8"))
    report = merge_run_shards(
        shard_dirs, sys_out,
        baseline_name=meta.get("baseline_name", baseline),
        judge_model_id=meta.get("judge_model_id", args.judge_model or args.hf_model),
        n_bootstrap=args.n_bootstrap, bootstrap_seed=args.seed,
    )
    print(f"[m4w13-hf] {baseline_alias}: merged {n} shards -> overall={report.overall_accuracy*100:.1f}% (n={report.n_sessions})", flush=True)


def _write_manifest(args: argparse.Namespace, systems: list[tuple[str, str]]) -> None:
    args.out.mkdir(parents=True, exist_ok=True)
    tier = "pilot" if args.judge_backend == "same_as_answerer" or args.limit is not None else "final-candidate"
    dataset_family = _dataset_family(args.slice)
    payload = {
        "backend": "huggingface",
        "slice": str(args.slice),
        "dataset": _DATASET_LABELS[dataset_family],
        "dataset_family": dataset_family,
        "systems": [alias for alias, _baseline in systems],
        "hf_model": args.hf_model,
        "judge_model": args.judge_model,
        "extractor_model": args.extractor_model or args.hf_model,
        "classifier_model": args.classifier_model or args.hf_model,
        "hf_dtype": args.hf_dtype,
        "hf_device_map": args.hf_device_map,
        "hf_load_in_4bit": args.hf_load_in_4bit,
        "hf_max_seq_len": args.hf_max_seq_len,
        "quality_preset": args.quality_preset,
        "judge_backend": args.judge_backend,
        "embedder_backend": args.embedder_backend,
        "embedder_device": args.embedder_device,
        "retrieval_k": args.retrieval_k,
        "seed": args.seed,
        "n_bootstrap": args.n_bootstrap,
        "limit": args.limit,
        "tier": tier,
        "run_tier": tier,
        "judge_tier": "same_as_answerer" if args.judge_backend == "same_as_answerer" else args.judge_backend,
        "raw_turn_fallback": bool(args.controller_raw_turn_fallback or args.recency_raw_turn_fallback),
        "complete": False,
        "thesis_use": "no_final_claim" if tier != "final-candidate" else "final_candidate_pending_review",
        "scorecard_config": str(_ACTIVE_SCORECARD_CONFIG),
        "scorecard_config_sha256": _sha256(_ACTIVE_SCORECARD_CONFIG),
        "resume": args.resume,
        "controller_progress": args.controller_progress,
        "controller_memory_top_k": args.controller_memory_top_k,
        "controller_raw_turn_fallback": args.controller_raw_turn_fallback,
        "controller_retrieval_neighbor_window": args.controller_retrieval_neighbor_window,
        "controller_include_assistant_context": args.controller_include_assistant_context,
        "controller_include_raw_user_context": args.controller_include_raw_user_context,
        "controller_retrieval_query_augmentation": args.controller_retrieval_query_augmentation,
        "controller_deterministic_numeric_supersede": args.controller_deterministic_numeric_supersede,
        "answer_retry_on_unknown": args.answer_retry_on_unknown,
        "controller_prior_top_k": args.controller_prior_top_k,
        "controller_prior_similarity_threshold": args.controller_prior_similarity_threshold,
        "controller_temporal_scaffold": args.controller_temporal_scaffold,
        "controller_computation_answerer": args.controller_computation_answerer,
        "recency_memory_top_k": args.recency_memory_top_k,
        "recency_raw_turn_fallback": args.recency_raw_turn_fallback,
        "recency_progress": args.recency_progress,
        "extraction_max_new_tokens": args.extraction_max_new_tokens,
        "relation_max_new_tokens": args.relation_max_new_tokens,
        "python": _preferred_python(),
        "note": (
            "Default same_as_answerer judge is intended for fast iteration; "
            "it is not directly comparable to Ollama phi3.5 judged reports."
        ),
    }
    (args.out / "manifest.json").write_text(
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
    p.add_argument("--slice", type=Path, default=Path("/content/longmemeval/longmemeval_s_cleaned.json"))
    p.add_argument("--out", type=Path, default=Path("runs/m4w13_hf"))
    p.add_argument("--systems", default="all")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-bootstrap", type=int, default=1000)
    p.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True,
                   help="Resume interrupted per-system runs from existing "
                        "answers/judgments instead of truncating progress.")
    p.add_argument("--quality-preset", choices=_QUALITY_PRESETS, default=_QUALITY_PRESET_NONE,
                   help="Lock an accuracy-first runtime profile. 'max-a10g' "
                        "forces Qwen2.5-7B fp16, serial workers, and controller "
                        "quality knobs. 'max-a100-40gb' uses the same quality "
                        "knobs without forcing the worker count.")
    p.add_argument("--hf-model", default="Qwen/Qwen2.5-3B-Instruct")
    p.add_argument("--judge-backend", choices=("same_as_answerer", "hf", "huggingface", "ollama", "fake"),
                   default="same_as_answerer")
    p.add_argument("--judge-model", default=None,
                   help="Optional judge model. Omit to share --hf-model as judge.")
    p.add_argument("--extractor-model", default=None,
                   help="Optional separate HF extractor model. Omit to share --hf-model.")
    p.add_argument("--classifier-model", default=None,
                   help="Optional separate HF classifier model. Omit to share --hf-model.")
    p.add_argument("--hf-dtype", choices=("bfloat16", "float16", "float32"), default="float16")
    p.add_argument("--hf-device-map", default="auto")
    p.add_argument("--hf-load-in-4bit", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--hf-trust-remote-code", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--hf-max-seq-len", type=int, default=4096)
    p.add_argument("--hf-enable-thinking", action=argparse.BooleanOptionalAction, default=None,
                   help="Chat-template thinking switch for reasoning models "
                        "(Qwen3/Qwen3.5). --no-hf-enable-thinking suppresses "
                        "<think> blocks. Default unset = leave template alone.")
    p.add_argument("--embedder-backend", choices=("sentence_transformer", "ollama"),
                   default="sentence_transformer")
    p.add_argument("--embedder-device", default="auto",
                   help="Device for sentence-transformer embeddings: auto, cpu, cuda, "
                        "or cuda:N. Default auto uses CUDA only when the installed "
                        "torch build reports torch.cuda.is_available().")
    p.add_argument("--embedder-st-model", default=None,
                   help="Override the sentence-transformers retrieval model id "
                        "(e.g. jinaai/jina-embeddings-v5-text-small).")
    p.add_argument("--embedder-trust-remote-code", action="store_true",
                   help="trust_remote_code=True for the ST embedder (Jina v5).")
    p.add_argument("--embedder-task", default=None,
                   help="encode() task for task-aware embedders (Jina v5: retrieval).")
    p.add_argument("--embedder-prompt-name", default=None,
                   help="encode() prompt_name for task-aware embedders (Jina v5).")
    p.add_argument("--fake-embedder", action="store_true")
    p.add_argument("--ollama-host", default="http://127.0.0.1:11434",
                   help="Used if --embedder-backend ollama or --judge-backend ollama.")
    p.add_argument("--judge-timeout-s", type=float, default=1800.0)
    p.add_argument("--embedder-ollama-model", default="llama3.2:3b")
    p.add_argument("--embedder-timeout-s", type=float, default=1800.0)
    p.add_argument("--embedder-batch-size", type=int, default=16)
    p.add_argument("--retrieval-k", type=int, default=5,
                   help="Top-k retrieval depth for memory systems. Forwarded "
                        "to run_baseline.py --k for b2/b3/b4/controller.")
    p.add_argument("--controller-progress", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--controller-memory-top-k", type=int, default=32,
                   help="Fast-mode prefilter for B4/controller. The runner embeds "
                        "all allowed haystack user turns on GPU, then sends only "
                        "the top-k turns through expensive LLM extraction. Use 0 "
                        "or omit the flag in run_baseline.py for exact full "
                        "controller ingestion.")
    p.add_argument("--controller-raw-turn-fallback", action=argparse.BooleanOptionalAction,
                   default=True,
                   help="When a selected turn yields no structured extraction, "
                        "index the raw user turn as an episodic memory. Default "
                        "true for fast Colab HF runs because small local models "
                        "under-extract LongMemEval answer facts.")
    p.add_argument("--controller-retrieval-neighbor-window", type=int, default=0,
                   help="Append same-session memories within +/-N turn indices "
                        "of each retrieved hit to the answer prompt. Default 0 "
                        "keeps fast runs focused; raise only for targeted "
                        "multi-turn diagnostics.")
    p.add_argument("--controller-include-assistant-context",
                   action=argparse.BooleanOptionalAction, default=False,
                   help="Add chunked assistant turns to the controller/B4 retrieval "
                        "pool so assistant-stated answers are reachable. Default off.")
    p.add_argument("--controller-include-raw-user-context",
                   action=argparse.BooleanOptionalAction, default=False,
                   help="Add raw user turn chunks to the controller/B4 retrieval "
                        "pool so facts missed by structured extraction remain "
                        "reachable at answer time.")
    p.add_argument("--controller-retrieval-query-augmentation",
                   action=argparse.BooleanOptionalAction, default=False,
                   help="Run additive retrieval passes for aggregation and temporal "
                        "questions before the controller/B4 answer prompt is built.")
    p.add_argument("--controller-deterministic-numeric-supersede",
                   action=argparse.BooleanOptionalAction, default=False,
                   help="Route same-slot numeric conflicts to Supersede without a "
                        "relation-classifier LLM call when the deterministic gate "
                        "is confident.")
    p.add_argument("--answer-retry-on-unknown", action=argparse.BooleanOptionalAction,
                   default=False,
                   help="Retry B4/controller answer generation once when the first "
                        "answer is exactly 'Unknown' and retrieved evidence is non-empty.")
    p.add_argument("--controller-prior-top-k", type=int, default=1,
                   help="Semantic same-type prior candidates for B4/controller. "
                        "Default 1 preserves newest-prior behavior.")
    p.add_argument("--controller-prior-similarity-threshold", type=float, default=0.0,
                   help="Minimum cosine similarity for semantic priors when "
                        "--controller-prior-top-k > 1.")
    p.add_argument("--controller-temporal-scaffold", action=argparse.BooleanOptionalAction,
                   default=False,
                   help="Append parsed event dates + a reference date to temporal "
                        "controller questions.")
    p.add_argument("--controller-computation-answerer", action=argparse.BooleanOptionalAction,
                   default=False,
                   help="Run deterministic date/numeric/list solvers before the "
                        "controller answer LLM.")
    p.add_argument("--session-workers", type=int, default=1,
                   help="Parallel session shards per system. Each shard is a separate "
                        "process that loads its OWN HF model copy into GPU memory, so "
                        "2-3 is the practical ceiling for an 8B model on one A100 "
                        "(use --hf-load-in-4bit for more). Merged result == serial.")
    p.add_argument("--recency-progress", action=argparse.BooleanOptionalAction, default=True,
                   help="Emit B3 recency heartbeat logs during fast HF runs.")
    p.add_argument("--recency-memory-top-k", type=int, default=32,
                   help="Fast-mode prefilter for B3 recency when using the M2 "
                        "LLM extractor. Mirrors --controller-memory-top-k so "
                        "B3 does not full-ingest every haystack turn in Colab.")
    p.add_argument("--recency-raw-turn-fallback", action=argparse.BooleanOptionalAction,
                   default=True,
                   help="When a selected B3 turn yields no structured extraction, "
                        "index the raw user turn as an episodic memory.")
    p.add_argument("--extraction-max-new-tokens", type=int, default=192,
                   help="Structured extraction token cap. Lower default keeps "
                        "Colab/T4 HF runs moving; raise for exact diagnostics.")
    p.add_argument("--relation-max-new-tokens", type=int, default=96,
                   help="Structured relation-classifier token cap for B4/controller.")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    _apply_quality_preset(args)

    systems = _select_systems(args.systems)
    if not args.dry_run:
        _check_python_environment(args, systems)
        _write_manifest(args, systems)

    env = dict(os.environ)
    env["PYTHONPATH"] = "src" + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("TOKENIZERS_PARALLELISM", "false")

    for alias, baseline in systems:
        _run_system(
            baseline_alias=alias,
            baseline=baseline,
            out_dir=args.out,
            args=args,
            env=env,
        )
    if not args.dry_run:
        _mark_manifest_complete(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
