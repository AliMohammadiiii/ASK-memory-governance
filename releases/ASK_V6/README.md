# ASK V6 audited release

## Paper

ASK: Explicit, Inspectable Write Decisions for Persistent Agent Memory

Frozen PDF:

`ASK_V6_FINAL.pdf`

PDF SHA-256:

`8702320fb916217d69ae6b152f47d23584f4d6e9b80c2653c17008cbc590c5f1`

Frozen source archive SHA-256:

`71894114ef0ea717153937bdab944b1380d24635cc8a3eda6b5fcc9e582ff855`

## Historical evaluated baseline

`f6bf66e4766d769727edf6b42c76b9977b14978a`

## Post-hoc audit branches

Validator hardening:

- branch: `audit/validator-hardening`
- commit: `4fc32ca38e7ec0ff4b50897531b704289f0d3e0a`

Parser JSON-fence normalization:

- branch: `audit/parser-json-fence-normalization`
- commit: `30b4f0cd68fe67f1bec729b3e928b7b22aa6665a`

These audit commits post-date the reported evaluations and are deliberately
kept separate from the historical evaluated baseline.

## Repository layout

- Paper source: `paper/ASK_V6/`
- Frozen release files: `releases/ASK_V6/`
- Audit supplement: `supplement/ASK_V6/`

## Build

From `paper/ASK_V6/`:

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Read `supplement/ASK_V6/KNOWN_LIMITATIONS.md` before interpreting results.
