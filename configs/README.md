# Configuration ownership

Maintained defaults and prospective run definitions live here. Each command
must record the configuration bytes or their hash in its run manifest.

Files under `configs/release/` define release gates. Model files define public
model identifiers and runtime parameters, never provider credentials. Recorded
experiment configurations under `experiments/` retain their original names
because manifests and reports refer to them.

No configuration is protected from maintenance merely by its filename. If a
configuration has already produced reported evidence, create a new version and
record its relationship to the consumed version instead of changing the old
record without disclosure.
