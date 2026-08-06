# Prompt registry

Prompt templates remain separate files so experiment manifests can hash their
exact bytes. `registry.yaml` assigns each template a stable identifier, purpose,
status, lineage, and related evidence.

Run `make prompt-check` after changing the registry. Do not edit a prompt that
has already produced reported evidence. Add a new version, update the registry,
and point future configurations to it.
