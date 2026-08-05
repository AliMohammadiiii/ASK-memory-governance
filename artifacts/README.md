# Research artifacts

This directory stores machine-readable evidence, derived analyses, and
provenance manifests that support reported results. It is not a workspace for
new runs.

- Raw or row-level inputs take precedence over summaries.
- Derived artifacts must identify their parent inputs and generating command.
- A consumed record is not silently edited to match later expectations. Record
  corrections in a new derived artifact with explicit parentage.
- Large, private, licensed, or identifying inputs remain outside Git. Public
  manifests may record approved hashes and aggregate metadata.
- Narrative claims are checked through `claims/` and the paper-output verifier.

Generated local runs belong under ignored run directories. Promote an output
here only after its scientific role, provenance, privacy status, and generating
procedure are documented.
