# Structural audit of MGP-6 v4.3 construction files (`hidden_structure_audit.py`)

Purpose: a post-hoc structural verification, run by the repository owner on the owner's machine, that the documented
construction of the benchmark holds in the files that were used. It prints and stores aggregate counts, booleans and
split-level means only.

**This script must not be used for any hidden performance tuning.** It reads no prediction and no model output, it
computes no accuracy, and its output is not an input to any prompt, model, controller or threshold decision. The hidden
split has been consumed; the result is a description of the data construction, reported after the fact.

The script does not search for, open or know the location of the private hidden files. You supply every path.
It needs only the Python standard library.

## What it checks

Part A (label free; reads `memory_before` and `dialogue` only)

| check | unit | meaning |
|---|---|---|
| `component_has_nine_items` | component | exactly nine items |
| `component_lengths_9_11_13_present`, `component_three_items_per_length` | component | dialogue lengths 9, 11, 13 present, three items each |
| `component_one_pool_of_six_distinct_sentences_across_all_items` | component | the numbered evidence sentences ("The first message says: ..." through the sixth) form one set of six distinct sentences, identical for all nine items |
| `triple_three_items`, `triple_pool_of_six_identical_for_the_three_items` | (component, length) | three items share one pool of six |
| `triple_indexed_pairs_partition_the_pool`, `component_all_three_triples_partition_the_pool` | (component, length) | the two sentences named by each item's index statement form three disjoint pairs whose union is the pool |
| `component_one_standing_value`, `component_one_proposed_value`, `component_one_principal_and_one_slot` | component | one standing value, one proposed (requested) value, one principal and one slot |
| `parse.failures` | item | index statement not naming two positions, numbered snippets not exactly six, requested value not found, duplicate id |

Part B (label dependent; runs only if you supply labels; labels are read to count and average, never printed)

| check | unit | meaning |
|---|---|---|
| `component_three_items_per_action` | component | three KEEP, three SUPERSEDE, three ABSTAIN |
| `component_one_item_per_action_in_each_length` | (component, length) | one item per action at each length |
| `mean_indexed_position_by_action` | split and pooled | mean of the indexed message positions (two per item) by action, as exact fractions, and whether the three means are identical |

"Label free" means that Part A never reads a label and gives identical output with or without a label file (tested with shuffled labels).
Part B cannot be label free, because action balance and position means by action are defined through the action. It reads the labels you give it, and only counts and averages them. The action names (KEEP, SUPERSEDE, ABSTAIN) appear as keys of the aggregate tables; no item-level label is printed or stored.

Components: if you give `--component-map`, the components are those of the map and the script reports whether the proxy partition (items sharing principal, slot and standing value) equals the map (`proxy_partition_equals_supplied_map`). Without a map, the components are the proxy groups.
The grammar for the index statement, the numbered sentences and the requested value is copied from `src/ask/eval/mgp6_v43.py` at the baseline commit; on all 360 public train and development items the extracted positions, sentences and requested values equal the output of the repository's `linked_evidence_view` (tested).

## Command (hidden construction files)

File names are those written by `benchmarks/mgp6/mgp6_v4_3/source/build_mgp6_v43_final.py`; use your local locations.

```bash
python3 hidden_structure_audit.py \
  --records  <private_hidden_inputs>/hidden_inputs.jsonl \
  --component-map <private_hidden_gold>/cluster_map_private.json \
  --labels   <private_hidden_gold>/hidden_gold.jsonl \
  --expect-items 540 --expect-components 60 \
  --out ~/Workspace/research/hidden_structure_audit_result.json
python3 hidden_structure_audit.py --verify ~/Workspace/research/hidden_structure_audit_result.json
```

Part A only (no label file): omit `--labels`. Write the output outside the repository. The JSON contains no text or ids, only counts, booleans, means, input file hashes and the script hash.

Output: the printed summary, `<out>` (JSON) and `<out>.sha256`. The JSON carries `content_sha256` (SHA-256 of the canonical JSON without that field), the SHA-256 of the script, the SHA-256 of each input file, and a statement that it is a post-hoc structural verification. `--verify` recomputes both hashes.
Failures print the exception type only and exit with status 2; use `--debug` on your own machine if you need the traceback (it can contain data).

## Validation on the public files (done; see `public_validation/`)

Command: `python3 hidden_structure_audit.py --records train.jsonl --records dev.jsonl --inline-labels --expect-items 360 --expect-components 40`.

| quantity | recorded in the audit | reproduced |
|---|---|---|
| public components | 40 | 40 (20 train, 20 dev) |
| (component, length) triples | 120 | 120; pool of six identical for the three items in 120 of 120; indexed pairs partition the pool in 120 of 120 |
| mean indexed position, train | 3.600 | 3.6000 for KEEP, SUPERSEDE and ABSTAIN (exact 18/5) |
| mean indexed position, development | 3.575 | 3.5750 for the three actions (exact 143/40) |
| mean indexed position, pooled | 3.5875 | 3.5875 for the three actions (exact 287/80) |
| action balance | 3 per action per component, 1 per action per length | 40 of 40 components, both checks |

One difference from an earlier note: the repository's analysis note says that the partition property was checked on the 80 of 120 triples whose index statement "parses mechanically". The cue grammar of the repository router parses all 120 triples (360 of 360 items), so this script checks the partition on all 120. The earlier figure of 80 is not a property of the data; it reflects the parser used for that note.

## What the output supports and does not support

Supports: a statement about the hidden construction files in the same terms as the public ones ("the structural checks listed in Part A pass in k of n components"), including the figures the manuscript currently says it cannot report for the 60 hidden components.
Does not support: any statement about shortcut absence, label correctness, difficulty, representativeness, or model behaviour. A failed check is reported as a count and is not repaired, rerun after editing data, or hidden. If a check fails, do not alter the data; report the failing count.

## Tests (TEST_LOG.txt)

17 unit tests: reproduction of the public figures, equality with the repository router on 360 items, label independence of Part A, seven corruption cases and one unmodified control on copies of the public data (pool change, non-partitioning pairs, missing item, label flip, changed standing value checked against a supplied map including a map that splits a component and a JSONL map, duplicated numbering, repeated sentence), output hygiene (no id, name or sentence from the public files appears in the output), hash and `--verify` behaviour, failure messages that do not echo data.
Not tested: the private hidden files themselves (never opened); files with line endings or encodings that differ from the public ones.
