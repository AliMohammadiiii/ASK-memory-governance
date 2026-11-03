"""Metrics helpers for relation-classifier predictions."""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

LABELS: tuple[str, ...] = ("support", "contradict", "supersede", "unclear")


@dataclass(frozen=True)
class LabelMetrics:
    label: str
    support: int
    predicted: int
    true_positive: int
    precision: float | None
    recall: float | None
    f1: float | None
    f1_ci_low: float | None = None
    f1_ci_high: float | None = None


def confusion_counts(
    gold: Iterable[str],
    predicted: Iterable[str],
    labels: tuple[str, ...] = LABELS,
) -> dict[tuple[str, str], int]:
    counts = Counter(zip(gold, predicted, strict=True))
    return {(g, p): counts[(g, p)] for g in labels for p in labels}


def per_label_metrics(
    gold: list[str],
    predicted: list[str],
    labels: tuple[str, ...] = LABELS,
) -> list[LabelMetrics]:
    result: list[LabelMetrics] = []
    for label in labels:
        tp = sum(1 for g, p in zip(gold, predicted, strict=True) if g == label and p == label)
        pred_n = sum(1 for p in predicted if p == label)
        gold_n = sum(1 for g in gold if g == label)
        precision = tp / pred_n if pred_n else None
        recall = tp / gold_n if gold_n else None
        if precision is None or recall is None or precision + recall == 0.0:
            f1 = None if precision is None or recall is None else 0.0
        else:
            f1 = 2 * precision * recall / (precision + recall)
        result.append(
            LabelMetrics(
                label=label,
                support=gold_n,
                predicted=pred_n,
                true_positive=tp,
                precision=precision,
                recall=recall,
                f1=f1,
            )
        )
    return result


def add_bootstrap_f1_cis(
    rows: list[LabelMetrics],
    gold: list[str],
    predicted: list[str],
    *,
    n_bootstrap: int = 1000,
    seed: int = 0,
    labels: tuple[str, ...] = LABELS,
) -> list[LabelMetrics]:
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted must have the same length")
    if not gold:
        return rows
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {label: [] for label in labels}
    n = len(gold)
    for _ in range(n_bootstrap):
        idxs = [rng.randrange(n) for _ in range(n)]
        g_sample = [gold[i] for i in idxs]
        p_sample = [predicted[i] for i in idxs]
        for metric in per_label_metrics(g_sample, p_sample, labels):
            if metric.f1 is not None:
                samples[metric.label].append(metric.f1)

    updated: list[LabelMetrics] = []
    for row in rows:
        vals = sorted(samples[row.label])
        if not vals:
            updated.append(row)
            continue
        lo = vals[int(0.025 * (len(vals) - 1))]
        hi = vals[int(0.975 * (len(vals) - 1))]
        updated.append(
            LabelMetrics(
                label=row.label,
                support=row.support,
                predicted=row.predicted,
                true_positive=row.true_positive,
                precision=row.precision,
                recall=row.recall,
                f1=row.f1,
                f1_ci_low=lo,
                f1_ci_high=hi,
            )
        )
    return updated
