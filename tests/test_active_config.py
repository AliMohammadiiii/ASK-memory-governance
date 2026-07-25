"""Active controller config contracts."""

from __future__ import annotations

from pathlib import Path

from ask.controller.active import load_scorecard_config


def test_active_controller_config_is_loadable() -> None:
    path = Path("configs/controller_active.yaml")

    config = load_scorecard_config(path)

    assert path.exists()
    assert config.theta_sup["stable_pref"] > config.theta_sup["episodic_fact"]
    assert config.theta_sup["episodic_fact"] > config.theta_sup["transient_pref"]


def test_legacy_proposal_config_is_archived_not_default_named() -> None:
    assert Path("configs/controller_legacy_proposal.yaml").exists()
    assert not Path("configs/default.yaml").exists()
    assert not Path("configs/scorecard_m3w9.yaml").exists()
