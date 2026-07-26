"""Run all M4-W13 HF systems concurrently on an A100-class Colab runtime.

This runner is intentionally separate from ``run_m4w13_hf.py``: that script is
serial and good for T4 debugging, while this one starts one subprocess per
system so b1, b2, b3, b4, and controller can all make progress at once on an
A100. Each subprocess still owns its output directory, cache files, and logs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from m4w13_validation import has_output_artifacts, validate_run_dir
from run_m4w13_hf import (
    _QUALITY_PRESET_NONE,
    _QUALITY_PRESETS,
    _apply_quality_preset,
    _check_python_environment,
    _command_for,
    _preferred_python,
    _select_systems,
    _write_manifest,
)

_DEFAULT_EMBEDDER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class RunningJob:
    alias: str
    baseline: str
    cmd: list[str]
    process: subprocess.Popen[str]
    log_path: Path
    log_fp: Any
    stream_thread: threading.Thread
    started_at: float
    last_status_at: float = 0.0


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(message: str) -> None:
    print(f"[{_timestamp()}] [a100-runner] {message}", flush=True)


def _shell_join(cmd: list[str]) -> str:
    return shlex.join(str(part) for part in cmd)


def _base_env(args: argparse.Namespace) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src" + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    # On a many-core box (e.g. 64 cores) each of the `max_workers` heavy
    # subprocesses otherwise spins up one OMP/MKL/BLAS thread *per core*, so two
    # concurrent 7B processes contend for 128 threads on 64 cores and lose
    # wall-clock to scheduler thrash on the CPU-side work (tokenization,
    # embedding, numpy). Give each worker a fair, non-overlapping slice. Respect
    # an explicit operator override.
    cpu_total = os.cpu_count() or 1
    workers = max(1, int(getattr(args, "max_workers", 1) or 1))
    per_worker_threads = max(1, cpu_total // workers)
    for var in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        env.setdefault(var, str(per_worker_threads))
    # Tight 40GB card with two model copies: fragmentation across long-lived
    # allocations is the usual cause of a late-run CUDA OOM. Expandable segments
    # let the allocator give memory back between the answer/extract/judge phases.
    env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    if args.cuda_visible_devices:
        env["CUDA_VISIBLE_DEVICES"] = args.cuda_visible_devices
    return env


def _log_configuration(args: argparse.Namespace, systems: list[tuple[str, str]]) -> None:
    visible = args.cuda_visible_devices or os.environ.get("CUDA_VISIBLE_DEVICES") or "all"
    _log("configuration:")
    _log(f"  systems={','.join(alias for alias, _baseline in systems)}")
    _log(f"  slice={args.slice}")
    _log(f"  out={args.out}")
    _log(f"  limit={args.limit}")
    _log(f"  resume={args.resume}")
    _log(f"  max_workers={args.max_workers}")
    _log(f"  quality_preset={args.quality_preset}")
    _log(f"  hf_model={args.hf_model}")
    _log(f"  judge_backend={args.judge_backend}")
    _log(f"  embedder_backend={args.embedder_backend}")
    _log(f"  embedder_device={args.embedder_device}")
    _log(f"  retrieval_k={args.retrieval_k}")
    _log(f"  controller_memory_top_k={args.controller_memory_top_k}")
    _log(f"  controller_raw_turn_fallback={args.controller_raw_turn_fallback}")
    _log(f"  controller_retrieval_neighbor_window={args.controller_retrieval_neighbor_window}")
    _log(f"  controller_include_assistant_context={args.controller_include_assistant_context}")
    _log(f"  controller_include_raw_user_context={args.controller_include_raw_user_context}")
    _log(
        f"  controller_retrieval_query_augmentation={args.controller_retrieval_query_augmentation}"
    )
    _log(
        f"  controller_deterministic_numeric_supersede={args.controller_deterministic_numeric_supersede}"
    )
    _log(f"  answer_retry_on_unknown={args.answer_retry_on_unknown}")
    _log(f"  controller_prior_top_k={args.controller_prior_top_k}")
    _log(f"  controller_prior_similarity_threshold={args.controller_prior_similarity_threshold}")
    _log(f"  controller_temporal_scaffold={args.controller_temporal_scaffold}")
    _log(f"  controller_computation_answerer={args.controller_computation_answerer}")
    _log(f"  recency_memory_top_k={args.recency_memory_top_k}")
    _log(f"  recency_raw_turn_fallback={args.recency_raw_turn_fallback}")
    _log(f"  recency_progress={args.recency_progress}")
    _log(f"  cuda_visible_devices={visible}")
    _log(f"  require_a100={args.require_a100}")
    _log(f"  stream_logs={args.stream_logs}")
    _log(f"  status_s={args.status_s}")
    _log(f"  clean_incomplete={args.clean_incomplete}")


def _log_system_state(args: argparse.Namespace) -> None:
    if args.dry_run:
        _log("dry-run: skipping runtime system checks")
        return
    _log(f"launcher_python={sys.executable}")
    _log(f"run_python={_preferred_python()}")
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log(f"nvidia-smi unavailable: {type(exc).__name__}: {exc}")
        return
    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            _log(f"nvidia-smi | {line}")
    if result.stderr.strip():
        for line in result.stderr.strip().splitlines():
            _log(f"nvidia-smi stderr | {line}")


def _validate_inputs(args: argparse.Namespace) -> None:
    if args.dry_run:
        _log("dry-run: skipping input existence checks")
        return
    _log("checking inputs")
    if not args.slice.exists():
        raise SystemExit(f"slice file not found: {args.slice}")
    size_mib = args.slice.stat().st_size / (1024**2)
    _log(f"slice exists: {args.slice} ({size_mib:.1f} MiB)")


def _check_a100(args: argparse.Namespace) -> None:
    if args.dry_run:
        return
    code = (
        "import json, torch\n"
        "if not torch.cuda.is_available():\n"
        "    print(json.dumps({'available': False}))\n"
        "    raise SystemExit(2)\n"
        "props = torch.cuda.get_device_properties(0)\n"
        "print(json.dumps({\n"
        "    'available': True,\n"
        "    'name': torch.cuda.get_device_name(0),\n"
        "    'total_gb': props.total_memory / (1024 ** 3),\n"
        "}))\n"
    )
    result = subprocess.run(
        [_preferred_python(), "-c", code],
        check=False,
        capture_output=True,
        env=_base_env(args),
        text=True,
    )
    try:
        info = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"could not inspect CUDA with {_preferred_python()}: "
            f"rc={result.returncode} stderr={result.stderr.strip()}"
        ) from exc
    if result.returncode != 0 or not info.get("available"):
        raise SystemExit("CUDA is not available; switch the Colab runtime to a GPU first")
    device_idx = int((args.cuda_visible_devices or "0").split(",")[0])
    name = str(info["name"])
    total_gb = float(info["total_gb"])
    _log(f"CUDA device={device_idx} name={name!r} memory={total_gb:.1f}GB")
    if args.require_a100 and "A100" not in name.upper():
        raise SystemExit(
            f"CUDA device is {name!r}, not an A100. Pass --no-require-a100 only "
            "if you intentionally want to run on this GPU."
        )
    if args.require_a100:
        _log("A100/CUDA check passed")
    else:
        _log("CUDA check passed; A100 requirement disabled")


def _prefetch_models(args: argparse.Namespace) -> None:
    if args.dry_run or args.no_prefetch:
        _log("model prefetch skipped")
        return

    model_ids = {args.hf_model}
    for model_id in (args.extractor_model, args.classifier_model):
        if model_id:
            model_ids.add(model_id)
    if args.judge_backend in {"hf", "huggingface"}:
        model_ids.add(args.judge_model or args.hf_model)
    if args.embedder_backend == "sentence_transformer":
        model_ids.add(getattr(args, "embedder_st_model", None) or _DEFAULT_EMBEDDER_MODEL)

    code = "from huggingface_hub import snapshot_download\nimport sys\nsnapshot_download(sys.argv[1])\n"
    env = _base_env(args)
    for model_id in sorted(model_ids):
        start = time.monotonic()
        _log(f"prefetch start: {model_id}")
        subprocess.run([_preferred_python(), "-c", code, model_id], check=True, env=env)
        _log(f"prefetch done: {model_id} in {time.monotonic() - start:.1f}s")


def _smoke_load_quality_model(args: argparse.Namespace) -> None:
    if args.dry_run or args.quality_preset == _QUALITY_PRESET_NONE:
        return
    code = (
        "from ask.inference.llm import HuggingFaceLLM, InferenceConfig\n"
        "llm = HuggingFaceLLM(InferenceConfig(\n"
        "    model_id=%r, dtype=%r, device_map=%r, load_in_4bit=%r,\n"
        "    trust_remote_code=%r, max_seq_len=%r, backend='huggingface'))\n"
        "resp = llm.generate('Return OK.', max_new_tokens=1, temperature=0.0, seed=0)\n"
        "print('[quality-smoke] loaded', resp.model_id, 'tokens', resp.completion_tokens)\n"
        % (
            args.hf_model,
            args.hf_dtype,
            args.hf_device_map,
            args.hf_load_in_4bit,
            args.hf_trust_remote_code,
            args.hf_max_seq_len,
        )
    )
    _log(f"quality preset load smoke start: {args.hf_model}")
    result = subprocess.run([_preferred_python(), "-c", code], env=_base_env(args), check=False)
    if result.returncode != 0:
        raise SystemExit(
            "quality preset load smoke failed; no automatic fallback or "
            f"quantization was attempted (rc={result.returncode})"
        )
    _log("quality preset load smoke passed")


def _stream_output(job: RunningJob, *, stream_logs: bool) -> None:
    assert job.process.stdout is not None
    try:
        for line in job.process.stdout:
            job.log_fp.write(line)
            if stream_logs:
                print(f"[{_timestamp()}] [{job.alias}] {line}", end="", flush=True)
    finally:
        try:
            job.log_fp.flush()
        except ValueError:
            pass


def _jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.strip():
                count += 1
    return count


def _expected_rows(args: argparse.Namespace) -> int | None:
    if args.limit is not None:
        return int(args.limit)
    if args.dry_run or not args.slice.exists():
        return None
    with args.slice.open("r", encoding="utf-8", errors="replace") as fh:
        return sum(1 for line in fh if line.strip())


def _fmt_eta(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


_SESSION_PATTERNS = (
    re.compile(r"\[(?:controller|naive_overwrite|recency)\]\s+([^:\s]+):"),
    re.compile(r"\[\s*\d+/\d+\]\s+\S+\s+(\S+)\s+"),
)


def _active_session_from_log(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = deque(fh, maxlen=200)
    except OSError:
        return None
    for line in reversed(lines):
        for pattern in _SESSION_PATTERNS:
            match = pattern.search(line)
            if match:
                return match.group(1)
    return None


def _job_status(job: RunningJob, out_dir: Path, *, expected_rows: int | None) -> str:
    run_dir = out_dir / job.alias
    elapsed = time.monotonic() - job.started_at
    answers = _jsonl_count(run_dir / "answers.jsonl")
    judgments = _jsonl_count(run_dir / "judgments.jsonl")
    rate = answers / elapsed if elapsed > 0 else 0.0
    eta = None
    if expected_rows is not None and answers < expected_rows and rate > 0:
        eta = (expected_rows - answers) / rate
    pct = ""
    if expected_rows:
        pct = f" ({answers / expected_rows * 100:.1f}%)"
    parts = [
        f"{job.alias}: elapsed={elapsed:.0f}s",
        f"answers={answers}/{expected_rows or '?'}{pct}",
        f"judgments={judgments}/{expected_rows or '?'}",
        f"rate={rate:.3f}/s",
        f"eta={_fmt_eta(eta)}",
    ]
    active_session = _active_session_from_log(job.log_path)
    if active_session:
        parts.append(f"active={active_session}")
    if job.alias in {"b3", "b4", "controller"}:
        parts.append(f"extract_trace={_jsonl_count(run_dir / 'extraction_trace.jsonl')}")
        parts.append(f"actions={_jsonl_count(run_dir / 'action_log.jsonl')}")
    if job.alias in {"b4", "controller"}:
        parts.extend(
            [
                f"relation_trace={_jsonl_count(run_dir / 'relation_trace.jsonl')}",
            ]
        )
    if (run_dir / "report.json").exists():
        parts.append("report=present")
    return " ".join(parts)


def _command_fingerprint(cmd: list[str]) -> str:
    payload = json.dumps([str(part) for part in cmd], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _command_manifest_path(run_dir: Path) -> Path:
    return run_dir / "run_command.json"


def _write_command_manifest(
    *,
    run_dir: Path,
    alias: str,
    baseline: str,
    cmd: list[str],
    expected_rows: int | None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "alias": alias,
        "baseline": baseline,
        "command": [str(part) for part in cmd],
        "command_fingerprint": _command_fingerprint(cmd),
        "expected_rows": expected_rows,
        "written_at": _timestamp(),
    }
    _command_manifest_path(run_dir).write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _is_complete_run(
    *,
    run_dir: Path,
    cmd: list[str],
    expected_rows: int | None,
) -> tuple[bool, str]:
    report_path = run_dir / "report.json"
    if not report_path.exists():
        return False, f"missing report={report_path}"
    manifest_path = _command_manifest_path(run_dir)
    if not manifest_path.exists():
        return False, f"missing command manifest={manifest_path}"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"invalid command manifest: {type(exc).__name__}"
    expected_fp = _command_fingerprint(cmd)
    if manifest.get("command_fingerprint") != expected_fp:
        return False, "command fingerprint changed"
    validation = validate_run_dir(
        run_dir,
        expected_rows=expected_rows,
        system=str(manifest.get("alias") or run_dir.name),
        baseline=str(manifest.get("baseline") or ""),
    )
    if not validation.ok:
        return False, "; ".join(validation.errors)
    return True, "report, required rows, and command fingerprint match"


def _archive_path(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = path.with_name(f"{path.name}.stale_{stamp}")
    i = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.stale_{stamp}_{i}")
        i += 1
    return candidate


def _archive_run_dir(run_dir: Path, reason: str) -> None:
    archived = _archive_path(run_dir)
    _log(f"archive incomplete {run_dir} -> {archived} ({reason})")
    shutil.move(str(run_dir), str(archived))


def _prepare_run_dir_for_launch(run_dir: Path, reason: str, *, clean_incomplete: bool) -> None:
    """Avoid run_baseline's report-level resume skip when output is stale."""
    if not run_dir.exists():
        return
    report_path = run_dir / "report.json"
    if not report_path.exists():
        if has_output_artifacts(run_dir):
            if clean_incomplete:
                _archive_run_dir(run_dir, reason)
                return
            raise SystemExit(
                f"{run_dir} contains incomplete output artifacts but has no report "
                f"({reason}). Re-run with --clean-incomplete to archive the "
                "bad directory before launching."
            )
        return
    if (
        "fingerprint" in reason
        or "command manifest" in reason
        or "invalid command manifest" in reason
    ):
        archived = _archive_path(run_dir)
        _log(f"archive stale {run_dir} -> {archived} ({reason})")
        shutil.move(str(run_dir), str(archived))
        return
    if clean_incomplete:
        _archive_run_dir(run_dir, reason)
        return
    raise SystemExit(
        f"{run_dir} is incomplete or inconsistent ({reason}). Re-run with "
        "--clean-incomplete to archive the bad directory before launching."
    )


