# ASK V6: known limitations and intentionally absent material

This public release intentionally excludes private benchmark inputs, private
gold labels, protected benchmark content, and credentials.

Not redistributed:

- MGP-6 hidden_inputs.jsonl
- MGP-6 hidden_gold.jsonl
- any private component map
- protected/raw LongMemEval benchmark content
- API keys and provider credentials

The hidden structural audit is post-hoc and aggregate-only. It supports the
reported construction checks but does not establish shortcut absence, label
correctness, benchmark difficulty, representativeness, or model behaviour.

No private component-map file was available, so equivalence between the proxy
partition and an official private component map was not tested.

The LongMemEval run is exploratory and controller-only. The primary grader
count is 128/180. The 137/180 count is a one-sided post-hoc sensitivity count
after nine manual adjudications.

No fresh matched five-system LongMemEval comparison is included.

Claim Check 4 was performed on frozen Revision 4. Revisions 5 and 6 contain
targeted corrections following that audit and subsequent provenance cleanup.
There was no additional independent full-paper claim check after Revision 4.
