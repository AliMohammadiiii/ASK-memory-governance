from __future__ import annotations

import math
from pathlib import Path

import pytest

from mgp_natural.errors import ValidationError
from mgp_natural.scoring.metrics import (
    brier_score,
    classification_metrics,
    cluster_bootstrap,
    expected_calibration_error,
    score_files,
)
from mgp_natural.util.io import iter_jsonl, write_jsonl


def test_correct_macro_f1_and_confusion_matrix() -> None:
    result = classification_metrics(
        ["KEEP", "SUPERSEDE", "ABSTAIN"],
        ["KEEP", "SUPERSEDE", "KEEP"],
    )
    assert math.isclose(result["accuracy"], 2 / 3)
    assert math.isclose(result["macro_f1"], (2 / 3 + 1 + 0) / 3)
    assert result["confusion_matrix"]["ABSTAIN"]["KEEP"] == 1


def test_provisional_gold_refused_without_flag(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="refuses provisional"):
        score_files(
            Path("data/fixtures/provisional_gold.jsonl"),
            Path("data/fixtures/predictions.jsonl"),
            tmp_path / "score.json",
        )


def test_provisional_smoke_is_not_publication_eligible(tmp_path: Path) -> None:
    result = score_files(
        Path("data/fixtures/provisional_gold.jsonl"),
        Path("data/fixtures/predictions.jsonl"),
        tmp_path / "score.json",
        allow_provisional_smoke=True,
    )
    assert result["publication_eligible"] is False
    assert result["required_statement"] == "publication_eligible = false"


def test_duplicate_prediction_ids(tmp_path: Path) -> None:
    rows = list(iter_jsonl(Path("data/fixtures/predictions.jsonl")))
    path = tmp_path / "pred.jsonl"
    write_jsonl(path, [*rows, rows[0]])
    with pytest.raises(ValidationError, match="duplicate prediction ID"):
        score_files(Path("data/fixtures/provisional_gold.jsonl"), path, tmp_path / "s.json", True)


def test_incomplete_coverage(tmp_path: Path) -> None:
    rows = list(iter_jsonl(Path("data/fixtures/predictions.jsonl")))
    path = tmp_path / "pred.jsonl"
    write_jsonl(path, rows[:-1])
    with pytest.raises(ValidationError, match="coverage"):
        score_files(Path("data/fixtures/provisional_gold.jsonl"), path, tmp_path / "s.json", True)


def test_invalid_action(tmp_path: Path) -> None:
    rows = list(iter_jsonl(Path("data/fixtures/predictions.jsonl")))
    rows[0]["action"] = "INVALID"
    path = tmp_path / "pred.jsonl"
    write_jsonl(path, rows)
    with pytest.raises(ValidationError, match="invalid predicted action"):
        score_files(Path("data/fixtures/provisional_gold.jsonl"), path, tmp_path / "s.json", True)


def test_cluster_bootstrap_is_deterministic() -> None:
    rows = [
        {"cluster": "a", "correct": 1.0},
        {"cluster": "a", "correct": 0.0},
        {"cluster": "b", "correct": 1.0},
    ]

    def statistic(sample: list[dict[str, object]]) -> float:
        return sum(float(row["correct"]) for row in sample) / len(sample)

    first = cluster_bootstrap(rows, "cluster", statistic, iterations=200, seed=11)
    second = cluster_bootstrap(rows, "cluster", statistic, iterations=200, seed=11)
    assert first == second


def test_calibration_metrics() -> None:
    gold = ["KEEP", "ABSTAIN"]
    pred = ["KEEP", "KEEP"]
    probs = [
        {"KEEP": 0.8, "SUPERSEDE": 0.1, "ABSTAIN": 0.1},
        {"KEEP": 0.6, "SUPERSEDE": 0.1, "ABSTAIN": 0.3},
    ]
    assert brier_score(gold, probs) > 0
    assert expected_calibration_error(gold, pred, [0.8, 0.6], bins=5) >= 0

