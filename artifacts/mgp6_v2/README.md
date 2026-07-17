# MGP-6 v2 per-item evidence

This directory restores the per-item prediction artifacts needed to reproduce
the MGP-6 v2 tables and run dependence-aware analyses. They were mechanically
extracted from the immutable source archive
`mgp6_v2_COMPLETE_2026-07-11.zip` (SHA-256
`76594b2895e619e240072f5a6bff42580fd27ba0d518c74e14190575f1e739ec`),
already registered in `artifacts/manifests/source_archives.json`.

Included:

- deterministic reference systems and ablations;
- structured and zero-shot LLM decision predictions;
- the incomplete six-shot predictions (174/180; never a final result);
- external-adapter predictions under the disclosed `NOOP -> ABSTAIN` mapping.

Raw provider logs are intentionally excluded. The files contain synthetic
MGP-6 scenarios and model outputs only; they contain no credential values.

Run the construct-validity and cluster-aware audit with:

```bash
python3 scripts/analysis/audit_mgp6_validity.py
```

The generated reports under `artifacts/analysis/` quantify shortcut leakage,
family- and minimal-pair-cluster uncertainty, calibration, false-commit and
missed-update rates, and cost sensitivity. These analyses do not make the
author-designed collection independent; they make its limitations measurable.
