# MGP-Natural

MGP-Natural is a research-engineering repository for constructing a **multi-domain natural-conversation benchmark for candidate-level write-time memory governance**, including action selection, attributable evidence, resulting state, and explicit lineage.

The primary actions are `KEEP`, `SUPERSEDE`, and `ABSTAIN`. `EXCLUDE` is a construction or annotation status, never a model action.

## Tracks

**StudyChat** is the human–LLM task, artifact, interaction-preference, correction, and uncertainty track. The supplied execution input is a sample derivative, not the complete StudyChat export.

**WikiConv** is the human–human collaborative editorial-state and revision-lineage track. It is not characterized as personal-assistant memory.

Track-specific manifests, continuity graphs, splits, statistics, evaluations, headline results, privacy/licensing analysis, and limitations remain separate. The repository does not define a mixed headline score.

## Current execution status

**Verdict: `NO_GO`.** The repository implements and fixture-tests the construction, privacy, blinding, annotation, adjudication, continuity, split, scoring, trajectory, claim, and release interfaces, but the natural-data benchmark is incomplete. The supplied StudyChat archive is a sample derivative; conservative mining yielded two provisional uncertainty candidates in one continuity component, so no valid three-way split exists. Natural WikiConv bytes were not acquired in this runtime.

The local suite currently passes 130 tests, supplementary offline static checks pass, private permissions are verified at exact `0700`/`0600`, the public-package boundary passes, and wheel/sdist plus a two-run synthetic clean-room smoke test pass. Ruff, mypy, the `build` frontend, Python 3.11/3.12, and external security scanners were unavailable in the execution environment and are recorded as blockers or limitations rather than passing gates.

Independent annotation, adjudication, manual privacy review, legal review, mapping reveal, valid natural-data splits, authorship review, venue compliance, and release approval remain external gates. Constructor-label smoke tests are explicitly non-publication-eligible.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
make install
make check
```

To reproduce the private derivative audit from the supplied archive:

```bash
cp /path/to/studychat_audit.zip .private/source/studychat_audit.zip
make reproduce
```

No command publishes, uploads, accepts gated terms, or silently calls a paid model. `make package-public` is expected to stop with a blocking message until recorded human approvals and independent gold exist.

## Important boundaries

- Existing StudyChat `llm_label` values are dialogue-act metadata only. They are not MGP labels and are removed from blind packets.
- Automated privacy scanning supports human review; it does not guarantee anonymity.
- Source wrapper licenses do not automatically resolve underlying conversation-content rights.
- The repository is not a public benchmark release and does not contain independently adjudicated gold.

See `docs/TASK_DEFINITION.md`, `docs/DATA_CONSTRUCTION.md`, `reports/EXECUTION_SUMMARY.json`, and `reports/readiness.json`.

## Full-source private execution

Keep raw sources outside this repository and point `MGP_FULL_INPUTS` to that private directory:

```bash
export MGP_FULL_INPUTS=/absolute/path/to/private/source/files
make full-audit-input
make full-reconstruct-studychat
make full-scan-wikiconv
make full-context-wikiconv
make full-privacy-blind
make annotate-ai-provisional
make full-continuity-splits
make full-validate
make test
make lint
make typecheck
make build
make claim-check-full
make readiness-full
```

Or run the full orchestration target:

```bash
make full-reproduce
```

The raw files are never copied into the repository. `make package-public` remains fail-closed until
human legal, privacy, annotation, adjudication, valid-split, and release approvals are recorded.

