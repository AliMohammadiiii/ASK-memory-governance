# MGP-6 v4.3 private-data audit

## Result: private assets are protected in an ignored local boundary

- Private hidden inputs, hidden gold, final human gold, and private audit assets
  were extracted only under `.private/benchmarks/mgp6/v4.3/`.
- `git check-ignore -v` confirms that representative hidden-input, hidden-gold,
  human-gold, mapping, annotation, and audit paths are covered by the exact
  `.gitignore` rule on line 40.
- No private record content was printed, committed, indexed, or passed to a
  model. A local split-map SHA-256 was recorded for freeze control; the
  split map itself was not exposed.
- The subsequently completed provider smoke and public-dev run used only public
  train/dev records. Their ignored logs and manifests record
  `hidden_gold_accessed=false`; neither run opened private inputs or gold.
- The committed deterministic rules-controller dev run likewise used only the
  public dev split; its ignored prediction, raw-response, manifest, and public
  metric files are covered by the existing `runs/` ignore rule.
- The subsequent model-backed B1 public-dev run used only
  `benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl`; its ignored prediction,
  raw-response, manifest, and public metric files record
  `hidden_gold_accessed=false`.
- The subsequent model-backed B2--B4 public-dev runs likewise used only that
  public development file. Their ignored artifacts record
  `hidden_gold_accessed=false`; no private component map was read by their
  public scoring.
- The ASK live-model-controller public-dev run likewise used only that public
  development file. Its ignored prediction, raw-response, manifest, and public
  metric files record `hidden_gold_accessed=false`.
- The improved public-indexed-evidence controller and all four required
  ablations likewise used only `public/dev.jsonl`. The controller extracts two
  publicly indexed messages from the public record and excludes four public
  unlinked messages; its guard trace contains only public positions, an
  evidence-text hash, and actions. No label or private field enters that view,
  model prompt, raw-response record, or guard trace. Every new ignored manifest
  records `hidden_gold_accessed=false`.
- The tracked public prompt template and loader contain no prohibited private
  keys; ignored fixture and provider-run logs contain public IDs and model
  responses only, with no private fields.
- The final hidden-control artifacts are tracked control-plane JSON only. They
  contain the expected hidden item count and public release/split facts, but
  neither private file paths nor private-file hashes, labels, mappings,
  annotations, consensus records, audit content, or hidden predictions.
  Their regression test rejects prohibited private/label keys before a hidden
  run can be authorized.
- The one final hidden prediction was completed using private hidden inputs only
  after the frozen controls passed CI. Its prediction file was sealed at 540/540
  unique public IDs before the local-private scorer read hidden gold. The scorer
  wrote aggregate metrics only under the ignored `runs/` boundary. Tracked
  reports record those aggregate metrics and SHA-256 values, never a hidden
  record, label, component mapping, human annotation, consensus, or raw
  response.

## Blocking protection gap

The narrow rule is `.private/benchmarks/mgp6/v4.3/`. It was added before private
extraction and verified before and after extraction. `DO_NOT_COMMIT.md` explains
the local boundary but is intentionally ignored with the directory.

## Current audit conclusion

Private MGP-6 v4.3 assets remain ignored and outside tracked artifacts. The
final authorization has been consumed. Hidden gold was opened only by the
separate local-private scorer after prediction coverage validation and hashing;
the result is represented in Git only by aggregate metrics and hashes.
