# M4-W14 Thesis Colab Run Review - 2026-06-08

Source upload: `/Users/ali/Downloads/runs.zip`  
Imported run root: `runs/m4w14_thesis_colab_20260608`  
Derived RC@C root: `runs/m4w15_thesis_colab_20260608`

## Verdict

The Colab run is a complete thesis-profile MGP-6 final-candidate run, but it is
not eligible for `FINAL` promotion under the current promotion gate.

The extraction/repair bug is not present in this run:

- controller extraction recall: 1.0
- controller T1 extraction recall: 1.0
- b4 extraction recall: 1.0
- b4 T1 extraction recall: 1.0

The uploaded run stopped before post-run metrics because the old sanity check
flagged `b1`/`b3` and `b2`/`b3` duplicate action confusion matrices. Rechecking
with the repaired sanity logic gives `ok: true`; this was a false positive
because recency is expected to emit `KEEP` actions on MGP-6 even when extraction
is healthy.

The remaining real promotion failure is statistical:

```text
controller - b4 action accuracy diff = +0.100
paired bootstrap 95% CI = [-0.033, +0.233]
```

Because the lower CI bound is not above zero, the run should be treated as
final-candidate / thesis-supporting evidence with caveats, not promoted to final
thesis numbers by `scripts/promote_to_final.py`.

## Main Results

| System | Action accuracy | State accuracy | Over-forgetting | Under-forgetting |
|---|---:|---:|---:|---:|
| b1 no-memory | 0.133 | 0.000 | 0.000 | 0.500 |
| b2 flat-vector | 0.133 | 0.000 | 0.000 | 0.500 |
| b3 recency | 0.133 | 0.133 | 0.000 | 0.500 |
| b4 naive-overwrite | 0.517 | 0.017 | 0.400 | 0.000 |
| controller | 0.617 | 0.600 | 0.200 | 0.100 |

## Per-Type Controller Accuracy

| Type | Action accuracy | State accuracy | Main error |
|---|---:|---:|---|
| T1 preference drift | 0.800 | 0.800 | under-revision via Abstain |
| T2 episodic contradiction | 1.000 | 1.000 | none |
| T3 stable preference supersede | 0.600 | 0.600 | under-revision via Abstain |
| T4 ambiguity | 0.700 | 0.700 | over-revision |
| T5 transient trap | 0.300 | 0.200 | over-revision |
| T6 confidence laundering | 0.300 | 0.300 | over-revision / Keep |

## Lineage And Stale-Memory Diagnostics

Superseded recoverability separates the controller from destructive overwrite:

| System | Revisions | Recoverable | Recoverability |
|---|---:|---:|---:|
| b4 naive-overwrite | 54 | 0 | 0.000 |
| controller | 36 | 36 | 1.000 |

MGP-6 stale-active-memory rate:

| System | Stale-active rate |
|---|---:|
| b1 no-memory | 0.500 |
| b2 flat-vector | 0.500 |
| b3 recency | 0.250 |
| b4 naive-overwrite | 0.000 |
| controller | 0.097 |

## RC@C

Default controller operating point:

| Coverage | Revision correctness | 95% CI |
|---:|---:|---:|
| 0.667 | 0.625 | [0.475, 0.775] |

Best threshold in the replayed sweep:

| theta_abs | Coverage | Revision correctness | 95% CI |
|---:|---:|---:|---:|
| 0.50 | 0.533 | 0.719 | [0.563, 0.875] |

## Follow-Up

The strongest defensible thesis framing from this run is:

1. The repaired extraction path is healthy on MGP-6.
2. The controller improves point-estimate action and state accuracy over naive
   overwrite, but the action-accuracy win is not statistically conclusive on
   n=60.
3. The lineage auditability claim is strong: controller recoverability is 1.0
   while naive overwrite is 0.0.
4. The next tuning target is reducing over-revision on T5/T6 without losing T2
   and T4 abstention behavior.

