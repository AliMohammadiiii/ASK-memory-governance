"""Typed ASK-MGP and ASK-LME adapter traces."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ask.controller.features import FeatureSnapshot
from ask.controller.policy import decide as decide_lme
from ask.controller.score import DEFAULT_SCORECARD_CONFIG, ScorecardConfig
from ask.memory.models import ControllerAction
from ask.protocol.core import (
    Action,
    ASKValidationError,
    ConfigurationIdentity,
    DecisionTrace,
    EvidenceReference,
    ReplayScope,
    StoreMode,
    evidence_set_digest,
)

_MGP_COMPOSITION_RULE = "rule_proposal_if_model_abstains_and_rule_not_abstain_else_model_proposal"
_LME_FEATURE_SCHEMA = "ask-lme-features/v1"
_LME_ORDERED_RULES = ("Abstain", "Supersede", "Keep")
_LME_RELATION_GUARD = "r < 0"


def _require_strict_binding(adapter: ASKMGPAdapter | ASKLMEAdapter, trace: DecisionTrace) -> None:
    """Strict replay: the adapter identity must hash its configuration and match the trace."""
    adapter.verify_configuration_identity()
    if trace.configuration != adapter.configuration:
        raise ASKValidationError(
            "trace_configuration_mismatch",
            "trace configuration identity differs from the replaying adapter identity",
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

    def frozen_configuration(self) -> dict[str, Any]:
        """Declared configuration mapping whose digest is the identity of this adapter.

        The mapping holds declared values only. It does not hash the composition code.
        """
        return _mgp_frozen_configuration(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            replay_scope=self.replay_scope,
            store_mode=self.store_mode,
        )

    def verify_configuration_identity(self) -> None:
        """Reject an identity whose digest is not that of ``frozen_configuration()``."""
        self.configuration.verify(self.frozen_configuration())

    @classmethod
    def bound(
        cls,
        configuration_id: str,
        *,
        store_mode: StoreMode = StoreMode.SINGLE_SLOT_VERSIONED,
    ) -> ASKMGPAdapter:
        """Construct an adapter whose identity is computed from its frozen configuration."""
        frozen = _mgp_frozen_configuration(
            adapter_id=cls.adapter_id,
            adapter_version=cls.adapter_version,
            replay_scope=cls.replay_scope,
            store_mode=store_mode,
        )
        identity = ConfigurationIdentity.from_configuration(
            configuration_id, cls.adapter_version, frozen
        )
        return cls(identity, store_mode=store_mode)

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

    def replay(self, trace: DecisionTrace, *, strict: bool = False) -> Action:
        if trace.adapter_id != self.adapter_id or trace.replay_scope != self.replay_scope:
            raise ValueError("trace does not declare ASK-MGP composition replay")
        if strict:
            _require_strict_binding(self, trace)
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

    def frozen_configuration(self) -> dict[str, Any]:
        """Declared configuration mapping whose digest is the identity of this adapter.

        It holds the scorecard weights and thresholds that the replay uses, and the declared
        rule order. It does not hash the policy code.
        """
        return _lme_frozen_configuration(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            replay_scope=self.replay_scope,
            store_mode=self.store_mode,
            config=self.config,
        )

    def verify_configuration_identity(self) -> None:
        """Reject an identity whose digest is not that of ``frozen_configuration()``."""
        self.configuration.verify(self.frozen_configuration())

    @classmethod
    def bound(
        cls,
        configuration_id: str,
        *,
        config: ScorecardConfig = DEFAULT_SCORECARD_CONFIG,
        store_mode: StoreMode = StoreMode.MULTI_RECORD,
    ) -> ASKLMEAdapter:
        """Construct an adapter whose identity is computed from its frozen configuration."""
        frozen = _lme_frozen_configuration(
            adapter_id=cls.adapter_id,
            adapter_version=cls.adapter_version,
            replay_scope=cls.replay_scope,
            store_mode=store_mode,
            config=config,
        )
        identity = ConfigurationIdentity.from_configuration(
            configuration_id, cls.adapter_version, frozen
        )
        return cls(identity, config=config, store_mode=store_mode)

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
                "feature_schema_version": _LME_FEATURE_SCHEMA,
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
                "relation_guard": _LME_RELATION_GUARD,
                "ordered_rules": _LME_ORDERED_RULES,
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

    def replay(self, trace: DecisionTrace, *, strict: bool = False) -> Action:
        if trace.adapter_id != self.adapter_id or trace.replay_scope != self.replay_scope:
            raise ValueError("trace does not declare ASK-LME final-policy replay")
        if strict:
            _require_strict_binding(self, trace)
        inputs = trace.inputs
        features = FeatureSnapshot(
            c=float(inputs["c"]),
            e=float(inputs["e"]),
            f=float(inputs["f"]),
            r=float(inputs["r"]),
            rho=float(inputs["rho"]),
        )
        decision = decide_lme(features, str(inputs["memory_type"]), self.config)
        if strict:
            replayed_thresholds = (
                ("theta_sup", decision.theta_sup),
                ("theta_abs", decision.theta_abs),
            )
            for name, value in replayed_thresholds:
                logged = trace.intermediates.get(name)
                if logged is None or float(logged) != value:
                    raise ASKValidationError(
                        "logged_threshold_mismatch",
                        f"logged {name} {logged!r} differs from replaying value {value!r}",
                    )
        replayed = decision.action
        if replayed != trace.final_action:
            raise ValueError("ASK-LME policy replay differs from logged action")
        return replayed


def _mgp_frozen_configuration(
    *,
    adapter_id: str,
    adapter_version: str,
    replay_scope: ReplayScope,
    store_mode: StoreMode,
) -> dict[str, Any]:
    return {
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "replay_scope": replay_scope.value,
        "store_mode": store_mode.value,
        "composition_rule": _MGP_COMPOSITION_RULE,
    }


def _lme_frozen_configuration(
    *,
    adapter_id: str,
    adapter_version: str,
    replay_scope: ReplayScope,
    store_mode: StoreMode,
    config: ScorecardConfig,
) -> dict[str, Any]:
    return {
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "replay_scope": replay_scope.value,
        "store_mode": store_mode.value,
        "feature_schema_version": _LME_FEATURE_SCHEMA,
        "weights": asdict(config.weights),
        "theta_sup": {key: config.theta_sup[key] for key in sorted(config.theta_sup)},
        "theta_abs": {key: config.theta_abs[key] for key in sorted(config.theta_abs)},
        "ordered_rules": list(_LME_ORDERED_RULES),
        "relation_guard": _LME_RELATION_GUARD,
    }