def _log_tail(path: Path, *, lines: int) -> None:
    if lines <= 0 or not path.exists():
        return
    _log(f"last {lines} lines from {path}:")
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in deque(fh, maxlen=lines):
            print(f"[{_timestamp()}] [tail] {line}", end="", flush=True)


def _start_job(
    *,
    alias: str,
    baseline: str,
    cmd: list[str],
    env: dict[str, str],
    log_dir: Path,
    stream_logs: bool,
) -> RunningJob:
    log_path = log_dir / f"{alias}.log"
    log_fp = log_path.open("w", encoding="utf-8", buffering=1)
    command_text = "$ " + _shell_join(cmd)
    log_fp.write(command_text + "\n\n")
    _log(f"launch {alias} ({baseline})")
    _log(f"{alias} command: {command_text}")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        bufsize=1,
    )
    job = RunningJob(
        alias=alias,
        baseline=baseline,
        cmd=cmd,
        process=process,
        log_path=log_path,
        log_fp=log_fp,
        stream_thread=threading.Thread(target=lambda: None),
        started_at=time.monotonic(),
    )
    job.stream_thread = threading.Thread(
        target=_stream_output,
        kwargs={"job": job, "stream_logs": stream_logs},
        name=f"stream-{alias}",
        daemon=True,
    )
    job.stream_thread.start()
    _log(f"started {alias} pid={process.pid}; log={log_path}")
    return job


