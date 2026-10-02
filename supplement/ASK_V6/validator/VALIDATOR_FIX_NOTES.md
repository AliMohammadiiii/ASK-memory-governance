# P17 validator correction, out-of-repository patch

Date: 2026-10-02. Baseline: `f6bf66e4766d769727edf6b42c76b9977b14978a`. Patch SHA-256: `ebaa8108ecc76ce2900ce074f5b808e04c46f0fcc9d6159767909e7bb285b123`.

## 0. Status declaration

Implementation facts, observations and design decisions are separated below. Read this section first.

What was done: a validator and configuration-binding correction was written against the baseline reference protocol (`src/ask/protocol/core.py`, `adapters.py`, `__init__.py`), a regression file was added, and the 19 audited tampering probes plus the 64-zero identity case were re-run against the unmodified baseline and the patched code.

What was not done, and why:
- The repository was not modified. `git status --short` of the repository was recorded before and after the work and is identical (5 lines: `M reports/paper_artifact_drift.json`, `M src/ask/eval/mgp6_v43.py`, `?? lmev12.txt`, `?? src/ask/eval/mgp6_v43.py.bak_before_json_fence`, `?? uv.lock`). The three protocol files in the working tree are byte-identical to the baseline blobs, so the patch applies to them.
- TEMPORAL_EVENT semantics were not implemented. Nothing in the baseline code, schema or architecture text specifies valid-time, event ordering or retroactive-update behavior, and an implementation would be speculation. In the patched validator `temporal_event` is checked with exactly the same accounting as `multi_record` for Abstain, Keep and Supersede (the baseline builder already treats it that way), and Keep admission remains `multi_record` only. Probe K05 is rejected by that accounting (an unrelated record changed), not by any temporal rule.
- The V12 SQLite runtime, the MGP-6 pipelines and every evaluated system were not touched. The patch is written by the auditor after the evaluations and no evaluated system calls it. It adds no conformance evidence for any of them.
- No documentation, Makefile target, JSON schema or existing test was edited. The patch contains 3 modified source files and 1 new test file (see section 9).
- Tests were not run under Python 3.11 (the repository supports 3.11 and 3.12; only 3.12.14 was available in the `ask-audit` environment).
- The repository hygiene, document-path and artifact-inventory tests cannot run in the git archive export (see section 7). Whether the new file passes the repository prose hygiene scan was not executed; that scan inspects `.j2 .md .rst .tex .txt` files, not `.py`.
- The 64-zero case is rejected by the verify step and by adapter and validator paths that receive the frozen configuration. The plain constructor still accepts 64 zeros (format check only), by design (section 4).

A self-consistent probe set is a regression suite for this code. It is not evidence that the validator is complete, and the tests were written by the same party as the patch (no independent test author). The ablation in section 6 measures how sensitive the tests are to each added check; it does not measure completeness.

## 1. Observations that shaped the design

1. Re-run on the unmodified baseline: 0 of 19 tampering probes rejected, 8 of 8 positive controls accepted (`PROBE_RESULTS_BASELINE_RERUN.json`). This reproduces the Phase 6 result.
2. The Phase 6 helper `rebuild_event` computed event identifiers over a body that omitted `configuration_id` and `configuration_sha256`, whereas `apply_transition` includes both. The tampered events in Phase 6 therefore carried identifiers that the builder would not have produced. This did not change the Phase 6 conclusion (the baseline never checks identifiers), but a validator that recomputes identifiers rejects every Phase 6 event for that reason alone. `PROBE_RESULTS_PATCHED_LEGACY_EVENT_ID.json` shows that outcome (18 probes rejected with `event_id_mismatch`, I02 with its own code). The headline run uses the builder's formula (`run_probes_patched.py` asserts that its local formula equals the builder's event id), so each rejection below comes from the intended check.
3. The validator signature `validate(before, after, event, trace)` does not receive the candidate record. Probe S06 (successor value differs from the candidate) cannot be decided from those four arguments, because neither the event nor the trace carries the candidate content. Binding the committed record to the candidate needs the candidate as an input or a candidate digest in the event. This patch uses the candidate-as-input route, which leaves the event schema and all event identifiers unchanged.
4. The builder's event identifiers are unchanged by the patch: four pinned identifiers (Abstain, Keep, Keep with admission, Supersede) computed on the unmodified baseline are asserted in the new test file, and the events and after states of the eight controls are equal between the two trees (`build_negative_table.py` asserts this).

