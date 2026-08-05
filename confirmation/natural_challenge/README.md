# Natural-write confirmation track

Status: `QUARANTINED_CANDIDATE_NOT_GOLD`.

This directory contains only aggregate audit and verification evidence for the
externally supplied MGP-Natural v0.1.0 candidate. It contains no raw dialogue,
provisional labels, source identifiers, private blinding key, annotator rows, or
gold data.

The parent candidate is useful as a feasibility seed, but it is not a valid
held-out benchmark:

- all 36 labels are single-curator provisional seed labels;
- the parent blind packet exposes `relation_to_prior` and source IDs, allowing
  deterministic recovery of all 36 provisional actions;
- page-family and contributor continuity produce two connected components of
  sizes 35 and 1, so the declared 24/6/6 split is not independent;
- consent or public-data basis, privacy review, attribution, modification
  notice, and redistribution approval are not complete; and
- exact source extraction and normalization cannot be reconstructed from the
  supplied archive alone.

The repository therefore derives only a private annotation draft. The derived
packet uses an allowlist projection, removes source locators and constructor
evidence, assigns HMAC-ordered `N` identifiers, and stores the reveal map and
secret below `.private/`. Public packaging is intentionally blocked.

Run the audited workflow with local input paths:

```bash
export MGP_NATURAL_ARCHIVE=/path/to/MGP-Natural-v0.1.0-release.zip
export MGP_NATURAL_DELIVERY_REPORT=/path/to/delivery-report.txt
export MGP_NATURAL_RESEARCH_REPORT=/path/to/research-report.txt

make mgpn-natural-audit PYTHON=.venv/bin/python
make mgpn-natural-manifest PYTHON=.venv/bin/python
make mgpn-natural-build-private PYTHON=.venv/bin/python
make mgpn-natural-verify-private PYTHON=.venv/bin/python
```

`mgpn-natural-package-public` must remain blocked until the human, legal,
privacy, independent-annotation, adjudication, and independent-split gates are
all satisfied. Synthetic paraphrases do not satisfy the natural-data gate.

See `reports/MGP_NATURAL_FINALIZATION.md` for the engineering verdict and
`reports/MGP_NATURAL_DATASET_LANDSCAPE_2026_08_03.md` for the audited research
landscape.

## MGP-Natural v0.2.2 full-workspace intake

The repository also contains the supplied v0.2.2 construction software under
`third_party/mgp-natural-v0.2.2/`, together with its schemas, tests, scripts,
and synthetic fixtures. The supplied `full` directory is a private derived
workspace, not the original raw-source archive layout. It includes source text,
blinding material, and other private artifacts, so it is never copied here.

`make mgpn-natural-full-intake` produces only the path-neutral receipt in
`mgp_natural_v0_2_2_full/intake_audit.json`. The current receipt records
workflow counts and a safe ZIP check, but it does not verify original source
archives, establish text rights, produce independent gold, or authorize a
release. See `reports/MGP_NATURAL_V0_2_2_INTAKE.md`.
