"""Run MGP-6 action-level evaluation for M4-W14.

The driver records action decisions and resulting memory state for B1-B4 plus
the controller, then computes action P/R/F1, over-/under-forgetting, per-type
breakdowns, and bootstrap CIs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parents[1] / "src"))

from ask.audit import ActionLogWriter  # noqa: E402
from ask.classifier import (  # noqa: E402
    CandidateMemory,
    PriorMemory,
    RelationClassifier,
    RelationOutput,
)
from ask.controller.active import (  # noqa: E402
    FeatureSnapshot,
    ScorecardConfig,
    c,
    decide,
    e,
    f,
    load_scorecard_config,
    r,
    rho,
)
from ask.eval.mgp6 import build_prediction, compute_report, consolidate_actions  # noqa: E402
from ask.eval.mgp6_schema import (  # noqa: E402
    MGP6MemoryItem,
    MGP6Scenario,
    load_mgp6_jsonl,
    validate_mgp6_coverage,
)
from ask.eval.recoverability import (  # noqa: E402
    aggregate_recoverability,
    recoverability_for_scenario,
)
from ask.eval.sanity import build_sanity_report  # noqa: E402
from ask.extraction import ExtractedItem, Extractor  # noqa: E402
from ask.inference.llm import StructuredLLM  # noqa: E402
from ask.inference.ollama import OllamaLLM  # noqa: E402
from ask.memory import ActionLogEntry, ControllerAction, MemoryType  # noqa: E402

SYSTEMS: tuple[tuple[str, str], ...] = (
    ("b1", "no_memory"),
    ("b2", "flat_vector"),
    ("b3", "recency"),
    ("b4", "naive_overwrite"),
    ("controller", "controller"),
)

LIGHT_MODELS = {
    "extractor": "llama3.2:3b",
    "classifier": "phi3.5:3.8b",
    "judge": "phi3.5:3.8b",
}

T4_MODELS = {
    "extractor": "llama3.2:3b",
    "classifier": "phi3.5:3.8b",
    "judge": "phi3.5:3.8b",
}

# Proposal-spec'd shared 7-8B instruction model (Final_Thesis_Proposal.md I.5,
# configs/inference.yaml: Llama-3-8B-Instruct primary, Qwen2.5-7B fallback).
# This is the ONLY profile permitted to earn a `final-candidate` tier; see the
# tier guard below. The judge is unused for MGP-6 (direct label/state metrics,
# judge_calls == 0), so its tag is immaterial to action/state numbers.
THESIS_MODELS = {
    "extractor": "llama3:8b",
    "classifier": "llama3:8b",
    "judge": "phi3.5:3.8b",
}

# The single model profile whose full runs may ever be promoted to final
# thesis numbers. Any other profile (light/t4/standard) is development tier.
SPEC_PROFILE = "thesis"

_PRIOR_TIMESTAMP = "2026-05-14T00:00:00Z"
_PERTURBATION_TIMESTAMP = "2026-05-14T00:00:01Z"


@dataclass
class RunContext:
    baseline: str
    out_dir: Path
    extractor: Extractor | None
    classifier: RelationClassifier | None
    config: ScorecardConfig
    action_log: ActionLogWriter
    seed: int
    extraction_max_new_tokens: int
    relation_max_new_tokens: int
    next_log_id: int = 1


@dataclass(frozen=True)
class Candidate:
    item: ExtractedItem
    source_turn: str
    timestamp: str


def _installed_ollama_models(host: str) -> set[str]:
    with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return {str(model.get("name") or model.get("model")) for model in payload.get("models", [])}


def _validate_models(host: str, models: set[str]) -> None:
    installed = _installed_ollama_models(host)
    missing = sorted(models - installed)
    if missing:
        raise SystemExit("Ollama is reachable, but missing model tags: " + ", ".join(missing))


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


def _scorecard_config_payload(config: ScorecardConfig, args: argparse.Namespace) -> dict[str, Any]:
    return {
        "scorecard_config": str(args.scorecard_config),
        "scorecard_config_sha256": _sha256(args.scorecard_config),
        "theta_abs_override": args.theta_abs,
        "theta_sup": {key: float(value) for key, value in config.theta_sup.items()},
        "theta_abs": {key: float(value) for key, value in config.theta_abs.items()},
    }


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_extractor(args: argparse.Namespace, out_dir: Path) -> Extractor:
    llm = OllamaLLM(
        model_id=args.extractor_model,
        host=args.ollama_host,
        timeout_s=args.ollama_timeout_s,
        num_ctx=args.structured_num_ctx,
        response_format="json",
        think=False,
    )
    return Extractor.from_template_file(
        StructuredLLM(llm),
        args.extraction_prompt,
        log_path=out_dir / "extraction_trace.jsonl",
    )


def _build_classifier(args: argparse.Namespace, out_dir: Path) -> RelationClassifier:
    llm = OllamaLLM(
        model_id=args.classifier_model,
        host=args.ollama_host,
        timeout_s=args.ollama_timeout_s,
        num_ctx=args.structured_num_ctx,
        response_format="json",
        think=False,
    )
    return RelationClassifier.from_template_files(
        StructuredLLM(llm),
        args.relation_stage1_prompt,
        args.relation_stage2_prompt,
        log_path=out_dir / "relation_trace.jsonl",
    )


def _initial_state(scenario: MGP6Scenario) -> list[dict[str, Any]]:
    return [_memory_item_to_state(item) for item in scenario.initial_memory_state]


def _memory_item_to_state(item: MGP6MemoryItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "type": item.type,
        "text": item.text,
        "confidence": item.confidence,
        "status": item.status,
        "supersedes_id": item.supersedes_id,
        "valid_from": item.valid_from or _PRIOR_TIMESTAMP,
    }


def _extract_candidates(ctx: RunContext, scenario: MGP6Scenario) -> list[Candidate]:
    if ctx.extractor is None:
        return []
    turn_idx = len(scenario.base_dialogue_prefix)
    turn = {
        "turn_id": f"{scenario.scenario_id}:perturbation",
        "session_id": scenario.scenario_id,
        "turn_idx": turn_idx,
        "role": "user",
        "content": scenario.perturbation_event,
        "timestamp": _PERTURBATION_TIMESTAMP,
    }
    prev_turn = None
    if scenario.base_dialogue_prefix:
        prior = scenario.base_dialogue_prefix[-1]
        prev_turn = {
            "turn_id": f"{scenario.scenario_id}:{turn_idx - 1}",
            "session_id": scenario.scenario_id,
            "turn_idx": turn_idx - 1,
            "role": prior["role"],
            "content": prior["content"],
            "timestamp": _PRIOR_TIMESTAMP,
        }
    output = ctx.extractor.extract(
        turn,
        (prev_turn, None),
        max_new_tokens=ctx.extraction_max_new_tokens,
        temperature=0.0,
        seed=ctx.seed,
    )
    return [
        Candidate(
            item=item, source_turn=scenario.perturbation_event, timestamp=_PERTURBATION_TIMESTAMP
        )
        for item in output.items
    ]


def _active_prior_for(candidate: Candidate, state: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the prior a candidate is compared against.

    LIMITATION (documented, matches `orchestrator._find_prior`): this returns
    only the *newest active same-type* prior, not a top-k semantically related
    set. For MGP-6 this is exact, because each scenario seeds a single initial
    memory of one type, so "newest active same-type" is the intended prior. On
    open corpora it is a deliberate Master's-scope simplification: a candidate
    that contradicts an *older* same-type memory while a newer unrelated one
    exists would be compared against the wrong prior. Top-k semantic prior
    selection is Part II work.
    """
    active = [
        item
        for item in state
        if item.get("status") == "active" and item.get("type") == candidate.item.type_guess
    ]
    return active[-1] if active else None


