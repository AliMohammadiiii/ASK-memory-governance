# Error Taxonomy

Date: 2026-07-13. Consolidated failure analysis across the three evidence tracks.
Sources: `artifacts/single_session_preference_error_taxonomy.json`,
`artifacts/results_ledger.json`, `artifacts/controller_run_comparison.json`,
`docs/audit/CONTROLLERRUN_FAILURE_LEDGER.md`,
`docs/research/SINGLE_SESSION_PREFERENCE_FAILURE_ANALYSIS.md`.

---

## 1. LongMemEval-M single-session-preference (SSP) taxonomy — 19 failing items

SSP is 11/30 correct in contaminated v7 (accuracy 0.3667, bootstrap 95% CI
[0.20, 0.53]); **19 items fail**, and the selected replay repairs 0/19. All counts
below are from the machine-readable taxonomy JSON (verified against
`judgments.jsonl` and the constructed `raw_prompt` per item).

This is a v7 failure taxonomy, not a stable v8 score. Replay prompts differ from
v7 prompts, so 0/19 does not isolate an answer-model effect. The Modal top-up
observes 8/29 SSP correct with one unresolved (maximum 9/30), disproving the
historical claim that SSP remained 11/30 under the attempted v8 configuration.

### 1.1 Primary category counts (n = 19)

| Primary category | Count | Share |
|---|---|---|
| retrieval-omission | 6 | 31.6% |
| cross-session-contamination | 4 | 21.1% |
| target-attribute-extraction-miss | 3 | 15.8% |
| distractor-entity-binding | 2 | 10.5% |
| polarity-error | 2 | 10.5% |
| unsupported-answer-specificity | 1 | 5.3% |
| immediate-request-vs-enduring-preference | 1 | 5.3% |

### 1.2 Combined (primary + secondary) mechanism mentions

| Mechanism | Mentions (of 19) |
|---|---|
| retrieval-omission | 11 |
| cross-session-contamination | 8 |
| distractor-entity-binding | 7 |
| target-attribute-extraction-miss | 5 |
| unsupported-answer-specificity | 3 |
| immediate-request-vs-enduring-preference | 2 |
| polarity-error | 2 |

### 1.3 Pipeline-layer distribution (an item may touch >1 layer)

| Pipeline layer | Items | Share of 19 |
|---|---|---|
| retrieval-ranking | 12 | 63.2% |
| answer-realization | 10 | 52.6% |
| context-construction (top-k trim) | 5 | 26.3% |
| attribution + target-binding | 5 | 26.3% |
| ingestion / extraction / persistence / judge-scorer / controller-policy | 0 | 0% |

### 1.4 Two dominant families

- **Grounding-supply failures** (retrieval-omission + cross-session-contamination):
  primary in **10/19**, present in **15/19**. The single supporting session's
  decisive turn is out-ranked by topically similar distractor sessions and trimmed
  away; the model then answers from the wrong session or fabricates. Corroborated
  by the 0/19 replay non-repair, although the replay changed more than the
  answerer and therefore does not identify a single causal component.
- **Answer-side binding/realisation failures** (target-attribute-miss,
  distractor-entity-binding, polarity, over-narrowing, unsupported specificity):
  primary in **9/19**. Here the decisive fact *was* in context but the model bound
  the preference to the wrong target or violated a stated negative constraint.

Illustrative items (verbatim from taxonomy): `75832dbd` (answered from an
environmental-sustainability distractor instead of AI-in-healthcare;
cross-session-contamination); `75f70248` (cat "Whiskers" from a distractor instead
of gold "Luna"; distractor-entity-binding — contamination, not free fabrication);
`1c0ddc50` (recommended "self-improvement" podcasts, an explicitly dis-preferred
genre; polarity-error); `95228167` (ignored the in-context Gibson-vs-Fender
comparison; target-attribute-extraction-miss). Honest caveat: `1da05512` (NAS) is
a borderline judge-severity case, not a clean pipeline defect.

Highest-leverage proposed fix (design, not yet run): make preference grounding
first-class and provenance-constrained (typed holder/target/attribute/polarity/
scope/source record), paired with an answer contract that asserts only
retrieved-and-grounded preferences. Necessary but not sufficient — ~9/19 are
answer-side failures that persist even with perfect grounding.

---

## 2. MGP-6 v2 controller error profile

### 2.1 Rule controller: conservative, one-directional misses

- Action accuracy 0.9222 (166/180). All 14 errors are SUPERSEDE items predicted
  ABSTAIN (**14 SUPERSEDE→ABSTAIN conservative misses**). Confusion: KEEP 24/24,
  ABSTAIN 66/66, SUPERSEDE 76/90.
- The controller **never invalidly commits**: invalid-commit rate 0.0. The failure
  direction is safe (it abstains rather than overwriting on a conflict it cannot
  resolve), which is exactly the behaviour the abstention component is designed to
  produce. Per-action F1: KEEP 1.0, SUPERSEDE 0.9157, ABSTAIN 0.9041.
- Interpretation: on this author-designed slice the residual error is a
  recall gap on supersession under weaker cues, not a safety failure.

### 2.2 LLM controller (qwen3.5-9b): premise-resistance collapse

- Action accuracy 0.8889 (160/180), macro-F1 0.8913 — statistically indistinguishable
  from the rule controller on accuracy (McNemar Holm p = 0.286).
- **Premise resistance 0.0889** vs 1.0 for the rule controller: the dominant
  qualitative failure. The LLM controller largely fails to reject false premises in
  the answer even when it labels the governance action correctly.
