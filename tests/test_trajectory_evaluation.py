from __future__ import annotations

from ask.eval.trajectory import TrajectoryStep, aggregate_trajectories, evaluate_trajectory


def test_trajectory_propagation_and_recovery_metrics() -> None:
    result = evaluate_trajectory(
        "t1",
        [
            TrajectoryStep("Keep", "Keep", True),
            TrajectoryStep(
                "Abstain",
                "Supersede",
                False,
                retrieval_affected=True,
                stale_retrieval=True,
                downstream_answer_correct=False,
                governance_cost=5.0,
            ),
            TrajectoryStep("Keep", "Keep", False, retrieval_affected=True),
            TrajectoryStep(
                "Supersede",
                "Supersede",
                True,
                rollback_attempted=True,
                rollback_succeeded=True,
                recovery_marker=True,
            ),
        ],
    )
    assert result.first_erroneous_write_position == 2
    assert result.state_corruption_count == 2
    assert result.maximum_persistence_length == 2
    assert result.propagation_count == 1
    assert result.recovery_latency_writes == 2
    assert result.residual_corruption is False
    assert result.cumulative_expected_governance_cost == 5.0


def test_cluster_bootstrap_is_deterministic() -> None:
    rows = [
        evaluate_trajectory("a", [TrajectoryStep("Keep", "Keep", True)]),
        evaluate_trajectory("b", [TrajectoryStep("Keep", "Abstain", True)]),
    ]
    assert aggregate_trajectories(rows, bootstrap_samples=100, seed=9) == aggregate_trajectories(
        rows, bootstrap_samples=100, seed=9
    )
