# Related Work Update (verified online, 2026-07-12)

Scope: this file supersedes the positioning claims of `research/deep_research_report.md` (the uploaded deep-research report) wherever they conflict. Every entry below was checked against arXiv/ACL Anthology/publisher pages on 2026-07-12 unless marked **[unverified]** or **[detail unverified]**. The deep-research report's citations were treated as leads, not truth; two of its attributions were wrong and are corrected here (RMM is Tan et al., not "Luo et al."; Generative Agents appeared at UIST 2023, not CHI 2023).

Evidence anchors used for "relationship to ASK" statements: `artifacts/results_ledger.json`, `docs/audit/SCIENTIFIC_SOURCE_OF_TRUTH.md` (both dated 2026-07-12).

**Headline change from the deep-research report:** the report's nearest neighbors (FadeMem, PAMU, RSCB-MC) are all real, but they are no longer the closest work. Verification surfaced a cluster of 2026 papers that are conceptually closer to ASK than Mem0/Letta/Graphiti/MemOS: **STALE** (implicit-conflict + premise-resistance probing), **Supersede** (the "supersession gap" on LongMemEval knowledge-update), **TOKI** (write-time contradiction resolution with audit lineage and an await-confirmation operator), **SAGE** (a write-side gate with ADD/NOOP routing), **MemGuard** (type-aware write-time memory roles), and **HaluMem** (operation-level memory evaluation including the update stage). These must be cited and differentiated in any submission.

---

## 1. Agent long-term memory systems

- **MemGPT** — Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S.G., Stoica, I., Gonzalez, J.E. (2023). "MemGPT: Towards LLMs as Operating Systems." arXiv:2310.08560. Open-source successor framework: **Letta**.
  Relevance: OS-style tiered memory with LLM-self-edited core memory; the canonical "agent manages its own memory" system.
  Relationship to ASK: ASK evaluates Letta on MGP-6 (0.678 action accuracy under NOOP→ABSTAIN upper-bound mapping, ledger `external/letta_memgpt`). MemGPT has no write-time decision criteria, no abstention, no lineage; its memory edits are opaque LLM function calls. Overlap: agent-controlled writes. Difference: ASK makes the write decision an explicit, scored, auditable three-way action.

- **Mem0** — Chhikara, P., Khant, D., Aryan, S., Singh, T., Yadav, D. (2025). "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory." arXiv:2504.19413. (Vendor blog lists an ECAI 2025 publication — **[detail unverified]**.)
  Relevance: production memory layer; extract-consolidate-retrieve pipeline with ADD/UPDATE/DELETE/NOOP tool calls decided by an LLM; graph variant.
  Relationship to ASK: evaluated on MGP-6 (0.622 NOOP→ABSTAIN upper bound; invalid-commit rate 1.0, ledger `external/mem0_2.0.11`). Overlap: per-item write operations. Difference: no uncertainty-driven refusal (NOOP is "nothing new", not "too ambiguous to commit"), no supersession lineage, no interpretable policy, no decision-level evaluation of its own write operations.

- **Zep / Graphiti** — Rasmussen, P., Paliychuk, P., Beauvais, T., Ryan, J., Chalef, D. (2025). "Zep: A Temporal Knowledge Graph Architecture for Agent Memory." arXiv:2501.13956. Graphiti open source (github.com/getzep/graphiti).
  Relevance: bi-temporal knowledge-graph memory; contradicted edges get invalidation timestamps rather than deletion — the strongest prior on supersession-with-history in a shipped system.
  Relationship to ASK: evaluated on MGP-6 (0.383 upper bound, ledger `external/graphiti_0.29.2`). Overlap: temporal invalidation ≈ supersession lineage; episodes ≈ provenance. Difference: invalidation is a side effect of LLM extraction, not a governed decision with an abstain option; Zep never scores whether an invalidation was *correct*. ASK's lineage claim must be phrased relative to Zep (lineage is not new; governed, evaluated lineage decisions are).

- **MemOS** — Li, Z., et al. (2025). "MemOS: A Memory OS for AI System." arXiv:2507.03724. (Large author list; first author verified.)
  Relevance: MemCube abstraction with versioning/provenance metadata and "lifecycle governance" vocabulary.
  Relationship to ASK: evaluated on MGP-6 but **bound-only** — supersession was not observable through its adapter (0.144, `claim_eligibility: bound_only_structural_limitation`; this must always be disclosed). Overlap: versioning + provenance metadata + the word "governance". Difference: no published decision rule for when to supersede vs keep vs refuse, no decision-level evaluation; architecture paper rather than policy paper.

