# Security review

## Result

The maintained offline package and reproducibility constraints pass local
security checks. Public release remains conditional on the existing legal,
privacy, and independent-review gates.

## Checks executed

- The repository validator found no committed credential, private-key, or
  machine-local path pattern in public candidates.
- Pinned pre-commit hooks check private keys, structured-file syntax, conflicts,
  line endings, Ruff lint, and Ruff formatting.
- `pip check` passed in the clean base-package installation.
- `pip-audit -r constraints/repro-py312.txt` reported no known vulnerabilities.
- The maintained ML lock pins `transformers==5.14.1` and
  `sentence-transformers==5.6.1` with exact transitive versions.
- Hugging Face answerer, judge, embedder, server, and runner paths accept and
  propagate immutable model revisions. Remote code remains disabled by default.
- The embedding server now binds to `127.0.0.1` by default and requires an
  explicit flag before trusting remote model code.

## Environment separation

The pre-existing feature-rich local virtual environment also contains external
memory-system packages. An audit of that mixed environment found 18 advisories
across `cryptography`, `diskcache`, `fastmcp`, `starlette`, and the former
Transformers 4.x installation. Those packages are not part of the clean core
constraint set. Transformers was upgraded for the maintained ML extra.

MemoryOS 2.0.23 still requires Transformers 4.x. Its exact external lock retains
Transformers 4.57.6 in a separate research-only environment. `pip check` and
imports for Mem0, Graphiti, Letta, and MemOS passed there. The environment uses
no production secrets and is not approved for production deployment.

## Remaining security actions

- Populate immutable Hugging Face commit revisions in each new recorded
  local-model configuration. Existing records remain unchanged where a revision
  was never observed.
- Re-audit the external-baseline environment before each use and replace or
  isolate packages with unresolved advisories.
- Keep release packaging blocked until the legal and privacy matrices receive
  human approval.
