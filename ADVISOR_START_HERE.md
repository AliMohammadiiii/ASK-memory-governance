# Advisor review guide

This repository presents ASK, a storage-agnostic protocol and state-transition
contract for auditable write-time memory governance in long-lived language
agents. MGP-6 is one diagnostic benchmark used in the research. The broader
contribution is the protocol: explicit KEEP, SUPERSEDE, and ABSTAIN decisions;
deterministic transition semantics; configuration and evidence identity;
provenance and supersession lineage; replay; and machine-checkable invariants.

## Recommended reading order

1. Read the compiled manuscript. In the working tree it is at
   `paper/paper_1/compiled/main.pdf`; in the advisor snapshot it is copied to
   `paper/ASK_paper.pdf`.
2. Check `paper/paper_1/contribution_audit.md` for the contribution boundary.
3. Read `docs/ASK_PROTOCOL.md` and
   `docs/architecture/REPOSITORY_ARCHITECTURE.md` for the normative protocol
   and separation between controller, adapter, store, and audit layer.
4. Inspect `claims/claims.csv` and `claims/mismatch_report.json` for the
   evidence-backed claim ledger.
5. Read `reports/GO_NO_GO.md` and `publication/NEXT_ACTIONS.md` before making a
   venue or submission decision.

The manuscript is intentionally anonymous. The current target strategy and
venue-specific constraints are under `publication/`.

## Verification

Use Python 3.11 or 3.12. From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
make advisor-check PYTHON=.venv/bin/python
```

The engineering, claim, trace, data-boundary, and manuscript-drift checks are
expected to pass. `make readiness` is expected to report `NO_GO` until the
listed human, legal, clean-reproduction, and prospective confirmation gates are
actually completed. That status is a disclosure, not a test failure to hide.

## Suggested review questions

- Is the protocol contribution stated clearly enough beyond MGP-6 and the
  controller implementation?
- Are any claims broader than the direct evidence supports?
- Is the current empirical package sufficient for TMLR after the explicit
  blockers are resolved, or should the broader JMLR evidence track be pursued?
- Which prospective confirmation items should be prioritized before submission?

## Sharing boundary

Do not zip or upload the raw working directory. It contains ignored local
evidence trees that are not redistributable. To build a sanitized review copy:

```bash
make advisor-package PYTHON=.venv/bin/python
```

Share `advisor_handoff/ask-memory-governance-advisor.zip`. The archive includes
a SHA-256 checksum and a per-file manifest. It excludes `.private`, external
datasets, local runs, raw independent annotations, application materials,
historical machine-local path records, credentials, and caches.
