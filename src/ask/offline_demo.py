"""Deterministic provider-free walkthrough of ASK decisions and replay."""

from __future__ import annotations

import hashlib

from ask.baselines.embeddings import FakeEmbedder
from ask.baselines.flat_vector_store import FlatVectorStore
from ask.baselines.flat_vector_store import MemoryItem as RetrievalItem
from ask.memory.models import ControllerAction
from ask.protocol import (
    ASKMGPAdapter,
    CandidateRecord,
    ConfigurationIdentity,
    EvidenceReference,
    MemoryRecord,
    apply_transition,
    replay_transition,
)

_CONFIG = ConfigurationIdentity("offline-demo", "ask-mgp/v1", "a" * 64)


def run_case(
    label: str,
    *,
    model_action: ControllerAction,
    rule_action: ControllerAction,
    initial: tuple[MemoryRecord, ...],
    prior_id: str | None,
    candidate: CandidateRecord,
    evidence_references: tuple[EvidenceReference, ...],
) -> None:
    adapter = ASKMGPAdapter(_CONFIG)
    action, trace = adapter.decide(
        model_proposal=model_action,
        rule_proposal=rule_action,
        rule_verdict="explicit_fixture_decision",
        evidence_references=evidence_references,
        guard_rule_id="offline-demo/v1",
    )
    after, event = apply_transition(
        initial,
        action=action,
        store_mode=adapter.store_mode,
        prior_record_id=prior_id,
        candidate=candidate,
        trace=trace,
    )
    replayed_state, replayed_event = replay_transition(
        initial, event=event, candidate=candidate, trace=trace
    )
    assert adapter.replay(trace) is action
    assert replayed_state == after and replayed_event == event
    print(f"{label}: {action.value}; replay={adapter.replay(trace).value}")
    print(f"  event={event.event_id}; evidence={event.evidence_digest}")
    print(
        "  state="
        f"{[(record.record_id, record.value, record.active, record.predecessor) for record in after]}"
    )


def main() -> None:
    query = "profile update: now omnivore"
    store = FlatVectorStore(embedder=FakeEmbedder(embedding_dim=32))
    store.add(
        [
            RetrievalItem("profile update: still vegetarian", "user", "fixture", 0),
            RetrievalItem(query, "user", "fixture", 1),
        ]
    )
    retrieved = store.search(query, k=1)[0].item
    evidence_digest = hashlib.sha256(retrieved.embed_text().encode("utf-8")).hexdigest()
    evidence = (EvidenceReference(f"{retrieved.session_id}:{retrieved.turn_idx}", evidence_digest),)
    print(
        f"retrieval: {retrieved.session_id}:{retrieved.turn_idx} (deterministic fixture embedding)"
    )
    old = MemoryRecord("m1", "stable_pref", "vegetarian", evidence_digest="c" * 64)
    run_case(
        "KEEP",
        model_action=ControllerAction.KEEP,
        rule_action=ControllerAction.ABSTAIN,
        initial=(old,),
        prior_id="m1",
        candidate=CandidateRecord("m2", "stable_pref", "vegetarian", 0.9, evidence_digest),
        evidence_references=evidence,
    )
    run_case(
        "SUPERSEDE",
        model_action=ControllerAction.SUPERSEDE,
        rule_action=ControllerAction.ABSTAIN,
        initial=(old,),
        prior_id="m1",
        candidate=CandidateRecord("m2", "stable_pref", "omnivore", 0.9, evidence_digest),
        evidence_references=evidence,
    )
    run_case(
        "ABSTAIN",
        model_action=ControllerAction.ABSTAIN,
        rule_action=ControllerAction.ABSTAIN,
        initial=(old,),
        prior_id="m1",
        candidate=CandidateRecord("m2", "stable_pref", "omnivore", 0.4, evidence_digest),
        evidence_references=evidence,
    )


if __name__ == "__main__":
    main()
