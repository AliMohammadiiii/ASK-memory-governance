# Security and privacy

Hidden inputs/gold, credentials, private conversations, participant identity,
raw independent labels, external datasets, and local model stores are private
by default. Prediction code must not import scorer/gold modules or log hidden
labels. Public builds scan secrets, absolute local paths, forbidden file names,
PDF metadata, and identity leakage.

Use pseudonyms in annotation artifacts, minimize collected data, document
consent/redaction, and keep the reveal map outside public artifacts. Hashes are
identifiers, not automatic anonymization. See `SECURITY.md` for vulnerability
reporting.
