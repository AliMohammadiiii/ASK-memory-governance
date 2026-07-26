"""Five reference systems for MGP-6 v2, closed-book two-stage protocol.

Every system implements the same interface::

    predict(scenario) -> {predicted_action, predicted_memory_state,
                          predicted_answer, confidence}

Write stage sees only ``base_dialogue_prefix``, ``initial_memory_state`` and
``perturbation_event`` (via :func:`extractor.read_evidence`). The answer stage
then reads ``evaluation_query`` and answers from the *predicted* state only.

The four baselines are deliberately weakened ablations, per the spec:

* **b1 no_memory**   - sanity floor, no stored state, always non-commit.
* **b2 flat_vector** - fixed retrieval, *no* write governance (never updates).
* **b3 recency**     - newest evidence always wins, retains a timeline; no abstain.
* **b4 naive_overwrite** - destructive replace on any contradiction; no lineage,
                       no abstain safeguard.
* **controller**     - rule-governed KEEP / SUPERSEDE / ABSTAIN with an
                       abstention safeguard and retained lineage (R1-R10).
"""

from __future__ import annotations

import copy
from typing import Any

try:
    from .extractor import Evidence, memory_value, read_evidence
except ImportError:  # pragma: no cover - allow flat import
    from extractor import Evidence, memory_value, read_evidence


# --------------------------------------------------------------------------- #
# state construction helpers
# --------------------------------------------------------------------------- #


def _slot_phrase(slot: str) -> str:
    return slot.replace("_", " ")


