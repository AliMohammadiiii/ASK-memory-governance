from __future__ import annotations

from pathlib import Path

import pytest

from mgp_natural.baselines.controllers import (
    DeterministicRuleBaseline,
    ExternalModelAdapter,
    NoMemoryBaseline,
    OverwriteBaseline,
    RecencyBaseline,
    metadata_for_offline_run,
    run_controller,
)
from mgp_natural.errors import ValidationError
from mgp_natural.trajectories.evaluate import evaluate_trajectory


def test_offline_baselines_emit_predictions(tmp_path: Path, blind_items: list[dict]) -> None:
    for controller in (NoMemoryBaseline(), RecencyBaseline(), OverwriteBaseline(), DeterministicRuleBaseline()):
        output = tmp_path / f"{controller.name}.jsonl"
        digest = run_controller(controller, blind_items, output)
        assert len(digest) == 64
        assert output.read_text().count("\n") == len(blind_items)


def test_external_model_requires_authorization() -> None:
    with pytest.raises(ValidationError, match="explicit authorization"):
        ExternalModelAdapter("provider", "model").predict({})
    with pytest.raises(ValidationError, match="no provider implementation"):
        ExternalModelAdapter("provider", "model", authorized=True).predict({})


def test_offline_run_metadata_records_no_fallback() -> None:
    metadata = metadata_for_offline_run("rule", "a" * 64, "b" * 64, "c" * 64)
    assert metadata.provider == "local-deterministic"
    assert metadata.fallback_policy == "disabled"
    assert metadata.cost == 0.0


def test_trajectory_error_and_recovery() -> None:
    gold = [
        {"prior_value": "a", "action": "SUPERSEDE", "resulting_value": "b"},
        {"prior_value": "b", "action": "KEEP", "resulting_value": "b"},
        {"prior_value": "b", "action": "SUPERSEDE", "resulting_value": "c"},
    ]
    pred = [
        {"prior_value": "a", "action": "ABSTAIN", "resulting_value": "a"},
        {"prior_value": "a", "action": "KEEP", "resulting_value": "a"},
        {"prior_value": "a", "action": "SUPERSEDE", "resulting_value": "c"},
    ]
    report = evaluate_trajectory(gold, pred)
    assert report["first_incorrect_write_index"] == 0
    assert report["stale_state_events"] == 1
    assert report["recovery_events"] == 1
    assert report["final_state_canonical"] is True


def test_trajectory_invalid_supersede() -> None:
    with pytest.raises(ValidationError, match="changed value"):
        evaluate_trajectory(
            [{"prior_value": "a", "action": "SUPERSEDE", "resulting_value": "a"}],
            [{"prior_value": "a", "action": "SUPERSEDE", "resulting_value": "a"}],
        )