def _terminate_jobs(jobs: dict[str, RunningJob]) -> None:
    _log(f"terminating {len(jobs)} running job(s)")
    for job in jobs.values():
        if job.process.poll() is None:
            _log(f"terminate {job.alias} pid={job.process.pid}")
            job.process.terminate()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if all(job.process.poll() is not None for job in jobs.values()):
            break
        time.sleep(0.5)
    for job in jobs.values():
        if job.process.poll() is None:
            _log(f"kill {job.alias} pid={job.process.pid}")
            job.process.kill()
        job.stream_thread.join(timeout=5)
        job.log_fp.close()


def _run_parallel(
    systems: list[tuple[str, str]],
    *,
    args: argparse.Namespace,
    env: dict[str, str],
) -> int:
    args.out.mkdir(parents=True, exist_ok=True)
    log_dir = args.out / "_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    _log(f"parallel run starting; logs={log_dir}")

    pending = list(systems)
    running: dict[str, RunningJob] = {}
    failures: list[tuple[str, int, Path]] = []
    last_global_status = 0.0
    expected_rows = _expected_rows(args)

    try:
        while pending or running:
            while pending and len(running) < args.max_workers:
                alias, baseline = pending.pop(0)
                cmd = _command_for(
                    baseline_alias=alias,
                    baseline=baseline,
                    out_dir=args.out,
                    args=args,
                )
                run_dir = args.out / alias
                reason = "skip-existing disabled"
                if args.skip_existing_complete:
                    complete, reason = _is_complete_run(
                        run_dir=run_dir,
                        cmd=cmd,
                        expected_rows=expected_rows,
                    )
                    if complete:
                        _log(f"skip {alias}: existing complete run ({reason})")
                        continue
                    _log(f"will run {alias}: {reason}")
                if args.dry_run:
                    print(_shell_join(cmd))
                    continue
                _prepare_run_dir_for_launch(
                    run_dir,
                    reason,
                    clean_incomplete=args.clean_incomplete,
                )
                _write_command_manifest(
                    run_dir=run_dir,
                    alias=alias,
                    baseline=baseline,
                    cmd=cmd,
                    expected_rows=expected_rows,
                )
                _log(f"queue -> launch: {alias}; pending_after_launch={len(pending)}")
                running[alias] = _start_job(
                    alias=alias,
                    baseline=baseline,
                    cmd=cmd,
                    env=env,
                    log_dir=log_dir,
                    stream_logs=args.stream_logs,
                )
            if args.dry_run:
                continue
            time.sleep(args.poll_s)
            now = time.monotonic()
            if args.status_s > 0 and now - last_global_status >= args.status_s:
                last_global_status = now
                _log(f"status: running={sorted(running)} pending={[alias for alias, _ in pending]}")
                for job in running.values():
                    _log(_job_status(job, args.out, expected_rows=expected_rows))
            for alias, job in list(running.items()):
                rc = job.process.poll()
                if rc is None:
                    continue
                job.stream_thread.join(timeout=5)
                job.log_fp.close()
                elapsed = time.monotonic() - job.started_at
                del running[alias]
                if rc == 0:
                    complete, complete_reason = _is_complete_run(
                        run_dir=args.out / alias,
                        cmd=job.cmd,
                        expected_rows=expected_rows,
                    )
                    if complete:
                        _log(f"done {alias} in {elapsed:.1f}s")
                        _log(_job_status(job, args.out, expected_rows=expected_rows))
                        continue
                    failures.append((alias, 1, job.log_path))
                    _log(f"FAILED {alias} validation after rc=0: {complete_reason}")
                    _log(_job_status(job, args.out, expected_rows=expected_rows))
                    if args.fail_fast:
                        _terminate_jobs(running)
                        return 1
                    continue
                failures.append((alias, rc, job.log_path))
                _log(f"FAILED {alias} rc={rc}; log={job.log_path}")
                _log_tail(job.log_path, lines=args.tail_lines_on_failure)
                if args.fail_fast:
                    _terminate_jobs(running)
                    return rc
    except KeyboardInterrupt:
        _terminate_jobs(running)
        _log("interrupted; partial JSONL progress is kept. Re-run the same command to resume.")
        return 130

    if args.dry_run:
        return 0
    if failures:
        _log("failures:")
        for alias, rc, log_path in failures:
            _log(f"  {alias}: rc={rc} log={log_path}")
        return 1
    _log("parallel run finished successfully")
    return 0


