# Reviewer 2 Audit

Date: 2026-07-12. The harshest *defensible* review of the ASK memory-governance
project. Each section states the attack, the evidence that exists, the honest
response, and the claim that must be weakened or dropped. Nothing here is
rhetorical: every number traces to the ledger or audit docs. Ends with the
"claims that survive" list, each tagged
`verified` / `supported` / `suggestive` / `hypothesized` / `future_work`.

---

## A1. Novelty — "isn't this just a rules heuristic?"

- **Attack.** The headline system is a hand-written rule controller that encodes
  KEEP/SUPERSEDE/ABSTAIN over typed memories. A deterministic policy that scores
  0.9222 on a dataset the same author wrote is a heuristic, not a research
  contribution.
- **Evidence.** Rule controller 0.9222/0.9399 on MGP-6; invalid-commit 0.0; the
  ablations show each component (abstain, provenance, typing, lineage) is load-bearing
  for a distinct metric.
- **Honest response.** The contribution is not "a rule wins"; it is (i) a *typed,
  provenance-and-abstention* governance formulation with an ablation that isolates
  which component prevents which failure (no_abstain → invalid-commit 1.0;
  no_provenance → 0.606; no_typing → KEEP-F1 0.0), and (ii) evidence that the same
  benefit transfers to an *LLM* controller (0.8889) and beats an unstructured
  zero-shot decision baseline (0.700, Holm p 1.6e-05). The framework — not the
  rule instantiation — is the claim.
- **Weaken/drop.** Drop any framing that the rule controller is a general-capability
  result. Lead with the *ablation* and the *LLM-controller > zero-shot* result.

## A2. Dataset size and self-authorship

- **Attack.** 180 author-designed scenarios across 6 template families is tiny and
  self-authored; results reflect the author's imagination, not the world.
- **Evidence.** n=180 (60/30/90 split); 6 types × 30; `template_family_id` tracked
  per item; positioned as a diagnostic slice.
- **Honest response.** Correct — MGP-6 is explicitly a diagnostic slice, not a
  benchmark. It is used for *mechanism isolation* (ablations, error direction), and
  every table is labelled as such. External adapters (Mem0/Letta/Graphiti/MemOS)
  are run on the same items to give a non-self-authored comparison surface.
- **Weaken/drop.** Never call MGP-6 a benchmark; never report a single headline
  MGP-6 number without the "author-designed diagnostic slice" qualifier.

## A3. Synthetic-template dependence and rule/template alignment

- **Attack.** The rule controller encodes the labelling manual, so high scores are
  circular: the grader and the system share a source.
- **Evidence.** Leakage audit §4/§8; templates and controller prompts authored in
  one effort; McNemar rule-vs-B2/B4 gives **c=0** (no item where the baseline is
  uniquely correct), i.e. one-directional and design-driven.
- **Honest response.** This is the single most damaging structural critique and it
  is conceded in the audit. Mitigations: LLM controller + zero-shot baselines on the
  same items dilute pure rule/template alignment; `template_family_id` enables a
  family-level holdout. **But the holdout has not been run**, so the residual
  circularity is live.
- **Weaken/drop.** Downgrade "the controller achieves 0.9222" to "on this
  diagnostic slice, whose labels the rule policy is aligned with, ...". The
  defensible cross-system claim is *LLM-controller > zero-shot*, which does not
  share the rule's manual.

## A4. Single-human annotator + LLM-panel (not multi-human IAA)

- **Attack.** Claiming high inter-annotator agreement is misleading: there is one
  human annotator and a panel of LLMs, which is not human IAA.
- **Evidence.** Human κ 0.98146 [0.93997, 1.0], 1 disagreement over 90 test items;
  panel Fleiss κ 0.9815, majority vote 100% vs gold. Docs dated 2026-07-10 predate
  the annotation (2026-07-11) and wrongly state agreement is unmeasured. Human
  review sheet 0/180 filled.
- **Honest response.** Conceded. Must be phrased "one independent annotator plus a
  four-model audit panel". The panel may share the author's reading because the
  manual is unambiguous by construction.
- **Weaken/drop.** Drop the words "inter-annotator agreement"/"human IAA". Report
  the two components separately with their exact caveats.

## A5. MGP-6 full-corpus vs test-split reporting

- **Attack.** Reporting 0.9222 (full corpus) hides that the controller was
  developed on train/dev; only the 90-item test split is legitimate.
- **Evidence.** Test-split rule controller 0.8889/0.9145 vs full-corpus
  0.9222/0.9399; LLM controller test-split 0.900/0.904.
- **Honest response.** Both are in the ledger and both are reported. The 3.3-pp
  drop on the test split is small and the conclusion is unchanged, but the test
  split is the number that belongs in an abstract.