## 2. What each check enforces (implementation facts)

`ASKInvariantValidator.validate(*, before, after, event, trace, candidate=None, configuration=None, expected_store_mode=None) -> ValidationReport`. Every rejection raises `ASKValidationError`, a subclass of `ValueError`, carrying `code`, `codes` and `violations`. The baseline structural checks run unchanged and keep their message texts (now prefixed with a reason code). The added checks, in execution order:

1. Event identity: `trace_evidence_digest_mismatch` (trace evidence digest must equal the digest of its evidence references) and `event_id_mismatch` (event identifier must equal the digest of the event body, `compute_event_id`).
2. Trace to event: `trace_event_record_mismatch` when a trace logs `prior_record_id` or `candidate_record_id` among its inputs (the LME adapter does, the MGP adapter does not) and the value differs from the event.
3. Store mode: `event_store_mode_mismatch` only when the caller passes `expected_store_mode`; the event states its own mode and the validator cannot otherwise confirm it.
4. Baseline checks: digests of supplied states, duplicate-identifier check, lineage, per-action rules, single-slot active count (unchanged; `before` uniqueness added).
5. Event field accounting: the candidate, resulting and predecessor identifiers and the admission flag must follow from the action (`event_candidate_id_mismatch`, `event_resulting_id_mismatch`, `event_predecessor_id_mismatch`, `event_admission_flag_mismatch`).
6. Record accounting. The only differences between `before` and `after` that an action may produce are:
   - Abstain, and Keep without admission: none.
   - Keep with admission (multi_record only): one added record equal to the candidate (type, value, evidence digest), active, no predecessor.
   - Supersede: the compared prior changes only `active` (True to False), and one record equal to the candidate is added, active, with the compared prior as predecessor.
   Everything else is reported with `unaccounted_record_removed`, `unaccounted_record_changed`, `unaccounted_record_added`, `retained_predecessor_removed`, `retained_predecessor_mutated` (names the changed fields), `successor_differs_from_candidate`, `admitted_record_differs_from_candidate`, `candidate_id_exists_in_before`, `committed_record_missing`. Preconditions: `prior_not_in_before`, `prior_not_active_before` (Keep and Supersede), `candidate_required`. All violations found in this stage are reported together.
7. Configuration: `ConfigurationIdentity.verify(configuration)` recomputes the digest of the supplied mapping (`configuration_digest_mismatch`).

`validate_event_chain(events, initial_state=None)` checks event-id recomputation and digest continuity across an ordered event log (`event_chain_break`, `initial_state_digest_mismatch`). It does not re-execute transitions.

Fail-closed inputs. `candidate` and `configuration` must be supplied. Passing `UNVERIFIED` skips that binding explicitly, and `ValidationReport.unverified` lists the skipped bindings (`candidate_content`, `configuration_digest`). Omitting `configuration` is rejected with `configuration_binding_required`; passing a value of the wrong type raises `TypeError` instead of skipping the binding.

Compatibility (a deliberate break): a caller that used the baseline four-argument form on a Supersede or an admitting Keep now receives a rejection unless it supplies the candidate and configuration or passes `UNVERIFIED`. A search of the `.py`, `.md`, `.toml` and `.json` files of the baseline export (excluding `paper/` and `thesis/`) found `ASKInvariantValidator` only in `src/ask/protocol/core.py`, `src/ask/protocol/__init__.py` and `tests/test_ask_protocol.py`; `apply_transition` is the only caller of `validate`, and the test file calls the private `_validate_lineage`. `apply_transition` and `replay_transition` keep their signatures and results; they gained a trailing optional `configuration` argument whose default `UNVERIFIED` preserves the format-only identity behavior that the existing tests rely on (their identities are `"1"*64`, `"2"*64`, `"a"*64`). `InMemoryASKStore.apply` forwards the same optional argument.

## 3. Results

Probe table (`NEGATIVE_TEST_TABLE.csv`, 19 tampering probes plus the zero-identity case R01 and the shifted-threshold replay R02 under strict replay):

