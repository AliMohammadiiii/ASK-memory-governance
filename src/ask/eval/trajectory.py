"""Trajectory-level propagation and recovery metrics for ASK evaluations."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class TrajectoryStep:
    expected_action: str
    observed_action: str
    state_correct: bool
    retrieval_affected: bool = False
    stale_retrieval: bool = False
    downstream_answer_correct: bool = True
    lineage_valid: bool = True
    rollback_attempted: bool = False
    rollback_succeeded: bool | None = None
    recovery_marker: bool = False
    governance_cost: float = 0.0


@dataclass(frozen=True)
class TrajectoryMetrics:
    trajectory_id: str
    write_count: int
    first_erroneous_write_position: int | None
    action_error_count: int
    action_error_rate: float
    state_corruption_count: int
    state_corruption_rate: float
    maximum_persistence_length: int
    propagation_count: int
    affected_retrieval_count: int
    stale_retrieval_count: int
    downstream_answer_corruption_count: int
    lineage_break_count: int
    rollback_attempt_count: int
    rollback_success_count: int
    recovery_opportunity_count: int
    recovery_success_count: int
    recovery_latency_writes: int | None
    residual_corruption: bool
    cumulative_expected_governance_cost: float


def evaluate_trajectory(trajectory_id: str, steps: list[TrajectoryStep]) -> TrajectoryMetrics:
    if not trajectory_id or not steps:
        raise ValueError("trajectory_id and at least one step are required")
    action_errors = [step.expected_action != step.observed_action for step in steps]
    corrupt = [not step.state_correct for step in steps]
    first_error = next((index + 1 for index, value in enumerate(action_errors) if value), None)
    maximum_persistence = 0
    current = 0
    for value in corrupt:
        current = current + 1 if value else 0
        maximum_persistence = max(maximum_persistence, current)
    first_corruption = next((index for index, value in enumerate(corrupt) if value), None)
    recovery_markers = [index for index, step in enumerate(steps) if step.recovery_marker]
    recovery_successes = [index for index in recovery_markers if not corrupt[index]]
    recovery_latency = None
    if first_corruption is not None and recovery_successes:
        first_recovery = next(
            (index for index in recovery_successes if index >= first_corruption), None
        )
        if first_recovery is not None:
            recovery_latency = first_recovery - first_corruption
    rollback_attempts = [step for step in steps if step.rollback_attempted]
    return TrajectoryMetrics(
        trajectory_id=trajectory_id,
        write_count=len(steps),
        first_erroneous_write_position=first_error,
        action_error_count=sum(action_errors),
        action_error_rate=sum(action_errors) / len(steps),
        state_corruption_count=sum(corrupt),
        state_corruption_rate=sum(corrupt) / len(steps),
        maximum_persistence_length=maximum_persistence,
        propagation_count=sum(corrupt[first_corruption + 1 :])
        if first_corruption is not None
        else 0,
        affected_retrieval_count=sum(step.retrieval_affected for step in steps),
        stale_retrieval_count=sum(step.stale_retrieval for step in steps),
        downstream_answer_corruption_count=sum(
            not step.downstream_answer_correct for step in steps
        ),
        lineage_break_count=sum(not step.lineage_valid for step in steps),
        rollback_attempt_count=len(rollback_attempts),
        rollback_success_count=sum(step.rollback_succeeded is True for step in rollback_attempts),
        recovery_opportunity_count=len(recovery_markers),
        recovery_success_count=len(recovery_successes),
        recovery_latency_writes=recovery_latency,
        residual_corruption=corrupt[-1],
        cumulative_expected_governance_cost=sum(step.governance_cost for step in steps),
    )


def aggregate_trajectories(
    results: list[TrajectoryMetrics], *, bootstrap_samples: int = 2000, seed: int = 43017
) -> dict[str, Any]:
    if not results:
        raise ValueError("at least one trajectory result is required")
    fields = (
        "action_error_rate",
        "state_corruption_rate",
        "maximum_persistence_length",
        "affected_retrieval_count",
        "stale_retrieval_count",
        "downstream_answer_corruption_count",
        "lineage_break_count",
        "cumulative_expected_governance_cost",
    )
    estimates = {field: mean(float(getattr(row, field)) for row in results) for field in fields}
    rng = random.Random(seed)
    draws: dict[str, list[float]] = {field: [] for field in fields}
    for _ in range(bootstrap_samples):
        sample = [rng.choice(results) for _ in results]
        for field in fields:
            draws[field].append(mean(float(getattr(row, field)) for row in sample))

    def interval(values: list[float]) -> list[float]:
        ordered = sorted(values)
        low = ordered[int(0.025 * (len(ordered) - 1))]
        high = ordered[int(0.975 * (len(ordered) - 1))]
        return [low, high]

    return {
        "schema_version": "ask-trajectory-report/v1",
        "status": "MEASURED_FROM_PROVIDED_TRAJECTORIES",
        "trajectory_count": len(results),
        "bootstrap": {
            "unit": "trajectory",
            "samples": bootstrap_samples,
            "seed": seed,
        },
        "estimates": estimates,
        "cluster_intervals_95": {field: interval(draws[field]) for field in fields},
        "trajectories": [asdict(row) for row in results],
    }
