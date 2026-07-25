# MGP-6 v4.3 experiment control plane

Versioned configurations are stored in `configs/experiments/mgp6_v43/` to
follow the repository-wide configuration convention. Runtime outputs belong in
the ignored `runs/mgp6_v43/` hierarchy. This directory holds the freeze index
and must never contain hidden gold, completed annotations, or model-facing
private metadata.

The current index is intentionally development-only. It does not authorize a
hidden prediction or scoring run.