def _classify(
    ctx: RunContext,
    scenario: MGP6Scenario,
    candidate: Candidate,
    prior: dict[str, Any],
) -> RelationOutput:
    if ctx.classifier is None:
        raise RuntimeError(f"{ctx.baseline} requires a relation classifier")
    return ctx.classifier.classify(
        CandidateMemory(
            text=candidate.item.text,
            type_guess=candidate.item.type_guess,
            source_turn=candidate.source_turn,
            session_id=scenario.scenario_id,
            turn_id=f"{scenario.scenario_id}:perturbation",
            timestamp=candidate.timestamp,
        ),
        PriorMemory(
            text=str(prior["text"]),
            type=str(prior["type"]),
            memory_id=str(prior["id"]),
            timestamp=str(prior.get("valid_from") or _PRIOR_TIMESTAMP),
        ),
        max_new_tokens=ctx.relation_max_new_tokens,
        temperature=0.0,
        seed=ctx.seed,
    )


def _controller_decision(
    ctx: RunContext,
    candidate: Candidate,
    prior: dict[str, Any] | None,
    relation: RelationOutput | None,
):
    candidate_payload = candidate.item.model_dump()
    candidate_payload["timestamp"] = candidate.timestamp
    candidate_payload["source_turn"] = candidate.source_turn
    if relation is not None:
        candidate_payload["relation_output"] = relation
    prior_payload = prior or {}
    features = FeatureSnapshot(
        c=c(candidate_payload),
        e=e(candidate_payload, prior_payload),
        f=f(candidate_payload),
        r=_controller_relation_signal(candidate_payload, prior_payload, relation),
        rho=rho(candidate.item.type_guess),
    )
    return decide(features, candidate.item.type_guess, ctx.config)


