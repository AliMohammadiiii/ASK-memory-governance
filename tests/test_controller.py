"""M3-W9 scorecard controller tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ksa.audit import ActionLogRecord, ActionLogWriter
from ksa.classifier.schema import RelationOutput
from ksa.controller.active import (
    FeatureSnapshot,
    ScorecardConfig,
    c,
    decide,
    e,
    f,
    r,
    rho,
    s_abs,
    s_rev,
)
from ksa.extraction.schema import EvidenceSpan, ExtractedItem
from ksa.memory.models import ControllerAction, MemoryType


def _candidate(**overrides: object) -> ExtractedItem:
    base = dict(
        text="User now prefers tea in the morning.",
        type_guess="stable_pref",
        evidence_span=EvidenceSpan(
            session_id="s1",
            turn_idx=4,
            char_start=10,
            char_end=90,
        ),
        extraction_confidence=0.82,
        negation_marker=False,
        hedge_marker=False,
    )
    base.update(overrides)
    return ExtractedItem(**base)


class _Classifier:
    def __init__(self, output: RelationOutput) -> None:
        self.output = output

    def classify(self, candidate: object, prior: object) -> RelationOutput:
        return self.output


def test_feature_c_reads_extraction_confidence() -> None:
    assert c(_candidate(extraction_confidence=0.73)) == pytest.approx(0.73)


def test_feature_e_combines_span_specificity_and_recency() -> None:
    candidate = {
        "text": "User now prefers tea in the morning.",
        "type_guess": "stable_pref",
        "evidence_span": {"char_start": 10, "char_end": 90},
        "timestamp": "2026-05-21T10:00:00Z",
    }
    prior = {"text": "User prefers coffee.", "type": "stable_pref", "timestamp": "2025-01-01T00:00:00Z"}

    assert e(candidate, prior) == pytest.approx(1.0)


def test_feature_f_counts_extraction_markers() -> None:
    assert f(_candidate(negation_marker=False, hedge_marker=False)) == 0.0
    assert f(_candidate(negation_marker=True, hedge_marker=False)) == 0.5
    assert f(_candidate(negation_marker=True, hedge_marker=True)) == 1.0
    assert f({"text": "Maybe the user does not want coffee now."}) == 1.0


def test_feature_r_uses_classifier_output_and_temporal_modulation() -> None:
    contradict_same = RelationOutput(
        logical_relation="contradict",
        temporal="same",
        same_subject=True,
        relation_to_prior_state="contradict",
        stage1_rationale="coffee versus tea",
        stage2_rationale="same subject",
    )
    support_newer = RelationOutput(
        logical_relation="support",
        temporal="newer",
        same_subject=True,
        relation_to_prior_state="support",
        stage1_rationale="same preference",
        stage2_rationale="candidate newer",
    )
    unclear = RelationOutput(
        logical_relation="independent",
        temporal="unknown",
        same_subject=False,
        relation_to_prior_state="unclear",
        stage1_rationale="different subject",
        stage2_rationale="different subject",
    )

    prior = {"text": "User prefers coffee.", "type": "stable_pref"}
    assert r(_candidate(), prior, classifier=_Classifier(contradict_same)) == pytest.approx(-0.9)
    assert r(_candidate(), prior, classifier=_Classifier(support_newer)) == pytest.approx(1.0)
    assert r(_candidate(), prior, classifier=_Classifier(unclear)) == 0.0


def test_feature_r_fails_without_classifier_or_embedded_relation() -> None:
    with pytest.raises(ValueError, match="RelationClassifier"):
        r(_candidate(), {"text": "User prefers coffee.", "type": "stable_pref"})


def test_feature_rho_type_prior_ordering() -> None:
    assert rho("stable_pref") == pytest.approx(0.9)
    assert rho("episodic_fact") == pytest.approx(0.6)
    assert rho("transient_pref") == pytest.approx(0.3)
    assert rho("stable_pref") > rho("episodic_fact") > rho("transient_pref")


def test_scorecard_adversarial_inputs() -> None:
    zero = FeatureSnapshot(c=0.0, e=0.0, f=0.0, r=0.0, rho=0.0)
    one = FeatureSnapshot(c=1.0, e=1.0, f=1.0, r=1.0, rho=1.0)
    mixed = FeatureSnapshot(c=0.9, e=0.8, f=0.5, r=-0.9, rho=0.6)

    assert s_rev(zero) == 0.0
    assert s_abs(zero) == 2.0
    assert s_rev(one) == pytest.approx(0.6)
    assert s_abs(one) == 1.0
    assert s_rev(mixed) == pytest.approx(1.97)
    assert s_abs(mixed) == pytest.approx(0.7)


def test_m3w91_supersede_score_monotonicity() -> None:
    base = FeatureSnapshot(c=0.8, e=0.7, f=0.0, r=-0.2, rho=0.6)
    stronger_update = FeatureSnapshot(c=0.8, e=0.7, f=0.0, r=-0.8, rho=0.6)
    higher_stability = FeatureSnapshot(c=0.8, e=0.7, f=0.0, r=-0.8, rho=0.9)

    assert s_rev(stronger_update) > s_rev(base)
    assert s_rev(higher_stability) < s_rev(stronger_update)


def test_action_rule_boundary_thresholds() -> None:
    features = FeatureSnapshot(c=1.0, e=1.0, f=0.0, r=-0.9, rho=0.9)
    score_value = s_rev(features)
    high_abs = {"stable_pref": 10.0, "episodic_fact": 10.0, "transient_pref": 10.0}

    equal = ScorecardConfig(
        theta_sup={"stable_pref": score_value, "episodic_fact": 0.75, "transient_pref": 0.55},
        theta_abs=high_abs,
    )
    below = ScorecardConfig(
        theta_sup={
            "stable_pref": score_value - 0.001,
            "episodic_fact": 0.75,
            "transient_pref": 0.55,
        },
        theta_abs=high_abs,
    )

    assert decide(features, MemoryType.STABLE_PREF, equal).action == ControllerAction.KEEP
    assert decide(features, MemoryType.STABLE_PREF, below).action == ControllerAction.SUPERSEDE


def test_abstain_rule_boundary_thresholds() -> None:
    features = FeatureSnapshot(c=0.0, e=0.0, f=0.0, r=0.0, rho=0.0)
    equal = ScorecardConfig(
        theta_sup={"stable_pref": 10.0, "episodic_fact": 9.0, "transient_pref": 8.0},
        theta_abs={"stable_pref": 2.0, "episodic_fact": 2.0, "transient_pref": 2.0},
    )
    below = ScorecardConfig(
        theta_sup={"stable_pref": 10.0, "episodic_fact": 9.0, "transient_pref": 8.0},
        theta_abs={"stable_pref": 1.999, "episodic_fact": 2.0, "transient_pref": 2.0},
    )

    assert decide(features, "stable_pref", equal).action == ControllerAction.KEEP
    assert decide(features, "stable_pref", below).action == ControllerAction.ABSTAIN


def test_rationale_contains_features_scores_and_thresholds() -> None:
    features = FeatureSnapshot(c=1.0, e=1.0, f=0.0, r=-1.0, rho=0.9)
    decision = decide(features, "stable_pref")

    for needle in (
        "c=1.000",
        "e=1.000",
        "f=0.000",
        "r=-1.000",
        "rho=0.900",
        "S_sup=",
        "S_rev=",
        "S_abs=",
        "θ_sup=",
        "θ_abs=",
        "supersede",
    ):
        assert needle in decision.rationale


def test_action_log_decision_roundtrip_via_pydantic(tmp_path: Path) -> None:
    features = FeatureSnapshot(c=1.0, e=1.0, f=0.0, r=-1.0, rho=0.9)
    decision = decide(features, "stable_pref")
    path = tmp_path / "action_log.jsonl"

    with ActionLogWriter(path, baseline="controller", fsync_on_write=False) as writer:
        writer.write_decision(
            entry_id=1,
            timestamp=datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC),
            candidate_text="User now prefers tea.",
            candidate_type="stable_pref",
            candidate_id=101,
            prior_memory_id=42,
            resulting_memory_id=102,
            decision=decision,
            session_id="s1",
        )

    raw = json.loads(path.read_text(encoding="utf-8").strip())
    record = ActionLogRecord.model_validate(raw)
    assert record.candidate_id == 101
    assert record.prior_memory_id == 42
    assert record.feature_r == -1.0
    assert record.action == ControllerAction.SUPERSEDE
    assert record.rationale == decision.rationale
