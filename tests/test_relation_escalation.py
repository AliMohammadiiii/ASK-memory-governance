from __future__ import annotations

from types import SimpleNamespace

from ask.pipeline.relation_escalation import marker_burden


def test_marker_burden_counts_two_boolean_markers() -> None:
    assert marker_burden(SimpleNamespace(negation_marker=False, hedge_marker=False)) == 0.0
    assert marker_burden(SimpleNamespace(negation_marker=True, hedge_marker=False)) == 0.5
    assert marker_burden(SimpleNamespace(negation_marker=True, hedge_marker=True)) == 1.0
    assert marker_burden(object()) == 0.0
