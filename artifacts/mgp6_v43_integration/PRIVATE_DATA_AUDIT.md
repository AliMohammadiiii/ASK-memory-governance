# MGP-6 v4.3 private-data audit

## Result: private assets are protected in an ignored local boundary

- Private hidden inputs, hidden gold, final human gold, and private audit assets
  were extracted only under `.private/benchmarks/mgp6/v4.3/`.
- `git check-ignore -v` confirms that representative hidden-input, hidden-gold,
  human-gold, mapping, annotation, and audit paths are covered by the exact
  `.gitignore` rule on line 40.
- No private record content was printed, committed, indexed, or passed to a
  model. A local split-map SHA-256 was recorded for future freeze control; the
  split map itself was not exposed.
- No model call was made.
- The tracked public prompt template and loader contain no prohibited private
  keys; ignored fixture-run logs contain public IDs and fixture actions only.

## Blocking protection gap

The narrow rule is `.private/benchmarks/mgp6/v4.3/`. It was added before private
extraction and verified before and after extraction. `DO_NOT_COMMIT.md` explains
the local boundary but is intentionally ignored with the directory.

## Required follow-up audit

After protection is added and private packages are placed, verify every private
file is ignored, scan non-private model-facing files for prohibited keys
(`gold_action`, `design_target`, `source_item_id`, `component_id`,
`private_item_id`, `annotator_id`, and `final_consensus`), and fail the
integration if any prohibited field is found.
