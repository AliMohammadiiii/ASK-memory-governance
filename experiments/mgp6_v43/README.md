# MGP-6 v4.3 experiment control plane

Versioned configurations are stored in `configs/experiments/mgp6_v43/` to
follow the repository-wide configuration convention. Runtime outputs belong in
the ignored `runs/mgp6_v43/` hierarchy. This directory holds the freeze index
and must never contain hidden gold, completed annotations, or model-facing
private metadata.

The selected ASK live-model-controller completed its one authorized hidden run.
The 540-item prediction file was coverage-validated and sealed before
local-private scoring; its SHA-256 is
e6a598799115c9fc80ae3e731f1b5d59a4947e48df5356b12ba518bafb846806. The
tracked final report contains aggregate metrics only. Do not rerun this consumed
final configuration or place private inputs, gold, annotations, mappings, or raw
responses in this directory.
