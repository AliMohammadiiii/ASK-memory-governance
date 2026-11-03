"""Pure helpers for the relation-escalation policy."""

from __future__ import annotations


def marker_burden(item: object) -> float:
    """Return the fraction of negation and hedge markers present on an item."""
    markers = (
        bool(getattr(item, "negation_marker", False)),
        bool(getattr(item, "hedge_marker", False)),
    )
    return sum(markers) / len(markers)
