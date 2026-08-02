from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "analysis" / "analyze_lme_scorecard.py"
    spec = importlib.util.spec_from_file_location("analyze_lme_scorecard", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(**overrides):
    row = {
        "id": 1,
        "action": "Keep",
        "candidate_type": "episodic_fact",
        "feature_c": 0.95,
        "feature_e": 0.80,
        "feature_f": 0.0,
        "feature_r": 1.0,
        "feature_rho": 0.6,
        "s_rev": 1.29,
        "s_abs": 0.05,
        "theta_sup": 0.75,
        "theta_abs": 0.70,
    }
    row.update(overrides)
    return row


def test_replay_requires_negative_relation_for_supersede():
    module = _load_module()
    assert module.replay_action(_row()) == "Keep"
    assert module.replay_action(_row(feature_r=-1.0, s_rev=2.49, action="Supersede")) == "Supersede"


def test_replay_checks_abstention_before_supersession():
    module = _load_module()
    row = _row(
        action="Abstain",
        feature_c=0.50,
        feature_f=0.5,
        feature_r=-1.0,
        s_abs=1.0,
        s_rev=1.89,
    )
    assert module.replay_action(row) == "Abstain"


def test_score_replays_logged_values():
    module = _load_module()
    s_sup, s_abs, update_pressure = module.score(_row())
    assert s_sup == 1.29
    assert abs(s_abs - 0.05) < 1e-12
    assert update_pressure == 0.0


def test_relation_ablation_disables_supersession_guard():
    module = _load_module()
    row = _row(feature_r=-1.0, s_rev=2.49, action="Supersede")
    assert module.replay_action(row) == "Supersede"
    assert module.replay_action(row, omitted=frozenset({"r"})) == "Keep"