def _prior_state(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    return copy.deepcopy(scenario.get("initial_memory_state", []))


def _new_id(scenario: dict[str, Any]) -> str:
    return f"{scenario['scenario_id'].lower()}-m2"


def _superseded_state(scenario: dict[str, Any], ev: Evidence, value: str) -> list[dict[str, Any]]:
    """Retain the prior record as superseded and add one active successor."""
    state = _prior_state(scenario)
    old = next(r for r in state if r.get("status") == "active")
    old["status"] = "superseded"
    new = {
        "id": _new_id(scenario),
        "type": old["type"],
        "text": f"{ev.slot} = {value}",
        "confidence": 0.95,
        "status": "active",
        "supersedes_id": old["id"],
        "valid_from": "session_2",
        "semantic_slot": ev.slot,
        "source": "direct_user_assertion",
    }
    state.append(new)
    return state


def _overwrite_state(scenario: dict[str, Any], ev: Evidence, value: str) -> list[dict[str, Any]]:
    """Destructive replace: no superseded record retained (b4 weakness)."""
    old = next(r for r in _prior_state(scenario) if r.get("status") == "active")
    return [
        {
            "id": old["id"],
            "type": old["type"],
            "text": f"{ev.slot} = {value}",
            "confidence": 0.95,
            "status": "active",
            "supersedes_id": None,
            "valid_from": "session_2",
            "semantic_slot": ev.slot,
            "source": "direct_user_assertion",
        }
    ]


def _keep_with_override(scenario: dict[str, Any], ev: Evidence, value: str) -> list[dict[str, Any]]:
    """Preserve the durable record; add the override as a transient_pref."""
    state = _prior_state(scenario)
    state.append(
        {
            "id": _new_id(scenario),
            "type": "transient_pref",
            "text": f"{ev.slot} = {value}",
            "confidence": 0.6,
            "status": "active",
            "supersedes_id": None,
            "valid_from": "session_2",
            "semantic_slot": ev.slot,
            "source": "direct_user_assertion",
        }
    )
    return state


# --------------------------------------------------------------------------- #
# answer construction
# --------------------------------------------------------------------------- #


def _durable_active_value(state: list[dict[str, Any]], slot: str) -> str | None:
    """Value the system would recall: active, same-slot, non-transient."""
    candidates = [
        r
        for r in state
        if isinstance(r, dict)
        and r.get("status") == "active"
        and r.get("semantic_slot") == slot
        and r.get("type") != "transient_pref"
    ]
    if not candidates:
        candidates = [
            r
            for r in state
            if isinstance(r, dict)
            and r.get("status") == "active"
            and r.get("semantic_slot") == slot
        ]
    return memory_value(candidates[0]["text"]) if candidates else None


def _answer(scenario: dict[str, Any], state: list[dict[str, Any]], slot: str) -> str:
    value = _durable_active_value(state, slot)
    if value is None:
        return "I do not have a stored value for that."
    phrase = _slot_phrase(slot)
    mode = scenario.get("query_mode")
    if mode == "premise_resistance":
        return f"No, that is not correct. The user's current {phrase} is {value}."
    if mode == "implicit_application":
        return f"Using the user's current {phrase}: {value}."
    return f"The user's current {phrase} is {value}."


def _pack(action: str, state: list[dict[str, Any]], answer: str, conf: float) -> dict[str, Any]:
    return {
        "predicted_action": action,
        "predicted_memory_state": state,
        "predicted_answer": answer,
        "confidence": round(conf, 3),
    }


# --------------------------------------------------------------------------- #
# systems
# --------------------------------------------------------------------------- #


def predict_b1(scenario: dict[str, Any]) -> dict[str, Any]:
    """No-memory sanity floor: no stored state, never commits, cannot answer."""
    return _pack("ABSTAIN", [], "I do not have any stored memory to answer from.", 0.0)


def predict_b2(scenario: dict[str, Any]) -> dict[str, Any]:
    """Flat retrieval, no write governance: state never changes; recall prior."""
    ev = read_evidence(scenario)
    if ev is None:
        return _pack("ABSTAIN", [], "I do not have a stored value for that.", 0.1)
    state = _prior_state(scenario)
    return _pack("KEEP", state, _answer(scenario, state, ev.slot), 0.5)


def predict_b3(scenario: dict[str, Any]) -> dict[str, Any]:
    """Recency: newest detected value always wins; timeline retained; no abstain."""
    ev = read_evidence(scenario)
    if ev is None:
        return _pack("ABSTAIN", [], "I do not have a stored value for that.", 0.1)
    if ev.candidate_conflicts:
        state = _superseded_state(scenario, ev, ev.candidate_value)
        return _pack("SUPERSEDE", state, _answer(scenario, state, ev.slot), 0.6)
    state = _prior_state(scenario)
    return _pack("KEEP", state, _answer(scenario, state, ev.slot), 0.5)


def predict_b4(scenario: dict[str, Any]) -> dict[str, Any]:
    """Naive overwrite: destructive replace on any contradiction; no lineage/abstain."""
    ev = read_evidence(scenario)
    if ev is None:
        return _pack("ABSTAIN", [], "I do not have a stored value for that.", 0.1)
    if ev.candidate_conflicts:
        state = _overwrite_state(scenario, ev, ev.candidate_value)
        return _pack("SUPERSEDE", state, _answer(scenario, state, ev.slot), 0.6)
    state = _prior_state(scenario)
    return _pack("KEEP", state, _answer(scenario, state, ev.slot), 0.5)


def predict_controller(scenario: dict[str, Any]) -> dict[str, Any]:
    """Rule-governed controller with an abstention safeguard and retained lineage."""
    ev = read_evidence(scenario)
    if ev is None:
        return _pack("ABSTAIN", [], "I do not have a stored value for that.", 0.1)

    # R1/R7: reject unattributed, laundered, garbled or unconfirmed evidence.
    if ev.third_party_unattributed or ev.laundered_or_noisy:
        state = _prior_state(scenario)
        return _pack("ABSTAIN", state, _answer(scenario, state, ev.slot), 0.8)

    # R6: a hedged temporary candidate abstains.
    if ev.temporary_hedged:
        state = _prior_state(scenario)
        return _pack("ABSTAIN", state, _answer(scenario, state, ev.slot), 0.7)

    # R6: a clear temporary override keeps durable memory (+ transient note).
    if ev.temporary_clear:
        if ev.has_candidate:
            state = _keep_with_override(scenario, ev, ev.candidate_value)
        else:
            state = _prior_state(scenario)
        return _pack("KEEP", state, _answer(scenario, state, ev.slot), 0.75)

    # R5: a reliable durable same-slot contradiction supersedes with lineage.
    if ev.candidate_conflicts:
        state = _superseded_state(scenario, ev, ev.candidate_value)
        return _pack("SUPERSEDE", state, _answer(scenario, state, ev.slot), 0.85)

    # R1: no usable durable evidence -> abstain (conservative safeguard).
    state = _prior_state(scenario)
    return _pack("ABSTAIN", state, _answer(scenario, state, ev.slot), 0.4)


SYSTEMS: dict[str, Any] = {
    "b1": predict_b1,
    "b2": predict_b2,
    "b3": predict_b3,
    "b4": predict_b4,
    "controller": predict_controller,
}

SYSTEM_LABELS = {
    "b1": "B1 no-memory (floor)",
    "b2": "B2 flat retrieval",
    "b3": "B3 recency",
    "b4": "B4 naive overwrite",
    "controller": "Controller (governed)",
}