- **A-MEM** — Xu, W., Liang, Z., Mei, K., Gao, H., Tan, J., Zhang, Y. (2025). "A-MEM: Agentic Memory for LLM Agents." arXiv:2502.12110.
  Relevance: Zettelkasten-style note construction, linking, and "memory evolution" (updating old notes when new ones arrive).
  Relationship to ASK: not experimentally compared. Overlap: dynamic per-item memory operations. Difference: always integrates new information (link/update); no abstention, no conflict semantics, no lineage, no action-level scoring.

- **MemoryBank** — Zhong, W., Guo, L., Gao, Q., Ye, H., Wang, Y. (2024). "MemoryBank: Enhancing Large Language Models with Long-Term Memory." AAAI 2024, 38(17):19724-19731. arXiv:2305.10250.
  Relevance: vector memory with Ebbinghaus-style decay; schedule-based forgetting.
  Relationship to ASK: background only. Forgetting is time-driven, not evidence-driven; no conflict handling, no write decisions.

- **Generative Agents** — Park, J.S., O'Brien, J., Cai, C.J., Morris, M.R., Liang, P., Bernstein, M.S. (2023). "Generative Agents: Interactive Simulacra of Human Behavior." UIST 2023. arXiv:2304.03442 **[venue/id from prior knowledge, consistent with citing papers; not re-fetched]**.
  Relevance: append-only event stream + reflection; canonical additive memory.
  Relationship to ASK: background; no revision or refusal machinery at all.

- **Memory-R1** — Yan, S., et al. (2025/2026). "Memory-R1: Enhancing Large Language Model Agents to Manage and Utilize Memories via Reinforcement Learning." arXiv:2508.19828.
  Relevance: RL-trained Memory Manager choosing ADD/UPDATE/DELETE/NOOP; the clearest prior formalization of memory writes as a discrete action space.
  Relationship to ASK: the strongest prior on "write ops as actions". Differences ASK can defend: (i) NOOP is not an uncertainty-driven abstain — there is no notion of declining because evidence is insufficient; (ii) policy is opaque (PPO/GRPO), ASK's is a five-feature interpretable scorecard; (iii) reward is answer-level, not decision-level; no lineage or memory-state scoring. Cite prominently; do not claim to have introduced the action-space idea.

- **RMM (Reflective Memory Management)** — Tan, Z., Yan, J., Hsu, I-H., Han, R., Wang, Z., et al. (2025). "In Prospect and Retrospect: Reflective Memory Management for Long-term Personalized Dialogue Agents." ACL 2025 (2025.acl-long.413). arXiv:2503.08026. **Correction: the deep-research report attributes this to "Luo et al." — wrong.**
  Relevance: prospective (merge-or-add at session end) + retrospective (RL-refined retrieval) memory management; evaluated on LongMemEval.
  Relationship to ASK: overlap on merge-vs-add ≈ supersede-vs-keep and on LongMemEval usage. Difference: no abstain, no contradiction semantics, no lineage, similarity-threshold rather than evidence-scored decisions.

- **SAGE** — (2026). "SAGE: A Novelty Gate for Efficient Memory Evolution in Agentic LLMs." arXiv:2605.30711. **[authors unverified]**
  Relevance: explicitly frames the gap as "principled write-side control": a von Mises-Fisher density gate routes candidate facts to ADD / NOOP / LLM-merge with an adaptive threshold. Motivation sentence is nearly ASK's.
  Relationship to ASK: overlap: write-time gate, transparent (geometric) scoring, NOOP routing. Differences: SAGE optimizes *efficiency* (skip redundant writes, cut API cost on LoCoMo), not *correctness under conflict*; no ABSTAIN-as-safety action, no supersession/lineage, no conflict typology, no decision-level accuracy metric. Must be cited; weakens any bare "first write-time gate" claim.

