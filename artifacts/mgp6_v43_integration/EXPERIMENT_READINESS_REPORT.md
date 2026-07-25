# MGP-6 v4.3 experiment readiness report

## Release readiness

The supplied release reports `READY_FOR_FINAL_PAPER_EXPERIMENTS` and zero failed
release gates. That release-level verdict does not authorize a repository-local
hidden run.

## Repository readiness

Ready for development-adapter work and continued development selection. The public-only v4.3 loader,
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

The public decision runner now accepts only the separately implemented
`decision_zero_shot` system. It deliberately rejects B1--B4 and controller
labels because those historical ASK systems do not yet have distinct v4.3
adapters; merely recording an alternate label would not change the method. The
registry marks those systems as adapter-required, which blocks their use in
development comparison and blocks configuration freeze.

## Hidden-run authorization

Not generated. `authorized` is not true. Hidden inputs and hidden gold are held
only in the ignored private boundary, and no model call or hidden scoring has
occurred.

## Next gate

Implement and test distinct v4.3 adapters for the selected historical systems,
then run them on public dev and record every dev-informed choice. Only then
replace the development index with a fully frozen final configuration and
authorization audit. Do not open hidden gold before finalized prediction files
are coverage-validated and hashed.
