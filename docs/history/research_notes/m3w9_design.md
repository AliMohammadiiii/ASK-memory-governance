# M3-W9 Design Note: Scorecard Controller

## Position

M3-W9 implements the controller as a diagnostic scorecard, not a learned model.
Every Keep / Supersede / Abstain decision must be recomputable from the
`action_log` row: the row carries the five features, both scores, both
thresholds, the action, and a one-line rationale.

G2 is treated as passed per `NOTES/G2_gate_decision.md`: the repaired relation
dev set reached `contradict-F1=0.696` and `supersede-F1=1.000`. The important
implementation consequence is to use the timestamp-aware M2-W7 classifier
path and preserve its residual uncertainty instead of hiding it.

## Feature Rationale

`c` is extraction confidence. M2-W5 found that local synthetic data inflates
coverage and can make extraction look cleaner than it is. Keeping raw
confidence visible prevents the controller from treating weak extractions as
strong updates.

`e` is evidence quality. It combines normalized span length with deterministic
recency. Span specificity addresses over-broad evidence, while recency follows
the M2-W7 finding that timestamp handling was necessary for reliable
supersede routing.

`f` is marker burden. Negation and hedge flags from the frozen extractor schema
are used as a precision penalty: negation can be a true update signal, but it is
also where extraction polarity mistakes become expensive.

`r` is the signed relation classifier signal. Support is positive,
contradiction/supersession is negative, and unclear/independent is zero. The
temporal qualifier modulates magnitude (`newer > same > unknown > older`) so
the controller can distinguish a strong current contradiction from an older or
ambiguous one.

`rho` is the type stability prior: `stable_pref=0.9`,
`episodic_fact=0.6`, `transient_pref=0.3`. This encodes the initial hypothesis
that stable preferences should require more evidence before replacement than
episodic facts or transient preferences.

## Weights

The initial score is:

```text
S_rev = 1.0*c + 0.8*e - 0.7*f + 1.2*r + 0.5*rho
S_abs = (1-c) + f - |r|
```

The largest absolute weight is on `r` because G2 establishes the classifier as
the main supersession signal, while the action rule still requires `r < 0` for
Supersede. Evidence quality and extraction confidence are next because M2
showed local data and extractor outputs are the main upstream validity risks.
Marker burden is subtractive to protect precision when hedges or negation make
the extracted candidate brittle. The type prior is deliberately smaller: it is
a hypothesis to be stress-tested at M4-W16, not an empirical fit.

## Threshold Hypothesis

Supersede thresholds are parameterized by type and ordered:

```text
stable_pref (0.90) > episodic_fact (0.75) > transient_pref (0.55)
```

Stable preferences require the highest score to replace because they represent
longer-lived beliefs. Transient preferences are expected to change more easily.
Episodic facts sit between the two: some facts are stable, but timestamped
updates should be allowed when evidence and relation signals are strong.

Abstain thresholds are also per-type:

```text
stable_pref (0.60), episodic_fact (0.70), transient_pref (0.80)
```

The stable preference threshold is lowest because a weak or unclear update to a
stable preference is more costly than a missed transient update. M4-W16 should
validate both threshold families with sensitivity sweeps.

## M2 Risk Defenses

The M1 notes show the checked-in LongMemEval slice is synthetic and too easy;
the controller therefore does not use baseline accuracy as a tuning signal.

The M2-W5 extractor note records useful marker fields and the risk that local
coverage is inflated by synthetic coffee-preference turns. The scorecard uses
`c`, `e`, and `f` to keep those extractor claims inspectable.

The M2-W7 error audit shows the main residual classifier failures are
`contradict -> unclear` and `unclear -> support`; therefore Abstain fires before
Supersede and `S_abs` rises when confidence is low, markers are present, or the
relation magnitude is weak.

The G2 note shows deterministic timestamp routing was necessary. The scorecard
keeps temporal modulation inside `r` and recency inside `e`, so a reviewer can
see whether a replacement came from current evidence or a weaker temporal
qualifier.