- **MemGuard** — Ha, H., Kim, J., Qian, C., Liu, J., Campbell, W.M., Wu, Y., Zhang, Y., McKeown, K., Hakkani-Tür, D., Ji, H. (2026). "MemGuard: Preventing Memory Contamination in Long-Term Memory-Augmented Large Language Models." arXiv:2605.28009.
  Relevance: assigns each memory an **explicit functional role (type) at write time** and keeps types isolated to prevent "heterogeneous memory contamination".
  Relationship to ASK: overlap: typed memory assigned at write time (directly adjacent to ASK's stable_pref/transient_pref/episodic_fact typing; ASK's no_typing ablation — macro-F1 0.9399→0.5680 — is the same argument made experimentally). Differences: no keep/supersede/abstain decision, no lineage, contamination/retrieval focus. Cite next to the typing ablation.

## 2. Memory lifecycle, revision, and conflict

- **FadeMem** — (2026). "FadeMem: Biologically-Inspired Forgetting for Efficient Agent Memory." arXiv:2601.18642. **[authors unverified; the deep-research report's "Wei et al." could not be confirmed]**
  Relevance: LLM classifies new-vs-old memory pairs (compatible/contradictory/subsumes/subsumed) and applies decay/fusion; tested on MSC, LoCoMo, LTI-Bench.
  Relationship to ASK: overlap: explicit contradiction handling at write time. Differences: always acts on detected conflict (no abstain), suppression instead of lineage-preserving supersession, LLM classifier instead of interpretable features, no decision-level scoring.

- **PAMU** — Sun, H., Zhang, Z., Zeng, S. (2025). "Preference-Aware Memory Update for Long-Term LLM Agents." arXiv:2510.09720.
  Relevance: sliding-window + EMA fusion of preference signals; updates only when drift is significant — a conservative, interpretable update trigger for preferences.
  Relationship to ASK: overlap: selective, interpretable updating of preference memory. Differences: preference vectors only (no facts), no discrete action space, no labeled abstain, no lineage/provenance, no per-decision evaluation.

- **TOKI** — Wang, Z. (2026). "TOKI: A Bitemporal Operator Algebra for Contradiction Resolution in LLM-Agent Persistent Memory." arXiv:2606.06240 (cs.DB).
  Relevance: argues contradiction resolution **is write-time concurrency control**; types four production heuristics (last-writer-wins, evidence-weighted merge, **await-confirmation**, per-rule policy) as bitemporal operators over a dual-row schema, each with an isolation precondition and a **provenance annotation preserving the losing fact in an audit row**.
  Relationship to ASK: the closest *conceptual* neighbor found. Overlap: write-time framing; await-confirmation ≈ ABSTAIN; audit row ≈ supersession lineage; explicit, interpretable operators. Differences (ASK's defense): TOKI is a formal/database contract (single-author cs.DB preprint), with no LLM-extraction decision policy over evidence/confidence features, no diagnostic dataset, no decision-accuracy or lineage-integrity measurement, no downstream evaluation. ASK supplies exactly the empirical layer TOKI lacks. High-priority citation.

- **Reddy, V., Challaram, S.** (2026). "Don't Ask the LLM to Track Freshness: A Deterministic Recipe for Memory Conflict Resolution." arXiv:2606.01435.
  Relevance: on MemoryAgentBench FactConsolidation, replacing LLM judgment with deterministic candidate-extraction + max(serial) beats LLM-based conflict resolution (+10.8 pts single-hop).
  Relationship to ASK: independent, convergent evidence for ASK's central design bet — deterministic/interpretable beats LLM judgment on update decisions (mirrors ASK's rule controller 0.9222 vs zero-shot LLM decision baseline 0.700). Differences: retrieval-assembly-time resolution with oracle-ish serial numbers, no abstain, no lineage, no typed memory.

- **Memory-R1, RMM, SAGE, MemGuard** — see §1; they are simultaneously lifecycle papers.

- **KEEM** — Kang, M., et al. (2026), dataset for integrative memory updates. **[unverified — could not be located online; do not cite without further verification]**

## 3. Benchmarks and evaluation for agent memory

- **LongMemEval** — Wu, D., Wang, H., Yu, W., Zhang, Y., Chang, K-W., Yu, D. (2025). "LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory." ICLR 2025. arXiv:2410.10813.
  Relevance: 500 questions over five abilities including knowledge updates and abstention; ASK's downstream evaluation substrate (stratified 180-item LongMemEval-M slice).
  Relationship to ASK: complementary — end-to-end QA only; it cannot attribute failure to the write decision. ASK has no final LongMemEval result: v7 is contaminated (controller 61.1%, naive overwrite 63.3%); the 77.2% carry-forward construction is `failure_replay_only` and contradicted by the top-up (96/154 raw observed; full-180 bound 53.3%-67.8%). No superiority claim is available.

- **HaluMem** — MemTensor et al. (2025). "HaluMem: Evaluating Hallucinations in Memory Systems of Agents." arXiv:2511.03506. **[individual authors not verified]**
  Relevance: first operation-level hallucination benchmark for memory systems — separately scores extraction, **updating**, and QA; finds hallucinations accumulate at extraction/update.
  Relationship to ASK: closest prior on *operation-level memory evaluation*. Differences: hallucination detection, not action selection — no KEEP/SUPERSEDE/ABSTAIN gold actions, no lineage-integrity or premise-resistance scoring, no abstention-on-write category. ASK contributes a scoped three-way decision diagnostic with lineage/state metrics; it makes no priority claim.

- **STALE** — Chao, H., Bai, Y., Sheng, R., Li, T., Sun, Y. (2026). "STALE: Can LLM Agents Know When Their Memories Are No Longer Valid?" arXiv:2605.06527.
  Relevance: 400 expert-validated **implicit-conflict** scenarios (1,200 queries); probes State Resolution, **Premise Resistance**, Implicit Policy Adaptation.
  Relationship to ASK: **highest-priority citation.** It shares MGP-6's constructs almost by name (implicit conflict; premise resistance — MGP-6's query modes include `premise_resistance`, and its one human-annotation disagreement is an `implicit_conflict` item). Differences: STALE probes *frozen agents' read-side recognition* of staleness; it does not define or score write actions, has no ABSTAIN-on-write, no supersession lineage, no memory-state metrics, and no controller. Any MGP-6 claim must be positioned as "write-time action diagnostic" explicitly against STALE's "read-side validity probing", and the construct-name overlap must be acknowledged.