| Probe | Tampering | Baseline | Patched | Reason code(s) | Check that fires | Ablations that make the probe pass |
|---|---|---|---|---|---|---|
| S01 | SUPERSEDE: retained predecessor value altered while deactivated | ACCEPTED | REJECTED | `retained_predecessor_mutated` | accounting, retained predecessor fields | record_accounting_all, changed_records, retained_predecessor_fields |
| S02 | SUPERSEDE: retained predecessor memory_type altered | ACCEPTED | REJECTED | `retained_predecessor_mutated` | accounting, retained predecessor fields | record_accounting_all, changed_records, retained_predecessor_fields |
| S03 | SUPERSEDE: retained predecessor evidence_digest altered | ACCEPTED | REJECTED | `retained_predecessor_mutated` | accounting, retained predecessor fields | record_accounting_all, changed_records, retained_predecessor_fields |
| S04 | SUPERSEDE: unrelated active record deleted | ACCEPTED | REJECTED | `unaccounted_record_removed` | accounting, removed records | record_accounting_all, removed_records |
| S05 | SUPERSEDE: unrelated record value mutated | ACCEPTED | REJECTED | `unaccounted_record_changed` | accounting, changed records | record_accounting_all, changed_records |
| S06 | SUPERSEDE: successor value differs from candidate value | ACCEPTED | REJECTED | `successor_differs_from_candidate` | accounting, successor equals candidate | record_accounting_all, added_records, successor_content_vs_candidate |
| S07 | SUPERSEDE: unrelated record deactivated | ACCEPTED | REJECTED | `unaccounted_record_changed` | accounting, changed records | record_accounting_all, changed_records |
| S08 | SUPERSEDE: extra unannounced active record inserted | ACCEPTED | REJECTED | `unaccounted_record_added` | accounting, added records | record_accounting_all, added_records |
| S09 | SUPERSEDE: event predecessor_record_id field wrong (points to unrelated record) | ACCEPTED | REJECTED | `event_predecessor_id_mismatch` | event field accounting | event_field_accounting |
| S10 | SUPERSEDE: event candidate_record_id field wrong | ACCEPTED | REJECTED | `event_candidate_id_mismatch` | event field accounting | event_field_accounting |
| S11 | SUPERSEDE of a prior that was already inactive before the transition | ACCEPTED | REJECTED | `prior_not_active_before` | accounting, prior active before | record_accounting_all, prior_active_before |
| S12 | SINGLE_SLOT SUPERSEDE: older inactive ancestor deleted and lineage pointer rewritten | ACCEPTED | REJECTED | `unaccounted_record_removed, retained_predecessor_mutated` | accounting, removed records; accounting, retained predecessor fields | record_accounting_all only (two independent detections) |
| K01 | MULTI KEEP (keep_admitted_candidate=False): candidate silently inserted | ACCEPTED | REJECTED | `unaccounted_record_added` | accounting, added records | record_accounting_all, added_records |
| K02 | MULTI KEEP: unrelated record deleted | ACCEPTED | REJECTED | `unaccounted_record_removed` | accounting, removed records | record_accounting_all, removed_records |
| K03 | MULTI KEEP: unrelated record value mutated | ACCEPTED | REJECTED | `unaccounted_record_changed` | accounting, changed records | record_accounting_all, changed_records |
| K04 | MULTI KEEP with prior_record_id=None: compared prior rewritten | ACCEPTED | REJECTED | `unaccounted_record_changed` | accounting, changed records | record_accounting_all, changed_records |
| K05 | TEMPORAL_EVENT KEEP: arbitrary mutation of unrelated record | ACCEPTED | REJECTED | `unaccounted_record_changed` | accounting, changed records | record_accounting_all, changed_records |
| I01 | Event id not equal to digest of event body | ACCEPTED | REJECTED | `event_id_mismatch` | event identity, event id recomputation | event_id_recompute |
| I02 | Trace evidence_digest does not equal digest of its evidence_references | ACCEPTED | REJECTED | `trace_evidence_digest_mismatch` | event identity, trace evidence digest | trace_evidence_set_digest |
| R01 | ConfigurationIdentity sha256 = 64 zeros checked against its frozen configuration | ACCEPTED | REJECTED | `configuration_digest_mismatch` | ConfigurationIdentity.verify | identity_verify, validator_configuration_verify |
| R02 | Replay with thresholds shifted +0.01 under an unchanged identity (action unchanged), strict replay | ACCEPTED | REJECTED | `configuration_digest_mismatch` | ConfigurationIdentity.verify | none (the logged-threshold comparison also fires) |

