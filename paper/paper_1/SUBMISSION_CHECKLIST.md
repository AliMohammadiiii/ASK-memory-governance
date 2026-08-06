# Submission readiness checklist

Status date: 2026-08-06. Manuscript: `main.tex` (47 pp: 43 pp body + appendix).
Verification script: `scripts/check_manuscript.py` (run from repo root).

This file records what has been mechanically verified, what remains open, and
what must be re-run after any venue template change. It is a working gate, not
a claim of acceptance readiness.

## A. Mechanically verified (2026-08-06)

| Check | Result |
|---|---|
| `pdflatex` + `bibtex` + 2x `pdflatex` | exit 0, no rerun flag outstanding |
| Undefined citations / references | 0 |
| Overfull hboxes | 1 remaining, 0.75 pt (negligible; was 2, incl. one at 69.8 pt) |
| BibTeX warnings | 0 |
| Bibliography coverage | 37 cited / 37 defined; 0 orphans, 0 missing |
| arXiv identifiers resolved against the arXiv API | 20/20 resolve |
| DOIs resolved against Crossref | 6/6 resolve to the cited work |
| Repository URLs (MemPatch, WRIT) | HTTP 200 |
| Hidden-split numbers vs `mgp6_v43_full_benchmark_analysis.json` | 44/44 exact (asserted by `check_manuscript.py`) |
| Derived arithmetic (CI widths, latency ratios, guard bound) | all reproduce |
| `\ref` targets without labels | 0 |
| Figures/tables referenced but missing on disk | 0 |

### AI-writing-signal scan (against the supplied 120-item checklist)

Strong signals — all zero: no placeholders (`[Insert…]`, `TBD`, `2025-XX-XX`),
no ChatGPT/Gemini/Grok/Perplexity markup leakage (`oaicite`, `contentReference`,
`turn0search0`, `[cite: 1]`, `:::writing`), no `utm_source=chatgpt.com`, no
assistant-voice residue, no fabricated citations, no unused-but-defined
references, no mid-sentence truncation.

Medium signals — all at or near zero: no cliché openers or transitions
("it is important to note", "in today's…", "despite these challenges"),
no `not only X but also`, no trailing participial summary clauses, no
promotional vocabulary, no vague attribution ("experts believe", "studies
show"), no boilerplate Challenges/Future-Outlook/Key-Takeaways sections, no
emoji, no em-dash overuse (zero em-dashes), 6 `\textbf` uses total.
AI-vocabulary density is 17 tokens across ~35k words, and each is used in its
technical sense (`harness` = evaluation harness; `robust` once; `additionally`
three times).

Sentence-length coefficient of variation is 0.74 overall (range 0.41–1.28
across sections), i.e. high burstiness — the opposite of the flat rhythm the
checklist flags. The 35 `X, Y, and Z` triples are technical enumerations
(`action, state, lineage`), not adjective padding.

**Conclusion: the checklist does not fire on this manuscript.** The prose reads
as author-written technical writing with an unusually disciplined hedging
register.

## B. Fixed in this pass

1. **Citation pointed at a retitled paper.** `reddy2026deterministic` cited
   arXiv 2606.01435 as "Don't Ask the LLM to Track Freshness: A Deterministic
   Recipe for Memory Conflict Resolution". That was the v1 title; v2 (2026-08-02)
   is "Reliable Post-Retrieval Assembly for Agent Memory: Separating Evidence
   Extraction from Policy Execution". This is checklist item 97 (valid DOI,
   wrong paper) — the single highest-risk citation defect a reviewer can find,
   because it is trivially checkable. Entry retitled, second author's name
   corrected to *Sumanth Reddy Challaram*, `note` field records the v1 title,
   and the related-work sentence now describes what the paper actually argues.
2. **Overfull hbox (69.8 pt).** The ten-element event tuple was set inline;
   now displayed.
3. **Abstract rebalanced.** The closing paragraph previously ended on
   MGP-Natural — a non-result — giving a quarantined artifact the final
   emphasis. It now closes on the contribution boundary, and the two
   instruments are framed as complementary (labels without realism / realism
   without labels) rather than as the paper's identity. All disclosures are
   preserved verbatim in substance.