- **Supersede** — Patel, V. (Vrin) (2026). "Supersede: Diagnosing and Training the Memory-Update Gap in LLM Agents." arXiv:2606.27472. Code/env released (verifiers/prime-rl stack).
  Relevance: isolates the "supersession gap" on the LongMemEval knowledge-update subset (92%→77% full-context→bounded memory on gpt-5.4); GRPO training nearly doubles a small model's supersession accuracy.
  Relationship to ASK: owns the *word* "supersede" in this space and the LongMemEval-knowledge-update diagnostic; must be cited and terminologically disambiguated. Differences: reward is answer-time fact currency; no write-action taxonomy, no abstention, no lineage or memory-state scoring, no interpretable policy — it trains the behavior end-to-end rather than governing the write.

- **GateMem** — Ren, Z., Yang, Y., Chen, Y., Zhao, Z., Fu, B., Shu, Z., Zhang, B., Xu, Y., Guo, D., Yan, S. (2026). "GateMem: Benchmarking Memory Governance in Multi-Principal Shared-Memory Agents." arXiv:2606.18829.
  Relevance: first benchmark using the phrase "memory governance"; but its axes are access control across principals, deletion compliance, and utility in *shared* memory pools.
  Relationship to ASK: different governance axis (authorization/privacy vs epistemic write correctness). Cite to disambiguate the term "memory governance"; low overlap otherwise.

- **ES-MemEval** — (2026). "ES-MemEval: Benchmarking Conversational Agents on Personalized Long-Term Emotional Support." WWW 2026 (DOI 10.1145/3774904.3792143). arXiv:2602.01885. **[individual authors not verified]**
  Relevance: names Conflict Detection and Abstention among five core memory capabilities.
  Relationship to ASK: validates the capability taxonomy; abstention is answer-level, domain is emotional support; no write actions or lineage.

- **LoCoMo** — Maharana, A., et al. (2024). "Evaluating Very Long-Term Conversational Memory of LLM Agents." ACL 2024. arXiv:2402.17753 **[id from prior knowledge; title/authors seen in citing papers, not re-fetched]**.
  Relevance: standard very-long-conversation QA benchmark (used by Mem0, FadeMem, SAGE).
  Relationship to ASK: scale-focused, not conflict-focused; optional comparator context only.

