# Changelog — eval harness hardening for full 500-Q LongMemEval-S + LongMemEval-M

Scope: the eval harness only — runner (`scripts/run_m4w13_ollama.py`,
`scripts/run_baseline.py`), loader (`src/ksa/data/longmemeval.py`), grader
(`src/ksa/eval/longmemeval.py`), plus the minimal root-cause fix for the
truncation bug in `src/ksa/pipeline/orchestrator.py`. No controller scoring /
policy / memory-DB / extraction semantics were changed.

All changes verified: **369 passed, 5 skipped** (full suite), incl. 14 new
regression tests in `tests/test_scaleup_500_m_fixes.py`. Ruff clean.

## Grader — `src/ksa/eval/longmemeval.py`

1. **Numeric/currency normalization (docx §8 false-negatives).**
   `_normalize_text` now collapses thousands separators between digits, so
   `$1,300`≡`$1300` and `$400,000`≡`$400000` produce the same token. The
   gold-token-guard no longer false-rejects a correctly-valued answer that
   differs only in comma formatting (the `$1300` vs gold `$1,300` case). Applies
   uniformly to the guard and the substring fallback.
2. **Degenerate-answer detector `looks_degenerate_answer()`** — a non-empty
   answer with no alphanumeric content (`$`, `...`, `-`). A real one-char answer
   like `3` or `A` is **not** degenerate, so counting answers are never
   misflagged.
3. **Answerable-only / abstention decomposition in `EvalReport`.**
   `build_eval_report` now also computes `answerable_n`, `answerable_accuracy`,
   `abstention_n`, `abstention_accuracy`, and `n_degenerate_answers`. Surfaced in
   `to_dict()` (→ `report.json`) and `summarize_markdown()`. This removes the
   abstention artifact (docx §7.1) from every future run without re-deriving it.
   Backward-compatible: classification is done at aggregation time from
   (competency, gold) — no `GradeResult` schema change.

## Loader — `src/ksa/data/longmemeval.py`

4. **Exact full-set slicing.** `sample_slice(n == len(pool))` short-circuits to
   the whole pool in deterministic id order (no largest-remainder rounding edge
   at n=500). `n > pool` still raises (guards typos). `build_slice.py --n all`
   (`/0`/`full`) builds the full 500 without sampling.
5. **Memory-safe JSON-array streaming for LongMemEval-M.** A top-level JSON
   array (the Hugging Face shape) is streamed with `ijson` when installed;
   otherwise it falls back to `json.load` with a one-time size warning. Added
   `convert_to_jsonl()` to turn the large M array into streaming JSONL once.
   Whitespace-tolerant array sniffing.
6. **Competency canonicalization (`canonical_competency`).** Case / whitespace /
   underscore variants (`Knowledge_Update`, `multi_session`) normalize to the
   canonical hyphenated label, so a single odd record cannot abort an otherwise
   good 500/M load. Genuinely unknown labels still raise with the line number.
7. Docstrings generalized from "LongMemEval-S / 50-session slice" to the full
   S/M family at any N.

## Runner — `scripts/run_baseline.py`, `scripts/run_m4w13_ollama.py`

8. **Blank-OR-degenerate answer guard** (`run_baseline.py`). The end-of-run
   check now counts degenerate answers (bare `$`) alongside blanks, reports
   both, and fails the run unless `--allow-blank-answers`. Catches silent
   context-saturation truncation at the run level.
9. **Resume tolerant to schema evolution** (`run_baseline.py`). `_grade_from_row`
   now requires only fields *without* a dataclass default, so adding optional
   `GradeResult` fields never invalidates an existing `judgments.jsonl` on
   resume.
10. **Correct S-vs-M manifest provenance** (`run_m4w13_ollama.py`). New
    `--dataset {auto,s,m,synthetic}` + filename inference; the manifest records
    `dataset`/`dataset_family` accurately instead of hardcoding
    "LongMemEval-S cleaned". An M run is never mislabeled S.

## Pipeline (root cause of the truncation bug) — `src/ksa/pipeline/orchestrator.py`

11. **Answer-retry now fires on a bare symbol.** The retry trigger
    (`_answer_needs_retry`, extracted for unit-testability) fires on exact
    `Unknown`, empty, **or** a degenerate `$`-style answer — the 852ce960 case
    the original `Unknown`-only trigger missed. Gated behind the existing
    opt-in `--answer-retry-on-unknown` and a non-empty retrieval set, so it is
    strictly additive. `answer_looks_truncated` telemetry also flags residual
    degenerate answers.

## Data downloader — `deploy/download_longmemeval_s.py`

12. Generalized to fetch S **or** M (`--dataset {s,m}`), with per-dataset default
    filenames and output paths.

## New launch artifacts

- `deploy/run_colab_lme_full.sh` — build the full slice + run all five systems on
  the full 500-Q S or M set (final `thesis` profile by default).
- `NOTES/m4w13_scaleup_500_and_M.md` — the end-to-end runbook, including the
  temperature-0 / multi-seed caveat (don't present 3 identical full-set runs as
  variance) and the n=500 bootstrap-CI guidance.

## Not changed (deliberately out of scope)

Controller scoring/policy, memory DB, extraction, relation classifier, and the
`.docx`/`.xlsx` analysis generator (not in this repo). The model tags
`qwen3.5:9b` / `gemma4` flagged in docx §9 are local Ollama aliases, not code —
confirm the underlying checkpoints for reproducibility; no rename was forced.
