# Scientific limitations and historical evidence

This source snapshot is an engineering example. Its deterministic fixture is
synthetic. Running its demo or tests is not a scientific reproduction, a real-
data evaluation, or evidence of user benefit or safety.

## Evidence omitted from this snapshot

The complete benchmark inputs, predictions, judgments, action logs, manifests,
and historical claim ledger are retained outside this public snapshot. In the
reviewed archive checkout, claim verification recorded 38 mismatches associated
with unavailable registered evidence and source artifacts. This snapshot does
not rerun claim verification and does not present the historical numbers below
as results reproduced from these files.

## Historical MGP-6 findings

MGP-6 v2 was an author-designed synthetic diagnostic, not an established
community benchmark. A lookup fitted on training plus development data and
given only `conflict_type` achieved 1.0000 accuracy and 1.0000 macro-F1 on the
held-out 90-item test split. This failed the shortcut-rejection validity gate:
the diagnostic did not distinguish governance reasoning from recognition of
author-visible scenario metadata. Its system scores are diagnostic only.

The later historical 77.2% construction (139/180) is selection-biased and is
not an observed homogeneous run. The raw 135/180 (75.0%) construction is also
not a homogeneous run. The 139/180 construction combines 110 retained successes
from one run, 25 machine-judged replay repairs, and four machine-assisted
semantic overrides. Those overrides are not independent human adjudication.
This constructed figure is failure-replay-only and does not support a
generalized performance claim.

## Historical LongMemEval qualification

The source archive records a homogeneous V12 controller result of 137/180
(76.1%) versus 114/180 (63.3%) for naive overwrite. The run remains
`final_candidate`, not fully frozen, because its launcher hash was stale and
its manifest was not finalized after resume. The run's source artifacts are not
included in this package, so these values are historical records rather than a
reproduced result here.

## Interpretation

The omitted historical ledger contains additional run-level validity findings,
failures, and qualifications. This short record retains the limitations needed
to interpret the selected results without implying that the curated package
reproduces them. The offline demonstration exercises software contracts only.
