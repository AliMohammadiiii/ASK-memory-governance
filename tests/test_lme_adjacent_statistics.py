from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = (ROOT / "runs_local/lme_final_controller_v12_qwen_180/b1/judgments.jsonl").is_file()


@pytest.mark.skipif(not AVAILABLE, reason="local V12 judgments are not publicly redistributed")
def test_four_adjacent_holm_family_matches_paper() -> None:
    path = ROOT / "scripts/analysis/build_lme_adjacent_statistics.py"
    spec = importlib.util.spec_from_file_location("lme_adjacent", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert report["family_size"] == 4
    assert [(row["b"], row["c"]) for row in report["comparisons"]] == [
        (34, 0),
        (48, 11),
        (44, 10),
        (31, 8),
    ]
    assert report["comparisons"][-1]["holm_adjusted_p"] == 0.0002940768754342571
