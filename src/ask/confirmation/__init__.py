"""Prospective independent-confirmation tooling.

Nothing in this package creates independent labels or satisfies a publication
gate.  It only prepares and audits label-free materials.
"""

from .blinding import (
    PROHIBITED_KEYS,
    build_packet,
    canonical_hash,
    make_commitment,
)

__all__ = ["PROHIBITED_KEYS", "build_packet", "canonical_hash", "make_commitment"]
