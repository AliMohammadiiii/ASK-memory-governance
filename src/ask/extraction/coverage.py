"""Rolling coverage monitor for precision-biased extraction."""

from __future__ import annotations

from collections import deque


class CoverageMonitor:
    """Alarm when recent extraction coverage drops below a baseline fraction.

    The monitor is intentionally alarm-only in Month 2. It does not relax the
    prompt or mutate extraction behavior; later controller work can decide what
    to do with a sustained alarm.
    """

    def __init__(
        self,
        baseline_rate: float,
        window_size: int = 50,
        alarm_factor: float = 0.5,
    ) -> None:
        if baseline_rate < 0.0:
            raise ValueError("baseline_rate must be non-negative")
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        if alarm_factor < 0.0:
            raise ValueError("alarm_factor must be non-negative")
        self.baseline_rate = float(baseline_rate)
        self.window_size = int(window_size)
        self.alarm_factor = float(alarm_factor)
        self._records: deque[tuple[float, int]] = deque()

    def record(self, n_items_extracted: int, n_turns_processed: int) -> None:
        """Append one aggregate observation to the rolling window."""
        if n_items_extracted < 0:
            raise ValueError("n_items_extracted must be non-negative")
        if n_turns_processed <= 0:
            raise ValueError("n_turns_processed must be positive")
        self._records.append((float(n_items_extracted), int(n_turns_processed)))
        self._trim_to_window()

    def current_rate(self) -> float:
        """Return items per turn over the retained rolling window."""
        turns = sum(turn_count for _items, turn_count in self._records)
        if turns == 0:
            return 0.0
        items = sum(item_count for item_count, _turn_count in self._records)
        return items / turns

    def is_alarmed(self) -> bool:
        """True iff observed coverage is below the configured alarm threshold."""
        turns = sum(turn_count for _items, turn_count in self._records)
        if turns == 0:
            return False
        return self.current_rate() < self.baseline_rate * self.alarm_factor

    def _trim_to_window(self) -> None:
        total_turns = sum(turn_count for _items, turn_count in self._records)
        while self._records and total_turns > self.window_size:
            over = total_turns - self.window_size
            item_count, turn_count = self._records[0]
            if turn_count <= over:
                self._records.popleft()
                total_turns -= turn_count
                continue

            keep_turns = turn_count - over
            keep_ratio = keep_turns / turn_count
            self._records[0] = (item_count * keep_ratio, keep_turns)
            total_turns = self.window_size