Positive controls accepted by the patched validator and still produced identically by the builder: C01 Supersede (multi), C02 Abstain, C03 Supersede (single slot with history), C04 Keep (multi), C05 Keep with admission, C06 Keep (single slot), C07 Supersede in `temporal_event` mode (multi-record rules only), C08 `replay_transition` of the preserved C01 event. The new test file runs nine parametrized controls (Abstain in multi-record and single-slot mode, Keep in multi-record mode with and without admission and without a prior, Keep in single-slot mode, Supersede in multi-record, single-slot-with-history and `temporal_event` modes), a replay round trip and an in-memory store round trip.

Other replay probes (`PROBE_RESULTS_PATCHED.json`):
- R02 under default (non-strict) replay is unchanged from the baseline: the shifted configuration is still accepted. The detection exists only in strict mode, which is opt-in.
- R02 strict replay with a shifted configuration that carries its own correctly computed identity is rejected with `trace_configuration_mismatch`. The unshifted strict control is accepted.
- R03 (a threshold shift that flips the action) is rejected by the baseline action comparison, as before.
- R04 (declared `sufficient_fields` `thresholds` and `configuration` are not keys of the trace) is not addressed by the patch.
- D01 (the reference module performs no durable I/O) is unchanged.

## 4. Configuration identity

Canonical serialization (`canonical_json_bytes`): `json.dumps` with `sort_keys=True`, separators `(",", ":")`, `ensure_ascii=False`, `allow_nan=False`, encoded as UTF-8. Accepted values: str-keyed mappings, lists, tuples, str, int, finite float, bool, None (an Enum is replaced by its value). Non-string keys, sets, bytes and non-finite floats raise. The integer 1 and the float 1.0 serialize differently. This is not RFC 8785 (float formatting and key ordering follow Python). `configuration_digest(mapping)` is the SHA-256 hex digest of those bytes.

- `ConfigurationIdentity.from_configuration(id, adapter_version, mapping)` computes the digest.
- `ConfigurationIdentity.verify(mapping)` recomputes it and raises `configuration_digest_mismatch`.
- `ConfigurationIdentity.unverified(id, adapter_version, sha256)` is the named format-only constructor. The plain constructor behaves identically and is kept because the existing tests construct identities with arbitrary digests; making it strict would break them. Neither form establishes that a digest identifies a configuration.
- Adapters: `frozen_configuration()` returns the declared mapping (MGP: adapter id, version, replay scope, store mode, a composition-rule label; LME: those plus weights, `theta_sup`, `theta_abs`, feature schema version, ordered rules, relation guard). `verify_configuration_identity()` verifies against it. `ASKLMEAdapter.bound(id, config=...)` and `ASKMGPAdapter.bound(id)` build adapters with a computed identity. `replay(trace, strict=True)` additionally requires `trace.configuration == adapter.configuration` and, for LME, that the logged `theta_sup` and `theta_abs` equal the replaying values.
- The digest covers the declared mapping only. It does not cover the policy code, and `configuration_id` and `adapter_version` labels are not inside the digest (the event identifier covers the label and the digest together).

## 5. Design decisions (decision record)

D1. Binding the candidate through a validator argument.
- Alternatives: add a candidate digest field to `TransitionEvent`; leave S06 unaddressed.
- Evidence: the event schema and every event identifier would change under the digest-field alternative; the four-argument call cannot decide S06.
- Reasoning: the argument route leaves identifiers and the wire schema unchanged. Cost: the candidate is trusted from the caller.
- Effect on manuscript claims: none by itself. A statement that the event binds the candidate content would be inaccurate for this patch.
- Reversible: yes.

D2. Fail-closed defaults in `validate`, explicit `UNVERIFIED` escape.
- Alternatives: lenient defaults with a warning; a constructor-level strict flag.
- Reasoning: a conformance checker that silently skips a binding reports less than it appears to. The report lists skipped bindings.
- Effect: breaks external four-argument callers (none in the repository).
- Reversible: yes.

D3. Frame condition enforced (records not named by the transition are unchanged).
- Evidence: Phase 6 classified S04, S05, S07, S08, K02 to K05 as class C, "unstated frame or mode conditions". The architecture text states retention of the prior and the successor lineage but not preservation of unrelated records.
- Reasoning: the baseline builder never alters unrelated records, so the condition matches the reference behavior. It is an auditor design choice and needs owner acceptance. A store that legitimately garbage-collects or compacts records would be rejected by this validator.
- Effect: any manuscript sentence describing the validator must state this condition as an added requirement, not as something the baseline checked.
- Reversible: yes (disable `_validate_transition_accounting` for the affected action).

