"""Shared baseline answer surface.

Every memory baseline (no-memory, flat-vector, recency, naive-overwrite) and
the eventual KSA controller emits a `BaselineAnswer`. The evaluator does not
know which baseline produced the answer — that is the point of the shared
shape and the contract is enforced by the test in
`tests/test_longmemeval_eval.py`.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BaselineAnswer:
    """One baseline's answer to one LongMemEval session.

    Carries enough metadata for:
      * grading (`text` + the session's gold answer in the evaluator);
      * compute accounting (`prompt_tokens`, `completion_tokens`, `latency_ms`);
      * reproducibility / debugging (`raw_prompt`, `seed`, `model_id`).

    The `extras` dict is reserved for baseline-specific telemetry that later
    baselines need but no-memory does not (e.g. retrieval scores, retrieved
    span ids). It is allowed to be empty.
    """

    session_id: str
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    raw_prompt: str
    seed: int = 0
    model_id: str = ""
    baseline: str = "unknown"
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)
