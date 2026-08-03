# Repository instructions for coding agents

- Treat this Git root as the authoritative ASK source. Local `runs/`,
  `runs_local/`, `.private/`, and external sibling archives are evidence inputs,
  not source trees to rewrite.
- Never expose hidden labels to model-facing code or rescore a consumed hidden
  split for model selection. Historical runs and manifests are immutable.
- Verify every paper number through a generating command and the claim ledger.
  Paper tables must be generated or drift-checked, never silently hand-edited.
- Preserve the public/private boundary. Do not add LongMemEval data, private
  mappings, raw independent annotations, provider keys, or local absolute paths
  to tracked files.
- Do not make paid API calls without explicit approval. Build and validate dry
  runs first, then record pending authorization and estimated cost separately
  from observed cost.
- Do not fabricate results, independent annotation, legal approval, native
  external-system execution, or successful reproduction.
- Do not rewrite historical manifests to look clean. Add derived manifests with
  explicit parentage and anomaly notes.
- Do not use destructive Git commands, rewrite history, amend, force-push, or
  discard user changes. Do not commit or push unless explicitly requested.
- Scientific prose is direct English, uses no em dash, and separates result from
  inference. Do not claim priority, SOTA, universality, safety, certification,
  independent audit, population generalization, or native system superiority
  without new direct evidence.
- Use `make help` for authoritative commands. The local supported interpreter is
  Python 3.11 or 3.12; when system Python differs, run
  `make <target> PYTHON=.venv/bin/python`.