D4. `temporal_event` handled with multi-record accounting, no temporal semantics (section 0).
- Alternative: reject `temporal_event` outright. This would also make `apply_transition` fail for that mode, which the baseline builder accepts for Supersede.
- Reversible: yes.

D5. Validator re-derives allowed differences from the action, rather than re-running the builder and comparing.
- Reasoning: named violations per difference, and the validator stays usable for states produced by another store.

D6. Strict adapter replay is opt-in.
- Reason: default adapters in existing tests carry arbitrary digests and must keep replaying.

## 6. Ablation (sensitivity of the tests to each added check)

One source line of the patched `core.py` was disabled per row, in a copy of the patched tree. A check is supported by the evidence only if disabling it lets a probe pass or fails a test. `ABLATION_RESULTS.json` has the replaced strings. Reference run: no probe accepted, 98 of 98 tests passing.

| Ablated check (one source line disabled) | Probes accepted afterwards | New-file tests failing |
|---|---|---|
| `event_id_recompute` | I01 | 1 |
| `trace_evidence_set_digest` | I02 | 1 |
| `event_field_accounting` | S09, S10 | 6 |
| `record_accounting_all` | K01, K02, K03, K04, K05, S01, S02, S03, S04, S05, S06, S07, S08, S11, S12 | 24 |
| `prior_active_before` | S11 | 2 |
| `removed_records` | K02, S04 | 3 |
| `changed_records` | K03, K04, K05, S01, S02, S03, S05, S07 | 9 |
| `added_records` | K01, S06, S08 | 8 |
| `retained_predecessor_fields` | S01, S02, S03 | 4 |
| `successor_content_vs_candidate` | S06 | 4 |
| `identity_verify` | R01, R01(validator path) | 8 |
| `validator_configuration_verify` | R01(validator path) | 3 |
| `trace_event_binding` | none of the 19 or R01/R02 | 1 |

Reading: every added check is exercised by at least one test. The R02 strict probe stays rejected when `identity_verify` is disabled because the logged-threshold comparison (`logged_threshold_mismatch`) also fires; the two checks overlap. `trace_event_binding` is covered by a dedicated test only; none of the 19 probes depends on it.

## 7. Test runs (`PYTEST_RESULTS.txt` has commands, exit codes and counts)

Environment: conda environment `ask-audit`, Python 3.12.14, pytest 9.1.1, pydantic 2.13.5, jsonschema 4.26.0, PyYAML 6.0.3. Trees: `/tmp/p17_base` (git archive export of the baseline) and `/tmp/p17_apply` (the same export after `git apply` of `validator_fix.patch`).

| Run | Result | Exit code |
|---|---|---|
| Baseline tree, five existing files (`test_ask_protocol.py`, `test_ask_formal_properties.py`, `test_memory_operations.py`, `test_temporal.py`, `test_supersede.py`) | 34 passed | 0 |
| Patched tree, the same five files, unmodified | 34 passed | 0 |
| Patched tree, `tests/test_ask_protocol_tampering.py` | 98 passed | 0 |
| Patched tree, five files plus the new file | 132 passed | 0 |
| Full `tests` directory, baseline tree | 9 failed, 672 passed, 19 skipped | 1 |
| Full `tests` directory, patched tree | 9 failed, 770 passed, 19 skipped | 1 |

The 9 failing tests have identical names in both trees. In the sampled failure messages the cause is `git` returning exit status 128 inside the non-repository export and the repo-local `.venv` interpreter being unusable here. They were not investigated one by one and are unrelated to the protocol files. Static checks on the patched files: `ruff check` and `ruff format --check` pass (ruff 0.16.10, repository configuration; the repository pins 0.16.0), and `mypy src/ask/protocol tests/test_ask_protocol_tampering.py` reports no issues (the baseline also reports none). `git apply --check` and `git apply` succeed on a clean export, and the result is byte-identical to `patched_tree/`.

## 8. Limitations and what is still not validated

