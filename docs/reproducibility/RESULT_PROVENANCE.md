# Result provenance

The supported result chain is:

```text
source data
-> validation and split contract
-> preprocessing or typed candidate formation
-> prompt and experiment configuration
-> execution and raw outputs
-> scoring and statistical analysis
-> generated tables and figures
-> claim ledger
-> paper and thesis statements
```

For each reported value, a reviewer must be able to recover the dataset and
split, data hash, code commit, environment, system and provider identifiers,
prompt hash, configuration hash, seed, command, raw output, metric code, derived
table or figure, and final claim identifier.

`claims/claims.csv` and `claims/source_inventory.json` connect public claims to
their evidence. `artifacts/manifests/` records repository files, source archives,
and derived parentage. `paper/paper_1/claims_evidence_matrix.md` and the thesis
claim matrix restrict how those values may be described.

MGP-6 v4.3 private labels and mappings remain outside Git. Public records expose
only the material required for the declared public workflow. LongMemEval input
is external and not redistributed. The completed V12 local evidence is checked
through a derived manifest that names its historical parent and recorded
anomalies.

Paper and thesis numbers are verified through generating commands. Hand edits
to a result table are not an accepted provenance path.
