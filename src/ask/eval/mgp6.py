"""MGP-6 action-level evaluation metrics."""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .mgp6_schema import MGP6Scenario

ACTIONS: tuple[str, ...] = ("KEEP", "SUPERSEDE", "ABSTAIN")


@dataclass(frozen=True)
class MGP6Prediction:
    scenario_id: str
    scenario_type: str
    initial_memory_type: str
    gold_action: str
    predicted_action: str
    memory_state: list[dict[str, Any]]
    action_sequence: list[str]
    candidate_type: str | None = None
    theta_sup: float | None = None
    correct_action: bool = False
    state_correct: bool = False
    over_forgetting: bool = False
    under_forgetting: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_type": self.scenario_type,
            "initial_memory_type": self.initial_memory_type,
            "gold_action": self.gold_action,
            "predicted_action": self.predicted_action,
            "memory_state": self.memory_state,
            "action_sequence": self.action_sequence,
            "candidate_type": self.candidate_type,
            "theta_sup": self.theta_sup,
            "correct_action": self.correct_action,
            "state_correct": self.state_correct,
            "over_forgetting": self.over_forgetting,
            "under_forgetting": self.under_forgetting,
        }


def normalize_action(value: Any) -> str:
    text = getattr(value, "value", value)
    text = str(text).strip().upper()
    if text in {"KEEP", "KEPT"}:
        return "KEEP"
    if text in {"SUPERSEDE", "SUPERSEDED", "SUPERSEDES"}:
        return "SUPERSEDE"
    if text in {"ABSTAIN", "ABSTAINED"}:
        return "ABSTAIN"
    raise ValueError(f"unknown MGP-6 action: {value!r}")


def consolidate_actions(actions: Iterable[Any]) -> str:
    normalized = [normalize_action(a) for a in actions]
    if not normalized:
        return "ABSTAIN"
    if "SUPERSEDE" in normalized:
        return "SUPERSEDE"
    if any(a == "KEEP" for a in normalized):
        return "KEEP"
    return "ABSTAIN"


def build_prediction(
    scenario: MGP6Scenario,
    *,
    predicted_action: Any,
    memory_state: list[dict[str, Any]],
    action_sequence: list[Any] | None = None,
    candidate_type: str | None = None,
    theta_sup: float | None = None,
) -> MGP6Prediction:
    action = normalize_action(predicted_action)
    seq = [normalize_action(a) for a in (action_sequence or [action])]
    over = _over_forgetting(scenario, memory_state)
    under = _under_forgetting(scenario, memory_state)
    state_correct = _state_correct(scenario, action, memory_state)
    return MGP6Prediction(
        scenario_id=scenario.scenario_id,
        scenario_type=scenario.type,
        initial_memory_type=scenario.initial_memory_state[0].type,
        gold_action=scenario.gold_action,
        predicted_action=action,
        memory_state=memory_state,
        action_sequence=seq,
        candidate_type=candidate_type,
        theta_sup=theta_sup,
        correct_action=action == scenario.gold_action,
        state_correct=state_correct,
        over_forgetting=over,
        under_forgetting=under,
    )