def _summarize(args: argparse.Namespace) -> None:
    summary_cmd = [
        _preferred_python(),
        "scripts/summarize_m4w13.py",
        str(args.out),
        "--json-out",
        str(args.out / "summary.json"),
        "--md-out",
        str(args.out / "summary.md"),
        "--require-complete",
    ]
    if args.dry_run:
        print(_shell_join(summary_cmd))
        return
    _log(f"summarize start: {_shell_join(summary_cmd)}")
    start = time.monotonic()
    subprocess.run(summary_cmd, check=True)
    _log(f"summarize done in {time.monotonic() - start:.1f}s")


def _zip_results(args: argparse.Namespace) -> Path | None:
    if args.no_zip:
        return None
    zip_out = args.zip_out
    if zip_out is None:
        default_root = Path("/content") if Path("/content").exists() else args.out.parent
        zip_out = default_root / f"{args.out.name}_results.zip"
    if args.dry_run:
        print(f"zip {args.out} -> {zip_out}")
        return zip_out
    zip_out.parent.mkdir(parents=True, exist_ok=True)
    if zip_out.exists():
        _log(f"removing existing zip: {zip_out}")
        zip_out.unlink()
    _log(f"zip start: {args.out} -> {zip_out}")
    start = time.monotonic()
    file_count = 0
    with zipfile.ZipFile(zip_out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(args.out.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(args.out.parent))
                file_count += 1
    size_mib = zip_out.stat().st_size / (1024**2)
    _log(
        f"zip done: {zip_out} files={file_count} size={size_mib:.1f}MiB "
        f"elapsed={time.monotonic() - start:.1f}s"
    )
    return zip_out


def _write_parallel_manifest(
    args: argparse.Namespace,
    systems: list[tuple[str, str]],
) -> None:
    if args.dry_run:
        return
    _log("writing manifest")
    _write_manifest(args, systems)
    manifest_path = args.out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "runner": "run_m4w13_hf_a100_parallel.py",
            "max_workers": args.max_workers,
            "require_a100": args.require_a100,
            "resume": args.resume,
            "cuda_visible_devices": args.cuda_visible_devices,
            "prefetch": not args.no_prefetch,
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _log(f"manifest written: {manifest_path}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--slice", type=Path, default=Path("/content/longmemeval/longmemeval_s_cleaned.json")
    )
    p.add_argument("--out", type=Path, default=Path("runs/m4w13_a100_50"))
    p.add_argument("--systems", default="all")
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional session cap. The shell wrapper defaults to 50 "
        "for development runs; omit this flag for the full slice.",
    )
    p.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Pass --resume to run_baseline so interrupted jobs "
        "continue from completed answers/judgments.",
    )
    p.add_argument(
        "--quality-preset",
        choices=_QUALITY_PRESETS,
        default=_QUALITY_PRESET_NONE,
        help="Lock an accuracy-first runtime profile. 'max-a10g' "
        "forces Qwen2.5-7B fp16, max-workers=1, and controller "
        "quality knobs. 'max-a100-40gb' keeps the worker count "
        "available for A100 40GB runs.",
    )
    p.add_argument(
        "--max-workers",
        type=int,
        default=2,
        help="Number of systems to run at once. Default 2 is the "
        "conservative A100 40GB setting for 7B fp16 model copies; "
        "raise only after confirming free VRAM.",
    )
    p.add_argument("--poll-s", type=float, default=10.0)
    p.add_argument(
        "--status-s",
        type=float,
        default=30.0,
        help="Emit per-system row-count status every N seconds. "
        "Use 0 to disable status heartbeats.",
    )
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-bootstrap", type=int, default=1000)
    p.add_argument("--hf-model", default="Qwen/Qwen2.5-3B-Instruct")
    p.add_argument(
        "--judge-backend",
        choices=("same_as_answerer", "hf", "huggingface", "ollama", "fake"),
        default="same_as_answerer",
    )
    p.add_argument("--judge-model", default=None)
    p.add_argument("--extractor-model", default=None)
    p.add_argument("--classifier-model", default=None)
    p.add_argument("--hf-dtype", choices=("bfloat16", "float16", "float32"), default="float16")
    p.add_argument("--hf-device-map", default="auto")
    p.add_argument("--hf-load-in-4bit", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--hf-trust-remote-code", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--hf-max-seq-len", type=int, default=4096)
    p.add_argument(
        "--hf-enable-thinking",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Chat-template thinking switch for reasoning models "
        "(Qwen3/Qwen3.5). Use --no-hf-enable-thinking to suppress "
        "<think> blocks. Default unset = leave template alone.",
    )
    p.add_argument(
        "--embedder-backend",
        choices=("sentence_transformer", "ollama"),
        default="sentence_transformer",
    )
    p.add_argument("--embedder-device", default="auto")
    p.add_argument(
        "--embedder-st-model",
        default=None,
        help="Override the sentence-transformers retrieval model id "
        "(e.g. jinaai/jina-embeddings-v5-text-small).",
    )
    p.add_argument(
        "--embedder-trust-remote-code",
        action="store_true",
        help="trust_remote_code=True for the ST embedder (Jina v5).",
    )
    p.add_argument(
        "--embedder-task",
        default=None,
        help="encode() task for task-aware embedders (Jina v5: retrieval).",
    )
    p.add_argument(
        "--embedder-prompt-name",
        default=None,
        help="encode() prompt_name for task-aware embedders (Jina v5).",
    )
    p.add_argument("--fake-embedder", action="store_true")
    p.add_argument("--ollama-host", default="http://127.0.0.1:11434")
    p.add_argument("--judge-timeout-s", type=float, default=1800.0)
    p.add_argument("--embedder-ollama-model", default="llama3.2:3b")
    p.add_argument("--embedder-timeout-s", type=float, default=1800.0)
    p.add_argument("--embedder-batch-size", type=int, default=16)
    p.add_argument(
        "--retrieval-k",
        type=int,
        default=5,
        help="Top-k retrieval depth for memory systems. Forwarded "
        "to run_baseline.py --k for b2/b3/b4/controller.",
    )
    p.add_argument("--controller-progress", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--controller-memory-top-k", type=int, default=32)
    p.add_argument(
        "--controller-raw-turn-fallback", action=argparse.BooleanOptionalAction, default=True
    )
    p.add_argument("--controller-retrieval-neighbor-window", type=int, default=0)
    p.add_argument(
        "--controller-include-assistant-context",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument(
        "--controller-include-raw-user-context",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument(
        "--controller-retrieval-query-augmentation",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument(
        "--controller-deterministic-numeric-supersede",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument(
        "--answer-retry-on-unknown", action=argparse.BooleanOptionalAction, default=False
    )
    p.add_argument("--controller-prior-top-k", type=int, default=1)
    p.add_argument("--controller-prior-similarity-threshold", type=float, default=0.0)
    p.add_argument(
        "--controller-temporal-scaffold", action=argparse.BooleanOptionalAction, default=False
    )
    p.add_argument(
        "--controller-computation-answerer", action=argparse.BooleanOptionalAction, default=False
    )
    p.add_argument("--recency-progress", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--recency-memory-top-k", type=int, default=32)
    p.add_argument(
        "--recency-raw-turn-fallback", action=argparse.BooleanOptionalAction, default=True
    )
    p.add_argument("--extraction-max-new-tokens", type=int, default=192)
    p.add_argument("--relation-max-new-tokens", type=int, default=96)
    p.add_argument("--cuda-visible-devices", default=None)
    p.add_argument("--require-a100", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--no-prefetch", action="store_true")
    p.add_argument("--fail-fast", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--skip-existing-complete",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="If <out>/<system>/report.json already exists, skip "
        "re-running that system. This makes interrupted A100 "
        "runs resumable without paying again for completed "
        "systems.",
    )
    p.add_argument(
        "--clean-incomplete",
        action="store_true",
        help="Archive incomplete or mismatched system output directories "
        "before launching. Without this flag, zero-line, missing, "
        "or stale artifacts fail fast with an explicit error.",
    )
    p.add_argument(
        "--stream-logs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Mirror each subprocess log line to notebook stdout with "
        "a system prefix while also writing per-system log files.",
    )
    p.add_argument("--tail-lines-on-failure", type=int, default=120)
    p.add_argument("--zip-out", type=Path, default=None)
    p.add_argument("--no-zip", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    _apply_quality_preset(args)

    if args.max_workers < 1:
        raise SystemExit("--max-workers must be >= 1")

    systems = _select_systems(args.systems)
    _log("start run_m4w13_hf_a100_parallel.py")
    _log_configuration(args, systems)
    _log_system_state(args)
    _validate_inputs(args)
    _check_python_environment(args, systems, include_prefetch=not args.no_prefetch)
    _check_a100(args)
    _prefetch_models(args)
    _smoke_load_quality_model(args)
    _write_parallel_manifest(args, systems)
    env = _base_env(args)
    rc = _run_parallel(systems, args=args, env=env)
    if rc != 0:
        return rc
    _summarize(args)
    _zip_results(args)
    _log("finished run_m4w13_hf_a100_parallel.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
