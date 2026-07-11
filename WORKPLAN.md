# Workplan

1. Preserve original archives outside Git.
2. Maintain one canonical package under `src/ksa`.
3. Treat MGP-6 v2 as a diagnostic benchmark, not a comprehensive public benchmark.
4. Keep large runs and third-party datasets outside Git; bind them through manifests and checksums.
5. Run offline tests and schema validation before any hosted-model evaluation.
6. Freeze prompt/config/data hashes before confirmation runs.
7. Generate result tables from machine-readable reports only.
