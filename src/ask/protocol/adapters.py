"""Typed ASK-MGP and ASK-LME adapter traces."""

from __future__ import annotations

from dataclasses import dataclass

from ask.controller.features import FeatureSnapshot
from ask.controller.policy import decide as decide_lme
from ask.controller.score import DEFAULT_SCORECARD_CONFIG, ScorecardConfig
from ask.memory.models import ControllerAction
from ask.protocol.core import (
    Action,
    ConfigurationIdentity,
    DecisionTrace,
    EvidenceReference,
    ReplayScope,
    StoreMode,
    evidence_set_digest,
)


@dataclass(frozen=True)
class ASKMGPAdapter:
    configuration: ConfigurationIdentity
    store_mode: StoreMode = StoreMode.SINGLE_SLOT_VERSIONED
    adapter_id: str = "ASK-MGP"
    adapter_version: str = "ask-mgp/v1"
    replay_scope: ReplayScope = ReplayScope.COMPOSITION_AND_TRANSITION

    def __post_init__(self) -> None:
        if self.configuration.adapter_version != self.adapter_version:
            raise ValueError("ASK-MGP configuration uses a different adapter version")

    def decide(
        self,
        *,
        model_proposal: Action,
        rule_proposal: Action,
        rule_verdict: str,
        evidence_references: tuple[EvidenceReference, ...],
        guard_rule_id: str,
    ) -> tuple[Action, DecisionTrace]:
        final_action = (
            rule_proposal
            if model_proposal is ControllerAction.ABSTAIN
            and rule_proposal is not ControllerAction.ABSTAIN
            else model_proposal
        )
        trace = DecisionTrace(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            replay_scope=self.replay_scope,
            configuration=self.configuration,
            evidence_references=evidence_references,
            evidence_digest=evidence_set_digest(evidence_references),
            inputs={
                "model_proposal": model_proposal.value,
                "rule_proposal": rule_proposal.value,
            },
            intermediates={
                "rule_verdict": rule_verdict,
                "guard_rule_id": guard_rule_id,
                "overrode_model_abstention": final_action != model_proposal,
            },
            final_action=final_action,
            sufficient_fields=(
                "model_proposal",
                "rule_proposal",
                "rule_verdict",
                "guard_rule_id",
                "configuration",
                "evidence_digest",
            ),
        )
        return final_action, trace

    def replay(self, trace: DecisionTrace) -> Action:
        if trace.adapter_id != self.adapter_id or trace.replay_scope != self.replay_scope:
            raise ValueError("trace does not declare ASK-MGP composition replay")
        model = ControllerAction(str(trace.inputs["model_proposal"]))
        rule = ControllerAction(str(trace.inputs["rule_proposal"]))
        replayed = (
            rule
            if model is ControllerAction.ABSTAIN and rule is not ControllerAction.ABSTAIN
            else model
        )
        if replayed != trace.final_action:
            raise ValueError("ASK-MGP composition replay differs from logged action")
        return replayed


@dataclass(frozen=True)
class ASKLMEAdapter:
    configuration: ConfigurationIdentity
    config: ScorecardConfig = DEFAULT_SCORECARD_CONFIG
    store_mode: StoreMode = StoreMode.MULTI_RECORD
    adapter_id: str = "ASK-LME"
    adapter_version: str = "ask-lme-scorecard/v1"
    replay_scope: ReplayScope = ReplayScope.FINAL_POLICY_AND_TRANSITION

    def __post_init__(self) -> None:
        if self.configuration.adapter_version != self.adapter_version:
            raise ValueError("ASK-LME configuration uses a different adapter version")

    def decide(
        self,
        *,
        features: FeatureSnapshot,
        memory_type: str,
        evidence_references: tuple[EvidenceReference, ...],
        prior_record_id: str | None,
        candidate_record_id: str,
    ) -> tuple[Action, DecisionTrace]:
        decision = decide_lme(features, memory_type, self.config)
        trace = DecisionTrace(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            replay_scope=self.replay_scope,
            configuration=self.configuration,
            evidence_references=evidence_references,
            evidence_digest=evidence_set_digest(evidence_references),
            inputs={
                "feature_schema_version": "ask-lme-features/v1",
                "memory_type": memory_type,
                "prior_record_id": prior_record_id,
                "candidate_record_id": candidate_record_id,
                "c": features.c,
                "e": features.e,
                "f": features.f,
                "r": features.r,
                "rho": features.rho,
            },
            intermediates={
                "s_sup": decision.s_rev,
                "s_abs": decision.s_abs,
                "theta_sup": decision.theta_sup,
                "theta_abs": decision.theta_abs,
                "relation_guard": "r < 0",
                "ordered_rules": ("Abstain", "Supersede", "Keep"),
            },
            final_action=decision.action,
            sufficient_fields=(
                "feature_schema_version",
                "memory_type",
                "c",
                "e",
                "f",
                "r",
                "rho",
                "thresholds",
                "ordered_rules",
                "relation_guard",
                "configuration",
            ),
        )
        return decision.action, trace

    def replay(self, trace: DecisionTrace) -> Action:
        if trace.adapter_id != self.adapter_id or trace.replay_scope != self.replay_scope:
            raise ValueError("trace does not declare ASK-LME final-policy replay")
        inputs = trace.inputs
        features = FeatureSnapshot(
            c=float(inputs["c"]),
            e=float(inputs["e"]),
            f=float(inputs["f"]),
            r=float(inputs["r"]),
            rho=float(inputs["rho"]),
        )
        replayed = decide_lme(features, str(inputs["memory_type"]), self.config).action
        if replayed != trace.final_action:
            raise ValueError("ASK-LME policy replay differs from logged action")
        return replayed
