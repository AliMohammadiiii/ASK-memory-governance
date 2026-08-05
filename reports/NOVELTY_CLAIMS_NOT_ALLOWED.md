# Novelty claims NOT ALLOWED (checked against verified literature and repo evidence, 2026-07-13)

Each entry: forbidden claim → why it fails → what to say instead (if anything).

**N1. "MGP-6 is a comprehensive benchmark" (or "benchmark" without qualification).**
Fails on evidence: 180 author-designed scenarios, one independent annotator (identity by author attestation), LLM audit panel is not human IAA, human review sheet 0/180 filled, two shipped metrics (over-/under-forgetting) saturate and are uninformative (SOT §1). Fails on literature: STALE (400 expert-validated scenarios) and HaluMem (15k memory points) occupy the "comprehensive" space.
Instead: "author-designed diagnostic slice (180 scenarios)", always.

**N2. "State of the art on LongMemEval" / any LongMemEval superiority or competitiveness claim.**
Fails on evidence: no LongMemEval number is final. The 77.2% value is a selection-biased carry-forward construction with heterogeneous judges and four Codex/GPT-5 overrides mislabeled as human. The non-empty top-up finds 13 regressions among 84 re-evaluated carried-forward items; combined raw evidence is 96/154 and the full-180 bound is 53.3%-67.8%. The contaminated v7 comparison has naive overwrite (63.3%) above the controller (61.1%).
Instead: C2 in ALLOWED and the top-up contradiction, both explicitly diagnostic.

**N3. "First memory system with abstention" (any variant: "we introduce abstention to memory systems").**
Fails on literature: the reject option is 55+ years old (Chow 1970; selective classification; learning to defer); RSCB-MC (arXiv:2604.27283) already uses explicit abstain/no-memory actions in memory control; TOKI's await-confirmation operator is abstain-on-write in formal form; LongMemEval/ES-MemEval score answer-level abstention.
Instead: A3 in ALLOWED (the measured diagnostic effect of abstain-on-write, with guards and no priority claim).

**N4. "Production memory safety" / "safe for deployment" / "prevents memory corruption in production".**
Fails on evidence: zero deployment or user-facing evaluation; MGP-6 is synthetic; LongMemEval runs were operationally unstable (316 HTTP-402 traces, 388 empty-extraction fallbacks). Fails on literature: the security/safety governance space (GateMem, MemGuard, memory-poisoning line, arXiv:2604.16548) addresses threat models ASK never tests (poisoning, multi-principal access, deletion compliance).
Instead: "a governance layer aimed at epistemic write correctness; security threat models are out of scope."

**N5. Any claim resting on diagnostic-only LongMemEval evidence**, including "the controller improves downstream QA", "governance helps on LongMemEval", "77.2% demonstrates effectiveness", or using v7/v8 numbers in a comparison table without their diagnostic labels.
Fails on evidence: ledger status for every LongMemEval row is `diagnostic_only`, `failure_replay_only`, `invalid`, `incomplete`, or `externally_pending`; none is `final_candidate`.
Instead: report as labeled diagnostics; the defensible downstream statement is the failure analysis (C2, D1).

**N6. "First to introduce Keep/Supersede/Abstain operations" or "we introduce memory update operations".**
Fails on literature: Memory-R1's ADD/UPDATE/DELETE/NOOP; RMM's merge/add; A-MEM's operations; Mem0's tool-called ops; SAGE's ADD/NOOP gate; TOKI types the whole heuristic family. Also a terminology collision: "Supersede" is now the title of arXiv:2606.27472.
Instead: A1/A2 in ALLOWED (operationalize and evaluate the ternary decision, with no priority claim).

**N7. "First versioned/lineage-tracking memory" or "we introduce provenance to agent memory".**
Fails on literature: Zep/Graphiti bi-temporal invalidation (retained history), MemOS MemCube versioning, TOKI audit rows.
Instead: B2 in ALLOWED (separately *scored* lineage; invisibility-to-action-accuracy result).

**N8. "First typed memory for LLM agents".**
Fails on literature: MemGuard assigns functional types at write time; MemOS types memory levels; MemGPT tiers.
Instead: B3 in ALLOWED (typing's measured causal contribution to write decisions).

**N9. "Multi-annotator human agreement validates MGP-6" / "human-verified gold labels" (plural humans).**
Fails on evidence: exactly one independent annotator (κ 0.9815, n=1, identity by author attestation); the 4-way κ 0.9815 panel is LLMs (SOT §1.2, ledger annotation block). Docs dated 2026-07-10 that say agreement is unmeasured must be reconciled before release.
Instead: "one independent annotator (κ 0.98) plus a four-model audit panel (Fleiss κ 0.98, majority vote 100% vs gold)."

**N10. "Our method fixes single-session preference failures" or any SSP accuracy improvement claim.**
Fails on evidence: the SSP method is proposed and unexecuted. The v7 11/30 is a contaminated diagnostic reference, replay repairs 0/19 under changed contexts, and the top-up is 8/29 observed with one unresolved (maximum 9/30).
Instead: D1 in ALLOWED.

**N11. "First operation-level / action-level evaluation of memory systems".**
Fails on literature: HaluMem (arXiv:2511.03506) is explicitly the first operation-level hallucination benchmark (extraction/update/QA); ROME/MEMIT established per-edit evaluation in weight space.
Instead: A2 in ALLOWED (the scoped write-action diagnostic with gold three-way labels and memory-state scoring, citing HaluMem).

**N12. "Memory governance" as an unclaimed term / "we coin memory governance".**
Fails on literature: SSGM (arXiv:2603.11768) and GateMem (arXiv:2606.18829, "Benchmarking Memory Governance") already use it; the security survey (arXiv:2604.16548) uses "governance across the memory lifecycle".
Instead: use the term with citations and immediately scope it: "epistemic write-time governance (which fact to trust), distinct from authorization-centric governance (who may write; GateMem)."

**N13. "Beats external memory systems" stated flatly (Mem0/Letta/Graphiti/MemOS rows without mapping and bound disclosure).**
Fails on evidence: all external numbers are mapping-dependent bounds; MemOS is bound-only with a structural adapter limitation; ledger eligibility is `final_candidate_with_mapping_disclosure` / `bound_only_structural_limitation`.
Instead: C1 in ALLOWED with mandatory phrasing.

**N14. Citing the few-shot (6-shot) LLM decision baseline as a complete result.**
Fails on evidence: only 174 predictions exist. Coverage-aware rescoring aligns six missing IDs as `INVALID` and yields 0.7833/0.7692, but the run remains `incomplete`. Those values may be disclosed only with that label. Also forbidden as results: `*_smoke`, `runs/m4w14`, `m4w15`, v5, v8 thinking-mode replay, and the old "controller 66%" m4w13 figure. The non-empty top-up may be cited only as incomplete evidence that invalidates the 77.2% carry-forward assumption.

**N15. "Validated by an established formal theory" (AGM compliance).**
Fails on evidence: no postulate-compliance proof or test exists in the repo. AGM may be cited as intellectual ancestry only.
