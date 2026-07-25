#!/usr/bin/env python3
"""Homogeneity + coverage gate for a multi-system LongMemEval run.

A run is paper-grade ("full homogeneous") only if, for EVERY system:

  1. report.json exists and n_sessions == expected N (default: slice size);
  2. answers.jsonl and judgments.jsonl cover exactly the slice session_ids
     (no missing, no extra, no duplicates);
  3. every row requested the frozen judge primary and any actually used judge
     is within the declared primary/fallback policy;
  4. every answer-side API call requested the frozen answer model (provider
     aliases are reported separately);
  5. slice sha256 is recorded for the provenance table.

Exits non-zero on any failure, printing a PASS/FAIL table. Run after
deploy/run_lme_v8_full_5systems.sh:

    python scripts/verify_homogeneous_run.py \
        --run-root runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v8_full5 \
        --slice data/slices/longmemeval_m_strat30_seed0.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _requested_models(value: Any) -> set[str]:
    """Collect requested model IDs from nested answer telemetry."""
    found: set[str] = set()
    if isinstance(value, dict):
        requested = value.get("requested_model")
        if isinstance(requested, str) and requested:
            found.add(requested)
        for child in value.values():
            found.update(_requested_models(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_requested_models(child))
    return found


def _selected_ids_hash(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(ids).encode()).hexdigest()


def check_system(
    run_root: Path,
    system: str,
    slice_ids: list[str],
    expected_n: int,
    *,
    expected_answer_model: str | None,
    expected_answer_provider: str | None,
    expected_judge_primary: str | None,
    allowed_judge_fallbacks: set[str],
    allowed_answer_providers: tuple[str, ...] = (),
    required_answer_providers: set[str] | None = None,
    allowed_auxiliary_models: set[str] | None = None,
) -> dict[str, Any]:
    sys_dir = run_root / system
    result: dict[str, Any] = {"system": system, "errors": [], "warnings": []}
    err = result["errors"].append

    report_path = sys_dir / "report.json"
    if not report_path.exists():
        err(f"missing {report_path}")
        return result
    report = json.loads(report_path.read_text(encoding="utf-8"))
    result["overall_accuracy"] = report.get("overall_accuracy")
    result["report_judge"] = report.get("judge_model_id")
    if expected_judge_primary and report.get("judge_model_id") != expected_judge_primary:
        err(
            f"report judge_model_id={report.get('judge_model_id')!r}, "
            f"expected primary {expected_judge_primary!r}"
        )
    n_sessions = report.get("n_sessions")
    result["n_sessions"] = n_sessions
    if n_sessions != expected_n:
        err(f"report n_sessions={n_sessions}, expected {expected_n}")

    slice_counter = Counter(slice_ids)
    for name in ("answers.jsonl", "judgments.jsonl"):
        path = sys_dir / name
        if not path.exists():
            err(f"missing {path}")
            continue
        rows = load_jsonl(path)
        raw_ids = [r.get("session_id") for r in rows]
        missing_ids = sum(1 for value in raw_ids if not isinstance(value, str) or not value)
        if missing_ids:
            err(f"{name}: {missing_ids} rows lack a non-empty string session_id")
        ids: Counter[str] = Counter(value for value in raw_ids if isinstance(value, str) and value)
        dupes = {k: c for k, c in ids.items() if c > 1}
        missing = set(slice_counter) - set(ids)
        extra = set(ids) - set(slice_counter)
        if dupes:
            err(
                f"{name}: duplicate session_ids {sorted(dupes)[:5]}"
                f"{' ...' if len(dupes) > 5 else ''}"
            )
        if missing:
            err(f"{name}: {len(missing)} slice ids missing (e.g. {sorted(missing)[:3]})")
        if extra:
            err(f"{name}: {len(extra)} ids not in slice (e.g. {sorted(extra)[:3]})")
        if name == "judgments.jsonl":
            judges = sorted({str(r.get("judge_model_id")) for r in rows})
            result["judge_models"] = judges
            missing_requested_judge = sum(1 for r in rows if not r.get("requested_judge_model_id"))
            if missing_requested_judge:
                err(
                    f"judgments.jsonl: {missing_requested_judge} rows lack requested_judge_model_id"
                )
            requested_judges = sorted(
                {
                    str(r.get("requested_judge_model_id"))
                    for r in rows
                    if r.get("requested_judge_model_id")
                }
            )
            result["requested_judge_models"] = requested_judges
            if expected_judge_primary and requested_judges != [expected_judge_primary]:
                err(
                    "judgments requested judge models "
                    f"{requested_judges}; expected only {expected_judge_primary!r}"
                )
            allowed_judges = {
                model for model in ({expected_judge_primary} | allowed_judge_fallbacks) if model
            }
            unexpected = set(judges) - allowed_judges if allowed_judges else set()
            if unexpected:
                err(f"unexpected actual judge model(s): {sorted(unexpected)}")
            result["model_fallbacks"] = sum(1 for r in rows if bool(r.get("used_model_fallback")))
            if not allowed_judge_fallbacks and result["model_fallbacks"]:
                err(
                    "judgments.jsonl: model fallback was used even though the "
                    "frozen policy declares no fallback model"
                )
            result["scoring_fallbacks"] = sum(
                1 for r in rows if bool(r.get("used_scoring_fallback"))
            )
            result["deterministic_guards"] = sum(
                1 for r in rows if r.get("judge_was_called") is False
            )
            missing_call_flag = sum(1 for r in rows if "judge_was_called" not in r)
            if missing_call_flag:
                err(f"judgments.jsonl: {missing_call_flag} rows lack judge_was_called")
            missing_raw_audit = sum(
                1
                for r in rows
                if r.get("judge_was_called", True)
                and (
                    not r.get("judge_prompt_hash")
                    or not r.get("judge_raw_response_hash")
                    or r.get("judge_raw_output") is None
                )
            )
            if missing_raw_audit:
                err(f"judgments.jsonl: {missing_raw_audit} judge calls lack raw/hash audit fields")
            missing_attempt_audit = sum(
                1
                for r in rows
                if r.get("judge_was_called", True) and "judge_attempt_index" not in r
            )
            if missing_attempt_audit:
                err(f"judgments.jsonl: {missing_attempt_audit} judge calls lack attempt audit")
            bad_fallback_reason = sum(
                1
                for r in rows
                if (bool(r.get("used_model_fallback")) or bool(r.get("used_scoring_fallback")))
                and not r.get("fallback_reason")
            )
            if bad_fallback_reason:
                err(f"judgments.jsonl: {bad_fallback_reason} fallback rows lack a reason")
            inconsistent_fallback_flag = sum(
                1
                for r in rows
                if bool(r.get("used_fallback"))
                != (bool(r.get("used_model_fallback")) or bool(r.get("used_scoring_fallback")))
            )
            if inconsistent_fallback_flag:
                err(
                    f"judgments.jsonl: {inconsistent_fallback_flag} rows have inconsistent fallback flags"
                )
            recomputed_accuracy = (
                sum(1 for r in rows if bool(r.get("correct"))) / len(rows) if rows else 0.0
            )
            result["recomputed_accuracy"] = recomputed_accuracy
            if (
                not isinstance(report.get("overall_accuracy"), (int, float))
                or abs(float(report.get("overall_accuracy", 0.0)) - recomputed_accuracy) > 1e-12
            ):
                err(
                    "report overall_accuracy does not equal judgments recomputation: "
                    f"{report.get('overall_accuracy')} vs {recomputed_accuracy}"
                )
            expected_usage = Counter(
                str(r.get("judge_model_id")) for r in rows if r.get("judge_was_called") is not False
            )
            if report.get("judge_models_used") != dict(expected_usage):
                err(
                    "report judge_models_used does not match judgments: "
                    f"{report.get('judge_models_used')} vs {dict(expected_usage)}"
                )
            expected_counts = {
                "n_model_fallbacks": result["model_fallbacks"],
                "n_scoring_fallbacks": result["scoring_fallbacks"],
                "n_deterministic_guards": result["deterministic_guards"],
            }
            for field, expected in expected_counts.items():
                if report.get(field) != expected:
                    err(f"report {field}={report.get(field)!r}; expected {expected}")
        if name == "answers.jsonl":
            result["answer_models"] = sorted({str(r.get("model_id")) for r in rows})
            requested_answer_models: set[str] = set()
            for row in rows:
                requested_answer_models.update(_requested_models(row))
            result["requested_answer_models"] = sorted(requested_answer_models)
            if expected_answer_model:
                unexpected_answer_models = requested_answer_models - {expected_answer_model}
                if unexpected_answer_models:
                    err(
                        "answer telemetry requested unexpected model(s): "
                        f"{sorted(unexpected_answer_models)}"
                    )
                if not requested_answer_models:
                    err("answer telemetry contains no requested_model provenance")
            raw_seeds = [r.get("seed") for r in rows]
            missing_seeds = sum(value is None for value in raw_seeds)
            if missing_seeds:
                err(f"answers.jsonl: {missing_seeds} rows lack seed provenance")
            seeds = sorted({str(value) for value in raw_seeds if value is not None})
            result["seeds"] = seeds
            if len(seeds) > 1:
                result["warnings"].append(f"multiple seeds: {seeds}")

    call_paths = sorted(sys_dir.rglob("llm_calls.jsonl"))
    call_rows = [row for path in call_paths for row in load_jsonl(path)]
    result["llm_call_logs"] = [str(path.relative_to(run_root)) for path in call_paths]
    if not call_rows:
        err("no llm_calls.jsonl telemetry found")
    requested_call_models = sorted(
        {str(row.get("requested_model")) for row in call_rows if row.get("requested_model")}
    )
    result["requested_call_models"] = requested_call_models
    allowed_requested_models = {
        model
        for model in ({expected_answer_model, expected_judge_primary} | allowed_judge_fallbacks)
        if model
    } | (allowed_auxiliary_models or set())
    unexpected_call_models = set(requested_call_models) - allowed_requested_models
    if unexpected_call_models:
        err(f"LLM telemetry requested unexpected models: {sorted(unexpected_call_models)}")
    if expected_answer_model:
        answer_calls = [
            row for row in call_rows if row.get("requested_model") == expected_answer_model
        ]
        if not answer_calls:
            err(f"no LLM call telemetry for answer model {expected_answer_model!r}")
        bad_actual_answer_models = sorted(
            {
                str(row.get("model"))
                for row in answer_calls
                if not str(row.get("model", "")).startswith(expected_answer_model)
            }
        )
        if bad_actual_answer_models:
            err(f"unexpected actual answer model aliases: {bad_actual_answer_models}")
        provider_policies = {
            json.dumps(row.get("provider_preferences"), sort_keys=True) for row in answer_calls
        }
        result["answer_provider_policies"] = sorted(provider_policies)
        if allowed_answer_providers:
            expected_policy = {
                "allow_fallbacks": True,
                "only": list(allowed_answer_providers),
            }
        elif expected_answer_provider:
            expected_policy = {
                "allow_fallbacks": False,
                "only": [expected_answer_provider],
                "order": [expected_answer_provider],
            }
        else:
            expected_policy = None
        if expected_policy is not None:
            bad_provider_policies = [
                row.get("provider_preferences")
                for row in answer_calls
                if row.get("provider_preferences") != expected_policy
            ]
            if bad_provider_policies:
                err(
                    f"{len(bad_provider_policies)} answer calls lack the frozen "
                    f"provider policy {expected_policy}"
                )
        actual_answer_providers = Counter(
            str(row.get("provider") or "unreported").lower() for row in answer_calls
        )
        result["actual_answer_providers"] = dict(actual_answer_providers)
        if allowed_answer_providers:
            allowed = {provider.lower() for provider in allowed_answer_providers}
            unexpected_providers = set(actual_answer_providers) - allowed
            if unexpected_providers:
                err(
                    "answer calls used provider(s) outside the frozen pool: "
                    f"{sorted(unexpected_providers)}"
                )
        if required_answer_providers:
            required = {provider.lower() for provider in required_answer_providers}
            missing_providers = required - set(actual_answer_providers)
            if missing_providers:
                err(
                    f"answer calls did not use every required provider: {sorted(missing_providers)}"
                )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--slice", type=Path, required=True)
    parser.add_argument("--systems", default="controller,b4,b3,b2,b1")
    parser.add_argument(
        "--expected-n", type=int, default=0, help="expected question count (0 = slice size)"
    )
    parser.add_argument("--sample-from", type=int, default=0)
    parser.add_argument(
        "--sample-to",
        type=int,
        default=-1,
        help="inclusive end within --slice (-1 = final row)",
    )
    parser.add_argument("--expected-answer-model", default=None)
    parser.add_argument("--expected-answer-provider", default=None)
    parser.add_argument(
        "--allowed-answer-provider",
        action="append",
        default=[],
        help="allowed provider slug for answer-side calls (repeatable)",
    )
    parser.add_argument(
        "--required-answer-provider",
        action="append",
        default=[],
        help="provider slug that must appear in answer-side telemetry (repeatable)",
    )
    parser.add_argument("--expected-judge-primary", default=None)
    parser.add_argument(
        "--allowed-judge-fallback",
        action="append",
        default=[],
        help="allowed actual fallback model (repeatable)",
    )
    parser.add_argument(
        "--allowed-auxiliary-model",
        action="append",
        default=[],
        help="model allowed in extraction/relation telemetry but not as final answerer",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="optional JSON output path (default <run-root>/homogeneity_report.json)",
    )
    args = parser.parse_args(argv)

    all_slice_rows = load_jsonl(args.slice)
    sample_to = len(all_slice_rows) - 1 if args.sample_to < 0 else args.sample_to
    if args.sample_from < 0 or sample_to < args.sample_from:
        parser.error("invalid --sample-from/--sample-to range")
    slice_rows = all_slice_rows[args.sample_from : sample_to + 1]
    raw_slice_ids = [r.get("session_id") for r in slice_rows]
    slice_ids = [item if isinstance(item, str) else "" for item in raw_slice_ids]
    expected_n = args.expected_n or len(slice_ids)
    slice_sha = sha256_file(args.slice)

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    results = [
        check_system(
            args.run_root,
            s,
            slice_ids,
            expected_n,
            expected_answer_model=args.expected_answer_model,
            expected_answer_provider=args.expected_answer_provider,
            expected_judge_primary=args.expected_judge_primary,
            allowed_judge_fallbacks=set(args.allowed_judge_fallback),
            allowed_answer_providers=tuple(args.allowed_answer_provider),
            required_answer_providers=set(args.required_answer_provider),
            allowed_auxiliary_models=set(args.allowed_auxiliary_model),
        )
        for s in systems
    ]

    # cross-system homogeneity
    global_errors: list[str] = []
    if expected_n != len(slice_ids):
        global_errors.append(
            f"expected-n={expected_n} but selected slice range has {len(slice_ids)} rows"
        )
    if any(not isinstance(item, str) or not item for item in slice_ids):
        global_errors.append("selected slice contains missing/non-string session_ids")
    if len(slice_ids) != len(set(slice_ids)):
        global_errors.append("selected slice contains duplicate session_ids")

    manifest_path = args.run_root / "manifest.json"
    manifest: dict[str, Any] = {}
    if not manifest_path.exists():
        global_errors.append(f"missing run manifest: {manifest_path}")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_expectations = {
            "slice_sha256": slice_sha,
            "evaluated_session_ids_sha256": _selected_ids_hash(slice_ids),
            "evaluated_n": len(slice_ids),
            "answer_model": args.expected_answer_model,
            "judge_primary": args.expected_judge_primary,
        }
        for field, expected in manifest_expectations.items():
            if expected is not None and manifest.get(field) != expected:
                global_errors.append(
                    f"manifest {field}={manifest.get(field)!r}; expected {expected!r}"
                )
        if args.allowed_auxiliary_model and manifest.get("main_model") not in set(
            args.allowed_auxiliary_model
        ):
            global_errors.append(
                "manifest main_model is not in the allowed auxiliary model set: "
                f"{manifest.get('main_model')!r}"
            )
        if args.allowed_answer_provider:
            expected_policy = {
                "only": args.allowed_answer_provider,
                "allow_fallbacks": True,
            }
            if manifest.get("answer_provider_policy") != expected_policy:
                global_errors.append("manifest answer_provider_policy differs from verifier")
        elif args.expected_answer_provider:
            expected_policy = {
                "order": [args.expected_answer_provider],
                "only": [args.expected_answer_provider],
                "allow_fallbacks": False,
            }
            if manifest.get("answer_provider_policy") != expected_policy:
                global_errors.append("manifest answer_provider_policy differs from verifier")
        config_path = Path(str(manifest.get("config_path", "")))
        if not config_path.is_file() or sha256_file(config_path) != manifest.get("config_sha256"):
            global_errors.append("manifest config hash is missing or stale")
        for raw_path, expected_hash in manifest.get("code_and_protocol_sha256", {}).items():
            path = Path(raw_path)
            if not path.is_file() or sha256_file(path) != expected_hash:
                global_errors.append(f"manifest code/protocol hash stale: {raw_path}")
    seed_sets = {r["system"]: tuple(r.get("seeds") or []) for r in results}
    if len({v for v in seed_sets.values() if v}) > 1:
        global_errors.append(f"seed differs across systems: {seed_sets}")

    ok = not global_errors and all(not r["errors"] for r in results)

    print(
        f"slice: {args.slice}  selected={args.sample_from}..{sample_to} "
        f"n={len(slice_ids)}  sha256={slice_sha[:16]}..."
    )
    print(f"{'system':<12}{'status':<8}{'n':>5}{'acc':>8}  judge / answerers")
    for r in results:
        status = "PASS" if not r["errors"] else "FAIL"
        acc = r.get("overall_accuracy")
        acc_s = f"{acc:.3f}" if isinstance(acc, (int, float)) else "-"
        judges = ",".join(r.get("judge_models") or ["?"])
        models = ",".join(r.get("answer_models") or ["?"])
        print(
            f"{r['system']:<12}{status:<8}{str(r.get('n_sessions', '-')):>5}"
            f"{acc_s:>8}  {judges} / {models}"
        )
        for e in r["errors"]:
            print(f"    ERROR  {e}")
        for w in r["warnings"]:
            print(f"    warn   {w}")
    for e in global_errors:
        print(f"GLOBAL ERROR  {e}")

    payload = {
        "run_root": str(args.run_root),
        "slice": str(args.slice),
        "slice_sha256": slice_sha,
        "sample_from": args.sample_from,
        "sample_to": sample_to,
        "expected_n": expected_n,
        "expected_answer_model": args.expected_answer_model,
        "expected_answer_provider": args.expected_answer_provider,
        "allowed_answer_providers": args.allowed_answer_provider,
        "required_answer_providers": args.required_answer_provider,
        "expected_judge_primary": args.expected_judge_primary,
        "allowed_judge_fallbacks": args.allowed_judge_fallback,
        "allowed_auxiliary_models": args.allowed_auxiliary_model,
        "homogeneous": ok,
        "systems": results,
        "global_errors": global_errors,
        "manifest_status": manifest.get("status"),
    }
    out = args.out or (args.run_root / "homogeneity_report.json")
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n{'HOMOGENEOUS RUN: PASS' if ok else 'HOMOGENEOUS RUN: FAIL'}  (report -> {out})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
