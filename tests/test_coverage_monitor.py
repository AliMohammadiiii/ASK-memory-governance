"""Coverage monitor tests."""

from __future__ import annotations

import pytest

from ksa.extraction.coverage import CoverageMonitor


def test_current_rate_uses_recent_window() -> None:
    monitor = CoverageMonitor(baseline_rate=1.0, window_size=3)

    monitor.record(n_items_extracted=4, n_turns_processed=4)
    monitor.record(n_items_extracted=1, n_turns_processed=1)

    assert monitor.current_rate() == pytest.approx(1.0)


def test_alarm_fires_below_baseline_factor() -> None:
    monitor = CoverageMonitor(baseline_rate=1.0, window_size=4, alarm_factor=0.5)

    monitor.record(n_items_extracted=1, n_turns_processed=4)

    assert monitor.current_rate() == pytest.approx(0.25)
    assert monitor.is_alarmed()


def test_alarm_is_quiet_without_records() -> None:
    monitor = CoverageMonitor(baseline_rate=1.0)

    assert monitor.current_rate() == 0.0
    assert not monitor.is_alarmed()


@pytest.mark.parametrize(
    ("baseline_rate", "window_size", "alarm_factor"),
    [(-0.1, 50, 0.5), (1.0, 0, 0.5), (1.0, 50, -0.5)],
)
def test_constructor_rejects_invalid_config(
    baseline_rate: float,
    window_size: int,
    alarm_factor: float,
) -> None:
    with pytest.raises(ValueError):
        CoverageMonitor(
            baseline_rate=baseline_rate,
            window_size=window_size,
            alarm_factor=alarm_factor,
        )
