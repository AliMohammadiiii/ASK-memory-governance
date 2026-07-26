"""Cascade wiring: primary (4B) relation classifier escalates decision-critical
or uncertain items to the larger (9B) classifier inside _classify_relation."""

from __future__ import annotations

import types

import ask.pipeline.orchestrator as O
from ask.classifier import RelationOutput


def _rel(label: str) -> RelationOutput:
    return RelationOutput(
        logical_relation="independent",
        temporal="unknown",
        same_subject=False,
        relation_to_prior_state=label,
        stage1_rationale="r",
        stage2_rationale="r",
    )


def _cand(conf: float = 0.9, neg: bool = False, hedge: bool = False):
    item = types.SimpleNamespace(
        text="cand text",
        type_guess="episodic_fact",
        extraction_confidence=conf,
        negation_marker=neg,
        hedge_marker=hedge,
    )
    return types.SimpleNamespace(
        item=item,
        source_turn="t1",
        session_id="s1",
        turn_id="u1",
        timestamp="2026-01-01",
    )


def _prior():
    return types.SimpleNamespace(
        text="prior text", type=types.SimpleNamespace(value="episodic_fact")
    )


def _bare_orchestrator():
    o = O.ControllerOrchestrator.__new__(O.ControllerOrchestrator)
    o.classifier = "PRIMARY"
    o.classifier_escalation = "BIG"
    o._relation_model_id = "qwen35-4b"
    o._escalation_model_id = "qwen35-9b"
    o._relation_prompt_fingerprint = "fp"
    o._relation_cache = {}
    o._relation_cache_hits = 0
    o._relation_cache_misses = 0
    o._relation_escalations = 0
    o._relation_escalation_eligible = 0
    o.relation_max_new_tokens = 128
    o.seed = 0
    o.relation_cache_path = None
    o.escalation_relations = ("contradict", "supersede", "unclear")
    o.escalation_extraction_confidence = 0.75
    o.escalation_marker_burden = 0.35
    return o


def test_cascade_escalates_decision_critical_relation(monkeypatch):
    o = _bare_orchestrator()
    calls: list[str] = []

    def fake_classify(classifier, candidate, prior, prov, **kw):
        calls.append(classifier)
        return _rel("supersede") if classifier == "PRIMARY" else _rel("contradict")

    monkeypatch.setattr(O, "classify_relation", fake_classify)
    out = o._classify_relation(_cand(), _prior(), None)

    assert calls == ["PRIMARY", "BIG"]  # escalated
    assert out.relation_to_prior_state == "contradict"  # 9B verdict wins
    assert o._relation_escalations == 1
    assert o._relation_escalation_eligible == 1


def test_cascade_keeps_fast_model_on_clean_support(monkeypatch):
    o = _bare_orchestrator()
    calls: list[str] = []

    def fake_classify(classifier, candidate, prior, prov, **kw):
        calls.append(classifier)
        return _rel("support")

    monkeypatch.setattr(O, "classify_relation", fake_classify)
    out = o._classify_relation(_cand(conf=0.95), _prior(), None)

    assert calls == ["PRIMARY"]  # no escalation
    assert out.relation_to_prior_state == "support"
    assert o._relation_escalations == 0
    assert o._relation_escalation_eligible == 1


def test_cascade_keeps_fast_model_on_independent_unclear(monkeypatch):
    o = _bare_orchestrator()
    calls: list[str] = []

    def fake_classify(classifier, candidate, prior, prov, **kw):
        calls.append(classifier)
        return _rel("unclear")

    monkeypatch.setattr(O, "classify_relation", fake_classify)
    out = o._classify_relation(_cand(conf=0.95), _prior(), None)

    assert calls == ["PRIMARY"]
    assert out.logical_relation == "independent"
    assert out.relation_to_prior_state == "unclear"
    assert o._relation_escalations == 0


def test_no_escalation_classifier_means_no_cascade(monkeypatch):
    o = _bare_orchestrator()
    o.classifier_escalation = None
    calls: list[str] = []

    def fake_classify(classifier, candidate, prior, prov, **kw):
        calls.append(classifier)
        return _rel("supersede")

    monkeypatch.setattr(O, "classify_relation", fake_classify)
    out = o._classify_relation(_cand(), _prior(), None)

    assert calls == ["PRIMARY"]  # cascade disabled
    assert out.relation_to_prior_state == "supersede"
    assert o._relation_escalations == 0
