"""Project-specific fail-closed exceptions."""


class MGPError(Exception):
    """Base class for repository errors."""


class ValidationError(MGPError):
    """Raised when an artifact violates a semantic or structural invariant."""


class GateBlockedError(MGPError):
    """Raised when a human or machine gate blocks an operation."""


class SourceChangedError(MGPError):
    """Raised when a pinned source no longer matches its manifest."""