- **Memora / FAMA** — Uddin, M.N., et al. (2026). "From Recall to Forgetting: Benchmarking Long-Term Memory for Personalized Agents." arXiv:2604.20006.
  Relevance: FAMA metric explicitly penalizes reliance on obsolete/invalidated memory (FAMA = max(0, MPA − λ·(1−FAA))).
  Relationship to ASK: nearest prior to ASK's stale-retrieval-rate idea, at answer level. Note for internal honesty: ASK's shipped over-/under-forgetting rates saturate at 1.0 and are uninformative (SOT §1) — do not contrast against FAMA using those metrics.

- **SSGM** — (2026). "Governing Evolving Memory in LLM Agents: Risks, Mechanisms, and the Stability and Safety Governed Memory (SSGM) Framework." arXiv:2603.11768. **[authors unverified; report says Zhu et al.]**
  Relevance: conceptual governance framework (memory poisoning, semantic drift, stability-plasticity); argues memory evolution must be decoupled from governance.
  Relationship to ASK: motivation-level ally; not implemented, no diagnostic, no metrics. Also cite the memory-security survey arXiv:2604.16548 ("mnemonic sovereignty": governance over what may be written, what stays auditable) for the same motivation.

- **RSCB-MC** — Iscan, M. (2026). "Learning When to Remember: Risk-Sensitive Contextual Bandits for Abstention-Aware Memory Retrieval in LLM-Based Coding Agents." arXiv:2604.27283.
  Relevance: risk-sensitive controller over memory *use* with explicit no-memory/abstain actions; 0.0% false-positive rate emphasis.
  Relationship to ASK: nearest prior on abstention as a memory-control action — but at retrieval/injection time in coding agents, not at write time in personal memory; learned bandit vs interpretable scorecard; no lineage/typing. It removes any priority claim; ASK instead scopes its contribution to controlled write-time operationalization and evaluation.

## 4. Belief revision and knowledge editing