- Secondary: invalid-commit rate 0.0758 (non-zero, unlike the rule controller's 0.0),
  stale-retrieval 0.3056 (vs 0.0778).

### 2.3 Zero-shot LLM decision baseline: invalid commits

- Action accuracy 0.700 (126/180), macro-F1 0.6657.
- **Invalid-commit rate 0.606**: without the governance scaffold, the unstructured
  decision baseline commits an invalid/conflicting state on ~61% of gold-ABSTAIN
  items. This is the single failure mode the provenance + abstention machinery is
  designed to prevent; ablating provenance reproduces the same 0.606 rate.

### 2.4 Ablation-induced failure modes (n=180)

| Removed component | New failure signature |
|---|---|
| abstain | invalid-commit rate → 1.0; accuracy 0.9222 → 0.5556 |
| provenance | invalid-commit rate → 0.606; accuracy → 0.700 |
| typing | KEEP F1 → 0.0; accuracy → 0.7889 |
| lineage | action labels unchanged; lineage integrity 0.8556 → 0.3689 |

---

## 3. LongMemEval-M failure classes (from the failure ledger)

From `docs/audit/CONTROLLERRUN_FAILURE_LEDGER.md` (F1–F12). These are
run/pipeline failures, distinct from the per-item SSP taxonomy above.

### 3.1 Provider contamination (the headline integrity problem)

- **F1 — HTTP-402 credit exhaustion → empty extraction fallbacks.** v7 extraction
  trace: 11,505 traces, 736 with an error field, **316 containing "402"**, **388
  empty extractions with zero model responses**. Fix (v8): re-raise instead of
  caching a synthetic empty (`--fail-on-extraction-error`), covered by
  `test_extractor_recovery.py`.
- **F2 — extraction-empty caching bug.** Cached empties baked into the shared cache
  survive resume and change memory state + answers. Fixed by content-keyed caching
  of real empties only.
- **F9 — relation-classifier no-response → semantic Keep.** No-response stage
  failures were converted to `independent/unclear`, cached, and allowed the session
  to complete with corrupted state. Fixed by re-raising on no-response.
- **Residual (F1/F2/F9 shared):** the **110 v7-retained-correct sessions were never
  re-executed** under the fixed pipeline; they carry v7's contaminated state into
  both the 135 (raw) and 139 (adjudicated) merged figures.

### 3.2 Extraction / config total-loss failures

- **F3 — thinking-mode token-budget failure.** Qwen thinking mode consumed the
  512-token extraction budget; strict v8 extraction aborted → **0 completed
  predictions** across 10 shards (INVALID replay). Fixed with
  `enable_thinking:false`; corrected rerun completed 70/70 (35.7%).
- **F4 — MiniLM signal-11 shard deaths.** Per-shard local embedder caused all ten
  shards to segfault during concurrent native init. Fixed with a shared HTTP
  embedding server.

### 3.3 Extraction fallbacks / answer generation

- **F7 — aggregation scaffold (unvalidated hint) removed.** On 11 count/sum
  questions the scaffold matched gold 2/11, final answer 1/11 — no value, added
  latency; removed in v8. Aggregation/counting remains unsolved (near-miss counts
  persist).
- **F8 — escalation no-op (BIG_MODEL == FAST_MODEL).** The v7 escalate-on-Unknown
  retry re-asked the same 9B model (26 retries, 7 rescues, 18 post-retry refusals).
  Fixed with a genuinely separate escalation model; benefit not measured in a clean
  run. The 139/180 construction carries v7 no-op-escalation answers into 110 slots.

### 3.4 Judge disagreement / grading

- **F6 — judge number-word/digit mismatch (false negatives).** e.g. gold "4" vs
  prediction "four"; "2" vs "twice"; "Valentine's Day" vs "February 14th"
  guard-rejected and overridden to correct. Fixed with multiplicative-number-word
  collapse and deferral of lexical/date mismatches to the LLM judge; residual guard
  still hard-rejects genuine numeric conflicts (some gold answers with internal
  acceptance rules still need manual adjudication).
- **F10 — scoring scaffold + report title bug + 5 verdict overrides applied in
  place** (controller 108→110/180); originals preserved as `.pre_adjudication.orig`.
- **Judge heterogeneity in the 77.2% construction:** Gemma-4-31b ×110,
  Qwen3.5-9B ×66, Codex/GPT-5 overrides ×4 — three judging regimes mixed, with
  the four model overrides misleadingly tagged `[human-adjudication]`; judge identity
  confounded with item difficulty. Machine-vs-adjudicator agreement 0.9428,
  Cohen κ 0.880 on the replay set.

### 3.5 Provenance / bookkeeping defects

- **F5 — v5 run misnaming + abort.** Dir `100_129` actually ran items 200–239;
  KeyboardInterrupt; no merged report → invalid.
- **F11 — broken manifest `replay_run` path.** The adjudicated artifact records a
  non-existent replay dir (`runs/lme_m_modal_qwen35_9b_v8_v7_failures_nothink`);
  the real dir is `runs/lme_m last version/lme_m_modal_qwen35_9b_v8_failures_nothink`.
  Computed value is internally consistent, but the manifest is not a runnable recipe.
- **F12 — SSP non-repair and carry-forward failure.** The selected replay repairs
  0/19 v7 failures, but its contexts differ and the causal attribution is not
  isolated. In the Modal top-up, 8/29 SSP items are observed correct with one
  unresolved (maximum 9/30), so the historical 11/30 carry-forward is false.
- **F13 — retained-success regressions.** The Modal top-up completes 84/110
  former v7 successes; 71 remain correct and 13 regress. Combined with replay,
  the attempt is 96/154 raw observed and bounded at 53.3%-67.8% over all 180.
