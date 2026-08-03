# Next actions to reach a defensible submission

Ordered by critical path, not by convenience.

1. **Freeze authorship and rights.** Resolve v4.3, annotations, model outputs,
   external data, paper license, funding/COI, and all author/OpenReview records.
2. **Commit and reproduce cleanly.** From a clean frozen commit, run
   `make clean-reproduction`; preserve the full environment and output hashes.
3. **Run prospective independent confirmation.** Human-review and freeze
   `confirmation/protocol.yaml` before labels; build the blind packet; obtain at
   least two genuinely independent annotations; preserve originals and
   adjudication; run the preregistered analysis.
4. **Add the minimum breadth that changes the decision.** For TMLR, prioritize
   independent confirmation and a small natural/trajectory challenge over many
   cosmetic baselines. For JMLR, additionally complete model-family,
   cross-storage/native, multi-judge/human, and robustness gates.
5. **Canonicalize the venue manuscript.** Import one authoritative TMLR source
   under `paper/tmlr/`, apply the official template unchanged, reconcile it
   against the 25-claim ledger, and retire competing generated copies.
6. **Build the actual anonymous archive.** Scan source, rendered PDF, PDF
   metadata, supplement, links, file names, acknowledgements, and extracted ZIP.
7. **Final red-team and submission-day review.** Re-check official policies,
   run every gate, inspect the archive independently, hash it, and submit only
   if readiness is `TMLR_GO_ONLY` or `JMLR_GO` as intended.

Do not spend paid inference until the exact frozen matrix and budget receive
explicit authorization. Do not ask an independent annotator to work before the
packet, consent, compensation, and redistribution terms are settled.
