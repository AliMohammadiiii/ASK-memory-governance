# M3-W11 Self-Review Log

Date opened: 2026-05-21

## Status

Initial authoring pass complete. Cold self-review was performed on 2026-05-22
after reopening the artifacts through the scheduled Codex follow-up.

Automation id:

```text
m3-w11-cold-self-review
```

## Initial Validation

Command:

```bash
source .venv/bin/activate
pytest tests/test_mgp6_schema.py
```

Result:

```text
1 passed
```

Coverage:

```text
n=60
T1=10, T2=10, T3=10, T4=10, T5=10, T6=10
SUPERSEDE=30, ABSTAIN=22, KEEP=8
```

Initial SHA-256 for `data/mgp6_v1_seed0.jsonl`:

```text
12e17af530067f0ec1cefa1131898e2c8bd2414ef20cfc4c37fb936148e65701
```

## Initial Review Notes

The first pass checked:

- Unique `scenario_id` values.
- 10 scenarios per type.
- Legal gold actions only: `KEEP`, `SUPERSEDE`, `ABSTAIN`.
- Scenario ids match type prefixes.
- `SUPERSEDE` rows preserve lineage through `supersedes_id`.
- `ABSTAIN` rows leave the prior active state unchanged.
- T5 `KEEP` rows preserve the stable prior and add only transient scoped items.

Known limitation found during review:

- The repository does not contain real LongMemEval-S dialogue prefixes. The
  scenario prefixes are therefore LongMemEval-shaped authored prefixes, not
  real borrowed release-prefix snippets.

No post-cold-review edits were required.

## Cold Review Checklist

On 2026-05-22, re-read all 60 rows and check:

- Artificial phrasing that makes the gold action too obvious.
- Leakage of the gold action into `perturbation_event`.
- T4/T5/T6 boundary mistakes.
- Stable preference versus transient preference type errors.
- Expected answer mismatch with gold memory state.
- Any scenario where same subject and same semantic slot are not clearly
  established.
- Any scenario whose `gold_memory_state` fails the manual rules in
  `docs/annotation_manual.md`.

If edits are made, record each changed `scenario_id`, the reason, and the new
SHA-256.

## Cold Review Results

Date performed: 2026-05-22

Artifacts reviewed:

- `data/mgp6_v1_seed0.jsonl`
- `docs/annotation_manual.md`
- `NOTES/m3w11_provenance.md`

Validation command:

```bash
source .venv/bin/activate
python - <<'PY'
from collections import Counter
from ksa.eval.mgp6_schema import load_mgp6_jsonl, validate_mgp6_coverage
scenarios = load_mgp6_jsonl('data/mgp6_v1_seed0.jsonl')
validate_mgp6_coverage(scenarios)
print('rows', len(scenarios))
print('types', dict(Counter(s.type for s in scenarios)))
print('actions', dict(Counter(s.gold_action for s in scenarios)))
PY
```

Validation result:

```text
rows 60
types {'T1': 10, 'T2': 10, 'T3': 10, 'T4': 10, 'T5': 10, 'T6': 10}
actions {'SUPERSEDE': 30, 'ABSTAIN': 22, 'KEEP': 8}
```

Cold-read findings:

- All 60 rows re-read by `scenario_id`, type, perturbation event, gold action,
  expected answer, and gold memory state.
- No gold-action leakage was found in the advisor-facing fields beyond the
  intended type labels and diagnostic perturbation wording.
- T1, T2, and T3 rows consistently use same-subject/same-slot updates and
  lineage-preserving `SUPERSEDE`.
- T4 rows consistently preserve the initial state under ambiguity, hedging,
  quoted speech, or referent uncertainty.
- T5 rows consistently distinguish clear transient scope (`KEEP` with a
  `transient_pref`) from hedged transient statements (`ABSTAIN`).
- T6 rows consistently reject low-confidence extraction artifacts and preserve
  the initial state.
- No expected-answer mismatches were found against the active gold memory
  state.
- No manual revisions were needed.

Post-review SHA-256 for `data/mgp6_v1_seed0.jsonl`:

```text
12e17af530067f0ec1cefa1131898e2c8bd2414ef20cfc4c37fb936148e65701
```

Changed scenarios:

```text
none
```
