# M2-W5 Literature Note

Sources checked: HaluMem (Chen, Niu, et al.,
https://arxiv.org/abs/2511.03506), Mem0 (Chhikara et al.,
https://arxiv.org/abs/2504.19413), Memory-R1 (Yan et al.,
https://arxiv.org/abs/2508.19828), and FadeMem (Wei et al.,
https://arxiv.org/abs/2601.18642).

## HaluMem Extraction Errors To Defend Against

- **Fabrication / invented facts.** HaluMem frames memory hallucination at the
  operation level, not only as downstream QA error. The extractor must not turn
  assistant acknowledgements, greetings, benchmark prefixes, or adjacent context
  into new memories.
- **Semantic error / attribute misassignment.** The extracted statement must
  preserve subject and attribute. "My sister likes tea" cannot become "User
  likes tea"; "I do not like coffee" cannot become a positive preference.
- **Omission pressure without precision collapse.** HaluMem separates extraction
  hallucination from omission. This week is intentionally precision-biased, but
  the coverage monitor tracks the opposite failure mode: extracting nothing.

## Patterns To Borrow

- **Mem0:** separate extracting salient facts from later consolidation and
  retrieval. This supports a small `ExtractionOutput` contract rather than a
  controller decision inside the extractor.
- **Memory-R1:** make memory operations explicit (`ADD`, `UPDATE`, `DELETE`,
  `NOOP` in that paper). For this week, the analogue is a first-class
  no-content output instead of forcing every turn into an item.
- **FadeMem:** memory lifecycle matters. Even though decay is out of scope here,
  the prompt should produce enough diagnostic metadata now, especially markers,
  so later lifecycle/error analysis is possible without a schema migration.

## Patterns To Reject

- **Broad "salience" extraction.** Mem0-style production memory systems can
  reward recall and personalization breadth. This thesis stage rejects that
  bias because upstream over-extraction contaminates later relation labels.
- **Extractor-side updating or conflict resolution.** Memory-R1 and FadeMem
  motivate update/fusion operations, but W5 should only admit candidate rows.
  Relation classification and supersession decisions belong to W7 and M3.
- **Automatic prompt relaxation.** Fade/decay systems act on coverage and
  importance. W5 has no gold labels yet, so low coverage triggers only an alarm;
  automatic relaxation would trade a detectable silence problem for silent
  false memories.
