# ASK integration record: MGP-Natural v0.2.2

This directory vendors the supplied MGP-Natural v0.2.2 **software only**:
Python sources, command-line scripts, tests, schemas, configurations, and
documentation. It is kept as a separate Apache-2.0 component so that its
research-construction workflow, release gates, and source-data restrictions
remain visible rather than being silently presented as ASK benchmark evidence.

The following external artifacts are deliberately excluded:

- StudyChat, WikiConv, Wikipedia, and any other source conversations;
- source manifests that enumerate private source files or their contents;
- constructed items, mappings, blinding secrets, packet outputs, annotations,
  adjudications, gold labels, scores, and generated reports; and
- the companion package's paper/result artifacts and built distributions.

The exact supplied private workspace is inspected only through
`make mgpn-natural-full-intake`; that command emits a path-neutral aggregate
receipt and remains non-publication-eligible. The vendored test suite can be
run without any private source data:

```bash
PYTHONPATH=third_party/mgp-natural-v0.2.2/src \
  .venv/bin/python -m pytest -q third_party/mgp-natural-v0.2.2/tests
```

The original component license is retained in [LICENSE](LICENSE). Its data and
content exclusion governs the files in this directory.

Two test-only integration adjustments are documented here. The execution-summary
test builds its required aggregate-report fixture in a temporary directory
instead of relying on excluded generated reports. The privacy test constructs a
secret-shaped scanner input at runtime so the parent repository's source-secret
scan can remain fail-closed. Neither adjustment changes construction, privacy,
blinding, annotation, scoring, or release behavior.
