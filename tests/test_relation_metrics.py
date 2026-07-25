"""Relation metrics tests."""

from __future__ import annotations

from ask.classifier.metrics import confusion_counts, per_label_metrics


def test_confusion_counts_include_all_label_pairs() -> None:
    counts = confusion_counts(["support", "contradict"], ["support", "unclear"])

    assert counts[("support", "support")] == 1
    assert counts[("contradict", "unclear")] == 1
    assert counts[("supersede", "support")] == 0


def test_per_label_metrics() -> None:
    rows = {r.label: r for r in per_label_metrics(["support", "support"], ["support", "unclear"])}

    assert rows["support"].precision == 1.0
    assert rows["support"].recall == 0.5
    assert rows["support"].f1 == 2 / 3
    assert rows["contradict"].f1 is None
