# TMLR Readiness Standard

## Scope

This file defines evidence needed for a serious TMLR submission. It does not declare the current repository publication-ready.

## Machine-actionable gates

- input scope audited and hashes pinned;
- source manifests recorded;
- reconstruction validated against anomalies and fixtures;
- versioned schemas and semantic validators pass;
- candidate mining and reason-coded exclusion pass;
- privacy scan and redaction artifacts exist;
- blind packet passes allowlist and nested leakage checks;
- continuity graphs and component-isolated splits pass;
- annotation, adjudication, and scoring validators pass fixtures;
- build and clean-room reproduction pass;
- claim ledger and public-package boundary pass; and
- current venue requirements are recorded from official sources.

Passing these gates demonstrates working infrastructure, not completed benchmark evidence.

## Human gates

- legal and redistribution approval for the exact release form;
- manual privacy review;
- annotation protocol approval;
- independent annotation by at least three annotators per item;
- independent additive adjudication;
- mapping reveal authorization;
- authorship and conflict confirmation;
- venue compliance review; and
- explicit release decision.

## Scientific evidence gates

A TMLR-quality release candidate should ordinarily contain at least 300 independently adjudicated natural items per source track, meaningful support for all three actions, complete evidence supervision, reconstructable `SUPERSEDE` states, valid continuity-disjoint splits, descriptive statistics, calibrated baseline comparisons, uncertainty intervals, and a documented error taxonomy. These are planning targets subject to natural yield and human approval, not quotas that justify duplication or weakened validity.

## Current blockers

The machine-generated verdict is `NO_GO`. The supplied StudyChat input is a sample derivative; its two surviving provisional candidates form one authoritative continuity component, so development and hidden-test splits are empty. Natural WikiConv source bytes were not materialized because the code runtime could not resolve official hosts. No independent annotation, adjudication, legal approval, manual privacy approval, model experiment, or release decision exists.

The code and synthetic-fixture infrastructure can be reviewed, but even `PRIVATE_PILOT_READY` is prohibited until manual privacy review and protocol approval are recorded. Ruff, mypy, the `build` frontend, Python 3.11/3.12, and external security scanners were unavailable in this environment; supplementary checks and an offline build fallback passed but do not replace those named-tool gates.

