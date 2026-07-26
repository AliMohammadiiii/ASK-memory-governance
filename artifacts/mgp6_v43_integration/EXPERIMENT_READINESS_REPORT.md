# MGP-6 v4.3 experiment readiness report

## Release readiness

The supplied release reports `READY_FOR_FINAL_PAPER_EXPERIMENTS` and zero failed
release gates. That release-level verdict does not authorize a repository-local
hidden run.

## Repository readiness

Ready for model-backed development selection. The public-only v4.3 loader,
prediction validator, evaluator, private ignore protection, regression tests,
development configuration registry, and development-only freeze index are in
place. The train engineering fixture passed; it is not a system-performance
experiment. A three-item public train live-provider smoke with OpenRouter/Qwen
also passed after disabling reasoning (`reasoning.effort=none`): 3 predictions,
0 failures, 0 parse retries, and 0 invalid responses. The public runner records invalid
model responses before failing, retries parse-level format failures separately
from HTTP retries, and can pass OpenRouter `reasoning.effort=none` for
development smoke runs. A complete public-dev `decision_zero_shot` run with
OpenRouter/Qwen is now recorded in `DEV_EXPERIMENT_REPORT.md`: it produced 180
coverage-validated predictions with zero API/parse failures, but its action
distribution was heavily skewed to `SUPERSEDE` (177 of 180). It is development
evidence only and is not selected for final hidden evaluation.

Commit `c37b8878512cd4125a4beb793dd2a6625c35a9df` implements distinct public
views and policies for B1--B4, the live and rules controllers, and all required
ablations. The deterministic rules controller has completed a public-dev run:
180 validated predictions, zero failures/retries/invalid responses, and no
provider or hidden-gold access. Its development accuracy was 0.3333 and
Macro-F1 was 0.2434, so it is not selected for hidden evaluation. See
`ADAPTER_IMPLEMENTATION_REPORT.md` for the adapter contract and evidence.

The B1--B4 model-backed baseline adapters have also completed public dev with
the same provider/model, frozen development decoding controls, and a clean
tracked worktree recorded in each manifest. All produced 180
coverage-validated predictions with zero failures/retries/invalid responses.
Their accuracy / Macro-F1 values were B1: 0.3667 / 0.3150, B2: 0.3556 / 0.2380,
B3: 0.3389 / 0.2309, and B4: 0.3444 / 0.2064. These are development-only
evidence, not selected hidden configurations; the full protocol and public-only
scores are in `DEV_EXPERIMENT_REPORT.md`.

The original full-view ASK live-model controller completed public dev with 180
coverage-validated predictions and zero failures/retries/invalid responses, but
its accuracy/Macro-F1 was only 0.3333/0.1771. The current public-indexed-
evidence controller routes precisely the two public messages linked by the
record index, excludes the four unlinked messages, and uses an ABSTAIN-only
public-evidence guard. Its public-dev run completed with 180/180 validated
predictions, zero failures/retries/invalid responses, and accuracy/Macro-F1
0.8556/0.8566. All four required public-dev ablations are now complete and
scored between Macro-F1 0.1905 and 0.2398. This is a selected development
candidate only; neither it nor any ablation is a frozen hidden configuration.

## Hidden-run authorization

Generated and verified. `experiments/mgp6_v43/FINAL_HIDDEN_CONFIG.json` freezes
the selected public-indexed-evidence `live_model_controller` at runtime commit
`af12517a15c9d9af4bb3bf95f7caee7330e6b243`; GitHub Actions CI run
[`30189412351`](https://github.com/AliMohammadiiii/KSA-memory-governance/actions/runs/30189412351)
for that exact SHA completed successfully. It records the release/split facts,
provider and exact requested model ID, prompt/system-prompt hashes, decoding,
seed, retry policy, timeout, concurrency, evaluator/runtime hashes, and the
environment lock.

`FINAL_HIDDEN_RUN_AUTHORIZATION.json` has `authorized: true` and binds every
one of those controls. It authorizes exactly one complete hidden prediction
generation. It does not authorize hidden-gold inspection during generation, and
it requires closing the model run, validating coverage, and hashing prediction
files before a separate local-private scoring step.

## Current gate

`READY_FOR_FINAL_HIDDEN_RUN`. No hidden model call, hidden prediction file, or
private scoring result exists yet. Hidden inputs and gold remain solely in the
ignored private boundary.
