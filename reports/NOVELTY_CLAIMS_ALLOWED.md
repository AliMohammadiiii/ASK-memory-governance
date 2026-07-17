# Novelty claims ALLOWED (narrowed after literature audit, 2026-07-13)

Rules of use: each claim is allowed only in the scope written and alongside the
evidence caveats in `docs/audit/SCIENTIFIC_SOURCE_OF_TRUTH.md`. The fast-moving
2026 literature contains close neighbors for update policy, supersession,
lineage, preference-aware updating, and abstention. The release therefore makes
no priority claim ("first" or "to our knowledge"). Its novelty is the controlled
operationalization and layered evaluation of a particular combination.

## A. Framing / problem claims

**A1.** "We study the write decision of a long-lived personal-agent memory as a ternary action — KEEP, SUPERSEDE (with recorded lineage), or ABSTAIN — and evaluate the decision separately from stored state and downstream answers."
- Guards: cite Memory-R1 (prior write-action space), TOKI (prior formal write-time framing incl. await-confirmation), RSCB-MC (prior abstain in memory control at retrieval time), SAGE (prior write-side gate). Allowed because none of these *evaluates* the three-way decision against gold actions.

**A2.** "MGP-6 is an author-designed diagnostic that isolates write-time KEEP/SUPERSEDE/ABSTAIN decisions with gold action labels and scores both the decision (action accuracy, macro-F1, invalid-commit) and resulting memory state (lineage integrity, stale retrieval)."
- Guards: cite HaluMem (operation-level hallucination eval — nearest prior), STALE (read-side implicit-conflict/premise-resistance probing — shared constructs), Supersede env (answer-level supersession gap on LongMemEval), ES-MemEval/LongMemEval (answer-level abstention categories). Mandatory accompanying caveats: author-designed diagnostic slice, 180 scenarios, one independent annotator (κ 0.98) plus a four-model audit panel — never "multi-annotator human agreement" (SOT §1.2).

**A3.** "We measure what an explicit abstain-on-write option contributes in this diagnostic: removing ABSTAIN drops action accuracy from 0.9222 to 0.5556 and raises invalid-commit rate from 0.0 to 1.0 on MGP-6."
- Guards: cite selective-prediction/learning-to-defer lineage (Chow; Geifman & El-Yaniv; Madras et al.; Mozannar & Sontag) as the origin of the reject option; RSCB-MC and TOKI as memory-control abstention precedents. The claim is about the *measurement on write decisions*, never about inventing abstention.

## B. Method claims

**B1.** "An interpretable five-feature scorecard controller is sufficient for high write-decision quality on this diagnostic (0.9222/0.9399), outperforming a zero-shot LLM decision baseline (0.700/0.6657) whose invalid-commit rate is 0.606, and never committing invalidly (invalid-commit 0.0)."
- Guards: cite Reddy & Challaram 2026 (independent convergent finding that deterministic beats LLM judgment on memory conflicts) and FadeMem (LLM-classifier alternative). Scope: "on this diagnostic" is mandatory.

**B2.** "Supersession is recorded as explicit lineage, and lineage correctness is scored separately from action accuracy; ablating lineage leaves action accuracy unchanged (0.9222) while lineage integrity collapses (0.8556 → 0.3689), showing that action-level metrics alone cannot see lineage corruption."
- Guards: cite Zep/Graphiti (bi-temporal invalidation) and MemOS (versioned MemCubes) as prior lineage *storage*; TOKI as prior lineage-with-audit formalism. The novelty is the *separate scoring* and the invisibility result.

**B3.** "Typed memory does causal work in write decisions: removing typing drops macro-F1 from 0.9399 to 0.5680 (KEEP F1 → 0.0); removing provenance drops accuracy from 0.9222 to 0.700 and raises invalid-commit from 0.0 to 0.606."
- Guards: cite MemGuard (typed functional roles at write time, contamination-motivated) and MemOS (typed levels). The novelty is the measured ablation, not typing itself.

**B4.** "The rule controller's conservative failure direction — all 14 SUPERSEDE errors become ABSTAIN, none become invalid commits — is a designed and verified property on MGP-6."
- Guards: none needed beyond ledger; keep scope to MGP-6.

## C. Comparison claims

**C1.** "Under a disclosed action mapping, four deployed memory systems (Mem0 0.622, Letta 0.678, Graphiti 0.383 as NOOP→ABSTAIN upper bounds; MemOS bound-only 0.144 due to a structural adapter limitation) leave a large gap to an interpretable governed controller on MGP-6."
- Mandatory phrasing elements: "upper bound", the mapping disclosure, and the MemOS structural-limitation sentence (SOT §1). Never present MemOS's figure as capability.

**C2.** "On a contaminated diagnostic LongMemEval-M run, naive overwrite (63.3%) outperformed our v7 controller (61.1%); we report this openly and analyze why."
- This negative claim is allowed and is a credibility asset. It may not be inverted into a superiority claim using the contradicted 77.2% construction (see NOT_ALLOWED N5).

## D. Analysis claims

**D1.** "We contribute a mechanism-level taxonomy for the 19 single-session-preference failures in the contaminated v7 LongMemEval run (grounding-supply primary in 10/19; answer-side discipline in 9/19) and a pre-registered, unexecuted correction design. The selected replay repairs 0/19, while the incomplete top-up reaches at most 9/30, so no improvement claim is made."
- Guards: cite PrefEval and PersonaMem for the preference-following failure context. Mandatory: the SSP method is PROPOSED, n=19 taxonomy from one run, no accuracy claim for any proposed arm (`docs/research/SINGLE_SESSION_PREFERENCE_METHOD.md` §6).

**D2.** "Answer-level QA accuracy cannot attribute failure to the write decision; MGP-6's decision-level and memory-state metrics are designed to close exactly this attribution gap."
- Guards: cite HaluMem (errors originate at extraction/update) and Supersede env (maintenance-not-comprehension bottleneck) as convergent evidence.

## E. Conjunction claim (the paper's core)

**E1.** "We operationalize and jointly evaluate (i) an explicit write-time KEEP/SUPERSEDE/ABSTAIN policy, (ii) recorded and separately scored supersession lineage, (iii) typed memory with measured ablations, (iv) an interpretable decision policy, and (v) decision-, state-, and answer-level outcomes. Each component has named precedents (Memory-R1; Zep/TOKI; MemGuard/MemOS; preference-aware update work; HaluMem/STALE), which we build on."
- This is the strongest allowed novelty formulation. The precedent list and the
  absence of a priority claim are mandatory.
