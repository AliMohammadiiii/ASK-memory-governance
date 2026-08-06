# Final Claim to Evidence Matrix

Date: 2026-08-06

Raw predictions, judgments, logs, and regenerating scripts outrank narrative
reports. “Primary” refers to the paper's stated evidentiary role, not to public
release status.

| ID | Manuscript claim | Status and unit | Configuration and raw evidence | Regeneration or validation |
|---|---|---|---|---|
| C01 | ASK is a storage-independent KEEP/SUPERSEDE/ABSTAIN governance contract over typed state with retained supersession lineage. | Verified specification and reference implementation; no priority claim. | `src/ask/protocol/`, `docs/ASK_PROTOCOL.md`, `tests/test_ask_protocol.py` | `make release-check PYTHON=.venv/bin/python` |
| C02 | The evaluated V12 path is narrower than the reference protocol. | Verified code boundary. The runtime does not call the generic validator or emit generic `TransitionEvent`. | `src/ask/pipeline/orchestrator.py`, `src/ask/memory/operations.py`, `src/ask/protocol/` | Static import/call inspection plus tests |
| C03 | MGP-6 v4.3 has 900 controlled synthetic items in 100 nine-item components, split 180/180/540 items and 20/20/60 components with exact class balance. | Verified dataset metadata; component is the statistical unit. | `benchmarks/mgp6/mgp6_v4_3/release_metadata/RELEASE_FACTS.json`, `public/SPLIT_SUMMARY.json` | Release verifier and `make verify-paper-artifacts` |
| C04 | One configuration frozen before hidden scoring obtains 0.848148 accuracy and 0.847873 macro-F1 on hidden `n=540`. | Primary controlled result; no hidden baseline or ablation comparison. Model/config/prompt hashes are in the frozen run. | `runs/mgp6_v43/final_hidden/`, `experiments/mgp6_v43/FINAL_HIDDEN_CONFIG.json`, `artifacts/analysis/mgp6_v43_full_benchmark_analysis.json` | `scripts/score_mgp6_v43.py` on the already-consumed artifact; not rerun for selection |
| C05 | Component-cluster 95% intervals are `[0.803704,0.888889]` for accuracy and `[0.802075,0.889351]` for macro-F1. | Primary uncertainty estimate clustered by semantic component. | `artifacts/analysis/mgp6_v43_full_benchmark_analysis.json` | `scripts/analysis/analyze_mgp6_v43_full.py` through the tracked analysis workflow |
| C06 | Hidden confusion counts are A→A/K/S `142/30/8`, K→A/K/S `18/151/11`, and S→A/K/S `6/9/165`. | Verified over three gold classes of 180 each. | Hidden predictions plus benchmark analysis JSON | Generated `paper/paper_1/tables/v43_confusion.tex` and drift checker |
| C07 | Of 38 gold-ABSTAIN errors, 30 are state-preserving KEEP and 8 are false-commit SUPERSEDE errors. | Verified operational decomposition; false-commit rate `8/180=0.04444` among gold ABSTAIN. | Hidden predictions and v4.3 analysis JSON | Table generator and drift checker |
| C08 | MGP-6 v4.3 public-development controller, guard, baseline, ablation, and external-adapter comparisons are not hidden evidence. | Verified experiment status. | `runs/benchmark_suite/v43_public_dev_complete_qwen35_9b/`, external development runs, integration reports | `make verify-paper-artifacts` |
| C09 | Historical MGP-6 v2 has a label shortcut: conflict type reaches 1.0 and type-only reaches 0.9667 on the held-out pilot split. | Verified construct failure; v2 capability claims rejected. | `artifacts/analysis/mgp6_validity_audit.json` | Existing deterministic audit |
| C10 | LongMemEval V12 reaches `137/180=0.761111` versus naive overwrite `114/180=0.633333`. | Downstream final candidate on one fixed slice, one seed, one answer model and judge. | `runs_local/lme_final_controller_v12_qwen_180/controller/report.json`, `b4/report.json`, judgments | `scripts/evaluation/generate_lme_paper_artifacts.py` and paper drift check |
| C11 | The paired controller-over-overwrite result has Holm-corrected `p=2.9e-4`, with discordant counts `b=31`, `c=8`. | Verified paired answer comparison over 180 questions; not a write-action test. | V12 adjudicated judgments and generated LongMemEval tables | LongMemEval paper-artifact generator |
| C12 | The V12 log contains 12,654 decisions: 11,478 KEEP, 779 ABSTAIN, 397 SUPERSEDE. | Verified runtime trace over 3,547 extracted candidates; no candidate-level gold. | `runs_local/lme_final_controller_v12_qwen_180/controller/action_log.jsonl`, `artifacts/analysis/lme_v12_scorecard_analysis.json` | `scripts/analysis/analyze_lme_scorecard.py` |
| C13 | The published five-feature rule exactly replays V12 scores and actions. | Verified execution fidelity only; not correctness or optimality. | V12 action log and scorecard analysis JSON | `scripts/analysis/analyze_lme_scorecard.py` |
| C14 | LongMemEval does not establish full run homogeneity. | Verified anomaly: manifest is nonterminal and homogeneity report includes a stale launcher hash and stale pre-adjudication aggregate. | V12 `manifest.json`, `homogeneity_report.json`, final judgments/reports | `scripts/evaluation/check_lme_run_homogeneity.py` plus direct parent-artifact comparison |
| C15 | MGP-Natural v0.1.0 is a 36-item feasibility seed from 76 Wikipedia discussion excerpts with provisional single-curator labels and no valid held-out continuity split. | Quarantined, not scored. Two continuity components have sizes 35 and 1; relation/source fields recover all 36 provisional actions. | `confirmation/natural_challenge/mgp_natural_v0_1_0/archive_audit.json`, `private_packet_verification.json` | `make mgpn-natural-audit`, `make mgpn-natural-dry-run` when the external archive is present |
| C16 | MGP-Natural v0.2.2 implements construction workflows for StudyChat human-AI and WikiConv human-human tracks, but supplies no independent gold or publication-eligible benchmark. | Quarantined private-derived intake. Aggregate construction counts are workflow receipts, not evaluation denominators. | `third_party/mgp-natural-v0.2.2/`, `confirmation/natural_challenge/mgp_natural_v0_2_2_full/intake_audit.json` | `make mgpn-natural-v022-test PYTHON=.venv/bin/python` |
| C17 | MGP-Natural's intended evaluation freezes a redacted continuity packet before blinded independent labeling and separate adjudication, then splits connected continuity components and reports tracks separately. | Prospective protocol only, not completed evidence. | `paper/paper_1/sections/04_mgp6.tex`, `docs/ANNOTATION_GUIDE.md`, MGP-Natural readiness code | Must be frozen before future annotation and scoring |
| C18 | The paper PDF is ASK-centered and builds without unresolved references or overfull boxes. | Verified manuscript artifact. | `paper/paper_1/`, `build/manuscripts/paper.pdf`, `paper/paper_1/main.log` | `make paper`, PDF rendering, `pdftotext`, log scan |

## Claim exclusions

- No MGP-Natural performance, agreement, generalization, or public-release claim.
- No native external-system superiority claim from adapter-mapped actions.
- No claim that LongMemEval supplies gold ASK decisions.
- No claim that the V12 action log replays extraction, relation inference, or a
  generic byte-identical transition event.
- No priority, state-of-the-art, complete-safety, certification, or population
  claim.
