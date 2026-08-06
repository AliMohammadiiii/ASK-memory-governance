# Publication strategy: speed, credibility, and defensible acceptance

Current decision: **submit nowhere yet (`NO_GO`)**.

## Primary route after the shared gates pass: TMLR

TMLR is the best current balance for this work because it uses rolling,
double-blind review, explicitly emphasizes technical correctness over subjective
significance, supports artifact material, and is designed for shorter turnaround
and sustained author--reviewer interaction. This is a fit argument, not a claim
about acceptance probability. Official sources: [TMLR overview](https://www.jmlr.org/tmlr/),
[author guide](https://jmlr.org/tmlr/author-guide.html), and
[editorial policies](https://jmlr.org/tmlr/editorial-policies.html).

Submit to TMLR only after all shared gates pass: rights, clean reproduction,
prospective confirmation, independent annotation, anonymity, final authorship,
OpenReview profiles, and current policy review. Lead with ASK as the auditable
protocol; treat MGP-6 as controlled evidence and disclose V12 provenance.

## Higher-burden route: JMLR

JMLR is credible but is not currently the fast or defensible first submission.
Its scope expects broad ML interest, principled insight, and sound validation;
the current artifact lacks the independent natural-write, trajectory,
model-family, cross-storage, multi-judge/human, and robustness evidence needed
to make that case. JMLR also notes that some papers may take a long time to
review, and long manuscripts can be harder to place. Official source:
[JMLR information for authors](https://www.jmlr.org/author-info.html).

Reconsider JMLR only after every JMLR-only gate passes and the manuscript
demonstrates a general lesson about auditable learning-system state transitions,
not merely a larger diagnostic or more baselines.

## Decision rule

- `JMLR_GO`: all shared and JMLR-specific gates pass; choose JMLR only if the
  authors accept the likely time/effort trade-off.
- `TMLR_GO_ONLY`: submit the anonymous, frozen TMLR package.
- `NO_GO`: do not submit; execute `NEXT_ACTIONS.md`.

No venue has a defensible guaranteed acceptance probability. Inflating claims,
hiding negative evidence, or treating templates as completed work would reduce
rather than increase the real acceptance chance.
