# Thesis claims-to-evidence matrix

Updated: 2026-07-15. The later construct-validity audit supersedes the older
ledger interpretation of MGP-6 v2 policy rows as `final_candidate`.

| ID | Claim | Evidence | Allowed status/wording | Prohibited wording |
| --- | --- | --- | --- | --- |
| C01 | KSA implements a three-action governed write path | `src/ksa/`, tests | implementation fact | invented updating, abstention, provenance, or lineage |
| C02 | Evaluation separates action, state/lineage, and answer | evaluation code and schema | methodological contribution | first operation-level evaluation |
| C03 | MGP-6 v2 is an author-designed 180-item pilot | gold JSONL | dataset context | independent, representative, or community benchmark |
| C04 | Conflict-type-only lookup reaches 1.000 test accuracy; type-only reaches 0.9667 | validity audit | failed construct-validity gate | held-out split isolates evidence reasoning |
| C05 | Reference test result is 0.8889 / 0.9145 | per-item predictions + audit | diagnostic on the pilot | population or external performance |
| C06 | Structured LLM test result is 0.9000 / 0.9040; paired family interval includes zero | per-item predictions + audit | neither superiority nor non-inferiority | reference matches/beats the LLM |
| C07 | Reference has 0/33 observed action false commits, upper bound 0.0868, and 10/45 missed updates | validity audit | finite-sample trade-off | zero risk or deployment safety |
| C08 | Cost regimes reverse the preferred policy | audit cost sensitivity | sensitivity analysis | validated production utility |
| C09 | No-lineage preserves action accuracy but lowers lineage integrity 0.8556→0.3689 | ablation artifacts | within-generator measurement demonstration | independent component effect |
| C10 | One human re-annotation plus a separate four-model panel | annotation audit | describe separately | multi-human IAA |
| C11 | Six-shot, mapped external, and all LongMemEval evidence are non-primary | run ledger/audits | incomplete/mapped/diagnostic/failure analysis | capability ranking or downstream improvement |
| C12 | V3 protocol is prospective and unexecuted | `benchmarks/mgp6/MGP6_V3_INDEPENDENT_PROTOCOL.md` | required confirmation design | claim that independent data or three-human annotation exist |

## Novelty boundary

The defensible contribution is a layered evaluation decomposition, a
reproducible construct-validity audit, and a transparent successor protocol.
The thesis makes no priority claim for update operations, abstention, typing,
provenance, lineage, governance, or operation-level evaluation.