def _controller_relation_signal(
    candidate_payload: dict[str, Any],
    prior_payload: dict[str, Any],
    relation: RelationOutput | None,
) -> float:
    if relation is None:
        return 1.0
    if relation.relation_to_prior_state == "unclear" and relation.logical_relation == "independent":
        return 1.0
    return r(candidate_payload, prior_payload)


def _new_state_item(
    candidate: Candidate,
    *,
    new_id: str,
    status: str = "active",
    supersedes_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": new_id,
        "type": candidate.item.type_guess,
        "text": candidate.item.text,
        "confidence": candidate.item.extraction_confidence,
        "status": status,
        "supersedes_id": supersedes_id,
        "valid_from": candidate.timestamp,
    }


def _write_action(
    ctx: RunContext,
    *,
    scenario_id: str,
    action: ControllerAction,
    candidate_text: str,
    candidate_type: str | None,
    rationale: str,
    prior_memory_id: str | None = None,
    resulting_memory_id: str | None = None,
    decision: Any | None = None,
) -> None:
    entry = ActionLogEntry(
        id=ctx.next_log_id,
        timestamp=datetime.now(UTC),
        action=action,
        candidate_text=candidate_text,
        rationale=rationale,
        session_id=scenario_id,
        baseline=ctx.baseline,
        candidate_type=MemoryType(candidate_type) if candidate_type else None,
        candidate_id=ctx.next_log_id if decision is not None else None,
        prior_memory_id=_numeric_id(prior_memory_id),
        resulting_memory_id=_numeric_id(resulting_memory_id),
        feature_c=getattr(getattr(decision, "features", None), "c", None),
        feature_e=getattr(getattr(decision, "features", None), "e", None),
        feature_f=getattr(getattr(decision, "features", None), "f", None),
        feature_r=getattr(getattr(decision, "features", None), "r", None),
        feature_rho=getattr(getattr(decision, "features", None), "rho", None),
        s_rev=getattr(decision, "s_rev", None),
        s_abs=getattr(decision, "s_abs", None),
        theta_sup=getattr(decision, "theta_sup", None),
        theta_abs=getattr(decision, "theta_abs", None),
    )
    ctx.action_log.write(entry)
    ctx.next_log_id += 1


def _numeric_id(value: str | None) -> int | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else None


def _run_non_updating(
    ctx: RunContext, scenario: MGP6Scenario
) -> tuple[list[dict[str, Any]], list[str], str | None, float | None]:
    state = _initial_state(scenario)
    _write_action(
        ctx,
        scenario_id=scenario.scenario_id,
        action=ControllerAction.KEEP,
        candidate_text="(no memory update)",
        candidate_type=scenario.initial_memory_state[0].type,
        rationale=f"{ctx.baseline}: no memory revision policy; prior state retained.",
    )
    return state, ["KEEP"], scenario.initial_memory_state[0].type, None


