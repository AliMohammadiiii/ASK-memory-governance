# MGP-6 v4.3.0-human-validated-final

The repository integrates the public train/dev release at
`benchmarks/mgp6/mgp6_v4_3/public/`. The release is a human-authored,
template-guided, controlled synthetic diagnostic for `KEEP`, `SUPERSEDE`, and
`ABSTAIN` decisions, not a deployment-generalization benchmark.

The public release comprises 180 train and 180 development records. The locked
release has 900 items in 100 components: 20/20/60 components and 180/180/540
items across train/dev/hidden. Train and dev are exactly balanced by action.
Hidden inputs, hidden gold, human gold, annotations, mappings, consensus, and
audit material live only under the ignored `.private/benchmarks/mgp6/v4.3/`
boundary. LongMemEval remains a separately reported external evaluation.

See `release_metadata/RELEASE_FACTS.json` beside the public data and
`experiments/mgp6_v43/FROZEN_CONFIG_INDEX.json` for the current execution gate.
