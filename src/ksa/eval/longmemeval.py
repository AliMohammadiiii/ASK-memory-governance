"""LongMemEval-S grader, evaluator driver, and per-competency report (M1-W2 §3.2).

This module is *baseline-agnostic*: the same evaluator runs every later
baseline + the eventual KSA controller (Month 4). Bugs introduced here
propagate to every result in Chapter 4 of the thesis — hence the explicit
test for bootstrap-CI agreement with the analytical Wilson interval and the
explicit cache contract.

Three public entry points:

  * `LongMemEvalGrader(judge_llm).grade(answer, session) -> GradeResult`
  * `evaluate_baseline(baseline, sessions, grader) -> EvalReport`
  * `bootstrap_accuracy_ci(corrects, n_resamples, seed) -> (lo, hi)`

Persistence:
  * The grader caches judge calls by `sha256(judge_prompt)` so a re-run after
    a code-only change finishes in seconds. Cache file is per-run-dir.
  * Raw judgments (correctness + judge rationale) are persisted to
    `judgments.jsonl` so qualitative analysis in Chapter 4 quotes the actual
    judge text, not a summary.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import random
import re
import statistics
import time
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ksa.baselines.base import BaselineAnswer
from ksa.data.longmemeval import LongMemEvalSession
from ksa.inference.llm import LLM

# --------------------------------------------------------------------- #
# Judge prompt                                                           #
# --------------------------------------------------------------------- #

# LongMemEval-style binary correctness rubric. The structure is the published
# template's substance — generous on paraphrase, strict on contradicted /
# fabricated content — re-implemented in our own words so no copyright is
# implicated. The judge's emitted JSON is parsed by `_parse_judge_output`.
#
# IMPORTANT: changing this string changes the cache key automatically because
# the full rendered prompt is hashed. No manual cache-bust needed.
_JUDGE_PROMPT_TEMPLATE = """You are an evaluator for a long-term-memory chat-assistant benchmark.

Compare the predicted answer to the gold answer. Be GENEROUS about
paraphrase, formatting, capitalization, and unit conventions. Be STRICT
about content: a prediction that contradicts the gold, fabricates a
specific value not in the gold, or returns the OLD value when the gold
is a knowledge update is INCORRECT.

For abstention questions (where the gold answer indicates the assistant
should refuse to answer), a prediction that declines, says it does not
know, or otherwise refuses to commit to a fact is CORRECT. A prediction
that fabricates a confident answer is INCORRECT.

Output a single JSON object on one line, nothing else, with these keys:
  - "correct": boolean (true if the prediction is correct, else false)
  - "rationale": string (one short sentence explaining your decision)

Question competency: {competency}
Question: {question}
Gold answer: {gold_answer}
Predicted answer: {predicted_answer}