- **AGM** — Alchourrón, C.E., Gärdenfors, P., Makinson, D. (1985). "On the Logic of Theory Change: Partial Meet Contraction and Revision Functions." Journal of Symbolic Logic 50(2):510-530. (Canonical; not re-verified online.)
  Relevance: revision/contraction/expansion with minimal-change postulates is the formal ancestor of KEEP/SUPERSEDE; AGM has no native abstain (non-prioritized belief revision — e.g., Hansson's semi-revision — covers declining input; cite as **[unverified detail]** if used).
  Relationship to ASK: ASK can be framed as an operational, resource-bounded approximation of non-prioritized revision for LLM memory; do not claim formal AGM compliance (never proven in this project).

- **ROME** — Meng, K., Bau, D., Andonian, A., Belinkov, Y. (2022). "Locating and Editing Factual Associations in GPT." NeurIPS 2022. arXiv:2202.05262. **MEMIT** — Meng, K., et al. (2023). "Mass-Editing Memory in a Transformer." ICLR 2023. arXiv:2210.07229. (Canonical; not re-fetched.)
  Relevance: parametric knowledge editing evaluates edits with efficacy/generalization/specificity — the decision-level-evaluation analogue in weight space.
  Relationship to ASK: different substrate (weights vs external store); editing assumes the edit *should* happen — no keep/abstain decision. Useful contrast: ASK governs *whether* to commit, editing research governs *how*.

- **TOKI** (see §2) is also the belief-revision-adjacent entry for external memory.

## 5. Selective prediction and abstention

Canonical line (not re-fetched; standard): **Chow (1970)**, IEEE Trans. Information Theory — reject option; **El-Yaniv & Wiener (2010)**, JMLR — selective classification foundations; **Geifman & El-Yaniv (2017)**, NeurIPS — selective deep classification; **Madras, Pitassi, Zemel (2018)**, NeurIPS — learning to defer; **Mozannar & Sontag (2020)**, ICML — consistent deferral.
  Relevance: abstention as coverage/risk trade-off; risk-coverage analysis is the right lens for ABSTAIN.
  Relationship to ASK: ASK transplants the reject option from *prediction time* to *memory-write time*. Because this literature exists, the claim "first memory system with abstention" is not allowed in any form (see NOVELTY_CLAIMS_NOT_ALLOWED.md); the transplant, plus its measured safety effect (no_abstain ablation: 0.9222→0.5556 accuracy, invalid-commit 0.0→1.0), is the defensible content. RSCB-MC (§3) already applies abstention to memory retrieval; ES-MemEval and LongMemEval score answer-level abstention.

## 6. Personalization and preference modeling

- **PrefEval** — Zhao, S., Hong, M., Liu, Y., Hazarika, D., Lin, K. (2025). "Do LLMs Recognize Your Preferences? Evaluating Personalized Preference Following in LLMs." ICLR 2025 (oral). arXiv:2502.09597.
  Relevance: 3,000 preference-query pairs; preference following collapses below 10% within ~10 turns zero-shot.
  Relationship to ASK: external motivation for the SSP failure line. In contaminated v7, SSP is 11/30; ASK's 19-item taxonomy attributes failure mechanism (grounding supply 10/19 primary vs answer-side discipline 9/19). The incomplete top-up reaches at most 9/30, so these are diagnostics rather than a stable cross-version score.

- **PersonaMem** — Jiang, B., Hao, Z., Cho, Y., Li, B., Yuan, Y., Chen, S., Ungar, L., Taylor, C.J., Roth, D. (2025). "Know Me, Respond to Me: Benchmarking LLMs for Dynamic User Profiling and Personalized Responses at Scale." COLM 2025. arXiv:2504.14225. PersonaMem-v2: arXiv:2512.06688.
  Relevance: dynamic user profiles across sessions; frontier models ~50%.
  Relationship to ASK: benchmark-side motivation for typed preference records; no write governance.

- **LaMP** — Salemi, A., Mysore, S., Bendersky, M., Zamani, H. (2023). "LaMP: When Large Language Models Meet Personalization." arXiv:2304.11406.
  Relevance: canonical personalization benchmark (7 tasks, retrieval-augmented personalization).
  Relationship to ASK: static profiles, no temporal revision; background citation only.

- **RealPref (Guo et al. 2026), ALPBench (Ren et al. 2026), LikeBench (Rahman et al. 2025)** — **[unverified: could not be confirmed online in this pass; do not cite without direct verification]**. A verified adjacent item exists if needed: "Towards Realistic Personalization: Evaluating Long-Horizon Preference Following..." arXiv:2603.04191 **[details unverified]**.

## 7. Provenance and auditability

- **Zep/Graphiti** (§1) — bi-temporal validity intervals; episodes as provenance; facts marked invalid, not deleted.
- **TOKI** (§2) — provenance annotation preserving the losing fact in an audit row; the explicit "auditability of the write decision" precedent.
- **MemOS** (§1) — MemCube provenance/version metadata.
- **HaluMem** (§3) — traces errors to the operation that produced them (evaluation-side provenance). Adjacent verified item: MemTrace, arXiv:2605.28732 ("Tracing and Attributing Errors in LLM Memory Systems") **[details beyond title unverified]**.
- **GateMem / memory-security survey (arXiv:2604.16548)** (§3) — auditability as a governance requirement (who wrote what, what must remain auditable).
  Relationship to ASK: provenance *storage* is well-precedented. ASK's distinct piece is scoring provenance's causal contribution to decisions (no_provenance ablation 0.9222→0.700, invalid-commit 0→0.606) and scoring lineage integrity itself (no_lineage: action accuracy unchanged, lineage integrity 0.8556→0.3689 — evidence that lineage errors are invisible to action-accuracy-only evaluations).

---

### Corrections to the deep-research report (for the record)
1. RMM is **Tan et al., ACL 2025**, not "Luo et al." (report §4.2/§6).
2. Generative Agents is **UIST 2023** (report bibliography says CHI 2023) and first author is Park, J.S. (report says "Park, D. H.").
3. MemoryBank is a system paper (AAAI 2024), not "a dataset for continual learning" (report bibliography).
4. FadeMem's authorship ("Wei et al.") and KEEM, RealPref, ALPBench, LikeBench, RPEval, BEAM/LIGHT, ONERULER, CareCall entries could not be verified in this pass — treat as [unverified] until checked.
5. The report's claim that "no prior system explicitly provides a third 'abstain' option" is now too strong: TOKI's await-confirmation operator (write time, formal) and RSCB-MC's abstain (retrieval time, empirical) both exist. Allowed phrasing is in NOVELTY_CLAIMS_ALLOWED.md.
