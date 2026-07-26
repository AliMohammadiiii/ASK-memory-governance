# MGP-6 v4.3 experiment control plane

Versioned configurations are stored in `configs/experiments/mgp6_v43/` to
follow the repository-wide configuration convention. Runtime outputs belong in
the ignored `runs/mgp6_v43/` hierarchy. This directory holds the freeze index
and must never contain hidden gold, completed annotations, or model-facing
private metadata.

The selected ASK live-model-controller is frozen for one hidden-prediction
generation. `FINAL_HIDDEN_CONFIG.json` and
`FINAL_HIDDEN_RUN_AUTHORIZATION.json` bind its public controls to successful CI
run `30189412351` at commit `af12517a15c9d9af4bb3bf95f7caee7330e6b243`. They
authorize prediction generation only: close the run, validate coverage, and
hash the predictions before any separate local-private scoring step.
