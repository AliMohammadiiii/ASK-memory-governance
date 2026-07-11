"""LongMemEval loader, session model, and stratified slicer.

Handles the full LongMemEval release family — LongMemEval-S (~115k-token
haystacks), LongMemEval-M (~500-session haystacks), and the Oracle split — at
any slice size, including the full 500-question set used for the final
thesis runs (M4-W13 §3.5). The same code path serves the original 50-session
dev slice (M1-W1 §3.1) and the 500-question scale-up; only the requested ``n``
changes.

Two on-disk shapes are accepted transparently:

  * **JSONL** (one JSON object per line) — the streaming fast path; memory use
    is bounded by the single largest record, so LongMemEval-M is safe here.
  * **JSON array** (the shape shipped on Hugging Face) — read lazily with
    ``ijson`` when it is installed, otherwise eagerly via ``json.load`` with a
    one-time warning. For LongMemEval-M, convert once to JSONL with
    ``convert_to_jsonl()`` (or ``build_slice.py``) so every later run streams.

One record per question, with the (cleaned) schema:

    {
      "session_id": "lme-s-00012",
      "turns": [
        {"role": "user",      "content": "...",  "timestamp": "2024-09-12T08:14:33Z"},
        {"role": "assistant", "content": "...",  "timestamp": "..."},
        ...
      ],
      "question": "What did I say I prefer for breakfast?",
      "gold_answer": "tea with no sugar",
      "competency": "knowledge-update",
      "supporting_session_ids": ["lme-s-00007", "lme-s-00012"]
    }

If the user has the released file in a slightly different shape (e.g. an
outer JSON array, or with `dialog`/`conversation` instead of `turns`), the
loader normalizes those variants. Any unknown shape raises with the
offending line number.

Note: The full file is not redistributable; researchers register at the
LongMemEval release page and place the file at the path passed to
`load_longmemeval_s()`. This module is expected to operate on that path.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# The seven LongMemEval competency labels. Source: Wu et al. (2025) §3.
LONGMEMEVAL_COMPETENCIES: tuple[str, ...] = (
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
    "multi-session",
    "knowledge-update",
    "temporal-reasoning",
    "abstention",
)

# Floors enforced by the stratified slicer (§3.1 mapping note §3).
# These ensure Supersede and Abstain are exercised by the dev slice.
_DEFAULT_FLOORS: dict[str, int] = {
    "knowledge-update": 5,
    "abstention": 5,
}

# Canonical alias map for the small formatting variants seen across LongMemEval
# releases / mirrors (underscores vs hyphens, casing). This keeps a single odd
# label from aborting an otherwise-good full 500-question or LongMemEval-M load
# at record #347, while still rejecting genuinely unknown competencies with the
# offending line number. Semantics are never remapped — only formatting.
_COMPETENCY_ALIASES: dict[str, str] = {
    "single_session_user": "single-session-user",
    "single_session_assistant": "single-session-assistant",
    "single_session_preference": "single-session-preference",
    "multi_session": "multi-session",
    "knowledge_update": "knowledge-update",
    "temporal_reasoning": "temporal-reasoning",
}


def canonical_competency(raw: str) -> str:
    """Normalize a release's competency string to the canonical hyphenated label.

    Tolerant of casing, surrounding whitespace, and underscore-vs-hyphen, all of
    which appear across LongMemEval mirrors. Unknown labels are returned
    unchanged so the dataclass validator can raise with the offending line.
    """
    key = raw.strip().lower().replace(" ", "-")
    if key in LONGMEMEVAL_COMPETENCIES:
        return key
    key = key.replace("_", "-")
    return _COMPETENCY_ALIASES.get(raw.strip().lower(), key)


# --------------------------------------------------------------------- #
# Dataclasses                                                            #
# --------------------------------------------------------------------- #


@dataclass(frozen=True)
class LongMemEvalTurn:
    role: str  # "user" | "assistant" (others rejected)
    content: str
    timestamp: str | None = None  # ISO-8601 if present in the source

    def to_dict(self) -> dict:
        d: dict = {"role": self.role, "content": self.content}
        if self.timestamp is not None:
            d["timestamp"] = self.timestamp
        return d


@dataclass(frozen=True)
class LongMemEvalCorpusSession:
    """One haystack session attached to a cleaned LongMemEval QA item."""

    session_id: str
    turns: tuple[LongMemEvalTurn, ...]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "turns": [t.to_dict() for t in self.turns],
        }


@dataclass(frozen=True)
class LongMemEvalSession:
    session_id: str
    turns: tuple[LongMemEvalTurn, ...]
    question: str
    gold_answer: str
    competency: str
    supporting_session_ids: tuple[str, ...] = field(default_factory=tuple)
    corpus_sessions: tuple[LongMemEvalCorpusSession, ...] = field(default_factory=tuple)
    question_date: str | None = None

    def __post_init__(self) -> None:
        if self.competency not in LONGMEMEVAL_COMPETENCIES:
            raise ValueError(
                f"unknown competency {self.competency!r}; expected one of "
                f"{LONGMEMEVAL_COMPETENCIES}"
            )
        for t in self.turns:
            if t.role not in ("user", "assistant"):
                raise ValueError(f"unknown turn role {t.role!r}")
        for session in self.corpus_sessions:
            for t in session.turns:
                if t.role not in ("user", "assistant"):
                    raise ValueError(f"unknown turn role {t.role!r}")

    def to_dict(self) -> dict:
        out = {
            "session_id": self.session_id,
            "turns": [t.to_dict() for t in self.turns],
            "question": self.question,
            "gold_answer": self.gold_answer,
            "competency": self.competency,
            "supporting_session_ids": list(self.supporting_session_ids),
        }
        if self.corpus_sessions:
            out["corpus_sessions"] = [s.to_dict() for s in self.corpus_sessions]
        if self.question_date is not None:
            out["question_date"] = self.question_date
        return out


def memory_session_ids(session: LongMemEvalSession) -> tuple[str, ...]:
    """Return session IDs that memory systems may index for this question.

    The cleaned LongMemEval release includes two different ID sets:

    * ``answer_session_ids``: gold evidence labels, exposed here as
      ``supporting_session_ids`` for evaluator/audit joins.
    * ``haystack_session_ids``: the actual memory corpus the system is allowed
      to search, exposed as ``corpus_sessions``.

    Memory baselines must not use gold evidence IDs to pre-filter retrieval on
    cleaned records. When attached haystack sessions are present, they are the
    source of truth for index construction. Legacy JSONL fixtures do not carry
    ``corpus_sessions``, so they retain the original ``supporting_session_ids``
    behavior.
    """
    if session.corpus_sessions:
        raw_ids = [s.session_id for s in session.corpus_sessions]
    else:
        raw_ids = list(session.supporting_session_ids)

    out: list[str] = []
    seen: set[str] = set()
    for sid in raw_ids:
        if sid == session.session_id or sid in seen:
            continue
        out.append(sid)
        seen.add(sid)
    return tuple(out)


# --------------------------------------------------------------------- #
# Loader                                                                 #
# --------------------------------------------------------------------- #


def _normalize_turn(raw: dict, *, default_timestamp: str | None = None) -> LongMemEvalTurn:
    role = _first_present(raw, ("role", "speaker", "from"))
    content = _first_present(raw, ("content", "text", "utterance"))
    timestamp_raw = _first_present(raw, ("timestamp", "ts", "time"))
    timestamp = str(timestamp_raw) if timestamp_raw is not None else default_timestamp
    if role is None or content is None:
        raise ValueError(f"turn missing role/content: {raw!r}")
    return LongMemEvalTurn(role=str(role), content=str(content), timestamp=timestamp)


def _first_present(raw: dict, keys: tuple[str, ...]) -> object | None:
    for key in keys:
        if key in raw:
            return raw[key]
    return None


def _normalize_corpus_session(raw: dict, line_no: int) -> LongMemEvalCorpusSession:
    try:
        session_id = str(raw["session_id"])
        turns_raw = _first_present(raw, ("turns", "dialog", "conversation", "messages"))
        if not isinstance(turns_raw, (list, tuple)):
            raise TypeError("turns must be a list or tuple")
        turns = tuple(_normalize_turn(turn) for turn in turns_raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"line {line_no}: malformed corpus session ({exc})") from exc
    return LongMemEvalCorpusSession(session_id=session_id, turns=turns)


def _normalize_cleaned_record(raw: dict, line_no: int) -> LongMemEvalSession:
    """Normalize the public `longmemeval-cleaned` QA schema.

    The cleaned release stores each evaluated question as one object containing
    `haystack_session_ids` and parallel `haystack_sessions`. There is no
    separate current dialogue session for the question itself, so `turns` is
    intentionally empty and the haystack sessions are attached as
    `corpus_sessions` for retrieval/controller baselines.
    """
    try:
        session_id = str(raw["question_id"])
        competency = canonical_competency(str(raw["question_type"]))
        question = str(raw["question"])
        question_date = (
            str(raw["question_date"])
            if raw.get("question_date") is not None
            else None
        )
        gold_answer = str(raw["answer"])
        supporting = tuple(str(sid) for sid in raw.get("answer_session_ids") or ())
        haystack_ids = [str(sid) for sid in raw.get("haystack_session_ids") or ()]
        haystack_dates = list(raw.get("haystack_dates") or ())
        haystack_sessions = list(raw.get("haystack_sessions") or ())
        if len(haystack_ids) != len(haystack_sessions):
            raise ValueError(
                "haystack_session_ids and haystack_sessions have different lengths "
                f"({len(haystack_ids)} != {len(haystack_sessions)})"
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"line {line_no}: malformed cleaned LongMemEval record ({exc})") from exc

    corpus_sessions = []
    for idx, (support_id, turns_raw) in enumerate(zip(haystack_ids, haystack_sessions)):
        default_timestamp = str(haystack_dates[idx]) if idx < len(haystack_dates) else None
        turns = tuple(
            _normalize_turn(turn, default_timestamp=default_timestamp)
            for turn in turns_raw
        )
        corpus_sessions.append(LongMemEvalCorpusSession(session_id=support_id, turns=turns))

    return LongMemEvalSession(
        session_id=session_id,
        turns=(),
        question=question,
        gold_answer=gold_answer,
        competency=competency,
        supporting_session_ids=supporting,
        corpus_sessions=tuple(corpus_sessions),
        question_date=question_date,
    )


def _normalize_record(raw: dict, line_no: int) -> LongMemEvalSession:
    """Convert a single JSON record into a `LongMemEvalSession`.

    Tolerates `turns` / `dialog` / `conversation` and the documented top-level
    keys. Raises ValueError with the offending line number on shape mismatch.
    """
    if {"question_id", "haystack_sessions", "question_type"}.issubset(raw):
        return _normalize_cleaned_record(raw, line_no)

    try:
        session_id = str(raw["session_id"]) if "session_id" in raw else str(raw["id"])
        turns_raw = _first_present(raw, ("turns", "dialog", "conversation", "messages"))
        if not isinstance(turns_raw, (list, tuple)):
            raise TypeError("turns must be a list or tuple")
        turns = tuple(_normalize_turn(t) for t in turns_raw)
        question = str(raw["question"]) if "question" in raw else str(raw["query"])
        question_date = (
            str(raw["question_date"])
            if raw.get("question_date") is not None
            else None
        )
        gold_answer = str(
            raw.get("gold_answer") or raw.get("answer") or raw.get("gold")
        )
        competency = canonical_competency(str(
            raw.get("competency")
            or raw.get("category")
            or raw.get("question_type")
        ))
        supporting = raw.get("supporting_session_ids") or raw.get("evidence_sessions") or ()
        supporting_tuple = tuple(str(s) for s in supporting)
        corpus_sessions = tuple(
            _normalize_corpus_session(s, line_no)
            for s in raw.get("corpus_sessions", ())
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"line {line_no}: malformed LongMemEval record ({exc})") from exc

    return LongMemEvalSession(
        session_id=session_id,
        turns=turns,
        question=question,
        gold_answer=gold_answer,
        competency=competency,
        supporting_session_ids=supporting_tuple,
        corpus_sessions=corpus_sessions,
        question_date=question_date,
    )


def _sniff_is_json_array(path: Path) -> bool:
    """True if the first non-whitespace byte of ``path`` is ``[`` (JSON array)."""
    with path.open("r", encoding="utf-8") as fh:
        while True:
            ch = fh.read(1)
            if ch == "":
                return False  # empty file → treat as (empty) JSONL
            if not ch.isspace():
                return ch == "["


def _iter_json_array(path: Path) -> Iterator[LongMemEvalSession]:
    """Yield records from a top-level JSON array.

    Uses ``ijson`` to stream items one at a time when it is installed, so a
    multi-gigabyte LongMemEval-M array never has to be fully materialized. Falls
    back to ``json.load`` (whole file in RAM) with a one-time stderr warning when
    ``ijson`` is unavailable.
    """
    try:
        import ijson  # type: ignore
    except ModuleNotFoundError:
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > 64:
            print(
                f"[longmemeval] WARNING: reading a {size_mb:.0f} MB JSON array "
                f"eagerly ({path}); install 'ijson' or run convert_to_jsonl() "
                "first to stream LongMemEval-M without loading it all into RAM.",
                file=sys.stderr,
                flush=True,
            )
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            raise ValueError("expected a top-level JSON array or JSONL")
        for i, raw in enumerate(data, start=1):
            yield _normalize_record(raw, line_no=i)
        return

    with path.open("rb") as fh:
        for i, raw in enumerate(ijson.items(fh, "item"), start=1):
            yield _normalize_record(raw, line_no=i)


def iter_longmemeval_s(path: str | Path) -> Iterator[LongMemEvalSession]:
    """Stream LongMemEval records (S or M), one per yielded session.

    JSONL inputs are streamed line by line. JSON-array inputs are streamed with
    ``ijson`` when available (see ``_iter_json_array``). Memory use is bounded by
    the single largest record, so LongMemEval-M is safe via the JSONL path.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"LongMemEval file not found: {p}")

    if _sniff_is_json_array(p):
        yield from _iter_json_array(p)
        return

    # JSONL fast path.
    with p.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            yield _normalize_record(raw, line_no=line_no)