- **Weaken/drop.** Lead with test-split figures; present full-corpus only as a
  labelled secondary column.

## A6. Baseline fairness — are B1–B4 straw men?

- **Attack.** B1 (no-memory), B2 (flat retrieval), B3 (recency), B4
  (naive-overwrite) are weak by construction; beating them is trivial and the c=0
  McNemar tables prove the comparison is rigged.
- **Evidence.** B2 0.1333, B3/B4 0.4222; all have invalid-commit 1.0; rule-vs-B2/B4
  c=0. **But** the zero-shot decision baseline (0.700), the few-shot baseline
  (pending), and the LLM controller (0.8889) are *not* straw men.
- **Honest response.** The classical baselines are diagnostic scaffolding, not the
  competitive comparison. The real bar is the zero-shot LLM decision baseline, and
  the framework beats it by a *tested, corrected* margin (RD +0.189, Holm p 1.6e-05).
- **Weaken/drop.** Don't headline "beats all baselines by 50+ points". Headline the
  zero-shot comparison; present B1–B4 as ablative context.

## A7. External-adapter fairness — mapping freedom + MemOS

- **Attack.** The NOOP→ABSTAIN vs NOOP→KEEP choice lets the analyst pick the
  favourable number, and MemOS's 0.144 is unfair because its adapter can't express
  supersession.
- **Evidence.** Two mappings retained per system (e.g. Mem0 0.622 vs 0.400; Letta
  0.678 vs 0.489); shipped guidance cites NOOP→ABSTAIN as an *upper bound*. MemOS
  cannot observe `replaced_old` → invalid-commit 1.0 structurally.
- **Honest response.** The mapping freedom is a disclosed analyst degree of freedom;
  both numbers are in the ledger and the favourable one is labelled "upper bound".
  MemOS is explicitly `bound_only_structural_limitation`, not a capability claim.
- **Weaken/drop.** Present external adapters as an *upper-bound* comparison with the
  mapping shown; drop any "ASK beats MemOS" phrasing — MemOS's number is a harness
  artifact.

## A8. Statistical power — n=180, SSP n=30

- **Attack.** n=180 (and n=30 per LME competency) is underpowered; the SSP CI
  [0.20, 0.53] is uselessly wide.
- **Evidence.** Wilson/bootstrap CIs throughout; SSP CI width ~0.33; the rule-vs-LLM
  MGP-6 test is *non-significant* (Holm p 0.286) precisely because of limited power +
  a small true gap.
- **Honest response.** Power is genuinely limited. This cuts both ways: it means the
  significant results (rule > B2/B4; LLM > zero-shot) are robust to it, and the
  non-significant one (rule vs LLM) is honestly reported as null rather than spun.
- **Weaken/drop.** Never imply the rule controller is significantly better than the
  LLM controller; report SSP with its wide CI, not as a point estimate.

## A9. Selection bias, judge dependence, and the contradicted 77.2% construction

- **Attack.** The 77.2% carries forward 110 selected v7 successes, replays only
  failures, mixes Gemma/Qwen/Codex-GPT-5 regimes, and mislabels four model
  overrides as human; it is not a run result.
- **Evidence.** The Modal top-up re-evaluates 84/110 carried-forward items: 71
  correct, 13 regressions. Combined raw evidence is 96/154 and the full-180 bound
  is 53.3%-67.8%, so this attempt cannot reach 77.2%.
- **Honest response.** Fully conceded and classified `failure_replay_only`.
- **Weaken/drop.** The value appears only while reconstructing invalid evidence,
  always beside the top-up contradiction; it cannot be a result or headline.

## A10. Missing full-benchmark evaluation — 500-item LongMemEval vs 180 slice

- **Attack.** LongMemEval has 500 items; a 180-item stratified slice is not the
  benchmark and cannot support benchmark claims.
- **Evidence.** Slice = 30×6 seed-0; no full-500 run in the evidence.
- **Honest response.** Correct; the slice is a stratified probe. No LongMemEval
  claim is made as a benchmark result.
- **Weaken/drop.** Drop "evaluated on LongMemEval-M" as if it were the full set;
  say "a stratified 180-item slice of LongMemEval-M".

## A11. Causal attribution — v8 fixes never confirmed on an untouched set

- **Attack.** The v7→v8 fixes were designed on the exact 70 failures and replayed on
  the same 70; the improvement is a training-on-the-test-set artifact.
- **Evidence.** Leakage audit §1; failure ledger F12/F13; 0/19 selected SSP
  failures repaired; 13/84 carried-forward successes regress in the top-up.
- **Honest response.** Conceded — there is no untouched LongMemEval confirmation set.
  The replay is diagnostic, not confirmatory. The frozen homogeneous rerun is the
  required next step and is explicitly outstanding.