def _run_recency(
    ctx: RunContext, scenario: MGP6Scenario
) -> tuple[list[dict[str, Any]], list[str], str | None, float | None]:
    state = _initial_state(scenario)
    candidates = _extract_candidates(ctx, scenario)
    if not candidates:
        _write_action(
            ctx,
            scenario_id=scenario.scenario_id,
            action=ControllerAction.ABSTAIN,
            candidate_text="(no extractable memory)",
            candidate_type=scenario.initial_memory_state[0].type,
            rationale="recency: M2 extractor emitted no memory item.",
        )
        return state, ["ABSTAIN"], None, None
    actions = []
    for idx, candidate in enumerate(candidates, start=1):
        new_id = f"p{idx}"
        state.append(_new_state_item(candidate, new_id=new_id))
        actions.append("KEEP")
        _write_action(
            ctx,
            scenario_id=scenario.scenario_id,
            action=ControllerAction.KEEP,
            candidate_text=candidate.item.text,
            candidate_type=candidate.item.type_guess,
            rationale="recency: admitted extracted item without relation check.",
            resulting_memory_id=new_id,
        )
    return state, actions, candidates[0].item.type_guess, None


def _run_naive(
    ctx: RunContext, scenario: MGP6Scenario
) -> tuple[list[dict[str, Any]], list[str], str | None, float | None]:
    state = _initial_state(scenario)
    candidates = _extract_candidates(ctx, scenario)
    if not candidates:
        _write_action(
            ctx,
            scenario_id=scenario.scenario_id,
            action=ControllerAction.ABSTAIN,
            candidate_text="(no extractable memory)",
            candidate_type=scenario.initial_memory_state[0].type,
            rationale="naive_overwrite: no extracted candidate.",
        )
        return state, ["ABSTAIN"], None, None

    actions = []
    for idx, candidate in enumerate(candidates, start=1):
        prior = _active_prior_for(candidate, state)
        relation = _classify(ctx, scenario, candidate, prior) if prior else None
        relation_value = relation.relation_to_prior_state if relation else "no_prior"
        action = (
            ControllerAction.SUPERSEDE
            if prior is not None and relation_value in {"contradict", "supersede"}
            else ControllerAction.KEEP
        )
        prior_id = str(prior["id"]) if prior else None
        new_id = f"p{idx}"
        if action == ControllerAction.SUPERSEDE and prior is not None:
            # Naive overwrite is destructive: remove the prior and insert the
            # candidate without a supersedes edge or inactive prior row.
            state = [item for item in state if str(item.get("id")) != prior_id]
        state.append(_new_state_item(candidate, new_id=new_id))
        actions.append(action.name)
        _write_action(
            ctx,
            scenario_id=scenario.scenario_id,
            action=action,
            candidate_text=candidate.item.text,
            candidate_type=candidate.item.type_guess,
            rationale=f"naive_overwrite: relation={relation_value}.",
            prior_memory_id=prior_id,
            resulting_memory_id=new_id,
        )
    return state, actions, candidates[0].item.type_guess, None


def _run_controller(
    ctx: RunContext, scenario: MGP6Scenario
) -> tuple[list[dict[str, Any]], list[str], str | None, float | None]:
    state = _initial_state(scenario)
    candidates = _extract_candidates(ctx, scenario)
    if not candidates:
        memory_type = scenario.initial_memory_state[0].type
        features = FeatureSnapshot(c=0.0, e=0.0, f=1.0, r=0.0, rho=rho(memory_type))
        decision = decide(features, memory_type, ctx.config)
        _write_action(
            ctx,
            scenario_id=scenario.scenario_id,
            action=decision.action,
            candidate_text="(no extractable memory)",
            candidate_type=memory_type,
            rationale=f"controller: no extracted candidate. {decision.rationale}",
            decision=decision,
        )
        return state, [decision.action.name], None, decision.theta_sup

    actions = []
    first_theta = None
    for idx, candidate in enumerate(candidates, start=1):
        prior = _active_prior_for(candidate, state)
        relation = _classify(ctx, scenario, candidate, prior) if prior else None
        decision = _controller_decision(ctx, candidate, prior, relation)
        first_theta = first_theta if first_theta is not None else decision.theta_sup
        prior_id = str(prior["id"]) if prior else None
        resulting_id = None
        if decision.action == ControllerAction.SUPERSEDE and prior is not None:
            prior["status"] = "superseded"
            resulting_id = f"p{idx}"
            state.append(_new_state_item(candidate, new_id=resulting_id, supersedes_id=prior_id))
        elif decision.action == ControllerAction.KEEP and prior is None:
            resulting_id = f"p{idx}"
            state.append(_new_state_item(candidate, new_id=resulting_id))
        actions.append(decision.action.name)
        _write_action(
            ctx,
            scenario_id=scenario.scenario_id,
            action=decision.action,
            candidate_text=candidate.item.text,
            candidate_type=candidate.item.type_guess,
            rationale=decision.rationale,
            prior_memory_id=prior_id,
            resulting_memory_id=resulting_id,
            decision=decision,
        )
    return state, actions, candidates[0].item.type_guess, first_theta


