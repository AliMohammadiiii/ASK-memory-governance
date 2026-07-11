"""LongMemEval-S loader and stratified slicer (M1-W1 §3.1).

Tests use a synthetic fixture that mimics the LongMemEval-S JSONL release
shape — the real file is gated behind registration and not redistributable.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import pytest

from ksa.baselines.flat_vector import build_session_corpus
from ksa.data.longmemeval import (
    LONGMEMEVAL_COMPETENCIES,
    LongMemEvalSession,
    iter_longmemeval_s,
    memory_session_ids,
    sample_slice,
    write_slice_jsonl,
)

# ----------------------------- fixtures ----------------------------- #


def _synth_session(idx: int, competency: str) -> dict:
    """Build a single LongMemEval-S-shaped record. Two-turn dialog by default."""
    return {
        "session_id": f"lme-s-{idx:05d}",
        "turns": [
            {
                "role": "user",
                "content": f"User utterance #{idx} in competency {competency}.",
                "timestamp": "2024-09-12T08:14:33Z",
            },
            {
                "role": "assistant",
                "content": f"Assistant reply #{idx}.",
                "timestamp": "2024-09-12T08:14:35Z",
            },
        ],
        "question": f"What was said in session {idx}?",
        "gold_answer": f"answer-{idx}",
        "competency": competency,
        "supporting_session_ids": [f"lme-s-{idx:05d}"],
    }


def _write_synth_jsonl(path: Path, n: int = 200) -> Path:
    """Make a 200-session fixture, ~28 per competency, deterministic."""
    rng = random.Random(1234)
    comps = list(LONGMEMEVAL_COMPETENCIES)
    # Roughly even distribution to start.
    records = []
    for i in range(n):
        comp = comps[i % len(comps)]
        records.append(_synth_session(i, comp))
    rng.shuffle(records)  # input order should not matter for the slicer
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return path


@pytest.fixture()
def synth_corpus(tmp_path: Path) -> Path:
    return _write_synth_jsonl(tmp_path / "longmemeval_synth.jsonl", n=200)


# ----------------------------- loader ------------------------------ #


def test_loader_streams_known_session_id_to_expected_competency(synth_corpus: Path) -> None:
    sessions = {s.session_id: s for s in iter_longmemeval_s(synth_corpus)}
    assert "lme-s-00007" in sessions
    # In the synth fixture, session i maps to competency i % 7. i=7 → index 0.
    assert sessions["lme-s-00007"].competency == LONGMEMEVAL_COMPETENCIES[0]
    assert sessions["lme-s-00013"].competency == LONGMEMEVAL_COMPETENCIES[6]
    # All seven competencies are reachable.
    seen = {s.competency for s in sessions.values()}
    assert seen == set(LONGMEMEVAL_COMPETENCIES)


def test_loader_streams_lazily_returns_session_dataclass(synth_corpus: Path) -> None:
    it = iter_longmemeval_s(synth_corpus)
    s = next(it)
    assert isinstance(s, LongMemEvalSession)
    assert s.competency in LONGMEMEVAL_COMPETENCIES
    assert all(t.role in ("user", "assistant") for t in s.turns)


def test_loader_handles_outer_array_variant(tmp_path: Path) -> None:
    p = tmp_path / "lm_array.json"
    records = [_synth_session(i, "abstention") for i in range(3)]
    p.write_text(json.dumps(records))
    out = list(iter_longmemeval_s(p))
    assert len(out) == 3
    assert all(s.competency == "abstention" for s in out)


def test_loader_rejects_unknown_competency(tmp_path: Path) -> None:
    p = tmp_path / "bad.jsonl"
    bad = _synth_session(0, "abstention")
    bad["competency"] = "not-a-real-category"
    p.write_text(json.dumps(bad) + "\n")
    with pytest.raises(ValueError):
        list(iter_longmemeval_s(p))


def test_loader_normalizes_alternative_keys(tmp_path: Path) -> None:
    """If a release variant uses `dialog`/`speaker`/`text`, the loader should still parse."""
    p = tmp_path / "alt.jsonl"
    rec = {
        "id": "lme-s-99999",
        "dialog": [
            {"speaker": "user", "text": "alt-shape utterance", "ts": "2024-01-01T00:00:00Z"}
        ],
        "query": "what?",
        "answer": "stuff",
        "category": "single-session-user",
    }
    p.write_text(json.dumps(rec) + "\n")
    out = list(iter_longmemeval_s(p))
    assert len(out) == 1
    assert out[0].session_id == "lme-s-99999"
    assert out[0].turns[0].content == "alt-shape utterance"


def test_loader_normalizes_cleaned_longmemeval_schema(tmp_path: Path) -> None:
    p = tmp_path / "longmemeval_s_cleaned.json"
    rec = {
        "question_id": "q-1",
        "question_type": "knowledge-update",
        "question": "What drink do I prefer now?",
        "question_date": "2023/05/30 (Tue) 23:40",
        "answer": "green tea",
        "answer_session_ids": ["answer-session"],
        "haystack_dates": ["2023/05/29 (Mon) 10:00", "2023/05/30 (Tue) 10:00"],
        "haystack_session_ids": ["distractor", "answer-session"],
        "haystack_sessions": [
            [{"role": "user", "content": "Please solve this puzzle."}],
            [{"role": "user", "content": "I now prefer green tea."}],
        ],
    }
    p.write_text(json.dumps([rec]), encoding="utf-8")

    out = list(iter_longmemeval_s(p))

    assert len(out) == 1
    session = out[0]
    assert session.session_id == "q-1"
    assert session.turns == ()
    assert session.gold_answer == "green tea"
    assert session.question_date == "2023/05/30 (Tue) 23:40"
    assert session.supporting_session_ids == ("answer-session",)
    assert memory_session_ids(session) == ("distractor", "answer-session")
    assert len(session.corpus_sessions) == 2
    assert session.corpus_sessions[1].turns[0].timestamp == "2023/05/30 (Tue) 10:00"


def test_slice_jsonl_round_trips_cleaned_corpus_sessions(tmp_path: Path) -> None:
    p = tmp_path / "cleaned.json"
    rec = {
        "question_id": "q-1",
        "question_type": "single-session-user",
        "question": "What degree did I graduate with?",
        "question_date": "2023/05/31 (Wed) 12:00",
        "answer": "Business Administration",
        "answer_session_ids": ["answer-session"],
        "haystack_dates": ["2023/05/30 (Tue) 10:00"],
        "haystack_session_ids": ["answer-session"],
        "haystack_sessions": [[{"role": "user", "content": "I graduated with Business Administration."}]],
    }
    p.write_text(json.dumps([rec]), encoding="utf-8")
    source = list(iter_longmemeval_s(p))
    out_path = tmp_path / "slice.jsonl"
    write_slice_jsonl(source, out_path)

    reparsed = list(iter_longmemeval_s(out_path))
    corpus = build_session_corpus(reparsed)

    assert reparsed[0].corpus_sessions[0].session_id == "answer-session"
    assert reparsed[0].question_date == "2023/05/31 (Wed) 12:00"
    assert "answer-session" in corpus
    assert corpus["answer-session"].turns[0].content == "I graduated with Business Administration."


# ------------------------------ slicer ----------------------------- #


def test_slice_returns_exactly_50_with_seed_zero(synth_corpus: Path) -> None:
    sessions = list(iter_longmemeval_s(synth_corpus))
    sliced = sample_slice(sessions, n=50, seed=0, stratify_by="competency")
    assert len(sliced) == 50


def test_slice_covers_at_least_five_distinct_competencies(synth_corpus: Path) -> None:
    sessions = list(iter_longmemeval_s(synth_corpus))
    sliced = sample_slice(sessions, n=50, seed=0)
    competencies = {s.competency for s in sliced}
    assert len(competencies) >= 5
    # Strong floor: knowledge-update and abstention each ≥ 5 (the mapping note's stipulation).
    counts: dict[str, int] = {}
    for s in sliced:
        counts[s.competency] = counts.get(s.competency, 0) + 1
    assert counts.get("knowledge-update", 0) >= 5
    assert counts.get("abstention", 0) >= 5


def test_slice_is_deterministic_under_fixed_seed(synth_corpus: Path) -> None:
    s1 = sample_slice(list(iter_longmemeval_s(synth_corpus)), n=50, seed=0)
    s2 = sample_slice(list(iter_longmemeval_s(synth_corpus)), n=50, seed=0)
    assert [s.session_id for s in s1] == [s.session_id for s in s2]


def test_slice_changes_with_seed(synth_corpus: Path) -> None:
    s_seed0 = sample_slice(list(iter_longmemeval_s(synth_corpus)), n=50, seed=0)
    s_seed1 = sample_slice(list(iter_longmemeval_s(synth_corpus)), n=50, seed=1)
    # The size of the intersection should be < 50 (otherwise the seed has no effect).
    overlap = set(s.session_id for s in s_seed0) & set(s.session_id for s in s_seed1)
    assert len(overlap) < 50


def test_slice_jsonl_is_byte_stable(synth_corpus: Path, tmp_path: Path) -> None:
    sessions = list(iter_longmemeval_s(synth_corpus))
    out_a = tmp_path / "a.jsonl"
    out_b = tmp_path / "b.jsonl"
    sliced = sample_slice(sessions, n=50, seed=0)
    write_slice_jsonl(sliced, out_a)
    # Re-slice from scratch, write again.
    sliced2 = sample_slice(list(iter_longmemeval_s(synth_corpus)), n=50, seed=0)
    write_slice_jsonl(sliced2, out_b)
    digest_a = hashlib.sha256(out_a.read_bytes()).hexdigest()
    digest_b = hashlib.sha256(out_b.read_bytes()).hexdigest()
    assert digest_a == digest_b


def test_slice_raises_on_oversize_request(synth_corpus: Path) -> None:
    sessions = list(iter_longmemeval_s(synth_corpus))
    with pytest.raises(ValueError):
        sample_slice(sessions, n=10_000, seed=0)
