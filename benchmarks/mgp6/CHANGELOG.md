# Changelog

## v2.2 - Final thesis artifact

- Re-authored all 30 cue-free supersession events as natural, domain-specific evidence and preserved their exact T4 attribution contrasts.
- Replaced all 27 meta-style implicit-application prompts with concrete tasks that reveal neither the active nor stale value.
- Added row-level pattern-provenance flags for LongMemEval, STALE, Memora, GateMem, and MemEvoBench construction influences; these are explicitly held out from model input.
- Synchronized all 180 review-sheet rows with the released event and answer surfaces.
- Hardened schema and strict validation for initial active state, predecessor fidelity, exactly one successor, immutable KEEP records, candidate coverage, exact pair structure and value contrast, application-query non-leakage, provenance flags, and unique event surfaces.
- Strengthened semantic artifact and duplicate scoring through normalized memory values; breakdowns now include action, artifact, and answer quality.
- Specified two-stage evaluation, fair four-baseline controls, and the complete LongMemEval 78 knowledge-update plus 30 `_abs` bridge.

## v2.1 - Naturalization + inference strengthening

- Rewrote human-facing dialogue (`base_dialogue_prefix`, `perturbation_event`, `evaluation_query`, `expected_answer`) into natural first-person language instead of slot=value scaffolding. All gold actions, memory states, lineage, ids, splits, `query_mode`, `subtype`, `judge_spec`, and `forbidden_answer_patterns` are unchanged.
- Kept memory-record `text` in the auditable `slot = value` form (schema-mandated); only the surface dialogue was naturalized.
- Strengthened six implicit-conflict rows (two per T1/T2/T3) into inference-required conflicts where a habit/circumstance implies the new durable value without stating it or using any R4 cue; flagged `quality_flags += ["inference_required"]`.
- Preserved minimal-pair integrity: each T4 abstention partner still quotes its supersession partner's exact surface line. The generation-time naturalization helper and backup are not release files.

## v2 - MGP-6 v2 Diagnostic

- Expanded the author-designed diagnostic slice from the 60-row prototype to 180 rows, with 30 rows per T1-T6 type.
- Fixed gold totals at 90 `SUPERSEDE`, 24 `KEEP`, and 66 `ABSTAIN`.
- Added train, dev, and test splits blocked by template family and minimal-pair group.
- Added `query_mode` and `memory_age`.
- Added premise-resistance and implicit-application queries.
- Folded cue-free supersession into T1-T3 through `subtype="implicit_conflict"` without changing action totals.
- Added 24 split-local minimal-pair groups, including six cue-free T4 abstention partners per supersession type.
- Adopted GateMem-style `judge_spec.include` and `judge_spec.not_include` answer scoring.
- Added premise-resistance rate, implicit-application accuracy, implicit-conflict recall, cue-dependence gap, and FAMA-style presence-and-absence conjunction metrics.
- Added strict lineage, active-only answer, transient capture, PII, query-floor, and distribution validation.

## v1 - Prototype

- Created a 60-row, six-type prototype for `KEEP`, `SUPERSEDE`, and `ABSTAIN` decisions.
- Established atomic semantic slots and auditable memory-state outputs.

## Planned, not included in v2 data

Future diagnostic blocks may cover T7 duplicate or paraphrase handling, T8 multi-session supersession chains, T9 transient-to-stable promotion, T10 stale-retrieval traps, T11 cross-domain leakage, T12 provenance conflict, and a dedicated T13 implicit-conflict block. A later schema may activate reserved `FORGET` and `forgotten` labels with a T14 explicit-deletion type. None of those labels or types appears in v2 rows.