def run_system(
    *,
    baseline: str,
    scenarios: list[MGP6Scenario],
    args: argparse.Namespace,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    extractor = None
    classifier = None
    if baseline in {"recency", "naive_overwrite", "controller"}:
        extractor = _build_extractor(args, out_dir)
    if baseline in {"naive_overwrite", "controller"}:
        classifier = _build_classifier(args, out_dir)

    predictions = []
    action_log_path = out_dir / "action_log.jsonl"
    config = _load_scorecard_config(args)
    with ActionLogWriter(action_log_path, baseline=baseline, mode="w") as writer:
        ctx = RunContext(
            baseline=baseline,
            out_dir=out_dir,
            extractor=extractor,
            classifier=classifier,
            config=config,
            action_log=writer,
            seed=args.seed,
            extraction_max_new_tokens=args.extraction_max_new_tokens,
            relation_max_new_tokens=args.relation_max_new_tokens,
        )
        for scenario in scenarios:
            if baseline in {"no_memory", "flat_vector"}:
                state, actions, candidate_type, theta_sup = _run_non_updating(ctx, scenario)
            elif baseline == "recency":
                state, actions, candidate_type, theta_sup = _run_recency(ctx, scenario)
            elif baseline == "naive_overwrite":
                state, actions, candidate_type, theta_sup = _run_naive(ctx, scenario)
            elif baseline == "controller":
                state, actions, candidate_type, theta_sup = _run_controller(ctx, scenario)
            else:
                raise ValueError(f"unknown system {baseline!r}")
            prediction = build_prediction(
                scenario,
                predicted_action=consolidate_actions(actions),
                memory_state=state,
                action_sequence=actions,
                candidate_type=candidate_type,
                theta_sup=theta_sup,
            )
            predictions.append(prediction)
            print(
                f"[mgp6] {baseline:<15} {scenario.scenario_id} "
                f"gold={scenario.gold_action:<9} pred={prediction.predicted_action:<9} "
                f"state_ok={prediction.state_correct}",
                flush=True,
            )

    report = compute_report(
        predictions,
        baseline=baseline,
        n_bootstrap=args.n_bootstrap,
        seed=args.seed,
    )
    prior_id_by_scenario = {
        scenario.scenario_id: scenario.initial_memory_state[0].id for scenario in scenarios
    }
    recoverability_rows = [
        recoverability_for_scenario(
            prior_id_by_scenario[prediction.scenario_id],
            prediction.memory_state,
        )
        for prediction in predictions
    ]
    report["recoverability"] = aggregate_recoverability(recoverability_rows)
    report["recoverability"]["note"] = (
        "superseded_recoverability tests H2: among scenarios where the system "
        "removed the prior from the active set, the fraction where the superseded "
        "prior is still retrievable via an inactive row + supersedes lineage edge. "
        "Lineage-preserving Supersede approaches 1.0; destructive overwrite is 0.0."
    )
    report["model_ids"] = {
        "extractor": args.extractor_model if extractor else None,
        "classifier": args.classifier_model if classifier else None,
        "judge": args.judge_model,
    }
    report["scorecard"] = _scorecard_config_payload(config, args)
    report["judge_calls"] = 0
    report["judge_note"] = (
        "MGP-6 action metrics are label/state comparisons; no LLM judge call "
        "is needed unless a later semantic state-text audit is enabled."
    )
    (out_dir / "mgp6_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    with (out_dir / "predictions.jsonl").open("w", encoding="utf-8") as fh:
        for prediction in predictions:
            fh.write(json.dumps(prediction.to_dict(), sort_keys=True))
            fh.write("\n")
    return report


def _select_systems(value: str) -> list[tuple[str, str]]:
    if value == "all":
        return list(SYSTEMS)
    requested = {item.strip() for item in value.split(",") if item.strip()}
    out = []
    for alias, baseline in SYSTEMS:
        if alias in requested or baseline in requested:
            out.append((alias, baseline))
    unknown = requested - {x for pair in SYSTEMS for x in pair}
    if unknown:
        raise SystemExit(f"unknown systems requested: {sorted(unknown)}")
    return out


def _render_note(reports: list[tuple[str, dict[str, Any]]], *, path: Path, limited: bool) -> None:
    lines = [
        "# M4-W14 MGP-6 Results",
        "",
        "MGP-6 is a 60-scenario action-level complement to LongMemEval-S. "
        "CIs are bootstrap percentile intervals over scenarios; per-cell "
        "variance is wide because support is small.",
        "",
        "| System | n | Action acc. | State acc. | Over-forgetting | Under-forgetting |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for alias, report in reports:
        lines.append(
            f"| {alias} `{report['baseline']}` | {report['n_scenarios']} | "
            f"{_pct(report['action_accuracy'])} | {_pct(report['state_accuracy'])} | "
            f"{_pct(report['over_forgetting_rate'])} | {_pct(report['under_forgetting_rate'])} |"
        )
    lines.extend(["", "## Threshold Ordering"])
    for _alias, report in reports:
        if report["baseline"] != "controller":
            continue
        ordering = report["threshold_ordering"]
        lines.append(
            f"- Controller: {ordering['empirical_status']}; "
            f"mean theta_sup by candidate type = "
            f"{ordering['mean_theta_sup_by_candidate_type']}."
        )
    if limited:
        lines.extend(
            [
                "",
                "> This note was generated from a limited run. It is not an "
                "acceptance-result artifact until all 60 scenarios are present.",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=Path("data/mgp6_v1_seed0.jsonl"))
    p.add_argument("--out", type=Path, default=Path("runs/m4w14"))
    p.add_argument("--systems", default="all", help="all or comma list of aliases/names")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-bootstrap", type=int, default=1000)
    p.add_argument("--ollama-host", default="http://localhost:11434")
    p.add_argument("--ollama-timeout-s", type=float, default=900.0)
    p.add_argument(
        "--model-profile",
        choices=("standard", "light", "t4", "thesis"),
        default="standard",
        help="Use 'light' for 3B/3.8B. Use 't4' for llama3.2 "
        "extraction and phi3.5 classify/judge. Use 'thesis' for the "
        "proposal-spec'd 7-8B model (llama3:8b) -- the ONLY profile "
        "whose runs may be promoted to final thesis numbers.",
    )
    p.add_argument("--extractor-model", default=None)
    p.add_argument("--classifier-model", default=None)
    p.add_argument("--judge-model", default=None)
    p.add_argument("--structured-num-ctx", type=int, default=4096)
    # v_final2 puts explicit first-person preference/fact UPDATES in scope, fixing
    # the 8B-model T1 over-abstention (recall 0.30) seen in runs/m4w14_thesis.
    # Revert with --extraction-prompt prompts/extraction_v_final.j2 if needed.
    p.add_argument("--extraction-prompt", type=Path, default=Path("prompts/extraction_v_final2.j2"))
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
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--fail-on-sanity",
        action="store_true",
        help="Exit non-zero if run-level sanity checks flag a likely pipeline bug.",
    )
    p.add_argument("--note-path", type=Path, default=Path("NOTES/m4w14_mgp6_results.md"))
    args = p.parse_args()
    if args.model_profile == "light":
        args.extractor_model = args.extractor_model or LIGHT_MODELS["extractor"]
        args.classifier_model = args.classifier_model or LIGHT_MODELS["classifier"]
        args.judge_model = args.judge_model or LIGHT_MODELS["judge"]
    elif args.model_profile == "t4":
        args.extractor_model = args.extractor_model or T4_MODELS["extractor"]
        args.classifier_model = args.classifier_model or T4_MODELS["classifier"]
        args.judge_model = args.judge_model or T4_MODELS["judge"]
    elif args.model_profile == "thesis":
        args.extractor_model = args.extractor_model or THESIS_MODELS["extractor"]
        args.classifier_model = args.classifier_model or THESIS_MODELS["classifier"]
        args.judge_model = args.judge_model or THESIS_MODELS["judge"]
    else:
        args.extractor_model = args.extractor_model or "gemma4:e4b"
        args.classifier_model = args.classifier_model or "gemma4:e4b"
        args.judge_model = args.judge_model or "phi4:14b"

    scenarios = load_mgp6_jsonl(args.input)
    validate_mgp6_coverage(scenarios)
    if args.limit is not None:
        scenarios = scenarios[: args.limit]
    systems = _select_systems(args.systems)

    if args.dry_run:
        print(f"[mgp6] input={args.input} scenarios={len(scenarios)}")
        for alias, baseline in systems:
            print(f"[mgp6] would run {alias}/{baseline} -> {args.out / alias}")
        return 0

    _validate_models(
        args.ollama_host,
        {args.extractor_model, args.classifier_model, args.judge_model},
    )

    args.out.mkdir(parents=True, exist_ok=True)
    # Tier guard: a run may only carry the `final-candidate` tier if it is a
    # full run (no --limit) AND used the proposal-spec'd `thesis` profile.
    # Any other profile is `development` and CANNOT be promoted to final by
    # scripts/promote_to_final.py. This makes the runs/m4w14 mislabel
    # (a 3B `light` run auto-stamped final-candidate) structurally impossible.
    is_spec_full = args.limit is None and args.model_profile == SPEC_PROFILE
    if args.limit is not None:
        run_tier = "smoke"
        thesis_use = "no_final_claim"
    elif is_spec_full:
        run_tier = "final-candidate"
        thesis_use = "final_candidate_pending_review"
    else:
        run_tier = "development"
        thesis_use = f"development_{args.model_profile}_profile_NOT_for_final"
    manifest = {
        "input": str(args.input),
        "dataset": "MGP-6 v1 author-designed diagnostic slice",
        "systems": [baseline for _, baseline in systems],
        "n": len(scenarios),
        "seed": args.seed,
        "n_bootstrap": args.n_bootstrap,
        "limit": args.limit,
        "tier": run_tier,
        "run_tier": run_tier,
        "judge_tier": "direct_label_state_comparison",
        "raw_turn_fallback": False,
        "complete": False,
        "thesis_use": thesis_use,
        "spec_profile": SPEC_PROFILE,
        "is_spec_profile": args.model_profile == SPEC_PROFILE,
        "models": {
            "extractor": args.extractor_model,
            "classifier": args.classifier_model,
            "judge": args.judge_model,
        },
        "model_profile": args.model_profile,
        "ollama_timeout_s": args.ollama_timeout_s,
        "scorecard": {
            "config": str(args.scorecard_config),
            "config_sha256": _sha256(args.scorecard_config),
            "theta_abs_override": args.theta_abs,
        },
        "started_at": datetime.now(UTC).isoformat(),
        "python": sys.executable,
        "cwd": os.getcwd(),
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    reports = []
    t0 = time.perf_counter()
    for alias, baseline in systems:
        report = run_system(
            baseline=baseline,
            scenarios=scenarios,
            args=args,
            out_dir=args.out / alias,
        )
        reports.append((alias, report))
    sanity = build_sanity_report(reports)
    (args.out / "sanity_report.json").write_text(
        json.dumps(sanity, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest["finished_at"] = datetime.now(UTC).isoformat()
    manifest["wall_clock_seconds"] = round(time.perf_counter() - t0, 2)
    manifest["complete"] = True
    manifest["sanity_ok"] = sanity["ok"]
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _render_note(reports, path=args.note_path, limited=args.limit is not None)
    print(f"[mgp6] wrote {args.note_path}", flush=True)

    if sanity["warnings"]:
        print("", flush=True)
        print("=" * 72, flush=True)
        print("[mgp6] SANITY WARNINGS — results may be INVALID:", flush=True)
        for warning in sanity["warnings"]:
            print(f"  !! {warning}", flush=True)
        print(f"[mgp6] wrote {args.out / 'sanity_report.json'}", flush=True)
        print("=" * 72, flush=True)
        if args.fail_on_sanity:
            return 2
    else:
        print(
            "[mgp6] sanity checks passed (extraction recall + distinct confusion matrices).",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