1. The event identifier is an unkeyed digest. A party that recomputes it over a self-consistent forged transition passes (`test_known_limit_self_consistent_forgery_of_all_bound_fields_is_accepted`). There is no signature, MAC or authenticated storage.
2. `validate` checks the supplied `before` state against the event digest only. Nothing ties `before` to the actual store content. `validate_event_chain` detects discontinuity inside a log and against a supplied initial state; it cannot detect a log that was rewritten consistently from its start.
3. `TransitionEvent.metadata` and `adapter_version` are not part of the event body hash (test `test_known_limit_event_metadata_is_not_part_of_the_event_identifier`).
4. The trace is only partly bound to the event: evidence digest, configuration identity, final action, and (when logged) prior and candidate identifiers. `inputs`, `intermediates` and `sufficient_fields` are not hashed into anything the event carries.
5. The candidate is supplied by the caller. No check relates `candidate.evidence_digest` to the trace evidence references, and `candidate.confidence` is not recorded in state, so it cannot be checked.
6. The configuration digest binds a declared mapping, not executable code. R04 (declared `sufficient_fields` that are not keys in the trace) is unchanged. Default (non-strict) replay is unchanged, so the baseline behavior of R02 remains the default.
7. The plain `ConfigurationIdentity` constructor still accepts any 64 hex characters; verification happens only when a mapping is supplied.
8. `event.store_mode` is self-reported unless the caller passes `expected_store_mode`.
9. `temporal_event` has no temporal semantics (section 0). Durability (D01) and persistence are unchanged: the reference module still performs no file or database I/O.
10. Whether the V12 SQLite runtime or any other store satisfies these conditions was not tested. The validator has never run on V12 state.
11. The frame condition (D3) is an auditor design decision; the owner must accept or revise it.
12. Python 3.11 was not tested; canonical float text follows Python's `repr` and is not RFC 8785.

## 9. Files in the patch

`validator_fix.patch` is a unified diff against the baseline files, applicable with `git apply` from the repository root.

| File | Added | Removed |
|---|---|---|
| `src/ask/protocol/__init__.py` | +14 | -0 |
| `src/ask/protocol/adapters.py` | +153 | -7 |
| `src/ask/protocol/core.py` | +585 | -34 |
| `tests/test_ask_protocol_tampering.py` | +876 | -0 |

`patched_tree/` holds complete copies of the four files at their patched state.

## 10. Apply and test (owner)

The working tree of the repository contains unrelated uncommitted changes. Apply the patch in a separate worktree or branch created from the baseline commit.

```
git worktree add ../ASK-validator-fix f6bf66e4766d769727edf6b42c76b9977b14978a
cd ../ASK-validator-fix
git apply --check /Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/p17_validator_fix/validator_fix.patch
git apply /Users/alimohammadi/Workspace/research/ASK_CLAUDE_SCIENCE_AUDIT_20260927/p17_validator_fix/validator_fix.patch
python -m pytest -q -p no:cacheprovider tests/test_ask_protocol.py tests/test_ask_formal_properties.py tests/test_memory_operations.py tests/test_temporal.py tests/test_supersede.py tests/test_ask_protocol_tampering.py
```

Expected: `132 passed`. The commands assume a Python 3.11 or 3.12 interpreter with the repository dependencies installed. `git worktree add` writes worktree metadata under the repository's `.git`; a plain clone checked out at the baseline commit works equally well. To reproduce the probe tables from the audit directory: `python run_probes_patched.py --tree <patched tree> --out PROBE_RESULTS_PATCHED.json`, then `python build_negative_table.py`. `python run_ablation.py --tree <patched tree> --harness run_probes_patched.py --out ABLATION_RESULTS.json` reproduces section 6. Patch SHA-256: `ebaa8108ecc76ce2900ce074f5b808e04c46f0fcc9d6159767909e7bb285b123`.

## 11. Suggested wording constraints for the manuscript (not applied)

- The baseline validator accepted all 19 self-consistent tampering probes in the Phase 6 harness and a re-run with the builder's event-id formula. That statement stays true of the evaluated code.
- This patch is an auditor-written correction made after the evaluations. No evaluated system calls it. Do not describe MGP-6, V12 or any benchmark result as validated by it.
- `docs/architecture/ASK_PROTOCOL.md` says every event binds action, storage mode, state digests, evidence digest, configuration identity, identifiers and lineage. For the baseline, the event identifier was never recomputed, and the configuration digest was never tied to a configuration. If the patch is adopted, that paragraph should state the frame condition, the unkeyed nature of the identifier, and the opt-in strict replay.
