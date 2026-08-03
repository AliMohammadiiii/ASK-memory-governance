# Initial publication-artifact audit

Audit date: 2026-08-02

## Status at discovery

`NO_GO`

The manuscript wording is defensible, and the existing offline source gate is
strong, but mandatory release, claim, clean reproduction, confirmation,
independent annotation, and venue administration gates are not complete.

## Verified at discovery

- Git and Serena resolve to the same repository root.
- The starting worktree was clean at commit
  `51decd61c297cdd2af0f3227e79307baa4df5697`.
- `make check PYTHON=.venv/bin/python` passed with 536 tests and 14 documented
  optional skips.
- Direct private scoring of the consumed MGP-6 v4.3 hidden predictions reproduced
  accuracy `0.8481481481481481`, macro-F1 `0.847872957121512`, the 3 by 3
  confusion matrix, and the 5,000-replicate component-cluster intervals.
- The implemented ASK-MGP guard only replaces a model `ABSTAIN` with a decisive
  public-evidence `KEEP` or `SUPERSEDE`; it leaves model `KEEP` and `SUPERSEDE`
  unchanged.
- The preserved V12 action log and aggregate reports exist locally.

## Critical gaps

| ID | Gap | Consequence |
|---|---|---|
| A1 | No root repository-specific `AGENTS.md` | future agents can miss private-data and claim rules |
| A2 | No canonical typed ASK protocol/state machine | audit semantics are distributed across runtime code and prose |
| C1 | No machine-enforced headline claim ledger | manuscript values can drift from evidence |
| C2 | Several paper tables are labelled generated but lack one authoritative drift gate | hand edits are not reliably detected |
| R1 | No clean isolated reproduction record for the current v4.3/V12 paper | replay and full reproduction remain conflated |
| P1 | V12 original manifest is not final and records a failed/resumed launcher | clean provenance cannot be claimed retrospectively |
| L1 | Dataset, annotation, model-output, and third-party redistribution decisions are incomplete | public artifact release remains blocked |
| H1 | Independent confirmation and authenticated independent annotation are incomplete | TMLR and JMLR mandatory gates fail |
| J1 | Natural write-labelled trajectories, multi-model breadth, cross-storage evidence, and multi-judge validation are absent | JMLR breadth gates fail |
| V1 | Current JMLR, TMLR, and OpenReview requirements are not yet captured from official sources | venue compliance is pending |

## Baseline command issue

Plain `make check` selected Homebrew Python 3.14, outside the supported 3.11 to
3.12 range, and failed because that interpreter lacked Ruff. The repository
virtual environment uses Python 3.12.12 and passed the gate. Authoritative local
commands must either activate `.venv` or pass `PYTHON=.venv/bin/python`.
