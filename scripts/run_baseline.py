"""Run a memory baseline over a LongMemEval-S slice and write report + judgments.

CLI matches M1-W2 §3.3 + M1-W3 §3.4:

    # Baseline 1 — no memory:
    python scripts/run_baseline.py \
        --baseline no_memory \
        --slice data/slices/longmemeval_s_50_seed0.jsonl \
        --out runs/m1w2/no_memory \
        --seed 0

    # Baseline 2 — flat-vector (MiniLM + FAISS IndexFlatIP, k=5):
    python scripts/run_baseline.py \
        --baseline flat_vector \
        --slice data/slices/longmemeval_s_50_seed0.jsonl \
        --out runs/m1w3/flat_vector \
        --seed 0 --k 5

Backends:
  --ollama         Use a local Ollama daemon (laptop/dev path; M1-W2 default)
  --fake           Use the deterministic FakeLLM (hermetic, no network)
  (default)        Use build_llm() — picks up configs/inference.yaml

Files written under --out:
  report.json         Aggregate per-competency report (EvalReport.to_dict())
  judgments.jsonl     One graded session per line (raw judge rationales)
  judge_cache.jsonl   Append-only judge-call cache (re-runs are instant)
  predictions.jsonl   One BaselineAnswer per line (M4 deliverable name)
  answers.jsonl       One BaselineAnswer per line (predictions + tokens; for
                      flat_vector, `extras` carries retrieval telemetry —
                      scores, session_ids, turn_idxs)
  run.log             stdout/stderr capture (caller pipes)
  results.md          Markdown rendering of the report (same as print_report.py)
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from m4w13_validation import action_log_required, validate_run_dir

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ksa.baselines import (  # noqa: E402
    FlatVectorBaseline,
    FlatVectorStore,
    NaiveOverwriteBaseline,
    NoMemoryBaseline,
    OllamaEmbedder,
    OpenAICompatibleEmbedder,
    RecencyPruningBaseline,
    TurnEmbedder,
    build_session_corpus,
    build_session_corpus_for_recency,
)
from ksa.classifier import RelationClassifier  # noqa: E402
from ksa.controller.active import ScorecardConfig, load_scorecard_config  # noqa: E402
from ksa.data.longmemeval import iter_longmemeval_s  # noqa: E402
from ksa.eval.judge import JudgeBackendConfig, build_judge_backend  # noqa: E402
from ksa.eval.longmemeval import (  # noqa: E402
    GradeResult,
    JudgmentCache,
    LongMemEvalGrader,
    build_eval_report,
    evaluate_baseline,
    looks_degenerate_answer,
)
from ksa.extraction import Extractor  # noqa: E402
from ksa.inference.llm import (  # noqa: E402
    LLM,
    HuggingFaceLLM,
    InferenceConfig,
    StructuredLLM,  # noqa: E402
)
from ksa.pipeline import ControllerOrchestrator  # noqa: E402

_BASELINES_M1_W2 = {"no_memory"}
_BASELINES_M1_W3 = {"flat_vector"}
_BASELINES_M1_W4 = {"recency"}
_BASELINES_M3_W10 = {"naive_overwrite", "controller"}
_BASELINES_KNOWN = _BASELINES_M1_W2 | _BASELINES_M1_W3 | _BASELINES_M1_W4 | _BASELINES_M3_W10
_QUALITY_PRESET_NONE = "none"
_QUALITY_PRESET_MAX_A10G = "max-a10g"
_QUALITY_PRESET_MAX_A100_40GB = "max-a100-40gb"
_QUALITY_PRESETS = (
    _QUALITY_PRESET_NONE,
    _QUALITY_PRESET_MAX_A10G,
    _QUALITY_PRESET_MAX_A100_40GB,
)
_MAX_A10G_MODEL = "Qwen/Qwen2.5-7B-Instruct"


@dataclass(frozen=True)
class _ResumeState:
    answer_rows: list[dict[str, Any]]
    grades: list[GradeResult]
    completed_session_ids: set[str]


def _iter_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _write_jsonl_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


def _grade_from_row(row: dict[str, Any]) -> GradeResult | None:
    fields = dataclasses.fields(GradeResult)
    payload = {f.name: row[f.name] for f in fields if f.name in row}
    # Only fields WITHOUT a default are mandatory. Optional fields (e.g. token
    # counts, used_fallback, and any future additions) fall back to their
    # dataclass defaults, so adding a field to GradeResult never invalidates an
    # existing judgments.jsonl on resume.
    required = {
        f.name
        for f in fields
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
    }
    if required - payload.keys():
        return None
    try:
        return GradeResult(**payload)
    except TypeError:
        return None


def _load_resume_state(
    *,
    sessions: list[Any],
    answers_path: Path,
    judgments_path: Path,
    baseline_name: str,
) -> _ResumeState:
    answer_by_session: dict[str, dict[str, Any]] = {}
    for row in _iter_jsonl_rows(answers_path):
        session_id = row.get("session_id")
        if not isinstance(session_id, str):
            continue
        row_baseline = row.get("baseline")
        if row_baseline is not None and row_baseline != baseline_name:
            continue
        answer_by_session[session_id] = row

    grade_by_session: dict[str, GradeResult] = {}
    for row in _iter_jsonl_rows(judgments_path):
        grade = _grade_from_row(row)
        if grade is not None:
            grade_by_session[grade.session_id] = grade

    answer_rows: list[dict[str, Any]] = []
    grades: list[GradeResult] = []
    completed_session_ids: set[str] = set()
    for sess in sessions:
        answer_row = answer_by_session.get(sess.session_id)
        grade = grade_by_session.get(sess.session_id)
        if answer_row is None or grade is None:
            continue
        if grade.competency != sess.competency:
            continue
        answer_rows.append(answer_row)
        grades.append(grade)
        completed_session_ids.add(sess.session_id)
    return _ResumeState(
        answer_rows=answer_rows,
        grades=grades,
        completed_session_ids=completed_session_ids,
    )


def _build_llm(args: argparse.Namespace) -> LLM:
    """Resolve the answerer LLM from CLI flags."""
    if args.fake:
        from ksa.inference.fake import FakeLLM

        return FakeLLM()
    if args.openai_compatible:
        return _openai_llm(args, require_json=False)
    if args.hf:
        return HuggingFaceLLM(_hf_config(args, args.hf_model))
    if args.ollama:
        from ksa.inference.ollama import OllamaLLM

        return OllamaLLM(
            model_id=args.ollama_model,
            host=args.ollama_host,
            timeout_s=args.ollama_timeout_s,
            think=args.ollama_think,
            num_ctx=args.ollama_num_ctx,
        )
    from ksa.inference.llm import build_llm, load_inference_config

    cfg = load_inference_config(args.config) if args.config else None
    return build_llm(cfg)


def _openai_llm(
    args: argparse.Namespace,
    *,
    model_id: str | None = None,
    require_json: bool,
    base_url: str | None = None,
    api_key_env: str | None = None,
    guided_json: dict | None = None,
    chat_template_kwargs_json: str | None = None,
    extra_body_json: str | None = None,
    fallback_model_ids: tuple[str, ...] | None = None,
    use_openmodel_primary: bool = True,
) -> LLM:
    from ksa.inference.fallback import FallbackLLM
    from ksa.inference.openai_compatible import OpenAICompatibleLLM
    from ksa.inference.openmodel_messages import OpenModelMessagesLLM

    response_format = {"type": "json_object"} if require_json else None
    # Provider-specific chat template kwargs. vLLM uses enable_thinking; NVIDIA
    # NIM models may use fields such as thinking/reasoning_effort.
    chat_template_kwargs: dict | None = None
    kwargs_json = chat_template_kwargs_json or getattr(
        args, "openai_chat_template_kwargs_json", None
    )
    if kwargs_json:
        parsed = json.loads(kwargs_json)
        if not isinstance(parsed, dict):
            raise SystemExit("--openai-chat-template-kwargs-json must decode to an object")
        chat_template_kwargs = parsed
    elif (enable_thinking := getattr(args, "openai_enable_thinking", None)) is not None:
        chat_template_kwargs = {"enable_thinking": bool(enable_thinking)}
    extra_body: dict | None = None
    body_json = extra_body_json or getattr(args, "openai_extra_body_json", None)
    if body_json:
        parsed = json.loads(body_json)
        if not isinstance(parsed, dict):
            raise SystemExit("--openai-extra-body-json must decode to an object")
        extra_body = parsed
    openai_llm = OpenAICompatibleLLM(
        model_id=model_id or args.openai_model,
        base_url=base_url or args.openai_base_url,
        api_key=args.openai_api_key,
        api_key_env=api_key_env or args.openai_api_key_env,
        timeout_s=args.openai_timeout_s,
        response_format=response_format,
        require_json=require_json,
        fallback_model_ids=(
            tuple(args.openai_fallback_model or ())
            if fallback_model_ids is None
            else fallback_model_ids
        ),
        log_path=args.openai_log_path or (args.out / "llm_calls.jsonl"),
        include_raw_response=args.openai_include_raw_responses,
        chat_template_kwargs=chat_template_kwargs,
        guided_json=guided_json,
        extra_body=extra_body,
        retry_max_attempts=getattr(args, "openai_retry_max_attempts", 3),
        retry_initial_delay_s=getattr(args, "openai_retry_initial_delay_s", 1.0),
        retry_max_delay_s=getattr(args, "openai_retry_max_delay_s", 10.0),
        # Expose the server context window so the controller prompt-budget guard
        # trims retrieved context instead of overflowing vLLM (HTTP 400).
        num_ctx=getattr(args, "openai_max_model_len", None),
    )
    if not (use_openmodel_primary and args.openmodel_primary):
        return openai_llm
    primary_model = args.openmodel_model or _openmodel_model_for(model_id or args.openai_model)
    openmodel_llm = OpenModelMessagesLLM(
        model_id=primary_model,
        base_url=args.openmodel_base_url,
        api_key_env=args.openmodel_api_key_env,
        api_key_envs=_split_csv(args.openmodel_api_key_envs),
        timeout_s=args.openmodel_timeout_s,
        require_json=require_json,
        log_path=args.openai_log_path or (args.out / "llm_calls.jsonl"),
        include_raw_response=args.openai_include_raw_responses,
    )
    return FallbackLLM((openmodel_llm, openai_llm))


def _openmodel_model_for(model_id: str) -> str:
    """Map provider-qualified DeepSeek ids to OpenModel ids."""
    if model_id == "deepseek-ai/deepseek-v4-flash":
        return "deepseek-v4-flash"
    return model_id.rsplit("/", 1)[-1]


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _hf_config(args: argparse.Namespace, model_id: str) -> InferenceConfig:
    return InferenceConfig(
        model_id=model_id,
        dtype=args.hf_dtype,
        device_map=args.hf_device_map,
        load_in_4bit=args.hf_load_in_4bit,
        trust_remote_code=args.hf_trust_remote_code,
        max_seq_len=args.hf_max_seq_len,
        enable_thinking=getattr(args, "hf_enable_thinking", None),
        backend="huggingface",
    )


def _build_judge(args: argparse.Namespace, answerer: LLM) -> LLM:
    """Resolve the judge LLM from explicit M4 backend flags."""
    if args.fake_judge:
        from ksa.inference.fake import FakeLLM

        return FakeLLM()

    if args.judge_backend == "openai_compatible":
        return _openai_llm(
            args,
            model_id=args.judge_model or args.openai_model,
            require_json=True,
            base_url=args.judge_openai_base_url,
            api_key_env=args.judge_openai_api_key_env,
            chat_template_kwargs_json=args.judge_openai_chat_template_kwargs_json,
            extra_body_json=args.judge_openai_extra_body_json,
            fallback_model_ids=tuple(
                args.judge_openai_fallback_model or args.openai_fallback_model or ()
            ),
            use_openmodel_primary=False,
        )

    judge_model = args.judge_model or args.ollama_judge_model
    judge_backend = args.judge_backend
    if args.judge_config:
        cfg = JudgeBackendConfig.from_yaml(args.judge_config)
    elif judge_model:
        backend = "ollama" if args.judge_backend == "same_as_answerer" else args.judge_backend
        cfg = JudgeBackendConfig(
            backend=backend,
            model_id=judge_model,
            ollama_host=args.ollama_host,
            num_ctx=args.judge_num_ctx,
            timeout_s=args.judge_timeout_s,
            response_format="json" if args.judge_json_format else None,
            think=args.judge_think,
            hf_dtype=args.hf_dtype,
            hf_device_map=args.hf_device_map,
            hf_load_in_4bit=args.hf_load_in_4bit,
            hf_trust_remote_code=args.hf_trust_remote_code,
            hf_max_seq_len=args.hf_max_seq_len,
        )
    else:
        cfg = JudgeBackendConfig(
            backend=judge_backend,
            model_id=args.judge_model
            or (args.hf_model if judge_backend in {"hf", "huggingface"} else None),
            ollama_host=args.ollama_host,
            num_ctx=args.judge_num_ctx,
            timeout_s=args.judge_timeout_s,
            response_format="json" if args.judge_json_format else None,
            think=args.judge_think,
            hf_dtype=args.hf_dtype,
            hf_device_map=args.hf_device_map,
            hf_load_in_4bit=args.hf_load_in_4bit,
            hf_trust_remote_code=args.hf_trust_remote_code,
            hf_max_seq_len=args.hf_max_seq_len,
        )
    return build_judge_backend(cfg, answerer=answerer)


def _load_scorecard_config(args: argparse.Namespace) -> ScorecardConfig:
    config = load_scorecard_config(args.scorecard_config)
    if args.theta_abs is None:
        return config
    if not 0.0 <= args.theta_abs <= 1.0:
        raise SystemExit("--theta-abs must be between 0.0 and 1.0")
    return ScorecardConfig(
        weights=config.weights,
        theta_sup=dict(config.theta_sup),
        theta_abs={memory_type: float(args.theta_abs) for memory_type in config.theta_abs},
    )


def _scorecard_config_payload(
    config: ScorecardConfig, args: argparse.Namespace
) -> dict[str, object]:
    return {
        "scorecard_config": str(args.scorecard_config),
        "scorecard_config_sha256": _sha256(args.scorecard_config),
        "theta_abs_override": args.theta_abs,
        "theta_sup": {key: float(value) for key, value in config.theta_sup.items()},
        "theta_abs": {key: float(value) for key, value in config.theta_abs.items()},
        "quality_preset": args.quality_preset,
        "answer_retry_on_unknown": args.answer_retry_on_unknown,
        "controller_prior_top_k": args.controller_prior_top_k,
        "controller_prior_similarity_threshold": args.controller_prior_similarity_threshold,
        "controller_temporal_scaffold": args.controller_temporal_scaffold,
        "controller_computation_answerer": args.controller_computation_answerer,
        "controller_include_raw_user_context": args.controller_include_raw_user_context,
        "controller_retrieval_query_augmentation": args.controller_retrieval_query_augmentation,
        "controller_deterministic_numeric_supersede": args.controller_deterministic_numeric_supersede,
    }


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_embedder(args: argparse.Namespace):
    """Build the retrieval embedder shared by memory baselines."""
    if args.fake_embedder:
        from ksa.baselines.embeddings import FakeEmbedder

        return FakeEmbedder(embedding_dim=64)
    if args.embedder_backend == "ollama":
        return OllamaEmbedder(
            model_id=args.embedder_ollama_model,
            host=args.embedder_ollama_host or args.ollama_host,
            timeout_s=(
                args.embedder_ollama_timeout_s
                if args.embedder_ollama_timeout_s is not None
                else args.ollama_timeout_s
            ),
            batch_size=args.embedder_ollama_batch_size,
        )
    if args.embedder_backend == "openai_compatible":
        return OpenAICompatibleEmbedder(
            model_id=args.embedder_openai_model,
            # Dedicated embedding endpoint (e.g. the shared jina server) so the
            # embedder does not hit the LLM server's base_url.
            base_url=getattr(args, "embedder_openai_base_url", None) or args.openai_base_url,
            api_key=args.openai_api_key,
            api_key_env=args.openai_api_key_env,
            timeout_s=args.embedder_openai_timeout_s or args.openai_timeout_s,
            batch_size=args.embedder_openai_batch_size,
            log_path=str(args.out / "embedding_calls.jsonl"),
            max_retries=args.embedder_openai_max_retries,
            backoff_s=args.embedder_openai_backoff_s,
            min_interval_s=args.embedder_openai_min_interval_s,
            max_batch_chars=args.embedder_openai_max_batch_chars,
        )
    embedder_kwargs: dict[str, object] = {"device": args.embedder_device}
    if getattr(args, "embedder_st_model", None):
        embedder_kwargs["model_id"] = args.embedder_st_model
    if getattr(args, "embedder_trust_remote_code", False):
        embedder_kwargs["trust_remote_code"] = True
    if getattr(args, "embedder_task", None):
        embedder_kwargs["task"] = args.embedder_task
    if getattr(args, "embedder_prompt_name", None):
        embedder_kwargs["prompt_name"] = args.embedder_prompt_name
    return TurnEmbedder(**embedder_kwargs)


def _build_extractor(args: argparse.Namespace, out_dir: Path):
    """Build the shared M2 extractor."""
    if args.ollama:
        from ksa.inference.ollama import OllamaLLM

        extractor_model = args.extractor_ollama_model or args.ollama_model
        extractor_inner = OllamaLLM(
            model_id=extractor_model,
            host=args.ollama_host,
            timeout_s=args.ollama_timeout_s,
            num_ctx=args.structured_num_ctx,
            response_format="json" if args.structured_json_format else None,
            think=args.ollama_think,
        )
    elif args.hf:
        extractor_model = args.extractor_hf_model or args.hf_model
        extractor_inner = HuggingFaceLLM(_hf_config(args, extractor_model))
    elif args.openai_compatible:
        extractor_inner = _openai_llm(
            args,
            model_id=args.extractor_openai_model or args.openai_model,
            require_json=True,
            base_url=getattr(args, "extractor_openai_base_url", None),
        )
    else:
        extractor_inner = _build_llm(args)

    extractor_llm = StructuredLLM(extractor_inner)
    return Extractor.from_template_file(
        extractor_llm,
        args.extraction_prompt,
        log_path=out_dir / "extraction_trace.jsonl",
    )


def _build_extractor_and_classifier(args: argparse.Namespace, out_dir: Path):
    """Build the shared M3-W10 extractor + relation classifier."""
    extractor = _build_extractor(args, out_dir)
    if args.ollama:
        from ksa.inference.ollama import OllamaLLM

        classifier_model = args.classifier_ollama_model or args.ollama_model
        classifier_inner = OllamaLLM(
            model_id=classifier_model,
            host=args.ollama_host,
            timeout_s=args.ollama_timeout_s,
            num_ctx=args.structured_num_ctx,
            response_format="json" if args.structured_json_format else None,
            think=args.ollama_think,
        )
    elif args.hf:
        classifier_model = args.classifier_hf_model or args.hf_model
        classifier_inner = HuggingFaceLLM(_hf_config(args, classifier_model))
    elif args.openai_compatible:
        classifier_inner = _openai_llm(
            args,
            model_id=args.classifier_openai_model or args.openai_model,
            require_json=True,
            base_url=getattr(args, "classifier_openai_base_url", None),
        )
    else:
        classifier_inner = _build_llm(args)

    classifier_llm = StructuredLLM(classifier_inner)
    classifier = RelationClassifier.from_template_files(
        classifier_llm,
        args.relation_stage1_prompt,
        args.relation_stage2_prompt,
        log_path=out_dir / "relation_trace.jsonl",
    )
    return extractor, classifier


def _build_classifier_escalation(args: argparse.Namespace, out_dir: Path):
    """Build the larger escalation relation classifier for the cascade.

    Returns None unless an escalation model is configured (HF via
    --classifier-escalation-hf-model, or vLLM/openai via
    --classifier-escalation-openai-model). Mirrors the primary classifier build
    but points at the bigger model / its endpoint, and writes a separate trace.
    """
    esc_hf = getattr(args, "classifier_escalation_hf_model", None)
    esc_openai = getattr(args, "classifier_escalation_openai_model", None)
    if not esc_hf and not esc_openai:
        return None
    if args.openai_compatible and esc_openai:
        inner = _openai_llm(
            args,
            model_id=esc_openai,
            require_json=True,
            base_url=getattr(args, "classifier_escalation_openai_base_url", None),
        )
    elif args.hf and esc_hf:
        inner = HuggingFaceLLM(_hf_config(args, esc_hf))
    elif args.ollama and esc_hf:
        from ksa.inference.ollama import OllamaLLM

        inner = OllamaLLM(
            model_id=esc_hf,
            host=args.ollama_host,
            timeout_s=args.ollama_timeout_s,
            num_ctx=args.structured_num_ctx,
            response_format="json" if args.structured_json_format else None,
            think=args.ollama_think,
        )
    else:
        return None
    classifier_llm = StructuredLLM(inner)
    return RelationClassifier.from_template_files(
        classifier_llm,
        args.relation_stage1_prompt,
        args.relation_stage2_prompt,
        log_path=out_dir / "relation_trace_escalation.jsonl",
    )


def _build_baseline(args: argparse.Namespace, llm: LLM, sessions):
    """Construct the requested baseline.

    `sessions` is the materialized slice list. Memory baselines use it to
    resolve the allowed per-question memory corpus into turns. For cleaned
    LongMemEval records this means attached `haystack_sessions`, not oracle
    `answer_session_ids`. The no-memory baseline ignores it.
    """
    if args.baseline == "no_memory":
        return NoMemoryBaseline(llm=llm, seed=args.seed)

    if args.baseline == "flat_vector":
        # Build session corpus over the slice. The baseline resolves the
        # allowed memory IDs at answer time and excludes the current session.
        # Embedder selection is controlled by --embedder-backend. The
        # default remains MiniLM for legacy runs; M4 Ollama drivers pass
        # --embedder-backend=ollama to avoid local torch/ST crashes.
        corpus = build_session_corpus(sessions)
        embedder = _build_embedder(args)
        store = FlatVectorStore(embedder=embedder)
        return FlatVectorBaseline(
            llm=llm,
            store=store,
            corpus=corpus,
            k=args.k,
            seed=args.seed,
        )

    if args.baseline == "recency":
        # M1-W4 §3.3 default: trivial extractor. M4-W13 can switch to the
        # proper M2 LLM extractor via --recency-extractor llm.
        corpus = build_session_corpus_for_recency(sessions)
        embedder = _build_embedder(args)
        action_log_path: Path | None = None
        if not args.no_action_log:
            action_log_path = args.out / "action_log.jsonl"
        extractor = _build_extractor(args, args.out) if args.recency_extractor == "llm" else None
        return RecencyPruningBaseline(
            llm=llm,
            embedder=embedder,
            corpus=corpus,
            extractor=extractor,
            capacity=args.capacity,
            k=args.k,
            seed=args.seed,
            action_log_path=action_log_path,
            append_action_log=getattr(args, "append_action_log", False),
            extraction_max_new_tokens=args.extraction_max_new_tokens,
            memory_prefilter_top_k=args.recency_memory_top_k,
            raw_turn_fallback=args.recency_raw_turn_fallback,
            progress=args.recency_progress,
        )

    if args.baseline in {"naive_overwrite", "controller"}:
        corpus = build_session_corpus(sessions)
        embedder = _build_embedder(args)
        extractor, classifier = _build_extractor_and_classifier(args, args.out)
        action_log_path: Path | None = None
        if not args.no_action_log:
            action_log_path = args.out / "action_log.jsonl"
        klass = (
            NaiveOverwriteBaseline if args.baseline == "naive_overwrite" else ControllerOrchestrator
        )
        scorecard_config = _load_scorecard_config(args)
        kwargs: dict[str, object] = dict(
            llm=llm,
            extractor=extractor,
            classifier=classifier,
            corpus=corpus,
            embedder=embedder,
            config=scorecard_config,
            k=args.k,
            seed=args.seed,
            action_log_path=action_log_path,
            append_action_log=getattr(args, "append_action_log", False),
            extraction_cache_path=args.out / "extraction_cache.jsonl",
            relation_cache_path=args.out / "relation_cache.jsonl",
            extraction_max_new_tokens=args.extraction_max_new_tokens,
            relation_max_new_tokens=args.relation_max_new_tokens,
            progress=args.controller_progress,
            memory_prefilter_top_k=args.controller_memory_top_k,
            raw_turn_fallback=args.controller_raw_turn_fallback,
            retrieval_neighbor_window=args.controller_retrieval_neighbor_window,
            include_assistant_context=args.controller_include_assistant_context,
            include_raw_user_context=args.controller_include_raw_user_context,
            retrieval_query_augmentation=args.controller_retrieval_query_augmentation,
            deterministic_numeric_supersede=args.controller_deterministic_numeric_supersede,
            answer_retry_on_unknown=args.answer_retry_on_unknown,
            prior_top_k=args.controller_prior_top_k,
            prior_similarity_threshold=args.controller_prior_similarity_threshold,
            temporal_scaffold=args.controller_temporal_scaffold,
            computation_answerer=args.controller_computation_answerer,
            # --- docx v7 fixes (opt-in; see orchestrator dataclass) ---
            per_competency_answer_prompt=args.per_competency_answer_prompt,
            verify_computation_bypass=args.controller_verify_computation_bypass,
            computation_bypass_min_confidence=args.controller_computation_bypass_min_confidence,
            ordinal_list_reconstruction=args.controller_ordinal_list_reconstruction,
            aggregation_scaffold=args.controller_aggregation_scaffold,
            extraction_concurrency=args.extraction_concurrency,
            fail_on_extraction_error=args.fail_on_extraction_error,
            shared_extraction_cache_path=(
                Path(args.shared_extraction_cache) if args.shared_extraction_cache else None
            ),
            answer_context_max_tokens=args.answer_context_max_tokens,
            answer_context_rerank=args.answer_context_rerank,
            history_aware_retrieval=args.controller_history_aware_retrieval,
            history_retrieval_k=args.controller_history_retrieval_k,
            answer_context_session_cap=args.answer_context_session_cap,
            prefilter_chunk_turns=args.prefilter_chunk_turns,
        )
        # §4 fix 3: optional stronger model for the escalate-on-Unknown retry.
        if getattr(args, "answer_escalation_openai_model", None):
            kwargs["answer_escalation_llm"] = _openai_llm(
                args,
                model_id=args.answer_escalation_openai_model,
                base_url=(args.answer_escalation_openai_base_url or args.openai_base_url),
                require_json=False,
            )
        if klass is ControllerOrchestrator:
            # Cascade: only the controller supports the escalation classifier.
            escalation = _build_classifier_escalation(args, args.out)
            if escalation is not None:
                kwargs["classifier_escalation"] = escalation
                kwargs["escalation_extraction_confidence"] = args.escalation_extraction_confidence
                kwargs["escalation_marker_burden"] = args.escalation_marker_burden
                kwargs["escalation_relations"] = tuple(
                    r.strip() for r in args.escalation_relations.split(",") if r.strip()
                )
        return klass(**kwargs)
    raise SystemExit(f"unknown baseline {args.baseline!r}")


def _apply_quality_preset(args: argparse.Namespace) -> None:
    if args.quality_preset == _QUALITY_PRESET_NONE:
        return
    if args.quality_preset not in {_QUALITY_PRESET_MAX_A10G, _QUALITY_PRESET_MAX_A100_40GB}:
        raise SystemExit(f"unknown quality preset {args.quality_preset!r}")
    args.fake = False
    args.ollama = False
    args.hf = True
    args.hf_model = _MAX_A10G_MODEL
    args.hf_dtype = "float16"
    args.hf_load_in_4bit = False
    args.hf_max_seq_len = max(int(args.hf_max_seq_len), 8192)
    args.k = 12
    args.recency_memory_top_k = 64
    args.recency_raw_turn_fallback = True
    args.controller_memory_top_k = 64
    args.controller_raw_turn_fallback = True
    args.controller_include_assistant_context = True
    args.controller_retrieval_neighbor_window = 2
    # Headroom so structured-JSON stages complete instead of truncating
    # mid-object (finish_reason=length) and losing the turn's extraction.
    args.extraction_max_new_tokens = 512
    args.relation_max_new_tokens = 256
    args.answer_retry_on_unknown = True
    args.controller_prior_top_k = 3
    args.controller_prior_similarity_threshold = 0.45
    args.controller_temporal_scaffold = True
    args.controller_computation_answerer = True
    args.controller_include_raw_user_context = True
    args.controller_retrieval_query_augmentation = True
    args.controller_deterministic_numeric_supersede = True


def _progress(i: int, n: int, sess, _ans, grade) -> None:
    mark = "✓" if grade.correct else "✗"
    pct = (100.0 * i / n) if n else 100.0
    print(
        f"  [{i:>3}/{n} {pct:5.1f}%] {mark} {sess.session_id:<22} {sess.competency:<28} "
        f"→ correct={grade.correct}",
        flush=True,
    )


def _resolve_sample_range(args: argparse.Namespace) -> tuple[int | None, int | None]:
    """Return a zero-based, half-open sample range from CLI args."""
    one_based = args.sample_from is not None or args.sample_to is not None
    zero_based = args.sample_start is not None or args.sample_end is not None
    if one_based and zero_based:
        raise SystemExit(
            "Use either --sample-from/--sample-to or --sample-start/--sample-end, not both."
        )
    if one_based:
        if args.sample_from is not None and args.sample_from < 1:
            raise SystemExit("--sample-from is 1-based and must be >= 1")
        if args.sample_to is not None and args.sample_to < 1:
            raise SystemExit("--sample-to is 1-based and must be >= 1")
        start = args.sample_from - 1 if args.sample_from is not None else None
        end = args.sample_to if args.sample_to is not None else None
    else:
        start = args.sample_start
        end = args.sample_end
        if start is not None and start < 0:
            raise SystemExit("--sample-start must be >= 0")
        if end is not None and end < 0:
            raise SystemExit("--sample-end must be >= 0")
    if start is not None and end is not None and start >= end:
        raise SystemExit("sample range is empty; start must be before end")
    return start, end


def _apply_sample_range(sessions: list, args: argparse.Namespace) -> list:
    start, end = _resolve_sample_range(args)
    if start is None and end is None:
        return sessions
    selected = sessions[start:end]
    start_label = 0 if start is None else start
    end_label = len(sessions) if end is None else min(end, len(sessions))
    print(
        f"[run_baseline] sample range: zero_based=[{start_label}:{end_label}) "
        f"selected={len(selected)}/{len(sessions)}",
        flush=True,
    )
    return selected


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", required=True, choices=sorted(_BASELINES_KNOWN))
    p.add_argument("--slice", required=True, type=Path, help="LongMemEval-S slice JSONL path")
    p.add_argument("--out", required=True, type=Path, help="Output directory; will be created")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-bootstrap", type=int, default=1000)
    p.add_argument(
        "--num-shards",
        type=int,
        default=1,
        help="Total session shards for parallel runs. >1 selects a "
        "round-robin subset (i %% num_shards == shard_index). "
        "Each shard is an independent process; merge afterwards.",
    )
    p.add_argument(
        "--shard-index", type=int, default=0, help="This process's shard index in [0, num_shards)."
    )
    p.add_argument(
        "--limit", type=int, default=None, help="Optional cap on sessions evaluated (smoke testing)"
    )
    p.add_argument(
        "--sample-from",
        type=int,
        default=None,
        help="1-based inclusive first sample to evaluate, e.g. 50.",
    )
    p.add_argument(
        "--sample-to",
        type=int,
        default=None,
        help="1-based inclusive last sample to evaluate, e.g. 100.",
    )
    p.add_argument(
        "--sample-start",
        type=int,
        default=None,
        help="Zero-based inclusive start index. Alternative to --sample-from.",
    )
    p.add_argument(
        "--sample-end",
        type=int,
        default=None,
        help="Zero-based exclusive end index. Alternative to --sample-to.",
    )
    p.add_argument(
        "--allow-blank-answers",
        action="store_true",
        help="Do not fail the run if one or more answer texts are blank. "
        "Use only for debugging broken model backends.",
    )
    p.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Resume from existing answers/judgments in --out. Completed "
        "session IDs are skipped, partial JSONL tails are ignored, "
        "and the final report is rebuilt from old plus new grades.",
    )
    p.add_argument(
        "--quality-preset",
        choices=_QUALITY_PRESETS,
        default=_QUALITY_PRESET_NONE,
        help="Lock a recall/accuracy-focused runtime profile. "
        "'max-a10g' and 'max-a100-40gb' force HF Qwen2.5-7B "
        "fp16 plus controller quality knobs; intended for "
        "quality runs, not final thesis-comparable numbers.",
    )

    # M1-W3 — flat-vector baseline knobs.
    p.add_argument(
        "--k",
        type=int,
        default=5,
        help="Top-k for flat_vector retrieval (default: 5; "
        "see NOTES/m1w3_design.md §2.4 for the choice). "
        "A k-sweep is deferred to Month-4 ablations.",
    )
    p.add_argument(
        "--embedder-device",
        default="cpu",
        help="Device for TurnEmbedder ('cpu' or 'cuda'). "
        "Default cpu — MiniLM-L6-v2 is ~80 MB and fine on CPU.",
    )
    p.add_argument(
        "--embedder-st-model",
        default=None,
        help="Override the sentence-transformers model id for the "
        "retrieval embedder (default: all-MiniLM-L6-v2). E.g. "
        "jinaai/jina-embeddings-v5-text-small — needs "
        "--embedder-trust-remote-code and a recent transformers.",
    )
    p.add_argument(
        "--embedder-trust-remote-code",
        action="store_true",
        help="Pass trust_remote_code=True when loading the ST model "
        "(required by custom-architecture embedders like Jina v5).",
    )
    p.add_argument(
        "--embedder-task",
        default=None,
        help="Optional encode() task for task-aware embedders "
        "(Jina v5: 'retrieval'). Ignored by models that don't "
        "accept it.",
    )
    p.add_argument(
        "--embedder-prompt-name",
        default=None,
        help="Optional encode() prompt_name for task-aware embedders "
        "(Jina v5: 'query' or 'document'). Ignored otherwise.",
    )
    p.add_argument(
        "--embedder-backend",
        choices=(
            "sentence_transformer",
            "ollama",
            "openai_compatible",
        ),
        default="sentence_transformer",
        help="Retrieval embedding backend. Use 'ollama' to avoid "
        "local sentence-transformers/torch and call /api/embed. "
        "Use 'openai_compatible' to call /v1/embeddings.",
    )
    p.add_argument(
        "--embedder-ollama-model",
        default="llama3.2:3b",
        help="Ollama model tag for retrieval embeddings when --embedder-backend=ollama.",
    )
    p.add_argument(
        "--embedder-ollama-host",
        default=None,
        help="Ollama host for retrieval embeddings. Defaults to --ollama-host.",
    )
    p.add_argument(
        "--embedder-ollama-timeout-s",
        type=float,
        default=None,
        help="HTTP timeout for Ollama embedding calls. Defaults to --ollama-timeout-s.",
    )
    p.add_argument(
        "--embedder-ollama-batch-size",
        type=int,
        default=16,
        help="Texts per Ollama /api/embed request.",
    )
    p.add_argument(
        "--embedder-openai-model",
        default="auto",
        help="OpenAI-compatible embedding model id for --embedder-backend=openai_compatible.",
    )
    p.add_argument(
        "--embedder-openai-base-url",
        default=None,
        help="Dedicated base_url for the embedding endpoint (e.g. the "
        "shared jina server at http://localhost:8100/v1). Defaults "
        "to --openai-base-url.",
    )
    p.add_argument(
        "--embedder-openai-timeout-s",
        type=float,
        default=None,
        help="HTTP timeout for OpenAI-compatible embeddings. Defaults to --openai-timeout-s.",
    )
    p.add_argument(
        "--embedder-openai-batch-size",
        type=int,
        default=16,
        help="Texts per OpenAI-compatible /v1/embeddings request.",
    )
    p.add_argument(
        "--embedder-openai-max-retries",
        type=int,
        default=6,
        help="Retries for transient /v1/embeddings 429/5xx errors.",
    )
    p.add_argument(
        "--embedder-openai-backoff-s",
        type=float,
        default=10.0,
        help="Initial exponential backoff for OpenAI-compatible embedding retries.",
    )
    p.add_argument(
        "--embedder-openai-min-interval-s",
        type=float,
        default=0.0,
        help="Minimum wall-clock spacing between OpenAI-compatible "
        "/v1/embeddings requests. Use for provider quota pacing.",
    )
    p.add_argument(
        "--embedder-openai-max-batch-chars",
        type=int,
        default=0,
        help="Split OpenAI-compatible embedding batches before the "
        "combined input character count exceeds this value. "
        "0 disables character-based splitting.",
    )
    p.add_argument(
        "--fake-embedder",
        action="store_true",
        help="Use the hermetic FakeEmbedder (sha256-based) instead of "
        "MiniLM. Only useful for smoke-testing the pipeline "
        "without sentence-transformers — DO NOT use for the "
        "thesis run. Mirrors the --fake / --fake-judge pattern.",
    )

    # M1-W4 — recency baseline knobs.
    p.add_argument(
        "--capacity",
        type=int,
        default=50,
        help="FIFO queue size for the recency baseline (default: 50; "
        "see NOTES/m1w4_design.md §1b for the choice). "
        "A capacity-sweep (N ∈ {10, 25, 50, 100}) is deferred "
        "to Month-4 ablations.",
    )
    p.add_argument(
        "--no-action-log",
        action="store_true",
        help="Disable action_log writing for recency. Default writes to <out>/action_log.jsonl.",
    )
    p.add_argument(
        "--recency-extractor",
        choices=("trivial", "llm"),
        default="trivial",
        help="B3 extractor mode. Use 'llm' for M4-W13 so recency "
        "uses the M2 extraction prompt instead of the M1 "
        "trivial every-user-turn extractor.",
    )
    p.add_argument(
        "--recency-memory-top-k",
        type=int,
        default=None,
        help="Optional fast-mode prefilter for B3 when "
        "--recency-extractor llm: embed all allowed haystack "
        "user turns and only run LLM extraction on the top-k "
        "turns nearest to the question. Omit for exact full "
        "B3 ingestion.",
    )
    p.add_argument(
        "--recency-raw-turn-fallback",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For B3 fast mode, if the extractor returns no items "
        "for a selected user turn, index the raw user turn as "
        "an episodic memory. Approximate recall-focused mode "
        "for small local HF extractors.",
    )
    p.add_argument(
        "--recency-progress",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Emit heartbeat logs while B3 resolves memory, "
        "prefilters, extracts turns, retrieves, and answers.",
    )

    # M3-W10 — shared extractor/classifier knobs for B4 and controller.
    # v_final -> v_final3: adds the episodic-events/acquisitions in-scope
    # section after the v4 run showed the precision rule discarding current
    # projects (Ford F-150), acquisitions (third plant), and trip durations.
    p.add_argument("--extraction-prompt", type=Path, default=Path("prompts/extraction_v_final3.j2"))
    p.add_argument(
        "--relation-stage1-prompt", type=Path, default=Path("prompts/relation_stage1_v0.j2")
    )
    p.add_argument(
        "--relation-stage2-prompt", type=Path, default=Path("prompts/relation_stage2_v0.j2")
    )
    p.add_argument("--scorecard-config", type=Path, default=Path("configs/controller_active.yaml"))
    p.add_argument(
        "--theta-abs",
        type=float,
        default=None,
        help="Override every controller theta_abs threshold for RC@C sweeps.",
    )
    p.add_argument("--extraction-max-new-tokens", type=int, default=512)
    p.add_argument("--relation-max-new-tokens", type=int, default=128)
    p.add_argument(
        "--controller-progress",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Emit heartbeat logs while B4/controller ingest memory, "
        "extract turns, retrieve, and answer. Useful for Colab "
        "runs where the first completed row can take a while.",
    )
    p.add_argument(
        "--controller-memory-top-k",
        type=int,
        default=None,
        help="Optional fast-mode prefilter for B4/controller: embed all "
        "allowed haystack user turns and only run LLM extraction "
        "on the top-k turns nearest to the question. Keeps the "
        "haystack corpus boundary but is approximate; omit for "
        "exact full-ingestion controller runs.",
    )
    p.add_argument(
        "--controller-raw-turn-fallback",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For B4/controller fast mode, if the extractor returns no "
        "items for a selected user turn, index the raw user turn "
        "as an episodic memory. This improves recall for small "
        "local HF extractors but is approximate.",
    )
    p.add_argument(
        "--controller-retrieval-neighbor-window",
        type=int,
        default=0,
        help="For B4/controller, append active memories from the same "
        "session within +/-N turn indices of each retrieved hit "
        "to the answer prompt. Useful when the answer requires "
        "nearby context from the same haystack session.",
    )
    p.add_argument(
        "--controller-include-assistant-context",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For B4/controller, add raw ASSISTANT turns from the allowed "
        "memory corpus to the retrieval pool. The user-only memory "
        "pipeline cannot otherwise answer questions whose evidence "
        "lives in assistant turns (the single-session-assistant "
        "competency; ~32%% of the LongMemEval dev slice). Default off "
        "so MGP-6 and validated controller runs are unchanged.",
    )
    p.add_argument(
        "--controller-include-raw-user-context",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For B4/controller, add raw USER turn chunks from the allowed "
        "memory corpus to the retrieval pool. Restores answer-time "
        "recall for facts the extraction prefilter never selected, "
        "with zero extra LLM extraction calls. Default off so "
        "validated runs are unchanged.",
    )
    p.add_argument(
        "--controller-retrieval-query-augmentation",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For B4/controller, run additive retrieval passes for "
        "aggregation/temporal questions: a widened main query, one "
        "query per event/item phrase named in the question, and a "
        "calendar-window pass for 'N weeks ago'/'in <month>' "
        "questions. Appended after the base top-k hits.",
    )
    p.add_argument(
        "--controller-deterministic-numeric-supersede",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For B4/controller, route same-slot numeric conflicts "
        "(shared anchor tokens, different numbers, newer timestamp) "
        "directly to Supersede without consulting the relation "
        "classifier LLM.",
    )
    p.add_argument(
        "--answer-retry-on-unknown",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For B4/controller, retry answer generation once when the "
        "first answer is exactly 'Unknown' but retrieved evidence "
        "is non-empty. Telemetry is written to answer extras.",
    )
    p.add_argument(
        "--controller-prior-top-k",
        type=int,
        default=1,
        help="Same-type prior candidates to compare semantically for "
        "B4/controller. Default 1 preserves newest-prior behavior; "
        "quality mode uses 3.",
    )
    p.add_argument(
        "--controller-temporal-scaffold",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For B4/controller, append a deterministic scaffolding block "
        "to temporal questions: event dates parsed from the memory "
        "TEXT (not just the session timestamp) plus a reference 'today' "
        "date, so the answerer does not have to parse/sort/subtract "
        "dates. Additive only (never overrides the model); default off.",
    )
    p.add_argument(
        "--controller-computation-answerer",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For B4/controller, run deterministic date/numeric/list solvers "
        "before the answer LLM. High-confidence results bypass the LLM; "
        "lower-confidence results are added as an auditable computation "
        "block. Default off for backwards-compatible experiment runs.",
    )
    p.add_argument(
        "--controller-prior-similarity-threshold",
        type=float,
        default=0.0,
        help="Minimum cosine similarity for a semantic prior to be sent "
        "to the relation classifier (only used when "
        "--controller-prior-top-k > 1). Priors below this are treated "
        "as independent without an LLM call, which cuts the dominant "
        "per-question latency and avoids small-model label noise on "
        "unrelated pairs. 0.0 (default) preserves current behavior.",
    )
    # --- docx v7 fixes (§4 accuracy / §5 efficiency; all opt-in) -------------
    p.add_argument(
        "--per-competency-answer-prompt",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="§4 fix 1: use a preference-profile answer prompt for "
        "single-session-preference questions (gold answers are "
        "'The user would prefer ...' profiles, not direct answers).",
    )
    p.add_argument(
        "--controller-verify-computation-bypass",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="§4 fix 5: never blindly emit a deterministic computation "
        "result — also run the LLM answer and reconcile (keep the "
        "LLM answer on disagreement).",
    )
    p.add_argument(
        "--controller-computation-bypass-min-confidence",
        type=float,
        default=0.0,
        help="§4 fix 5: minimum computation confidence required before a "
        "deterministic answer may bypass the LLM. 0.0 keeps prior behavior.",
    )
    p.add_argument(
        "--controller-ordinal-list-reconstruction",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="§4 fix 6: for 'Nth item of the list' questions, reassemble "
        "the full enumerated assistant list before indexing item N.",
    )
    p.add_argument(
        "--controller-aggregation-scaffold",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="§4 fix 4: for count/sum questions with no deterministic "
        "answer, ask the model to LIST matching mentions as JSON, "
        "then dedup + count/sum in code as a hint to the answerer.",
    )
    p.add_argument(
        "--extraction-concurrency",
        type=int,
        default=1,
        help="§5 fix 1: number of concurrent per-turn extraction calls "
        "within one question. 1 = serial (default). The ordered "
        "Keep/Supersede/Abstain decisions still run sequentially.",
    )
    p.add_argument(
        "--fail-on-extraction-error",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Abort the current session on provider/no-response or "
        "unrecoverable extraction output so shard retry/resume "
        "cannot publish silently incomplete memory state.",
    )
    p.add_argument(
        "--shared-extraction-cache",
        default=None,
        help="§5 fix 3: path to a content-keyed extraction cache shared "
        "across runs/ranges/systems (read at startup in addition to "
        "the per-run cache).",
    )
    p.add_argument(
        "--answer-context-max-tokens",
        type=int,
        default=0,
        help="§5 fix 4: cap the answer context at this many tokens (below "
        "num_ctx) for a tighter, cleaner context. 0 disables the cap.",
    )
    p.add_argument(
        "--answer-context-rerank",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="§5 fix 4: rerank retrieved items by score before the answer "
        "context cap so the highest-signal hits survive.",
    )
    p.add_argument(
        "--controller-history-aware-retrieval",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For explicit historical-state questions only, retrieve "
        "tagged superseded lineage alongside active memory. Current "
        "and unqualified questions remain active-only.",
    )
    p.add_argument(
        "--controller-history-retrieval-k",
        type=int,
        default=4,
        help="Maximum tagged superseded lineage rows added for an "
        "explicit historical-state question.",
    )
    p.add_argument(
        "--answer-context-session-cap",
        type=int,
        default=0,
        help="Before prompt-budget overflow, prioritize at most this "
        "many items per session in each role group. 0 disables.",
    )
    p.add_argument(
        "--prefilter-chunk-turns",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="§5 fix 6: chunk user turns before the extraction prefilter "
        "embeds them, so a long turn's tail is not lost to the "
        "embedder's 256-token truncation.",
    )
    p.add_argument(
        "--answer-escalation-openai-model",
        default=None,
        help="§4 fix 3: OpenAI-compatible model id for the escalate-on-"
        "Unknown answer retry (stronger than the primary answerer). "
        "Defaults to reusing the primary answerer when unset.",
    )
    p.add_argument(
        "--answer-escalation-openai-base-url",
        default=None,
        help="Base URL for --answer-escalation-openai-model. Defaults to --openai-base-url.",
    )
    p.add_argument(
        "--extractor-ollama-model",
        default=None,
        help="Ollama model for the M3-W10 extractor. Defaults to --ollama-model.",
    )
    p.add_argument(
        "--classifier-ollama-model",
        default=None,
        help="Ollama model for the M3-W10 relation classifier. Defaults to --ollama-model.",
    )
    p.add_argument(
        "--extractor-hf-model",
        default=None,
        help="HuggingFace model id for the M3-W10 extractor. Defaults to --hf-model.",
    )
    p.add_argument(
        "--classifier-hf-model",
        default=None,
        help="HuggingFace model id for the M3-W10 relation classifier. Defaults to --hf-model.",
    )
    p.add_argument(
        "--extractor-openai-model",
        default=None,
        help="OpenAI-compatible model id for the M3-W10 extractor. Defaults to --openai-model.",
    )
    p.add_argument(
        "--classifier-openai-model",
        default=None,
        help="OpenAI-compatible model id for the M3-W10 relation classifier. Defaults to --openai-model.",
    )
    # --- Per-role OpenAI/vLLM endpoint routing (role-based model standard) ---
    p.add_argument(
        "--openai-enable-thinking",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="vLLM chat_template_kwargs enable_thinking switch for "
        "Qwen3/Qwen3.5. --no-openai-enable-thinking suppresses "
        "<think> blocks server-side. Default unset.",
    )
    p.add_argument(
        "--extractor-openai-base-url",
        default=None,
        help="Override the OpenAI/vLLM base_url for the extractor "
        "(e.g. the 4B fast-path server). Defaults to --openai-base-url.",
    )
    p.add_argument(
        "--classifier-openai-base-url",
        default=None,
        help="Override the base_url for the primary relation classifier "
        "(4B fast path). Defaults to --openai-base-url.",
    )
    # --- Relation-classifier cascade (4B fast path -> 9B escalation) ---------
    p.add_argument(
        "--classifier-escalation-openai-model",
        default=None,
        help="Escalation relation classifier model id on an "
        "OpenAI/vLLM endpoint (e.g. the 9B server). Enables the "
        "cascade when set.",
    )
    p.add_argument(
        "--classifier-escalation-openai-base-url",
        default=None,
        help="base_url for the escalation classifier (9B server). Defaults to --openai-base-url.",
    )
    p.add_argument(
        "--classifier-escalation-hf-model",
        default=None,
        help="Escalation relation classifier HF model id (HF/ollama "
        "backends). Enables the cascade when set.",
    )
    p.add_argument(
        "--escalation-extraction-confidence",
        type=float,
        default=0.75,
        help="Escalate to the larger relation model when extraction "
        "confidence is below this (cascade).",
    )
    p.add_argument(
        "--escalation-marker-burden",
        type=float,
        default=0.35,
        help="Escalate when the negation/hedge marker burden exceeds this fraction (cascade).",
    )
    p.add_argument(
        "--escalation-relations",
        default="contradict,supersede,unclear",
        help="Comma-separated final relations that always escalate to "
        "the larger model (decision-critical labels).",
    )
    p.add_argument("--structured-num-ctx", type=int, default=4096)
    p.add_argument(
        "--structured-json-format",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Ask Ollama structured extractor/classifier calls for JSON output.",
    )

    # Answerer LLM selection.
    p.add_argument(
        "--config", type=Path, default=None, help="Inference config YAML (overrides default)"
    )
    p.add_argument(
        "--fake", action="store_true", help="Use the deterministic FakeLLM as the answerer"
    )
    p.add_argument(
        "--ollama", action="store_true", help="Use a local Ollama daemon as the answerer"
    )
    p.add_argument(
        "--hf",
        action="store_true",
        help="Use an in-process HuggingFace Transformers model as the answerer. "
        "For Colab/T4 speed, use one shared --hf-model for answerer, "
        "extractor, classifier, and judge.",
    )
    p.add_argument(
        "--openai-compatible",
        action="store_true",
        help="Use an OpenAI-compatible /v1/chat/completions endpoint "
        "as the answerer, extractor, classifier, or judge. This "
        "is the FreeLLMAPI path for local thesis runs.",
    )
    p.add_argument("--openai-base-url", default="http://localhost:3001/v1")
    p.add_argument(
        "--openai-max-model-len",
        type=int,
        default=8192,
        help="Server context window (vLLM --max-model-len). Exposed as "
        "the answerer's num_ctx so the controller prompt-budget "
        "guard trims retrieved context and never overflows the "
        "context window (avoids vLLM HTTP 400).",
    )
    p.add_argument(
        "--openai-api-key",
        default=None,
        help="Bearer token for the OpenAI-compatible endpoint. Prefer "
        "setting --openai-api-key-env instead of passing secrets "
        "on the command line.",
    )
    p.add_argument(
        "--openai-api-key-env",
        default="FREELLMAPI_KEY",
        help="Environment variable containing the OpenAI-compatible Bearer token.",
    )
    p.add_argument(
        "--openai-model",
        default="cogito-2.1:671b",
        help="Primary OpenAI-compatible model id. Defaults to the "
        "FreeLLMAPI route that passed the thesis supersession "
        "probe fastest.",
    )
    p.add_argument(
        "--openai-fallback-model",
        action="append",
        default=None,
        help="Additional OpenAI-compatible model id to try if the "
        "validation gate fails. Can be repeated.",
    )
    p.add_argument("--openai-timeout-s", type=float, default=120.0)
    p.add_argument("--openai-retry-max-attempts", type=int, default=3)
    p.add_argument("--openai-retry-initial-delay-s", type=float, default=1.0)
    p.add_argument("--openai-retry-max-delay-s", type=float, default=10.0)
    p.add_argument(
        "--openai-chat-template-kwargs-json",
        default=None,
        help="JSON object merged as chat_template_kwargs for "
        "OpenAI-compatible requests. Overrides "
        "--openai-enable-thinking when set.",
    )
    p.add_argument(
        "--openai-extra-body-json",
        default=None,
        help="JSON object merged into OpenAI-compatible request "
        "bodies. Use this for provider-specific routing such "
        "as OpenRouter's provider.order/provider.only.",
    )
    p.add_argument(
        "--openmodel-primary",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Try OpenModel Messages API before the OpenAI-compatible "
        "endpoint for answer/extractor/classifier calls.",
    )
    p.add_argument("--openmodel-base-url", default="https://api.openmodel.ai/v1")
    p.add_argument("--openmodel-api-key-env", default="OPENMODEL_API_KEY")
    p.add_argument(
        "--openmodel-api-key-envs",
        default=None,
        help="Comma-separated OpenModel API key env names. Calls "
        "start from the next key in round-robin order and try "
        "the remaining keys before falling back.",
    )
    p.add_argument(
        "--openmodel-model",
        default=None,
        help="OpenModel model id for primary calls. Defaults to a "
        "mapped form of --openai-model, e.g. deepseek-v4-flash.",
    )
    p.add_argument("--openmodel-timeout-s", type=float, default=120.0)
    p.add_argument(
        "--openai-log-path",
        type=Path,
        default=None,
        help="JSONL metadata log for OpenAI-compatible calls. Defaults to <out>/llm_calls.jsonl.",
    )
    p.add_argument(
        "--openai-include-raw-responses",
        action="store_true",
        help="Store raw response text in llm_calls.jsonl. Default keeps only hashes and metadata.",
    )
    p.add_argument(
        "--hf-model", default="Qwen/Qwen2.5-3B-Instruct", help="HuggingFace model id for --hf runs."
    )
    p.add_argument("--hf-dtype", choices=("bfloat16", "float16", "float32"), default="float16")
    p.add_argument("--hf-device-map", default="auto")
    p.add_argument("--hf-load-in-4bit", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--hf-trust-remote-code", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--hf-max-seq-len", type=int, default=4096)
    p.add_argument(
        "--hf-enable-thinking",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Control the chat-template thinking switch for reasoning "
        "models (Qwen3/Qwen3.5). Pass --no-hf-enable-thinking to "
        "suppress <think> blocks so the small answer/JSON budget is "
        "spent on the final answer. Default (unset) leaves the "
        "template alone — correct for non-thinking models like "
        "Qwen2.5. The harness also strips any stray <think> span.",
    )
    p.add_argument(
        "--ollama-model",
        default="gemma4:e4b",
        help="Ollama tag for the answerer (default: gemma4:e4b)",
    )
    p.add_argument(
        "--ollama-num-ctx",
        type=int,
        default=8192,
        help="Context window for the answerer Ollama model. Must exceed "
        "the answer prompt size, or Ollama truncates the prompt and "
        "leaves no room to generate (the answer comes back as a single "
        "token). The controller/quality prompts (k>=10, assistant "
        "context, neighbor window) can reach ~8k tokens, so the old "
        "2048 default broke them. Raise further for very large k.",
    )
    p.add_argument("--ollama-host", default="http://localhost:11434")
    p.add_argument(
        "--ollama-timeout-s",
        type=float,
        default=900.0,
        help="HTTP timeout for answerer/extractor/classifier Ollama calls.",
    )
    p.add_argument(
        "--ollama-think",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable Ollama thinking output for answerer/extractor/classifier. "
        "Default false so reasoning models return final content instead of "
        "spending the token budget on hidden thinking.",
    )

    # Judge LLM selection.
    p.add_argument(
        "--fake-judge", action="store_true", help="Use the FakeLLM as the judge (smoke runs only)"
    )
    p.add_argument(
        "--judge-config",
        type=Path,
        default=None,
        help="YAML file containing a 'judge:' backend config",
    )
    p.add_argument(
        "--judge-backend",
        choices=(
            "same_as_answerer",
            "ollama",
            "huggingface",
            "hf",
            "fake",
            "openai_compatible",
        ),
        default="same_as_answerer",
        help="Judge backend. M4-W13 Ollama runs should use --judge-backend "
        "ollama with --judge-model. Fast HF runs can use "
        "--judge-backend same_as_answerer or hf. FreeLLMAPI runs "
        "can use --judge-backend openai_compatible.",
    )
    p.add_argument(
        "--judge-model",
        default=None,
        help="Explicit judge model id. With --judge-backend ollama, this is the Ollama tag.",
    )
    p.add_argument("--judge-num-ctx", type=int, default=2048)
    p.add_argument(
        "--judge-timeout-s",
        type=float,
        default=900.0,
        help="HTTP timeout for judge Ollama calls. Large local judges can cold-load slowly.",
    )
    p.add_argument(
        "--judge-json-format",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Ask Ollama judge calls for JSON output.",
    )
    p.add_argument(
        "--judge-think",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable Ollama thinking output for judge calls. Default false.",
    )
    p.add_argument(
        "--judge-openai-chat-template-kwargs-json",
        default=None,
        help="JSON object used as chat_template_kwargs only for an OpenAI-compatible judge.",
    )
    p.add_argument(
        "--judge-openai-extra-body-json",
        default=None,
        help="JSON object merged into OpenAI-compatible judge request bodies.",
    )
    p.add_argument(
        "--judge-openai-fallback-model",
        action="append",
        default=None,
        help="Additional OpenAI-compatible judge model id to try if "
        "the primary judge is unavailable or fails validation. "
        "Can be repeated. Defaults to --openai-fallback-model "
        "when omitted.",
    )
    p.add_argument(
        "--judge-openai-base-url",
        default=None,
        help="Endpoint for the OpenAI-compatible judge. Defaults to --openai-base-url.",
    )
    p.add_argument(
        "--judge-openai-api-key-env",
        default=None,
        help="Environment variable containing the OpenAI-compatible Bearer token for the judge. "
        "Defaults to --openai-api-key-env.",
    )
    p.add_argument(
        "--ollama-judge-model",
        default=None,
        help="Legacy alias for --judge-backend ollama --judge-model MODEL.",
    )
    args = p.parse_args()
    _apply_quality_preset(args)

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    answers_path = out_dir / "answers.jsonl"
    predictions_path = out_dir / "predictions.jsonl"
    judgments_path = out_dir / "judgments.jsonl"
    cache_path = out_dir / "judge_cache.jsonl"
    report_path = out_dir / "report.json"
    md_path = out_dir / "results.md"

    print(f"[run_baseline] baseline={args.baseline} slice={args.slice} out={out_dir}", flush=True)
    # Memory-safe streaming load. Previously every shard did
    # `list(iter_longmemeval_s(...))`, materializing the ENTIRE slice (all rows
    # WITH their full haystack corpus_sessions, ~5 MB/row) before selecting its
    # ~1/num_shards share. At 40 rows x 20 shards that fit; at 180 rows it OOMs
    # and the OS kills the shards mid-startup. We now stream the file and keep
    # only THIS shard's rows, applying the exact same window -> limit ->
    # round-robin ordering, so per-session grades are unchanged.
    _range_start, _range_end = _resolve_sample_range(args)
    _limit = args.limit if args.limit else None
    _pos = 0  # position within the sample-range window (pre-shard)
    sessions = []
    for _i, _sess in enumerate(iter_longmemeval_s(args.slice)):
        if _range_start is not None and _i < _range_start:
            continue
        if _range_end is not None and _i >= _range_end:
            break
        if _limit is not None and _pos >= _limit:
            break
        if args.num_shards <= 1 or _pos % args.num_shards == args.shard_index:
            sessions.append(_sess)
        _pos += 1
    if args.num_shards > 1:
        print(
            f"[run_baseline] shard {args.shard_index}/{args.num_shards}: "
            f"{len(sessions)} sessions (streamed; window pos<{_pos})",
            flush=True,
        )
    print(f"[run_baseline] {len(sessions)} sessions loaded", flush=True)

    if args.resume and report_path.exists():
        validation = validate_run_dir(
            out_dir,
            expected_rows=len(sessions),
            system=args.baseline,
            baseline=args.baseline,
            require_action_log=(
                action_log_required(None, args.baseline) and not args.no_action_log
            ),
        )
        if validation.ok:
            print(
                f"[run_baseline] resume: existing validated complete report found "
                f"at {report_path}; skipping",
                flush=True,
            )
            return 0
        raise SystemExit(
            "[run_baseline] resume refused because existing report/output artifacts "
            "are incomplete or inconsistent:\n"
            + "\n".join(f"  - {error}" for error in validation.errors)
        )

    resume_state = _ResumeState(answer_rows=[], grades=[], completed_session_ids=set())
    if args.resume:
        resume_state = _load_resume_state(
            sessions=sessions,
            answers_path=answers_path,
            judgments_path=judgments_path,
            baseline_name=args.baseline,
        )
        # Rewrite progress files into canonical session order and drop partial
        # tails before appending new rows.
        _write_jsonl_rows(answers_path, resume_state.answer_rows)
        _write_jsonl_rows(predictions_path, resume_state.answer_rows)
        _write_jsonl_rows(judgments_path, [grade.to_dict() for grade in resume_state.grades])
        print(
            "[run_baseline] resume: "
            f"completed={len(resume_state.completed_session_ids)}/{len(sessions)} "
            f"remaining={len(sessions) - len(resume_state.completed_session_ids)}",
            flush=True,
        )
    else:
        answers_path.write_text("", encoding="utf-8")
        predictions_path.write_text("", encoding="utf-8")

    remaining_sessions = [
        sess for sess in sessions if sess.session_id not in resume_state.completed_session_ids
    ]
    args.append_action_log = args.resume and bool(resume_state.completed_session_ids)

    if not remaining_sessions:
        judge_model_id = (
            resume_state.grades[0].judge_model_id if resume_state.grades else "unknown-judge"
        )
        report = build_eval_report(
            baseline_name=args.baseline,
            judge_model_id=judge_model_id,
            grades=resume_state.grades,
            n_bootstrap=args.n_bootstrap,
            bootstrap_seed=args.seed,
        )
        payload = report.to_dict()
        payload["wall_clock_seconds"] = 0.0
        payload["slice_path"] = str(args.slice)
        payload["seed"] = args.seed
        payload["sample_range"] = {
            "sample_from": args.sample_from,
            "sample_to": args.sample_to,
            "sample_start": args.sample_start,
            "sample_end": args.sample_end,
        }
        if args.baseline in {"naive_overwrite", "controller"}:
            payload["scorecard"] = _scorecard_config_payload(_load_scorecard_config(args), args)
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(report.summarize_markdown(), encoding="utf-8")
        print("[run_baseline] resume: all requested sessions already complete", flush=True)
        return 0

    print("[run_baseline] build answerer start", flush=True)
    answerer = _build_llm(args)
    print(f"[run_baseline] build answerer done: {getattr(answerer, 'model_id', '?')}", flush=True)
    print("[run_baseline] build judge start", flush=True)
    judge = _build_judge(args, answerer)
    print(f"[run_baseline] build judge done: {getattr(judge, 'model_id', '?')}", flush=True)
    print(
        f"[run_baseline] answerer={getattr(answerer, 'model_id', '?')} "
        f"judge={getattr(judge, 'model_id', '?')}",
        flush=True,
    )

    print("[run_baseline] build baseline start", flush=True)
    baseline = _build_baseline(args, answerer, sessions)
    print(f"[run_baseline] build baseline done: {baseline.__class__.__name__}", flush=True)
    cache = JudgmentCache(cache_path)
    grader = LongMemEvalGrader(judge_llm=judge, cache=cache, seed=args.seed)

    # Persist answers as a side effect of the eval (post-hoc, since the
    # evaluator already takes care of judgments). We hook into the progress
    # callback to write each answer the moment it's generated.
    answers_count = {
        "n": len(resume_state.answer_rows),
        "blank": sum(1 for row in resume_state.answer_rows if not str(row.get("text", "")).strip()),
        "degenerate": sum(
            1
            for row in resume_state.answer_rows
            if looks_degenerate_answer(str(row.get("text", "")))
        ),
    }

    def progress_cb(i, n, sess, ans, grade):
        with answers_path.open("a", encoding="utf-8") as fh:
            line = json.dumps(ans.to_dict(), sort_keys=True)
            fh.write(line)
            fh.write("\n")
        with predictions_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.write("\n")
        answers_count["n"] += 1
        if not ans.text.strip():
            answers_count["blank"] += 1
        elif looks_degenerate_answer(ans.text):
            answers_count["degenerate"] += 1
        completed = len(resume_state.completed_session_ids)
        _progress(completed + i, completed + n, sess, ans, grade)

    def start_cb(i, n, sess):
        completed = len(resume_state.completed_session_ids)
        current = completed + i
        total = completed + n
        pct = (100.0 * (current - 1) / total) if total else 0.0
        print(
            f"[run_baseline] example start "
            f"[{current}/{total} {pct:5.1f}%] {sess.session_id} "
            f"competency={sess.competency}",
            flush=True,
        )

    def stage_cb(stage, i, n, sess, ans, grade):
        completed = len(resume_state.completed_session_ids)
        current = completed + i
        total = completed + n
        pct = (100.0 * (current - 1) / total) if total else 0.0
        parts = [
            "[run_baseline:stage]",
            f"stage={stage}",
            f"sample={current}/{total}",
            f"pct={pct:.1f}",
            f"session_id={sess.session_id}",
            f"competency={sess.competency}",
        ]
        if ans is not None:
            parts.extend(
                [
                    f"answer_chars={len(ans.text)}",
                    f"prompt_tokens={ans.prompt_tokens}",
                    f"completion_tokens={ans.completion_tokens}",
                    f"latency_ms={ans.latency_ms:.1f}",
                ]
            )
        if grade is not None:
            parts.append(f"correct={grade.correct}")
        print(" ".join(parts), flush=True)

    first_session = remaining_sessions[0].session_id if remaining_sessions else "n/a"
    print(
        f"[run_baseline] evaluation start: remaining={len(remaining_sessions)} "
        f"first_session={first_session}",
        flush=True,
    )
    t0 = time.perf_counter()
    report = evaluate_baseline(
        baseline,
        remaining_sessions,
        grader,
        progress_callback=progress_cb,
        start_callback=start_cb,
        stage_callback=stage_cb,
        n_bootstrap=args.n_bootstrap,
        bootstrap_seed=args.seed,
        judgments_path=judgments_path,
        judgments_mode="a" if args.resume else "w",
        initial_grades=resume_state.grades,
    )
    wall_s = time.perf_counter() - t0

    # Persist report.
    payload = report.to_dict()
    payload["wall_clock_seconds"] = round(wall_s, 2)
    payload["slice_path"] = str(args.slice)
    payload["seed"] = args.seed
    payload["sample_range"] = {
        "sample_from": args.sample_from,
        "sample_to": args.sample_to,
        "sample_start": args.sample_start,
        "sample_end": args.sample_end,
    }
    if args.baseline in {"naive_overwrite", "controller"}:
        payload["scorecard"] = _scorecard_config_payload(_load_scorecard_config(args), args)
    print(f"[run_baseline] report generation start: {report_path}", flush=True)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    md_path.write_text(report.summarize_markdown(), encoding="utf-8")
    print(f"[run_baseline] report generation done: {report_path}", flush=True)

    print("", flush=True)
    print("=" * 72, flush=True)
    print(
        f"[run_baseline] done in {wall_s:.1f}s. "
        f"overall={report.overall_accuracy * 100:.1f}% "
        f"(95% CI {report.overall_ci_low * 100:.1f} – {report.overall_ci_high * 100:.1f})",
        flush=True,
    )
    print(f"[run_baseline] report → {report_path}", flush=True)
    print(f"[run_baseline] judgments → {judgments_path}", flush=True)
    print(f"[run_baseline] answers → {answers_path}", flush=True)
    print(f"[run_baseline] predictions → {predictions_path}", flush=True)
    print(f"[run_baseline] markdown → {md_path}", flush=True)
    if answers_count["blank"] or answers_count["degenerate"]:
        print(
            f"[run_baseline] ERROR: {answers_count['blank']}/{answers_count['n']} "
            f"answers were blank and {answers_count['degenerate']}/{answers_count['n']} "
            "were degenerate (non-empty but no alphanumeric content, e.g. a bare "
            "'$' from session 852ce960's truncated/saturated context window). "
            "Blank usually means the model spent its budget on hidden thinking; "
            "degenerate usually means the answer prompt filled num_ctx — raise "
            "--ollama-num-ctx or lower --k. Re-run with --allow-blank-answers "
            "only to debug a known-broken backend.",
            flush=True,
        )
        if not args.allow_blank_answers:
            raise SystemExit(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
