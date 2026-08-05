# Robustness Protocol

## Perturbation families

- paraphrased candidate turns;
- context truncation;
- distractor turns;
- conflicting evidence;
- evidence-order perturbation;
- anonymization perturbation;
- long-context distance;
- source-domain shift;
- slot-name variation;
- candidate ambiguity;
- confidence calibration; and
- annotation-guideline sensitivity.

## Gold-preservation review

Every perturbation is prospectively classified as either benchmark-preserving or decision-changing. A benchmark-preserving variant must retain principal, slot, chronology, and decision semantics after independent review. Decision-changing variants receive a new gold decision or are used only as counterfactual diagnostics.

## Hidden-test discipline

Perturbation templates, severity levels, and seeds are frozen before hidden-test unsealing. Hidden-test variants are not used for prompt, model, threshold, or controller tuning.

## Current boundary

Protocols and synthetic tests can be prepared now. No natural robustness result is claimed until independently adjudicated base items and reviewed perturbations exist.

