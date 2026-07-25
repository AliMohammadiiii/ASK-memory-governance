# MGP-6 v4.3 integration changelog

## 2026-07-25 — dry-run preflight

- Activated Serena for the repository and completed read-only discovery.
- Verified the outer handoff and nested release in an isolated temporary
  directory.
- Confirmed ZIP integrity, five internal release archives, readiness metadata,
  and zero failed release gates.
- Recorded a proposed repository path map.
- Stopped before release placement and implementation because pre-existing
  uncommitted changes overlap `.gitignore`, paper sources, and thesis sources.

No benchmark records, private files, code, configurations, test files, paper
sources, thesis sources, ignore rules, releases, or experiment outputs were
changed.

## 2026-07-25 — implemented public integration and protected private placement

- Added a narrow ignored private boundary at `.private/benchmarks/mgp6/v4.3/`.
- Extracted hidden inputs, hidden gold, final human gold, and audit assets only
  beneath that ignored boundary; no private content was added to Git paths.
- Installed public train/dev records, safe metadata, and immutable source
  provenance under `benchmarks/mgp6/mgp6_v4_3/`; placed only the verified public
  and source/builder archives under `releases/MGP6_v4.3.0/`.
- Added the public-only loader/evaluator, resumable runner, configuration
  registry, development-only freeze index, documentation, and privacy tests.
- Updated the paper and authoritative ASK thesis with release facts and explicit
  pending-result placeholders; historical v2 results remain historical.

## 2026-07-25 — integration commit and CI confirmation

- Committed the selected public integration as
  `41f7ceeb38c971874b52578c4b622a704b992715`
  (`Integrate MGP-6 v4.3 final release`).
- Ran the complete local GitHub Actions-equivalent sequence after development
  dependencies were installed: repository validation, pytest, Ruff, Mypy, and
  package build all passed.
- Created `mgp6-v43-experiments` from that integration commit. Existing
  historical untracked material remains intentionally unmodified and untracked.

## 2026-07-25 — OpenRouter smoke-run hardening

- Committed `86e3674` (`Harden MGP-6 v4.3 OpenRouter smoke runner`) on
  `mgp6-v43-experiments`.
- Added runner support for OpenRouter reasoning control via
  `--reasoning-effort none`, raised the development default generation budget
  to 128 tokens, and separated transport retries from parse-format retries.
- Persisted raw invalid model responses and manifest counters before surfacing a
  parse failure, preserving public-only auditability without exposing private
  labels.
- Re-ran full local verification: `git diff --check`, Ruff, scoped Mypy,
  repository validation, full pytest, package build, and a deterministic runner
  smoke all passed.
- Confirmed a three-item public train OpenRouter/Qwen smoke with
  `--reasoning-effort none`: 3 predictions, 0 failures, 0 parse retries, 0
  invalid responses, and no hidden-gold access.

## 2026-07-25 — public development execution recorded

- Completed the `decision_zero_shot` OpenRouter/Qwen configuration over all 180
  public development records using the recorded non-reasoning decoding controls.
- Validated strict prediction coverage and scored only public dev labels. The
  run had zero invalid responses, failures, and retries; the resulting action
  distribution was strongly skewed to `SUPERSEDE`, so the configuration is not
  selected for final hidden evaluation.
- Recorded run, prompt, artifact hashes, aggregate metrics, operational totals,
  and the explicit private-boundary statement in `DEV_EXPERIMENT_REPORT.md`.
- No hidden input, hidden gold, final human gold, or private audit record was
  accessed.

## 2026-07-25 — historical-system label guard

- Found that `scripts/run_mgp6_v43.py` rendered the same generic public
  decision prompt for every accepted `--system` label. This was not a valid
  implementation of the historical baselines or controllers.
- Restricted the runner to the one actually implemented method,
  `decision_zero_shot`, and added a regression test that rejects `b1`.
- Marked B1--B4, the rules and live controllers, and feature ablations as
  requiring distinct v4.3 adapters in the development configuration index.
- The gate returns to development preparation until those adapters are tested;
  no provider call, hidden input, or private scoring occurred for this guard.

## 2026-07-25 — explicit v4.3 adapters and public scorer

- Committed `c37b8878512cd4125a4beb793dd2a6625c35a9df`
  (`Implement MGP-6 v4.3 system adapters`).
- Added distinct public-only adapter views and prompt policies for B1--B4, the
  live controller, and required ablations; added a deterministic rules adapter
  that uses the existing ASK scorecard without a provider call.
- Added the public train/dev scorer with strict coverage validation and
  operational accounting. It cannot read a hidden dataset without public gold
  and intentionally does not read the private component map.
- Ran and scored the committed deterministic rules controller on public dev:
  180 validated predictions, 0 failures/retries/invalid responses/provider
  calls, accuracy 0.3333, Macro-F1 0.2434, and no hidden-gold access.
- Re-ran full repository validation: 539 passed, 11 skipped; Ruff, Mypy,
  repository validation, and package build all passed.

## 2026-07-25 — B1 public development execution recorded

- Completed and public-scored the B1 no-memory OpenRouter/Qwen configuration
  over all 180 public development records after the adapter implementation.
- Strict coverage validation passed with 180 valid JSON predictions and zero
  failures, retries, or invalid responses. Public-dev accuracy was 0.3667 and
  Macro-F1 was 0.3150; this is development evidence only and B1 is not selected
  for hidden evaluation.
- The run manifest records the then-current commit
  `e309893a7e643baa1d5a409d665c49656ceb977e`, a clean tracked worktree, and
  `hidden_gold_accessed=false`. No hidden input, gold, final human gold, or
  private audit asset was accessed.

## 2026-07-25 — B2--B4 public development executions recorded

- Completed and public-scored B2 flat retrieval, B3 recency, and B4 overwrite
  over all 180 public development records, using separate ignored output paths
  and the same pre-registered model, seed, and decoding controls.
- Each run passed strict coverage with 180 valid JSON predictions and zero
  failures, retries, or invalid responses. Public-dev accuracy / Macro-F1 was
  B2: 0.3556 / 0.2380, B3: 0.3389 / 0.2309, and B4: 0.3444 / 0.2064.
- All three manifests record commit `ff33594e73f46e1b9d6281ea7ec5b90ee2960d17`,
  a clean tracked worktree, and `hidden_gold_accessed=false`. None is selected
  for hidden evaluation; no private asset was accessed.

## 2026-07-26 — live-model-controller development execution recorded

- Completed and public-scored the ASK `live_model_controller` over all 180
  public development records using its controller-policy prompt and the same
  pre-registered provider, model, seed, and decoding controls.
- Strict coverage validation passed with 180 valid JSON predictions and zero
  failures, retries, or invalid responses. Public-dev accuracy was 0.3333 and
  Macro-F1 was 0.1771; 176 predictions were SUPERSEDE. This is development
  evidence only and the configuration is not selected for hidden evaluation.
- The manifest records commit `b5a6c602492c2bbcc8dd688371bd4f8d08556e03`, a
  clean tracked worktree, and `hidden_gold_accessed=false`. No hidden input,
  gold, final human gold, or private audit asset was accessed.
