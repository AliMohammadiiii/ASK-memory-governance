"""Quality-preset must not clobber explicit prompt-slim flags (M4W13).

Regression test for the bug where ``--quality t4`` force-enabled assistant
context and the +/-1 neighbor window even when the user passed
``--no-controller-include-assistant-context`` and
``--controller-retrieval-neighbor-window 0`` — the prompt-slim run could not
actually slim the prompt because the preset reverted those flags.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_m4w13_ollama import (  # type: ignore[import-not-found]  # noqa: E402
    _apply_t4_quality,
    _explicitly_set_dests,
)


def _namespace(**overrides: object) -> argparse.Namespace:
    base = dict(
        quality="t4",
        controller_include_assistant_context=False,
        answer_retry_on_unknown=False,
        controller_prior_top_k=1,
        controller_prior_similarity_threshold=0.0,
        k=5,
        controller_retrieval_neighbor_window=0,
        ollama_num_ctx=8192,
        controller_temporal_scaffold=False,
        controller_computation_answerer=False,
        controller_include_raw_user_context=False,
        controller_retrieval_query_augmentation=False,
        controller_deterministic_numeric_supersede=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_explicit_slim_flags_survive_quality_preset() -> None:
    explicit = {
        "controller_include_assistant_context",
        "controller_retrieval_neighbor_window",
        "k",
    }
    args = _namespace(
        controller_include_assistant_context=False,
        controller_retrieval_neighbor_window=0,
        k=6,
    )
    _apply_t4_quality(args, explicit)

    # Explicitly-passed prompt-slim flags are preserved.
    assert args.controller_include_assistant_context is False
    assert args.controller_retrieval_neighbor_window == 0
    assert args.k == 6
    # Knobs the user did not touch still get the validated quality bundle.
    assert args.controller_computation_answerer is True
    assert args.controller_temporal_scaffold is True
    assert args.controller_prior_top_k == 3
    assert args.controller_include_raw_user_context is True


def test_quality_preset_applies_when_nothing_is_explicit() -> None:
    args = _namespace()
    _apply_t4_quality(args, set())
    assert args.controller_include_assistant_context is True
    assert args.controller_retrieval_neighbor_window == 1
    assert args.k == 10
    assert args.ollama_num_ctx == 16384
    assert args.answer_retry_on_unknown is True


def test_quality_none_is_a_noop() -> None:
    args = _namespace(quality="none")
    _apply_t4_quality(args, set())
    assert args.controller_include_assistant_context is False
    assert args.k == 5
    assert args.controller_retrieval_neighbor_window == 0


def test_explicitly_set_dests_recognizes_no_form_and_default_value() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--controller-include-assistant-context",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument("--controller-retrieval-neighbor-window", type=int, default=0)
    parser.add_argument("--k", type=int, default=5)

    seen = _explicitly_set_dests(
        parser,
        [
            "--no-controller-include-assistant-context",
            "--controller-retrieval-neighbor-window",
            "0",
            "--k=6",
        ],
    )
    assert "controller_include_assistant_context" in seen
    assert "controller_retrieval_neighbor_window" in seen
    assert "k" in seen
