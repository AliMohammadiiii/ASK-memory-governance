# MGP-Natural v0.2.2 private-workspace intake

Status: `QUARANTINED_PRIVATE_DERIVED_WORKSPACE`.

This record is generated from
`confirmation/natural_challenge/mgp_natural_v0_2_2_full/intake_audit.json`.
It documents the supplied private derivative workspace without importing its
conversation text, source identifiers, mappings, labels, annotations, or
secrets into the repository.

## What the intake verified

- The supplied layout contains the expected 18 private-workspace artifacts.
- The annotation-bundle ZIP passed structural integrity checks and the auditor
  rejects duplicate names, encryption, symbolic links, and unsafe member paths.
- The aggregate receipt records 16,851 private StudyChat rows, 431 StudyChat
  redacted construction items, and 54 WikiConv redacted construction items.
- It records 4,706 automated privacy findings and 485 redaction-log rows.
- The vendored MGP-Natural v0.2.2 code, scripts, schemas, configurations,
  documentation, and rights-cleared synthetic fixtures are in
  `third_party/mgp-natural-v0.2.2/`. Its isolated test suite passes 132 tests
  locally through `make mgpn-natural-v022-test PYTHON=.venv/bin/python`.

These are private-workflow and engineering counts. They are not counts of
independently labeled benchmark examples, independent source conversations, or
evaluation observations. No paper table, performance metric, confidence
interval, or mixed-track headline is derived from them.

## What remains unverified or blocked

The supplied directory is a **derived workspace**, not the original 13-file
raw-source archive layout. The receipt therefore sets
`raw_source_archive_integrity_verified: false`. It does not reproduce source
acquisition, establish rights to underlying text, or verify the original
StudyChat and WikiConv source manifests.

Publication remains ineligible. The following gates remain open:

1. Reacquire and integrity-audit the original source archives outside Git.
2. Obtain explicit source-content, attribution, modification, consent,
   privacy, and redistribution decisions.
3. Complete manual privacy review after redaction.
4. Freeze the protocol before independent annotation.
5. Collect independent annotations and separate adjudication.
6. Build and review continuity-aware, track-specific splits before any score.

Run the aggregate audit with:

```bash
export MGP_NATURAL_FULL_INPUTS=/path/to/private/workspace
make mgpn-natural-full-intake PYTHON=.venv/bin/python
```

The command never copies the supplied workspace into the repository. It records
the input directory only as `$MGP_NATURAL_FULL_INPUTS` and deliberately omits
the private-secret hashes from its public receipt.