- **Weaken/drop.** Drop any "v8 fixes improved LongMemEval by X" causal claim. The
  taxonomy is a v7 diagnostic; replay contexts differ, so even answer-model causal
  attribution is unavailable.

## A12. Overstated safety framing risk

- **Attack.** "Abstention-aware, safe memory governance" oversells: on the only
  externally-sourced task (LongMemEval slice) the controller did **not** beat naive
  overwrite (61.1% vs 63.3%), and SSP sits at 36.7%.
- **Evidence.** Source-of-truth §1; B4 > controller on the contaminated v7 slice;
  v7 SSP 11/30; the top-up observes 8/29 with one unresolved.
- **Honest response.** The "safety" evidence is real but narrow: on MGP-6 the
  controller has invalid-commit 0.0 and only conservative SUPERSEDE→ABSTAIN misses,
  which *is* a safety-relevant property. But that is a within-diagnostic property,
  not a demonstrated end-task safety benefit.
- **Weaken/drop.** Restrict "safe" claims to the MGP-6 invalid-commit/abstention
  behaviour; drop any general "safer memory on long-horizon tasks" phrasing.

## A13. Salami-slicing risk

- **Attack.** MGP-6, LongMemEval slice, SSP taxonomy, external adapters — this looks
  like one modest result sliced into several papers.
- **Evidence.** A single controller, a single evidence base, one ledger.
- **Honest response.** These are facets of one contribution (a governance formulation
  + its diagnostic + its dominant open failure), and they belong in one paper/thesis.
  The SSP taxonomy is an error analysis of the same system, not a separate result.
- **Weaken/drop.** Package as one contribution; do not present the SSP taxonomy or
  the external-adapter table as independent papers.

---

## Five most damaging findings (ranked)

1. **A11/A3 — no untouched confirmation set + rule/label circularity.** The two
   strongest results are structurally compromised: the LongMemEval 77.2% is a
   contradicted carry-forward construction, and the MGP-6 0.9222 comes
   from a system aligned with the labels it is graded against. Neither is a clean
   generalisation result.
2. **A9 — the 77.2% headline is selection-biased and empirically contradicted**:
   the top-up finds 13 regressions and bounds the attempted full result below it.
3. **A6/A1 — the decisive baseline gaps are one-directional (c=0)** against weak
   baselines; the only non-circular competitive win is LLM-controller > zero-shot.
4. **The rule controller is NOT statistically better than the LLM controller**
   (Holm p 0.286) — the "rules win" story does not survive its own significance test.
5. **A12 — on the only external task the controller did not beat naive overwrite**
   (61.1% vs 63.3%) and SSP is 36.7%, undercutting a strong safety/efficacy framing.

---

## Claims that survive (with strength tags)

| Claim | Tag |
|---|---|
| Removing abstention drives MGP-6 invalid-commit to 1.0 and accuracy to 0.5556; removing provenance drives invalid-commit to 0.606 — components are load-bearing for distinct failures (ablation, n=180). | **verified** |
| The rule controller makes only conservative errors on MGP-6 (14 SUPERSEDE→ABSTAIN, invalid-commit 0.0). | **verified** |
| A structured (zero-shot) LLM decision baseline is significantly improved by the governance formulation: LLM controller 0.8889 vs zero-shot 0.700, RD +0.189, McNemar Holm p 1.6e-05. | **verified** |
| The rule controller (0.9222) and the LLM controller (0.8889) are statistically indistinguishable on MGP-6 action accuracy (Holm p 0.286). | **verified** (a null, and it must be stated as such) |
| The rule controller outperforms flat-retrieval and naive-overwrite baselines on MGP-6 by large, one-directional margins. | **supported** (real but design-aligned; must carry the circularity caveat) |
| One independent human annotator (κ 0.98) and a four-model panel (Fleiss κ 0.98) agree with the MGP-6 gold labels. | **supported** (not human IAA) |
| Single-session-preference is the weakest v7 LongMemEval competency (11/30, CI [0.20, 0.53]); 0/19 selected failures repair in replay, while the incomplete top-up reaches at most 9/30. Grounding-supply is primary in 10/19 v7 failures. | **supported diagnostic** (not a stable cross-version score) |
| External memory systems, on the MGP-6 items under a favourable NOOP→ABSTAIN mapping, upper-bound at 0.678 (Letta) / 0.622 (Mem0) / 0.383 (Graphiti); MemOS cannot express supersession. | **suggestive** (mapping- and harness-dependent) |
| Provenance-constrained, typed preference grounding + an answer contract would repair the plurality of SSP failures. | **hypothesized** (proposed design, not run) |
| The governance benefit generalises to real long-horizon tasks / the full LongMemEval benchmark / other base models. | **future_work** (requires the frozen homogeneous rerun, full-500 eval, multi-seed/model runs) |