## C. Open before submission

### C1. Blocking

- [ ] **Venue template.** Source is venue-neutral `article` 11pt. TMLR requires
      its own stylefile and forbids formatting changes; TMLR reviews are
      **not** anonymous by default, so the current `\author{Ali Mohammadi}`
      is correct for TMLR but must be removed if a double-blind venue is
      chosen. `VENUE_VARIANT_README.md` already gates this correctly.
- [ ] **Redistribution licence for MGP-6 v4.3.** The paper states no licence
      has been selected. TMLR/JMLR reviewers will ask whether the diagnostic is
      obtainable. Either select a licence or state the access procedure
      explicitly in the artifact appendix.
- [ ] **Two V12 provenance gaps** (stale launcher hash; manifest not written to
      terminal status after resume). Disclosed in §9, which is the right call,
      but closing them is cheap and removes a reviewer objection.

### C2. Recommended

- [ ] **Three orphan tables** are generated but never `\input`:
      `tables/external_systems.tex`, `tables/lme_competency.tex`,
      `tables/mcnemar.tex`. Their content is covered by `lme_competency_full`
      and `v43_mcnemar`. Either drop them or fold the external-systems table
      into an appendix — as-is they are dead files a reproducer will trip over.
- [ ] **Three orphan figures** likewise unused: `lme_competency_heatmap.png`,
      `lme_system_accuracy.png`, `lme_v12_systems.png`.
- [ ] **Length.** 47 pp is within TMLR's variable-length policy but long. If a
      reviewer complains, §6.11 (the v2 pilot, ~6 pp) is the natural appendix
      candidate: it is explicitly framed as a negative result and nothing in
      §7–§10 depends on its details.
- [ ] **OpenReview-hosted citations** (LongMemEval, MEMIT, PrefEval, PersonaMem)
      were not machine-verified — the sandbox could not reach the API. Confirm
      the four forum IDs by hand before submission.

## D. What would strengthen the paper scientifically

Ordered by return on effort. None is required for submission; items 1–2 are
what a reviewer is most likely to demand.

1. **A hidden-split baseline.** The single strongest objection available to a
   reviewer is that *every* comparison is on the split used for selection. The
   one-shot protocol is honest and well executed, but it means the headline
   0.8481 has nothing to be compared against. Authorising **one** additional
   hidden run for the naive-overwrite baseline would convert the paper's main
   result from "one number" to "one contrast", at the cost of one more
   pre-registered run. This is the highest-value remaining experiment.
2. **MGP-Natural.** As the abstract concedes, both instruments are
   author-constructed. Even a small independently annotated natural-dialogue
   set (100–200 items, three blinded annotators) would move the external-validity
   claim from "future work" to "preliminary evidence". The construction
   workflow already exists at v0.2.2; the gate is rights review and annotation,
   not software.
3. **Calibrate the abstention.** The disclosed defect — selective accuracy
   0.8449 < overall 0.8481 — is reported openly, which is to the paper's
   credit. But a reviewer will ask whether a threshold sweep on *development*
   fixes it. If it does, that is a real result; if it does not, that is a
   stronger negative finding than the current one-line disclosure.
4. **A second model backbone.** Every model-backed row is `qwen/qwen3.5-9b`.
   Running the frozen controller on one more backbone at development would show
   whether the composition effect is model-specific. Cheap, and it pre-empts
   the "n=1 model" objection.

## E. Re-run after any change

```bash
export PATH="/Library/TeX/texbin:$PATH"
cd paper/paper_1
pdflatex -interaction=nonstopmode main && bibtex main \
  && pdflatex -interaction=nonstopmode main \
  && pdflatex -interaction=nonstopmode main
python3 ../../scripts/check_manuscript.py     # from repo root
```

Regenerate tables from raw artifacts rather than editing them by hand: the
`v43_*.tex` and `lme_*.tex` files are auto-generated, and
`artifacts/analysis/mgp6_v43_full_benchmark_analysis.json` is the source of
truth.