JSON:"""


def _render_judge_prompt(
    *, competency: str, question: str, gold_answer: str, predicted_answer: str
) -> str:
    return _JUDGE_PROMPT_TEMPLATE.format(
        competency=competency,
        question=question,
        gold_answer=gold_answer,
        predicted_answer=predicted_answer,
    )


# --------------------------------------------------------------------- #
# Result types                                                           #
# --------------------------------------------------------------------- #


@dataclass(frozen=True)
class GradeResult:
    """One graded answer."""

    session_id: str
    competency: str
    correct: bool
    judge_score: float  # binary in Week 2; reserved float for partial-credit
    judge_rationale: str
    judge_model_id: str
    # Echo of the answer text + gold for downstream qualitative analysis.
    predicted: str
    gold: str
    # Echo of the underlying LLM telemetry for the per-competency token /
    # latency rollup. None if the answer didn't carry it.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    # M1-W2 hotfix: when the LLM judge emits empty/unparseable text,
    # `normalized_substring_grade` decides correctness. This flag makes
    # every fallback-routed grade auditable for Chapter 4 qualitative
    # analysis. False on grades where the LLM judge produced a parseable
    # JSON output.
    used_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class CompetencyRow:
    """One row of the per-competency results table."""

    competency: str
    n: int
    accuracy: float
    accuracy_ci_low: float
    accuracy_ci_high: float
    mean_prompt_tokens: float
    mean_latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class EvalReport:
    """Container for the run-level results table + raw per-session grades."""

    baseline_name: str
    judge_model_id: str
    n_sessions: int
    overall_accuracy: float
    overall_ci_low: float
    overall_ci_high: float
    rows: list[CompetencyRow] = field(default_factory=list)
    grades: list[GradeResult] = field(default_factory=list)
    # Abstention decomposition (docx §7.1): the headline accuracy is inflated by
    # "free" abstention points a no-memory system passes trivially. Reporting
    # answerable-only accuracy alongside overall removes that artifact. These are
    # 0/0.0 on an empty report and always derivable from `grades`.
    answerable_n: int = 0
    answerable_accuracy: float = 0.0
    abstention_n: int = 0
    abstention_accuracy: float = 0.0
    # Count of non-empty answers with no alphanumeric content (truncation
    # artifacts like a bare "$"); a nonzero value flags a data-quality bug, not a
    # memory-quality signal (docx §8 / §9).
    n_degenerate_answers: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_name": self.baseline_name,
            "judge_model_id": self.judge_model_id,
            "n_sessions": self.n_sessions,
            "overall_accuracy": self.overall_accuracy,
            "overall_ci_low": self.overall_ci_low,
            "overall_ci_high": self.overall_ci_high,
            "answerable_n": self.answerable_n,
            "answerable_accuracy": self.answerable_accuracy,
            "abstention_n": self.abstention_n,
            "abstention_accuracy": self.abstention_accuracy,
            "n_degenerate_answers": self.n_degenerate_answers,
            "rows": [r.to_dict() for r in self.rows],
        }

    def summarize_markdown(self, *, ci_decimals: int = 1) -> str:
        """Render the per-competency table as a markdown table.

        Used by `scripts/print_report.py` to write `NOTES/m1w2_results.md`.
        """
        lines = [
            f"# Baseline `{self.baseline_name}` — LongMemEval results",
            "",
            f"- **Judge:** `{self.judge_model_id}`",
            f"- **N sessions:** {self.n_sessions}",
            f"- **Overall accuracy:** {self.overall_accuracy * 100:.{ci_decimals}f}% "
            f"(95% CI: {self.overall_ci_low * 100:.{ci_decimals}f} – "
            f"{self.overall_ci_high * 100:.{ci_decimals}f})",
            f"- **Answerable-only accuracy:** "
            f"{self.answerable_accuracy * 100:.{ci_decimals}f}% "
            f"({self.answerable_n} answerable; abstention "
            f"{self.abstention_accuracy * 100:.{ci_decimals}f}% of {self.abstention_n})",
        ]
        if self.n_degenerate_answers:
            lines.append(
                f"- **⚠ Degenerate answers:** {self.n_degenerate_answers} "
                "(non-empty but no alphanumeric content — likely truncation)"
            )
        lines += [
            "",
            "| Competency | n | Accuracy | 95% CI | Avg prompt tokens | Avg latency (ms) |",
            "|---|---:|---:|---|---:|---:|",
        ]
        for r in self.rows:
            ci = (
                f"{r.accuracy_ci_low * 100:.{ci_decimals}f} – "
                f"{r.accuracy_ci_high * 100:.{ci_decimals}f}"
            )
            n_marker = "" if r.n >= 5 else " [n<5: CI unreliable]"
            lines.append(
                f"| {r.competency} | {r.n} | "
                f"{r.accuracy * 100:.{ci_decimals}f}%{n_marker} | "
                f"{ci} | {r.mean_prompt_tokens:.0f} | {r.mean_latency_ms:.0f} |"
            )
        return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- #
# Bootstrap CI                                                           #
# --------------------------------------------------------------------- #


def bootstrap_accuracy_ci(
    corrects: list[bool] | list[int],
    *,
    n_resamples: int = 1000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentile-bootstrap 95% CI on the mean of a boolean array.

    For an empty input, returns (0.0, 0.0). For a one-element input the CI
    collapses to (x, x). The seed makes the bootstrap deterministic — that's
    the same property we commit to using in Month 4 (proposal §I.7.2).
    """
    n = len(corrects)
    if n == 0:
        return (0.0, 0.0)
    arr = [int(bool(c)) for c in corrects]
    if n == 1:
        return (float(arr[0]), float(arr[0]))
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_resamples):
        s = 0
        for _i in range(n):
            s += arr[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo_idx = int(math.floor((alpha / 2) * n_resamples))
    hi_idx = int(math.ceil((1 - alpha / 2) * n_resamples)) - 1
    lo_idx = max(0, min(lo_idx, n_resamples - 1))
    hi_idx = max(0, min(hi_idx, n_resamples - 1))
    return (means[lo_idx], means[hi_idx])


def _wilson_interval(p: float, n: int, *, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval — used as the analytical reference in tests."""
    if n == 0:
        return (0.0, 0.0)
    denom = 1.0 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return ((centre - margin) / denom, (centre + margin) / denom)


# --------------------------------------------------------------------- #
# Grader                                                                 #
# --------------------------------------------------------------------- #


class _NullCache:
    def get(self, _key: str) -> dict | None:
        return None

    def put(self, _key: str, _value: dict) -> None:
        pass


class JudgmentCache:
    """Append-only on-disk cache of `(prompt_hash, judge_model_id) → response`.

    Loaded eagerly at __init__ so re-runs are fast. Writes are synchronous to
    survive a crash mid-run.
    """

    def __init__(self, path: Path | None) -> None:
        self.path = Path(path) if path else None
        self._mem: dict[str, dict] = {}
        if self.path and self.path.exists():
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        self._mem[rec["key"]] = rec["value"]
                    except (json.JSONDecodeError, KeyError):
                        # tolerate a single corrupted line; subsequent runs
                        # will overwrite it on a hit.
                        continue

    @staticmethod
    def make_key(prompt: str, judge_model_id: str) -> str:
        h = hashlib.sha256()
        h.update(judge_model_id.encode("utf-8"))
        h.update(b"\x00")
        h.update(prompt.encode("utf-8"))
        return h.hexdigest()

    def get(self, key: str) -> dict | None:
        return self._mem.get(key)

    def put(self, key: str, value: dict) -> None:
        self._mem[key] = value
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"key": key, "value": value}, sort_keys=True))
                fh.write("\n")


def _parse_judge_output(text: str) -> tuple[bool, str]:
    """Best-effort JSON parse → (correct, rationale).

    Tolerant: extracts the first {...} block, accepts string-ified booleans
    ("true"/"false"/"1"/"0"), falls back to a heuristic if no JSON is found.
    """
    # Try a fenced block first.
    fragment = text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        fragment = text[start : end + 1]
    try:
        obj = json.loads(fragment)
    except json.JSONDecodeError:
        # Heuristic fallback: any "correct: true|false" anywhere.
        lower = text.lower()
        if '"correct":true' in lower.replace(" ", "") or "'correct':true" in lower.replace(" ", ""):
            return True, "[parse-fallback] judge output not JSON; matched correct=true"
        if '"correct":false' in lower.replace(" ", "") or "'correct':false" in lower.replace(" ", ""):
            return False, "[parse-fallback] judge output not JSON; matched correct=false"
        return False, f"[parse-fail] judge output not parseable: {text[:200]!r}"

    raw_correct = obj.get("correct", False)
    if isinstance(raw_correct, bool):
        correct = raw_correct
    elif isinstance(raw_correct, (int, float)):
        correct = bool(int(raw_correct))
    elif isinstance(raw_correct, str):
        correct = raw_correct.strip().lower() in ("true", "1", "yes", "y")
    else:
        correct = False
    rationale = str(obj.get("rationale", "")).strip()
    return correct, rationale


# --------------------------------------------------------------------- #
# Substring-match fallback grader                                        #
# --------------------------------------------------------------------- #


_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")
# Thousands separators *between digits* only: "1,300" -> "1300", "400,000" ->
# "400000". This is the docx-recommended numeric/currency normalization that
# stops the gold-token-guard from false-rejecting "$1300" against gold "$1,300"
# (and "$400000" against "$400,000"). It never touches non-numeric commas.
_THOUSANDS_SEP_RE = re.compile(r"(?<=\d)[,٬](?=\d)")
# Any alphanumeric (incl. unicode word chars). Used to tell a real one-token
# answer ("3", "A") from a degenerate punctuation-only one ("$", "...", "-").
_ALNUM_RE = re.compile(r"\w", re.UNICODE)
_REFUSAL_MARKERS = (
    "i don't know", "i do not know",
    "not sure", "unclear", "unable to", "cannot", "can't",
    "do not have", "don't have", "not have access",
    "does not contain information", "do not contain information",
    "doesn't contain information", "not contain information",
    "no information", "did not say", "didn't say", "did not state",
    "not provided", "not available", "no record", "no mention",
    "not mentioned", "abstain", "unknown", "not enough",
)
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "was", "were", "be", "been", "being",
    "do", "does", "did", "of", "to", "in", "on", "at", "for", "with",
    "and", "or", "but", "that", "this", "these", "those",
    # mild paraphrase smoothing — verbs that judges commonly accept either way
    "said", "says", "say", "told", "stated", "states",
    # coreference smoothing — pronouns and the role nouns the LongMemEval
    # gold answers and our predictions use interchangeably ("they prefer X"
    # vs. "the user prefers X" describes the same person).
    "i", "me", "my", "mine",
    "you", "your", "yours",
    "he", "him", "his",
    "she", "her", "hers",
    "they", "them", "their", "theirs",
    "we", "us", "our", "ours",
    "it", "its",
    "user", "users", "assistant", "assistants",
})


def _crude_stem(token: str) -> str:
    """Strip common English inflections so prefer/prefers/preferred/preferring match.

    Deliberately crude — no nltk, no Porter stemmer dependency. The point is
    a documented Week-2 mitigation for the empty-judge failure mode, not a
    research-grade lemmatizer. Order matters: longest suffix first.
    """
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


# --- number-word <-> digit normalization (docx §4 fix 2 / failure F) --------
# The gold-token-guard compared surface tokens, so a correct "four" was
# hard-rejected against gold "4" (observed on session 89941a93). Canonicalizing
# spelled-out cardinals to their digit form on BOTH sides removes that whole
# class of false-negative ("four"->"4", "twenty-seven"->"27", "two hundred"->
# "200"). Digits are left unchanged, so real value mismatches ("2" vs "3") still
# fail.
_NUMBER_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_NUMBER_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
_NUMBER_SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
# Ordinal spellings map to the same cardinal digit so "twenty-seventh" == "27".
_NUMBER_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fifth": 5, "eighth": 8, "ninth": 9,
    "twelfth": 12,
}
# Multiplicative adverbs the cardinal table cannot express. Without this map a
# digit answer "2" is hard-rejected against gold "We've met up twice."
# (strat30 v7 false negative, session 5c40ec5b — made systematic by the v7
# answer prompt instructing digit-form numbers). Mapped BEFORE the cardinal
# collapse so "twice" == "2" on both sides of the guard.
_MULTIPLICATIVE_NUMBER_WORDS = {"once": "1", "twice": "2", "thrice": "3"}


def _collapse_number_words(tokens: list[str]) -> list[str]:
    """Replace spelled-out cardinal runs with their digit string, in order.

    Non-number tokens pass through unchanged. "and" only bridges two number
    words (so "one hundred and twenty" -> "120" but a bare "and" is untouched).
    """
    out: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        base = tok[:-2] if tok.endswith(("st", "nd", "rd", "th")) and tok[:-2] in (
            _NUMBER_UNITS.keys() | _NUMBER_TENS.keys() | _NUMBER_SCALES.keys()
        ) else tok
        if base in _NUMBER_ORDINALS:
            out.append(str(_NUMBER_ORDINALS[base]))
            i += 1
            continue
        if base not in _NUMBER_UNITS and base not in _NUMBER_TENS and base not in _NUMBER_SCALES:
            out.append(tok)
            i += 1
            continue
        # Consume a maximal number-word run.
        result = 0
        current = 0
        consumed = 0
        while i < n:
            w = tokens[i]
            w = w[:-2] if w.endswith(("st", "nd", "rd", "th")) and w[:-2] in (
                _NUMBER_UNITS.keys() | _NUMBER_TENS.keys() | _NUMBER_SCALES.keys()
            ) else w
            if w in _NUMBER_UNITS:
                current += _NUMBER_UNITS[w]
            elif w in _NUMBER_TENS:
                current += _NUMBER_TENS[w]
            elif w == "hundred":
                current = max(1, current) * 100
            elif w in _NUMBER_SCALES:
                result += max(1, current) * _NUMBER_SCALES[w]
                current = 0
            elif w == "and" and consumed > 0 and i + 1 < n:
                nxt = tokens[i + 1]
                if nxt in _NUMBER_UNITS or nxt in _NUMBER_TENS or nxt in _NUMBER_SCALES:
                    i += 1
                    continue
                break
            else:
                break
            consumed += 1
            i += 1
        out.append(str(result + current))
    return out


def _normalize_text(s: str) -> set[str]:
    """Lowercase, collapse numeric separators, strip punctuation, drop function
    words → set of stemmed tokens.

    The numeric-separator collapse means "$1,300" and "$1300" normalize to the
    same token {1300}, so currency/number formatting no longer drives a
    gold-token-guard false-negative (docx §8 recommendation). Spelled-out
    cardinals are collapsed to digits ("four"->"4") so number-word vs digit is
    no longer a false negative either (docx §4 fix 2 / failure F)."""
    s = _THOUSANDS_SEP_RE.sub("", s.lower())
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    tokens = _collapse_number_words(
        [_MULTIPLICATIVE_NUMBER_WORDS.get(t, t) for t in s.split() if t]
    )
    return {_crude_stem(t) for t in tokens if t and t not in _STOPWORDS}


def _numeric_content_tokens(text: str) -> set[str]:
    """Normalized tokens containing digits, used for provable value conflicts."""
    return {token for token in _normalize_text(text) if any(ch.isdigit() for ch in token)}


def looks_degenerate_answer(text: str) -> bool:
    """True for a non-empty answer that carries no alphanumeric content.

    Catches silent context-window truncation artifacts like a bare ``$`` /
    ``...`` / ``-`` (observed on LongMemEval session 852ce960, where a saturated
    prompt left the model room to emit only ``$`` instead of ``$400,000``). A
    legitimate one-character answer such as ``3`` or ``A`` carries an
    alphanumeric character and is NOT degenerate, so counting-question answers
    are never mistaken for truncation.
    """
    t = text.strip()
    return bool(t) and _ALNUM_RE.search(t) is None


# Golds with more content tokens than this are treated as verbose sentence
# answers: the token guard no longer hard-rejects them (a concise correct
# answer cannot contain every token of a long gold), deferring to the LLM judge.
def _is_abstention_competency(competency: str) -> bool:
    return "abstention" in competency.lower()


def _looks_like_abstention_gold(gold: str) -> bool:
    # Anchored to the HEAD of the gold: LongMemEval abstention golds open with
    # these phrases ("The information provided is not enough. ...", "You did
    # not mention ..."). An unanchored substring match misclassified an
    # answerable multi-session gold containing the late parenthetical
    # "(scale not mentioned)" as abstention (strat30 v7, gpt4_59c863d7),
    # inflating abstention_n and — worse — making a refusal auto-correct there.
    lower = gold.lower()[:40]
    return any(
        marker in lower
        for marker in (
            "did not mention",
            "didn't mention",
            "did not state",
            "didn't state",
            "did not say",
            "didn't say",
            "you did not mention",
            "you didn't mention",
            "no information",
            "not mentioned",
            # LongMemEval abstention golds all open with this exact phrase, e.g.
            # "The information provided is not enough. You mentioned X but not Y."
            "information provided is not enough",
            "is not enough",
            "not enough information",
        )
    )


def _looks_like_refusal(predicted: str) -> bool:
    lower = predicted.lower()
    return any(marker in lower for marker in _REFUSAL_MARKERS)


def normalized_substring_grade(
    *, predicted: str, gold: str, competency: str
) -> tuple[bool, str]:
    """Documented Week-2 mitigation for the self-judging empty-output failure mode.

    Used ONLY when the LLM judge emits empty / unparseable output. Returns:
      - For non-abstention questions: correct iff every content token of `gold`
        appears as a content token of `predicted`. Generous on word order,
        articles, plural-vs-singular roots, and the said/says/told dropouts.
      - For abstention questions: the gold typically encodes a refusal (e.g.
        "the user did not state ..."); a correct prediction declines or
        admits insufficient evidence. We match a small set of refusal phrases.

    The returned rationale is tagged with `[substring-fallback]` so every
    grade routed through this path is auditable in the qualitative-analysis
    appendix.

    NOT a substitute for an LLM judge in general — this is intentionally
    crude. It exists to prevent the self-judging artifact from making the
    Week-2 numbers uninterpretable. The Month-4 swap to the
    LongMemEval-published judge (eval_protocol.md §3) should remove all
    grades routed through this fallback.
    """
    if _is_abstention_competency(competency) or _looks_like_abstention_gold(gold):
        # Heuristic: a correct abstention answer hedges or refuses.
        if _looks_like_refusal(predicted):
            return True, "[substring-fallback] abstention: prediction declines/hedges"
        # Some abstention golds in the synthetic slice are positive statements
        # (placeholder format); fall through to token-set match in that case.

    pred_tokens = _normalize_text(predicted)
    gold_tokens = _normalize_text(gold)
    if not gold_tokens:
        # Defensive: nothing to match against → conservative incorrect.
        return False, "[substring-fallback] empty gold tokens"

    missing = gold_tokens - pred_tokens
    if not missing:
        return True, "[substring-fallback] all gold content tokens present in prediction"
    return (
        False,
        f"[substring-fallback] {len(missing)}/{len(gold_tokens)} gold tokens missing: "
        f"{sorted(missing)[:6]}",
    )


@dataclass
class LongMemEvalGrader:
    """Wraps an LLM and a cache; turns one BaselineAnswer + session into a GradeResult."""

    judge_llm: LLM
    cache: JudgmentCache | _NullCache = field(default_factory=_NullCache)
    max_new_tokens: int = 256
    seed: int = 0

    @property
    def judge_model_id(self) -> str:
        return getattr(self.judge_llm, "model_id", "unknown-judge")

    def grade(
        self, answer: BaselineAnswer, session: LongMemEvalSession
    ) -> GradeResult:
        is_abstention = _is_abstention_competency(
            session.competency
        ) or _looks_like_abstention_gold(session.gold_answer)
        if not answer.text.strip() and not is_abstention:
            return GradeResult(
                session_id=answer.session_id,
                competency=session.competency,
                correct=False,
                judge_score=0.0,
                judge_rationale="[blank-answer] non-abstention prediction is empty",
                judge_model_id=self.judge_model_id,
                predicted=answer.text,
                gold=session.gold_answer,
                prompt_tokens=answer.prompt_tokens,
                completion_tokens=answer.completion_tokens,
                latency_ms=answer.latency_ms,
                used_fallback=False,
            )

        if looks_degenerate_answer(answer.text):
            return GradeResult(
                session_id=answer.session_id,
                competency=session.competency,
                correct=False,
                judge_score=0.0,
                judge_rationale=(
                    "[degenerate-answer] prediction contains no alphanumeric content"
                ),
                judge_model_id=self.judge_model_id,
                predicted=answer.text,
                gold=session.gold_answer,
                prompt_tokens=answer.prompt_tokens,
                completion_tokens=answer.completion_tokens,
                latency_ms=answer.latency_ms,
                used_fallback=False,
            )

        if not is_abstention and _looks_like_refusal(answer.text):
            return GradeResult(
                session_id=answer.session_id,
                competency=session.competency,
                correct=False,
                judge_score=0.0,
                judge_rationale="[refusal-guard] non-abstention prediction refuses to answer",
                judge_model_id=self.judge_model_id,
                predicted=answer.text,
                gold=session.gold_answer,
                prompt_tokens=answer.prompt_tokens,
                completion_tokens=answer.completion_tokens,
                latency_ms=answer.latency_ms,
                used_fallback=False,
            )

        if is_abstention and _looks_like_refusal(answer.text):
            return GradeResult(
                session_id=answer.session_id,
                competency=session.competency,
                correct=True,
                judge_score=1.0,
                judge_rationale="[abstention-guard] prediction refuses for abstention gold",
                judge_model_id=self.judge_model_id,
                predicted=answer.text,
                gold=session.gold_answer,
                prompt_tokens=answer.prompt_tokens,
                completion_tokens=answer.completion_tokens,
                latency_ms=answer.latency_ms,
                used_fallback=False,
            )

        if not is_abstention:
            token_match, token_rationale = normalized_substring_grade(
                predicted=answer.text,
                gold=session.gold_answer,
                competency=session.competency,
            )
        else:
            token_match, token_rationale = True, ""
        # Surface-token mismatch is diagnostic, not a semantic verdict. The v7
        # audit found correct date/number synonyms such as "Valentine's Day" vs
        # "February 14th" and "2" vs "twice" being hard-rejected. Bypass the
        # judge only for a provable numeric conflict where both sides contain
        # normalized numbers and the sets disagree; all lexical/entity/date
        # mismatches defer to the semantic judge.
        pred_numbers = _numeric_content_tokens(answer.text)
        gold_numbers = _numeric_content_tokens(session.gold_answer)
        numeric_conflict = bool(pred_numbers and gold_numbers and pred_numbers != gold_numbers)
        if (
            not is_abstention
            and not token_match
            and numeric_conflict
        ):
            return GradeResult(
                session_id=answer.session_id,
                competency=session.competency,
                correct=False,
                judge_score=0.0,
                judge_rationale=token_rationale.replace(
                    "[substring-fallback]", "[gold-token-guard]", 1
                ),
                judge_model_id=self.judge_model_id,
                predicted=answer.text,
                gold=session.gold_answer,
                prompt_tokens=answer.prompt_tokens,
                completion_tokens=answer.completion_tokens,
                latency_ms=answer.latency_ms,
                used_fallback=False,
            )

        prompt = _render_judge_prompt(
            competency=session.competency,
            question=session.question,
            gold_answer=session.gold_answer,
            predicted_answer=answer.text,
        )
        key = JudgmentCache.make_key(prompt, self.judge_model_id)
        cached = self.cache.get(key)
        used_fallback = False
        if cached is not None:
            # When re-grading from cache (e.g. after a parser change), the
            # source of truth is the cached `raw` judge text, not the cached
            # parsed correctness. Re-parse so a regrade picks up new logic.
            raw = str(cached.get("raw", ""))
            correct, rationale = _parse_judge_output(raw)
            if not raw.strip() or rationale.startswith("[parse-fail]"):
                fb_correct, fb_rationale = normalized_substring_grade(
                    predicted=answer.text,
                    gold=session.gold_answer,
                    competency=session.competency,
                )
                correct, rationale = fb_correct, fb_rationale
                used_fallback = True
        else:
            resp = self.judge_llm.generate(
                prompt,
                max_new_tokens=self.max_new_tokens,
                temperature=0.0,
                seed=self.seed,
            )
            correct, rationale = _parse_judge_output(resp.text)
            if not resp.text.strip() or rationale.startswith("[parse-fail]"):
                fb_correct, fb_rationale = normalized_substring_grade(
                    predicted=answer.text,
                    gold=session.gold_answer,
                    competency=session.competency,
                )
                correct, rationale = fb_correct, fb_rationale
                used_fallback = True
            self.cache.put(
                key,
                {
                    "correct": correct,
                    "rationale": rationale,
                    "raw": resp.text,
                    "judge_model_id": self.judge_model_id,
                    "used_fallback": used_fallback,
                },
            )

        return GradeResult(
            session_id=answer.session_id,
            competency=session.competency,
            correct=correct,
            judge_score=1.0 if correct else 0.0,
            judge_rationale=rationale,
            judge_model_id=self.judge_model_id,
            predicted=answer.text,
            gold=session.gold_answer,
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
            latency_ms=answer.latency_ms,
            used_fallback=used_fallback,
        )


# --------------------------------------------------------------------- #
# Driver                                                                 #
# --------------------------------------------------------------------- #


def evaluate_baseline(
    baseline: Any,
    sessions: Iterable[LongMemEvalSession],
    grader: LongMemEvalGrader,
    *,
    progress_callback: Any = None,
    start_callback: Any = None,
    stage_callback: Any = None,
    n_bootstrap: int = 1000,
    bootstrap_seed: int = 0,
    judgments_path: Path | None = None,
    judgments_mode: str = "w",
    initial_grades: Iterable[GradeResult] | None = None,
) -> EvalReport:
    """Run `baseline.answer(session)` over every session, grade each, return a report.

    `baseline` only needs `.answer(session) -> BaselineAnswer` and a
    `BASELINE_NAME` attribute. The evaluator does not import or check the
    baseline's class — that is the point of the shared shape.

    Side effects: writes one JSONL line per graded session to
    `judgments_path` (if provided) as the run progresses, so a crash mid-run
    leaves partial-but-readable results. The judge cache (held by `grader`)
    is also written incrementally.
    """
    if judgments_mode not in {"w", "a"}:
        raise ValueError(f"judgments_mode must be 'w' or 'a'; got {judgments_mode!r}")

    sessions = list(sessions)
    grades: list[GradeResult] = list(initial_grades or [])

    if judgments_path is not None:
        judgments_path.parent.mkdir(parents=True, exist_ok=True)
        if judgments_mode == "w":
            # Truncate at start so each fresh evaluator run produces a clean file.
            judgments_path.write_text("", encoding="utf-8")

    for i, sess in enumerate(sessions, start=1):
        if start_callback is not None:
            start_callback(i, len(sessions), sess)
        if stage_callback is not None:
            stage_callback("answer:start", i, len(sessions), sess, None, None)
        t0 = time.perf_counter()
        answer = baseline.answer(sess)
        gen_ms = (time.perf_counter() - t0) * 1000.0
        # If the baseline forgot to populate latency, fall back to wall-clock.
        if answer.latency_ms <= 0.0:
            answer = dataclasses.replace(answer, latency_ms=gen_ms)
        if stage_callback is not None:
            stage_callback("answer:done", i, len(sessions), sess, answer, None)

        if stage_callback is not None:
            stage_callback("judge:start", i, len(sessions), sess, answer, None)
        grade = grader.grade(answer, sess)
        if stage_callback is not None:
            stage_callback("judge:done", i, len(sessions), sess, answer, grade)
        grades.append(grade)

        if judgments_path is not None:
            with judgments_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(grade.to_dict(), sort_keys=True))
                fh.write("\n")

        if progress_callback is not None:
            progress_callback(i, len(sessions), sess, answer, grade)

    baseline_name = getattr(baseline, "BASELINE_NAME", baseline.__class__.__name__)
    return build_eval_report(
        baseline_name=baseline_name,
        judge_model_id=grader.judge_model_id,
        grades=grades,
        n_bootstrap=n_bootstrap,
        bootstrap_seed=bootstrap_seed,
    )


def build_eval_report(
    *,
    baseline_name: str,
    judge_model_id: str,
    grades: Iterable[GradeResult],
    n_bootstrap: int = 1000,
    bootstrap_seed: int = 0,
) -> EvalReport:
    """Aggregate already computed grades into the standard EvalReport.

    Used by `evaluate_baseline` and by resumable run drivers that have a
    prefix of completed grades on disk and only need to evaluate the remainder.
    """
    grades = list(grades)

    # --- aggregate ----------------------------------------------------- #
    by_comp: dict[str, list[GradeResult]] = defaultdict(list)
    for g in grades:
        by_comp[g.competency].append(g)

    rows: list[CompetencyRow] = []
    for comp in sorted(by_comp):
        bucket = by_comp[comp]
        n = len(bucket)
        acc = sum(1 for g in bucket if g.correct) / n if n else 0.0
        lo, hi = bootstrap_accuracy_ci(
            [g.correct for g in bucket],
            n_resamples=n_bootstrap,
            seed=bootstrap_seed,
        )
        mean_pt = statistics.fmean(g.prompt_tokens for g in bucket) if n else 0.0
        mean_lat = statistics.fmean(g.latency_ms for g in bucket) if n else 0.0
        rows.append(
            CompetencyRow(
                competency=comp,
                n=n,
                accuracy=acc,
                accuracy_ci_low=lo,
                accuracy_ci_high=hi,
                mean_prompt_tokens=mean_pt,
                mean_latency_ms=mean_lat,
            )
        )

    overall_n = len(grades)
    overall_acc = sum(1 for g in grades if g.correct) / overall_n if overall_n else 0.0
    overall_lo, overall_hi = bootstrap_accuracy_ci(
        [g.correct for g in grades], n_resamples=n_bootstrap, seed=bootstrap_seed
    )

    # Abstention decomposition. Classify each graded item from its competency +
    # gold using the same predicates the grader uses to route abstention items,
    # so the split is consistent with how they were scored — no GradeResult
    # schema change and fully backward-compatible with old judgments.jsonl.
    def _is_abstention_grade(g: GradeResult) -> bool:
        return _is_abstention_competency(g.competency) or _looks_like_abstention_gold(g.gold)

    abstention_grades = [g for g in grades if _is_abstention_grade(g)]
    answerable_grades = [g for g in grades if not _is_abstention_grade(g)]
    abstention_n = len(abstention_grades)
    answerable_n = len(answerable_grades)
    abstention_acc = (
        sum(1 for g in abstention_grades if g.correct) / abstention_n
        if abstention_n else 0.0
    )
    answerable_acc = (
        sum(1 for g in answerable_grades if g.correct) / answerable_n
        if answerable_n else 0.0
    )
    n_degenerate = sum(1 for g in grades if looks_degenerate_answer(g.predicted))

    return EvalReport(
        baseline_name=baseline_name,
        judge_model_id=judge_model_id,
        n_sessions=overall_n,
        overall_accuracy=overall_acc,
        overall_ci_low=overall_lo,
        overall_ci_high=overall_hi,
        answerable_n=answerable_n,
        answerable_accuracy=answerable_acc,
        abstention_n=abstention_n,
        abstention_accuracy=abstention_acc,
        n_degenerate_answers=n_degenerate,
        rows=rows,
        grades=grades,
    )
