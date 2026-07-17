# Nearest-Neighbor Analysis (verified 2026-07-12)

Eight nearest neighbors, ordered by novelty threat. "Compared experimentally" refers to MGP-6 v2 runs in `artifacts/results_ledger.json` (all numbers below are ledger values, n=180). KSA reference: rule controller 0.9222 action accuracy / 0.9399 macro-F1, invalid-commit 0.0.

Global fairness caveat for all MGP-6 external comparisons: MGP-6 is an author-designed diagnostic; external systems were not built to emit KEEP/SUPERSEDE/ABSTAIN, so their scores come from an action-mapping (NOOP→ABSTAIN reported as the upper bound, NOOP→KEEP as the lower) through adapters we wrote. These are *capability bounds under our mapping*, not the systems' benchmark performance, and MemOS's number is a structural bound only (supersession not expressible through its adapter). The paper must print the mapping table and both bounds.

---

## 1. STALE (Chao, Bai, Sheng, Li, Sun — arXiv:2605.06527, May 2026)
- **Exact overlap:** a diagnostic benchmark for exactly MGP-6's hardest constructs: implicit conflict (a later observation invalidates a memory without explicit negation) and **premise resistance** (rejecting queries that presuppose the stale state). MGP-6 uses the same construct names (`premise_resistance` query mode; `implicit_conflict` scenario type). 400 expert-validated scenarios / 1,200 queries vs MGP-6's 180 scenarios / 1 external annotator.
- **Exact difference:** STALE probes *frozen agents at read time* — can the agent recognize a belief is outdated when answering. It never defines write actions, never scores what the memory store should look like, has no ABSTAIN action, no lineage, no controller, and no policy proposal. KSA scores the *write decision itself* plus resulting memory state (lineage integrity, invalid-commit, stale-retrieval).
- **Novelty threat: HIGH.** It occupies the "diagnostic for memory validity under implicit conflict" slot with more scenarios and expert validation. If reviewers see MGP-6 without a STALE citation, the construct-name collision looks like ignorance or worse.
- **Implementation availability:** paper on arXiv; dataset availability not verified.
- **Compared experimentally: NO.** (Published after MGP-6 design freeze window; feasible future work: run KSA's read-side probes on STALE.)
- **Fairness caveats if compared later:** STALE is read-side; KSA's controller would need its answerer stack, confounding write policy with retrieval/reading.

## 2. TOKI (Wang — arXiv:2606.06240, June 2026, cs.DB)
- **Exact overlap:** the write-time governance *thesis itself*: contradiction resolution is write-time control; heuristics typed as explicit operators; an **await-confirmation** operator that is functionally ABSTAIN; provenance annotation that preserves the losing fact in an audit row (functionally supersession lineage); interpretability by construction.
- **Exact difference:** TOKI is a formal contract (bitemporal operator algebra, isolation preconditions) with — as far as verifiable — no evidence/confidence-driven decision policy over LLM-extracted content, no diagnostic dataset, no measurement of decision accuracy, lineage integrity, or downstream QA, and no typed personal-memory schema. Single-author cs.DB preprint. KSA supplies the empirical layer: a concrete 5-feature policy and a scored diagnostic.
- **Novelty threat: HIGH** (conceptual). Kills any claim that the write-time framing or abstain-on-write idea is new. KSA's claim is the scoped operationalization and controlled empirical evaluation, without a priority assertion.
- **Implementation availability:** no code found.
- **Compared experimentally: NO** (formal framework; nothing runnable found).
- **Fairness caveats:** not comparable as a system; compare as formalism (KSA's actions can be described as instances of TOKI-style operators — doing so in the paper is a cheap robustness move).

## 3. Supersede environment (Patel — arXiv:2606.27472, June 2026)
- **Exact overlap:** isolates the memory-update ("supersession") failure on the **same substrate KSA uses** — LongMemEval knowledge-update — and shows it is a distinct, unsolved, scale-robust failure (92%→77% frontier model; 68%→28% as history grows). Terminology collision on "supersede".
- **Exact difference:** it is an RL *training environment*: reward = answering from the current value. No write-action taxonomy, no ABSTAIN, no lineage/memory-state scoring, no interpretable policy, no typed memory; it trains the behavior end-to-end instead of governing writes. Its diagnostic is answer-level; MGP-6's is decision-level.
- **Novelty threat: HIGH** (terminology + evidence). Its 92→77 result also *supports* KSA's motivation (maintenance, not comprehension, is the bottleneck) — cite it as convergent evidence.
- **Implementation availability:** YES — code, environment, model, data released (github.com/Vrin-cloud/supersede).
- **Compared experimentally: NO.** A future MGP-6 run of its trained policy is possible in principle but conflates training substrate with test substrate.
- **Fairness caveats:** different objective (trainability vs governance); comparing accuracy across the two setups is apples-to-oranges without a shared protocol.

## 4. Mem0 (Chhikara, Khant, Aryan, Singh, Yadav — arXiv:2504.19413)
- **Exact overlap:** per-item write operations (ADD/UPDATE/DELETE/NOOP) decided at ingestion; production focus; LongMemEval/LoCoMo evaluation.
- **Exact difference:** operations decided by prompted LLM without declared criteria; NOOP is not uncertainty-driven; no lineage (updates overwrite), no decision-level self-evaluation, no interpretable policy.
- **Novelty threat: MEDIUM.** It is the default reviewer referent for "memory system with update ops".
- **Implementation availability:** YES (open source + SaaS).
- **Compared experimentally: YES** — MGP-6: **0.622 / 0.442 (NOOP→ABSTAIN upper bound; NOOP→KEEP 0.400/0.249), invalid-commit 1.0** (`external/mem0_2.0.11`, final_candidate_with_mapping_disclosure).
- **Fairness caveats:** mapping disclosure mandatory; Mem0 was not designed to abstain, so its invalid-commit 1.0 is partly definitional — frame as "cannot express refusal", not "always wrong".

## 5. Letta / MemGPT (Packer et al. — arXiv:2310.08560)
- **Exact overlap:** agent-controlled memory writes; the historical reference system for self-managed memory.
- **Exact difference:** memory edits are opaque tool calls; no conflict semantics, abstention, lineage, typing, or write-decision evaluation.
- **Novelty threat: LOW-MEDIUM** (ubiquitous baseline, not a claims threat).
- **Implementation availability:** YES (Letta, open source).
- **Compared experimentally: YES** — MGP-6: **0.678 / 0.488 upper bound (NOOP→KEEP 0.489/0.302)** (`external/letta_memgpt`).
- **Fairness caveats:** as above; Letta run used qwen3.5-9b backbone — same-model comparison with KSA's LLM-backed controller (0.8889) is the fair pairing.

## 6. Zep / Graphiti (Rasmussen, Paliychuk, Beauvais, Ryan, Chalef — arXiv:2501.13956)
- **Exact overlap:** supersession-with-history in production: bi-temporal validity intervals, contradicted edges invalidated not deleted, episodes as provenance. The strongest prior art against a bare "lineage is new" claim.
- **Exact difference:** invalidation is an extraction side effect with no governed decision (no abstain, no evidence-weighted keep-vs-supersede choice) and no measurement of invalidation correctness.
- **Novelty threat: MEDIUM** (kills "first supersession lineage"; leaves separately scored lineage as a measured design choice, not a priority claim).
- **Implementation availability:** YES (Graphiti open source, 20k+ stars).
- **Compared experimentally: YES** — MGP-6: **0.383 / 0.219 upper bound (NOOP→KEEP 0.139/0.104)** (`external/graphiti_0.29.2`).
- **Fairness caveats:** Graphiti's graph write path is optimized for entity/relation extraction, not personal preference records; low MGP-6 score partly reflects adapter granularity mismatch — say so.

## 7. MemOS (Li et al. — arXiv:2507.03724)
- **Exact overlap:** "lifecycle governance" vocabulary, MemCube versioning + provenance metadata, typed memory levels.
- **Exact difference:** no published keep/supersede/abstain rule, no decision-level or lineage evaluation; architecture not policy.
- **Novelty threat: MEDIUM** (vocabulary overlap invites "already done" skims; the differentiation is that MemOS never *decides* or *measures*).
- **Implementation availability:** YES (github.com/MemTensor/MemOS, preview).
- **Compared experimentally: YES, but bound-only** — MGP-6: **0.144 / 0.164; supersession not observable through its adapter** (`external/memos`, claim_eligibility `bound_only_structural_limitation`). This number may only be reported with the structural-limitation disclosure and must never be presented as a capability measurement.
- **Fairness caveats:** strongest caveat of all four externals — the harness could not express supersession in MemOS at all; the honest sentence is "MGP-6's supersession construct is inexpressible through the MemOS adapter we built; the 0.144 figure is a floor imposed by that limitation, not MemOS's ability."

## 8. HaluMem (MemTensor — arXiv:2511.03506) with SAGE (arXiv:2605.30711) and Memory-R1 (arXiv:2508.19828) as satellites
- **Exact overlap:** HaluMem: operation-level evaluation of memory systems, separately scoring the *update* stage — the nearest prior to MGP-6's evaluation philosophy, and its stated conclusion ("interpretable and constrained memory operations" needed) is KSA's premise. SAGE: write-side gate with ADD/NOOP routing and transparent scoring (efficiency-motivated). Memory-R1: learned write-action space including NOOP.
- **Exact difference:** HaluMem scores hallucination presence, not action-choice correctness against a gold three-way decision, and has no abstention or lineage constructs. SAGE has no conflict/safety semantics, no abstain, no lineage. Memory-R1 is opaque and answer-rewarded.
- **Novelty threat: MEDIUM** each; jointly they fence in three of KSA's components (operation-level eval / write gate / action space), which is exactly why KSA's defensible claim is the conjunction + decision-level scoring, not any component.
- **Implementation availability:** HaluMem YES (github.com/MemTensor/HaluMem); SAGE not verified; Memory-R1 YES (github.com/yansikuan/memory-r1).
- **Compared experimentally: NO** (none of the three).
- **Fairness caveats:** n/a (cite-and-differentiate, not compare).

---

## Summary verdict

- The four systems compared on MGP-6 (Mem0, Letta, Graphiti, MemOS) are the right *experimental* comparators but are no longer the closest *conceptual* neighbors.
- The three highest novelty threats are **STALE, TOKI, and Supersede** — all 2026, all currently arXiv-only, none with write-time decision-level + memory-state + lineage scoring. KSA's window is real but narrow and closing; the integrated paper should be submitted this cycle and must cite all three.
- No verified prior work combines: write-time KEEP/SUPERSEDE/ABSTAIN gold labels + decision-level scoring + lineage-integrity scoring + interpretable policy + measured abstention ablation. That conjunction is the novelty; every individual component now has a nameable neighbor.
