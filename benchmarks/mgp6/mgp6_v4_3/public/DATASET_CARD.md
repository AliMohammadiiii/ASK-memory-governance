# MGP-6 v4.3 Dataset Card

## Identity

MGP-6 v4.3 is a **human-authored, template-guided, controlled synthetic benchmark** for decision-level governance of long-lived personalized memory.

## Task

For each dialogue, predict one action:

- `KEEP`: retain the existing stored value.
- `SUPERSEDE`: replace it with the proposed value.
- `ABSTAIN`: do not commit a change because material evidence remains unresolved.

## Size and split

- 900 items
- 100 semantic components
- Train: 180 items / 20 components
- Dev: 180 items / 20 components
- Hidden: 540 items / 60 components
- Exact class balance in every split
- Components are never cut across splits
- Every domain contributes one component to train, one to dev, and three to hidden

## Human validation

Two completed human annotation packets cover all 900 items. Their labels agree on all items (`Cohen's kappa = 1.0`). No label adjudication or exclusion was required. Human completion is accepted based on an explicit data-owner attestation. Reviewer identity was not independently authenticated by the release builder.

## Shortcut controls

The final split is component-held-out. Word, character, identifier, punctuation, length, restricted-view, and shallow-tree baselines are recorded in the private audit package.

## Intended use

- Controlled evaluation of memory update policies
- Abstention and selective-decision evaluation
- Ablation studies
- Comparison with external memory benchmarks

## Limitations

- Constructed scenarios are not a substitute for real-world deployment evaluation.
- The benchmark should be paired with an external benchmark such as LongMemEval.
- Human completion is owner-attested rather than cryptographically identity-verified.
- Public redistribution terms were not supplied in this conversation; select a license before public hosting.