def compute_report(
    predictions: list[MGP6Prediction],
    *,
    baseline: str,
    n_bootstrap: int = 1000,
    seed: int = 0,
) -> dict[str, Any]:
    rows = list(predictions)
    n = len(rows)
    confusion = _confusion(rows)
    return {
        "baseline": baseline,
        "n_scenarios": n,
        "action_accuracy": _rate(rows, lambda r: r.correct_action),
        "action_accuracy_ci": _ci(
            rows, lambda sample: _rate(sample, lambda r: r.correct_action), n_bootstrap, seed
        ),
        "state_accuracy": _rate(rows, lambda r: r.state_correct),
        "state_accuracy_ci": _ci(
            rows, lambda sample: _rate(sample, lambda r: r.state_correct), n_bootstrap, seed + 1
        ),
        "over_forgetting_rate": _rate(rows, lambda r: r.over_forgetting),
        "over_forgetting_ci": _ci(
            rows, lambda sample: _rate(sample, lambda r: r.over_forgetting), n_bootstrap, seed + 2
        ),
        "under_forgetting_rate": _rate(rows, lambda r: r.under_forgetting),
        "under_forgetting_ci": _ci(
            rows, lambda sample: _rate(sample, lambda r: r.under_forgetting), n_bootstrap, seed + 3
        ),
        "confusion_matrix": confusion,
        "per_action": _per_action(rows, n_bootstrap=n_bootstrap, seed=seed + 10),
        "per_type": _per_group(
            rows, key=lambda r: r.scenario_type, n_bootstrap=n_bootstrap, seed=seed + 20
        ),
        "per_initial_memory_type": _per_group(
            rows, key=lambda r: r.initial_memory_type, n_bootstrap=n_bootstrap, seed=seed + 30
        ),
        "threshold_ordering": _threshold_ordering(rows),
        "predictions": [r.to_dict() for r in rows],
    }


def _confusion(rows: list[MGP6Prediction]) -> dict[str, dict[str, int]]:
    out = {gold: dict.fromkeys(ACTIONS, 0) for gold in ACTIONS}
    for row in rows:
        out[row.gold_action][row.predicted_action] += 1
    return out


def _per_action(
    rows: list[MGP6Prediction],
    *,
    n_bootstrap: int,
    seed: int,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for idx, action in enumerate(ACTIONS):

        def precision_metric(sample: list[MGP6Prediction], current_action: str = action) -> float:
            return _precision(sample, current_action)

        def recall_metric(sample: list[MGP6Prediction], current_action: str = action) -> float:
            return _recall(sample, current_action)

        def f1_metric(sample: list[MGP6Prediction], current_action: str = action) -> float:
            return _f1(sample, current_action)

        out[action] = {
            "precision": _precision(rows, action),
            "precision_ci": _ci(rows, precision_metric, n_bootstrap, seed + idx * 3),
            "recall": _recall(rows, action),
            "recall_ci": _ci(rows, recall_metric, n_bootstrap, seed + idx * 3 + 1),
            "f1": _f1(rows, action),
            "f1_ci": _ci(rows, f1_metric, n_bootstrap, seed + idx * 3 + 2),
            "support": sum(1 for row in rows if row.gold_action == action),
            "predicted": sum(1 for row in rows if row.predicted_action == action),
        }
    return out


def _per_group(
    rows: list[MGP6Prediction],
    *,
    key: Callable[[MGP6Prediction], str],
    n_bootstrap: int,
    seed: int,
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[MGP6Prediction]] = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    out = {}
    for idx, group_key in enumerate(sorted(groups)):
        bucket = groups[group_key]
        out[group_key] = {
            "n": len(bucket),
            "action_accuracy": _rate(bucket, lambda r: r.correct_action),
            "action_accuracy_ci": _ci(
                bucket,
                lambda sample: _rate(sample, lambda r: r.correct_action),
                n_bootstrap,
                seed + idx * 4,
            ),
            "state_accuracy": _rate(bucket, lambda r: r.state_correct),
            "over_forgetting_rate": _rate(bucket, lambda r: r.over_forgetting),
            "under_forgetting_rate": _rate(bucket, lambda r: r.under_forgetting),
            "gold_actions": dict(Counter(row.gold_action for row in bucket)),
            "predicted_actions": dict(Counter(row.predicted_action for row in bucket)),
        }
    return out


def _threshold_ordering(rows: list[MGP6Prediction]) -> dict[str, Any]:
    buckets: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    totals: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.candidate_type is None:
            continue
        totals[row.candidate_type] += 1
        if not row.correct_action:
            errors[row.candidate_type] += 1
        if row.theta_sup is not None:
            buckets[row.candidate_type].append(float(row.theta_sup))

    mean_theta = {
        memory_type: sum(values) / len(values)
        for memory_type, values in sorted(buckets.items())
        if values
    }
    required = ("stable_pref", "episodic_fact", "transient_pref")
    has_all = all(memory_type in mean_theta for memory_type in required)
    ordered = (
        has_all
        and mean_theta["stable_pref"] > mean_theta["episodic_fact"] > mean_theta["transient_pref"]
    )
    return {
        "expected_order": list(required),
        "mean_theta_sup_by_candidate_type": mean_theta,
        "errors_by_candidate_type": dict(sorted(errors.items())),
        "n_by_candidate_type": dict(sorted(totals.items())),
        "empirical_status": "confirmed" if ordered else "insufficient_coverage_or_refuted",
        "confirmed": ordered,
    }


def _precision(rows: list[MGP6Prediction], action: str) -> float:
    predicted = [row for row in rows if row.predicted_action == action]
    if not predicted:
        return 0.0
    return sum(1 for row in predicted if row.gold_action == action) / len(predicted)


def _recall(rows: list[MGP6Prediction], action: str) -> float:
    gold = [row for row in rows if row.gold_action == action]
    if not gold:
        return 0.0
    return sum(1 for row in gold if row.predicted_action == action) / len(gold)


def _f1(rows: list[MGP6Prediction], action: str) -> float:
    p = _precision(rows, action)
    r = _recall(rows, action)
    if p + r == 0.0:
        return 0.0
    return 2 * p * r / (p + r)


def _rate(rows: list[MGP6Prediction], predicate: Callable[[MGP6Prediction], bool]) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if predicate(row)) / len(rows)


