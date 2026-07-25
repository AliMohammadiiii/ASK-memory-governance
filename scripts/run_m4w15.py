"""Run M4-W15 RC@C threshold sweep and assemble the main results table."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.eval.m4w15 import (  # noqa: E402
    assemble_threshold_report,
    build_main_table,
    load_threshold_reports,
    plot_rc_curve,
    threshold_dir_name,
    threshold_values,
    validate_prerequisites,
)

LIGHT_MODELS = {
    "answerer": "llama3.2:3b",
    "embedder": "llama3.2:3b",
    "extractor": "llama3.2:3b",
    "classifier": "phi3.5:3.8b",
    "judge": "phi3.5:3.8b",
}

T4_MODELS = {
    "answerer": "qwen3.5:9b",
    "embedder": "llama3.2:3b",
    "extractor": "llama3.2:3b",
    "classifier": "phi3.5:3.8b",
    "judge": "phi3.5:3.8b",
}


def _installed_ollama_models(host: str) -> set[str]:
    with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return {str(model.get("name") or model.get("model")) for model in payload.get("models", [])}


def _validate_models(host: str, models: set[str]) -> None:
    installed = _installed_ollama_models(host)
    missing = sorted(models - installed)
    if missing:
        raise SystemExit("Ollama is reachable, but missing model tags: " + ", ".join(missing))


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_synthetic_slice(path: Path) -> bool:
    return "synthetic" in path.name.lower()


def _run(command: list[str], *, cwd: Path, dry_run: bool) -> None:
    print("$ " + " ".join(command), flush=True)
    if not dry_run:
        subprocess.run(command, cwd=cwd, check=True)


def _mgp6_command(args: argparse.Namespace, theta: float, threshold_dir: Path) -> list[str]:
    command = [
        sys.executable,
        "scripts/run_mgp6.py",
        "--input",
        str(args.mgp6_input),
        "--out",
        str(threshold_dir / "mgp6"),
        "--systems",
        "controller",
        "--seed",
        str(args.seed),
        "--n-bootstrap",
        str(args.n_bootstrap),
        "--ollama-host",
        args.ollama_host,
        "--ollama-timeout-s",
        str(args.ollama_timeout_s),
        "--model-profile",
        args.model_profile,
        "--extractor-model",
        args.extractor_model,
        "--classifier-model",
        args.classifier_model,
        "--judge-model",
        args.judge_model,
        "--scorecard-config",
        str(args.scorecard_config),
        "--theta-abs",
        f"{theta:.2f}",
        "--note-path",
        str(threshold_dir / "mgp6_results.md"),
    ]
    if args.limit is not None:
        command.extend(["--limit", str(args.limit)])
    return command


def _longmemeval_command(args: argparse.Namespace, theta: float, threshold_dir: Path) -> list[str]:
    command = [
        sys.executable,
        "scripts/run_baseline.py",
        "--baseline",
        "controller",
        "--slice",
        str(args.longmemeval_slice),
        "--out",
        str(threshold_dir / "longmemeval" / "controller"),
        "--seed",
        str(args.seed),
        "--n-bootstrap",
        str(args.n_bootstrap),
        "--ollama",
        "--ollama-model",
        args.answerer_model,
        "--ollama-host",
        args.ollama_host,
        "--ollama-timeout-s",
        str(args.ollama_timeout_s),
        "--judge-backend",
        "ollama",
        "--judge-model",
        args.judge_model,
        "--judge-timeout-s",
        str(args.judge_timeout_s),
        "--embedder-backend",
        args.embedder_backend,
        "--extractor-ollama-model",
        args.extractor_model,
        "--classifier-ollama-model",
        args.classifier_model,
        "--scorecard-config",
        str(args.scorecard_config),
        "--theta-abs",
        f"{theta:.2f}",
    ]
    if args.embedder_backend == "ollama":
        command.extend(
            [
                "--embedder-ollama-model",
                args.embedder_model,
                "--embedder-ollama-timeout-s",
                str(args.embedder_timeout_s or args.ollama_timeout_s),
                "--embedder-ollama-batch-size",
                str(args.embedder_batch_size),
            ]
        )
    if args.limit is not None:
        command.extend(["--limit", str(args.limit)])
    return command


def _assemble_sweep(args: argparse.Namespace) -> list[dict[str, Any]]:
    reports = []
    sweep_dir = args.out / "sweep"
    for theta in threshold_values():
        threshold_dir = sweep_dir / threshold_dir_name(theta)
        reports.append(
            assemble_threshold_report(
                threshold_dir,
                threshold=theta,
                n_bootstrap=args.n_bootstrap,
                seed=args.seed,
            )
        )
    png_path = args.out / "rc_at_c_curve.png"
    pdf_path = args.out / "rc_at_c_curve.pdf"
    plot_rc_curve(reports, png_path=png_path, pdf_path=pdf_path)
    print(f"[m4w15] wrote {png_path}", flush=True)
    print(f"[m4w15] wrote {pdf_path}", flush=True)
    return reports


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("runs/m4w15"))
    p.add_argument("--m4w13-root", type=Path, default=Path("runs/m4w13"))
    p.add_argument("--m4w14-root", type=Path, default=Path("runs/m4w14"))
    p.add_argument("--longmemeval-slice", type=Path, default=Path("data/longmemeval_s_synthetic.jsonl"))
    p.add_argument("--mgp6-input", type=Path, default=Path("data/mgp6_v1_seed0.jsonl"))
    p.add_argument("--scorecard-config", type=Path, default=Path("configs/controller_active.yaml"))
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-bootstrap", type=int, default=1000)
    p.add_argument("--limit", type=int, default=None,
                   help="Smoke-run cap. Do not use for acceptance artifacts.")
    p.add_argument("--ollama-host", default="http://localhost:11434")
    p.add_argument("--ollama-timeout-s", type=float, default=900.0)
    p.add_argument("--judge-timeout-s", type=float, default=900.0)
    p.add_argument("--embedder-backend", choices=("sentence_transformer", "ollama"),
                   default="ollama",
                   help="Retrieval embedding backend for LongMemEval controller sweeps.")
    p.add_argument("--embedder-model", default=None)
    p.add_argument("--embedder-timeout-s", type=float, default=None)
    p.add_argument("--embedder-batch-size", type=int, default=16)
    p.add_argument("--model-profile", choices=("standard", "light", "t4"), default="standard",
                   help="Use 'light' for 3B/3.8B. Use 't4' for qwen3.5:9b "
                        "answering, llama3.2 extraction, and phi3.5 judge/classifier.")
    p.add_argument("--answerer-model", default=None)
    p.add_argument("--extractor-model", default=None)
    p.add_argument("--classifier-model", default=None)
    p.add_argument("--judge-model", default=None)
    p.add_argument("--skip-model-check", action="store_true")
    p.add_argument("--skip-sweep", action="store_true",
                   help="Only assemble plots/table from existing M4-W15 sweep reports.")
    p.add_argument("--allow-incomplete", action="store_true",
                   help="Permit assembly with missing prerequisite cells. Not for acceptance runs.")
    p.add_argument("--allow-synthetic-longmemeval", action="store_true",
                   help="Permit the local synthetic LongMemEval slice. Not for acceptance runs.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the full 21-point plan without running or writing outputs.")
    args = p.parse_args()
    if args.model_profile == "light":
        args.answerer_model = args.answerer_model or LIGHT_MODELS["answerer"]
        args.embedder_model = args.embedder_model or LIGHT_MODELS["embedder"]
        args.extractor_model = args.extractor_model or LIGHT_MODELS["extractor"]
        args.classifier_model = args.classifier_model or LIGHT_MODELS["classifier"]
        args.judge_model = args.judge_model or LIGHT_MODELS["judge"]
    elif args.model_profile == "t4":
        args.answerer_model = args.answerer_model or T4_MODELS["answerer"]
        args.embedder_model = args.embedder_model or T4_MODELS["embedder"]
        args.extractor_model = args.extractor_model or T4_MODELS["extractor"]
        args.classifier_model = args.classifier_model or T4_MODELS["classifier"]
        args.judge_model = args.judge_model or T4_MODELS["judge"]
    else:
        args.answerer_model = args.answerer_model or "gemma4:e4b"
        args.embedder_model = args.embedder_model or "llama3.2:3b"
        args.extractor_model = args.extractor_model or "gemma4:e4b"
        args.classifier_model = args.classifier_model or "gemma4:e4b"
        args.judge_model = args.judge_model or "phi4:14b"

    if _is_synthetic_slice(args.longmemeval_slice):
        print(
            "[m4w15] LongMemEval slice path looks synthetic; use --longmemeval-slice "
            "with the real LongMemEval-S file for acceptance.",
            flush=True,
        )
        if not args.dry_run and not args.allow_synthetic_longmemeval:
            raise SystemExit("Refusing to create M4-W15 acceptance artifacts from a synthetic slice.")

    prereqs = validate_prerequisites(args.m4w13_root, args.m4w14_root)
    if not prereqs.ok:
        print(prereqs.format(), flush=True)
        if not args.dry_run and not args.allow_incomplete:
            raise SystemExit("M4-W15 requires complete runs/m4w13 and runs/m4w14 before running.")
    elif prereqs.warnings:
        print(prereqs.format(), flush=True)
        if not args.dry_run and not args.allow_incomplete:
            raise SystemExit("M4-W15 prerequisite artifacts are present but incomplete.")

    if args.dry_run:
        print(f"[m4w15] theta_abs grid: {[f'{value:.2f}' for value in threshold_values()]}", flush=True)

    if not args.skip_model_check and not args.dry_run:
        _validate_models(
            args.ollama_host,
            {
                args.answerer_model,
                args.embedder_model,
                args.extractor_model,
                args.classifier_model,
                args.judge_model,
            },
        )

    if args.dry_run:
        for theta in threshold_values():
            threshold_dir = args.out / "sweep" / threshold_dir_name(theta)
            _run(_mgp6_command(args, theta, threshold_dir), cwd=_THIS.parents[1], dry_run=True)
            _run(_longmemeval_command(args, theta, threshold_dir), cwd=_THIS.parents[1], dry_run=True)
        print(f"[m4w15] would write {args.out / 'rc_at_c_curve.png'}")
        print(f"[m4w15] would write {args.out / 'rc_at_c_curve.pdf'}")
        print("[m4w15] would write NOTES/m4w15_main_table.md")
        print(f"[m4w15] would write {args.out / 'main_table.csv'}")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "started_at": datetime.now(UTC).isoformat(),
        "theta_abs_grid": [round(value, 2) for value in threshold_values()],
        "m4w13_root": str(args.m4w13_root),
        "m4w14_root": str(args.m4w14_root),
        "longmemeval_slice": str(args.longmemeval_slice),
        "mgp6_input": str(args.mgp6_input),
        "scorecard_config": str(args.scorecard_config),
        "scorecard_config_sha256": _sha256(args.scorecard_config),
        "limit": args.limit,
        "tier": "smoke" if args.limit is not None else "final-candidate",
        "run_tier": "smoke" if args.limit is not None else "final-candidate",
        "judge_tier": "ollama" if not args.skip_sweep else "assembled_existing_outputs",
        "raw_turn_fallback": False,
        "complete": False,
        "thesis_use": "no_final_claim" if args.limit is not None else "final_candidate_pending_review",
        "models": {
            "answerer": args.answerer_model,
            "embedder": args.embedder_model,
            "extractor": args.extractor_model,
            "classifier": args.classifier_model,
            "judge": args.judge_model,
        },
        "model_profile": args.model_profile,
        "embedder_backend": args.embedder_backend,
        "embedder_timeout_s": args.embedder_timeout_s or args.ollama_timeout_s,
        "embedder_batch_size": args.embedder_batch_size,
        "ollama_timeout_s": args.ollama_timeout_s,
        "judge_timeout_s": args.judge_timeout_s,
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    if not args.skip_sweep:
        for theta in threshold_values():
            threshold_dir = args.out / "sweep" / threshold_dir_name(theta)
            _run(_mgp6_command(args, theta, threshold_dir), cwd=_THIS.parents[1], dry_run=False)
            _run(_longmemeval_command(args, theta, threshold_dir), cwd=_THIS.parents[1], dry_run=False)

    reports = _assemble_sweep(args) if not args.skip_sweep else load_threshold_reports(args.out / "sweep")
    if args.skip_sweep:
        plot_rc_curve(
            reports,
            png_path=args.out / "rc_at_c_curve.png",
            pdf_path=args.out / "rc_at_c_curve.pdf",
        )

    build_main_table(
        m4w13_root=args.m4w13_root,
        m4w14_root=args.m4w14_root,
        markdown_path=Path("NOTES/m4w15_main_table.md"),
        csv_path=args.out / "main_table.csv",
        n_bootstrap=args.n_bootstrap,
        seed=args.seed,
    )
    manifest["finished_at"] = datetime.now(UTC).isoformat()
    manifest["complete"] = True
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("[m4w15] wrote NOTES/m4w15_main_table.md", flush=True)
    print(f"[m4w15] wrote {args.out / 'main_table.csv'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