def load_longmemeval_s(path: str | Path) -> Iterator[LongMemEvalSession]:
    """Public alias for `iter_longmemeval_s`. Returns a fresh iterator each call."""
    return iter_longmemeval_s(path)


# Release-agnostic aliases (S / M / Oracle all share this loader).
iter_longmemeval = iter_longmemeval_s
load_longmemeval = load_longmemeval_s


def convert_to_jsonl(src: str | Path, dst: str | Path) -> int:
    """Convert a LongMemEval JSON-array release to streaming JSONL (one record/line).

    Run this once on the large LongMemEval-M array so every later loader call
    takes the memory-light JSONL fast path. Returns the number of records
    written. Records are normalized + re-serialized so the output matches what
    the loader produces for a slice.
    """
    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with dst_path.open("w", encoding="utf-8") as out:
        for session in iter_longmemeval_s(src):
            out.write(json.dumps(session.to_dict(), sort_keys=True, ensure_ascii=False))
            out.write("\n")
            n += 1
    return n


# --------------------------------------------------------------------- #
# Slicer                                                                 #
# --------------------------------------------------------------------- #


def sample_slice(
    sessions: Iterable[LongMemEvalSession],
    n: int = 50,
    seed: int = 0,
    stratify_by: str = "competency",
    floors: dict[str, int] | None = None,
) -> list[LongMemEvalSession]:
    """Deterministic stratified sample.

    For `stratify_by="competency"`:
      1. Group sessions by competency.
      2. Apply `floors` (defaults to `_DEFAULT_FLOORS`) — sample at least the
         floor count from each named competency, drawing without replacement.
      3. Allocate the remaining slots proportionally to bucket size, using the
         largest-remainder method (deterministic).
      4. If a bucket cannot satisfy its allotment, redistribute the deficit
         to other buckets in deterministic order.
      5. Sort the final slice by `session_id` so the JSONL artifact is
         byte-stable across runs with the same seed.

    `seed` controls *within-bucket* shuffling only — not the cross-bucket
    allocation, which is purely deterministic.
    """
    if stratify_by != "competency":
        raise NotImplementedError(f"stratify_by={stratify_by!r} not supported")

    pool = list(sessions)
    if n <= 0:
        return []
    if n == len(pool):
        # Full-set request (e.g. n=500 on the 500-question release): return the
        # whole pool, deterministically ordered. Short-circuiting here avoids any
        # largest-remainder rounding edge case when the quota equals the pool and
        # makes "build the full set" a first-class, exact operation.
        return sorted(pool, key=lambda s: s.session_id)
    if n > len(pool):
        raise ValueError(f"requested n={n} but only {len(pool)} sessions available")

    floors = dict(floors) if floors is not None else dict(_DEFAULT_FLOORS)

    # Bucket by competency.
    buckets: dict[str, list[LongMemEvalSession]] = defaultdict(list)
    for s in pool:
        buckets[s.competency].append(s)
    # Sort within each bucket so seed-controlled shuffle is reproducible
    # regardless of input order.
    for k in buckets:
        buckets[k].sort(key=lambda s: s.session_id)

    # Within-bucket deterministic shuffle.
    rng = random.Random(seed)
    for k in sorted(buckets.keys()):
        rng_local = random.Random(_hash_seed(seed, k))
        rng_local.shuffle(buckets[k])
    del rng  # not used after this; the per-bucket RNG above is what matters

    # Apply floors (capped by bucket size).
    quotas: dict[str, int] = {k: 0 for k in buckets}
    remaining = n
    for k, floor in floors.items():
        if k not in buckets:
            continue
        take = min(floor, len(buckets[k]), remaining)
        quotas[k] = take
        remaining -= take

    # Largest-remainder allocation of the leftover slots, in proportion to
    # bucket sizes (excluding the floor we already took).
    if remaining > 0:
        residual_pool = {k: max(0, len(b) - quotas[k]) for k, b in buckets.items()}
        total = sum(residual_pool.values())
        if total == 0:
            raise ValueError("no residual sessions available to fill slice")
        # Initial floor allocation: integer share.
        shares: dict[str, float] = {
            k: remaining * (residual_pool[k] / total) for k in residual_pool
        }
        floor_alloc = {k: int(shares[k]) for k in shares}
        allocated = sum(floor_alloc.values())
        deficit = remaining - allocated
        # Distribute the deficit by largest fractional remainder, ties broken
        # by competency name (deterministic).
        remainders = sorted(
            ((shares[k] - floor_alloc[k], k) for k in shares),
            key=lambda x: (-x[0], x[1]),
        )
        for _, k in remainders[:deficit]:
            floor_alloc[k] += 1
        for k in floor_alloc:
            quotas[k] = quotas.get(k, 0) + floor_alloc[k]

    # Cap quotas at bucket size; redistribute any overflow.
    overflow = 0
    for k in list(quotas):
        cap = len(buckets[k])
        if quotas[k] > cap:
            overflow += quotas[k] - cap
            quotas[k] = cap
    if overflow > 0:
        # Hand overflow to buckets with capacity, in deterministic order.
        for k in sorted(buckets, key=lambda c: (-len(buckets[c]), c)):
            cap_left = len(buckets[k]) - quotas[k]
            if cap_left <= 0:
                continue
            take = min(cap_left, overflow)
            quotas[k] += take
            overflow -= take
            if overflow == 0:
                break
    if overflow > 0:
        raise ValueError(
            "cannot fit n sessions across buckets with given floors and pool sizes"
        )

    # Materialize the slice.
    selected: list[LongMemEvalSession] = []
    for k in sorted(buckets):
        selected.extend(buckets[k][: quotas[k]])

    # Final sort for byte-stable JSONL output.
    selected.sort(key=lambda s: s.session_id)
    return selected


def _hash_seed(seed: int, label: str) -> int:
    """Deterministic per-bucket seed: stable across runs, OS, Python version."""
    h = hashlib.blake2b(f"{seed}:{label}".encode(), digest_size=8).digest()
    return int.from_bytes(h, "big")


def write_slice_jsonl(
    sessions: Sequence[LongMemEvalSession],
    out_path: str | Path,
) -> Path:
    """Write a slice to JSONL with sorted keys (byte-stable) and a trailing newline."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        for s in sessions:
            fh.write(json.dumps(s.to_dict(), sort_keys=True, ensure_ascii=False))
            fh.write("\n")
    return p