def _ci(
    rows: list[MGP6Prediction],
    metric: Callable[[list[MGP6Prediction]], float],
    n_bootstrap: int,
    seed: int,
) -> list[float]:
    if not rows:
        return [0.0, 0.0]
    if len(rows) == 1:
        value = metric(rows)
        return [value, value]
    rng = random.Random(seed)
    values = []
    for _ in range(n_bootstrap):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        values.append(metric(sample))
    values.sort()
    lo_idx = max(0, min(len(values) - 1, int(0.025 * len(values))))
    hi_idx = max(0, min(len(values) - 1, int(0.975 * len(values)) - 1))
    return [values[lo_idx], values[hi_idx]]


def _prior_status(scenario: MGP6Scenario, memory_state: list[dict[str, Any]]) -> str | None:
    prior_id = scenario.initial_memory_state[0].id
    for item in memory_state:
        if str(item.get("id")) == prior_id:
            return str(item.get("status", "active"))
    return None


def _gold_prior_status(scenario: MGP6Scenario) -> str | None:
    prior_id = scenario.initial_memory_state[0].id
    for item in scenario.gold_memory_state:
        if item.id == prior_id:
            return item.status
    return None


def _has_new_active(memory_state: list[dict[str, Any]], prior_id: str) -> bool:
    return any(
        str(item.get("id")) != prior_id and str(item.get("status", "active")) == "active"
        for item in memory_state
    )


def _gold_has_new_active(scenario: MGP6Scenario) -> bool:
    prior_id = scenario.initial_memory_state[0].id
    return any(
        item.id != prior_id and item.status == "active" for item in scenario.gold_memory_state
    )


def _over_forgetting(scenario: MGP6Scenario, memory_state: list[dict[str, Any]]) -> bool:
    return (
        _gold_prior_status(scenario) == "active"
        and _prior_status(scenario, memory_state) != "active"
    )


def _under_forgetting(scenario: MGP6Scenario, memory_state: list[dict[str, Any]]) -> bool:
    return (
        _gold_prior_status(scenario) != "active"
        and _prior_status(scenario, memory_state) == "active"
    )


def _state_correct(
    scenario: MGP6Scenario,
    predicted_action: str,
    memory_state: list[dict[str, Any]],
) -> bool:
    prior_id = scenario.initial_memory_state[0].id
    return (
        predicted_action == scenario.gold_action
        and _prior_status(scenario, memory_state) == _gold_prior_status(scenario)
        and _has_new_active(memory_state, prior_id) == _gold_has_new_active(scenario)
    )
