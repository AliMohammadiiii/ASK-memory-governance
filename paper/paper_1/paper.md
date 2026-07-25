# Introduction

A language agent that persists across sessions must decide what to do
with each candidate memory: retain the current record, replace it with a
newer one, or decline to commit because the evidence is insufficient.
Deployed systems often make this decision through opaque LLM tool calls
(Packer et al. 2023; Chhikara et al. 2025) or additive event logs (Park
et al. 2023). A wrong write can remain latent until much later: an
ambiguous statement becomes a durable fact, a stale preference survives,
or a correction erases its predecessor. End-to-end QA then reveals an
error without identifying which layer caused it.

We take the write transition itself as the object of evaluation. The
action is <span class="smallcaps">Keep</span>, lineage-preserving
<span class="smallcaps">Supersede</span>, or write-time
<span class="smallcaps">Abstain</span> over typed, provenance-tracked
records. This combines established ideas from selective prediction (Chow
1970; Geifman and El-Yaniv 2017), belief revision (Alchourrón et al.
1985), and agent memory operations (Yan et al. 2025; Chhikara et al.
2025; Wang 2026). We claim neither the individual operations nor
abstention, typing, provenance, and lineage as new. The contribution is
a harness that makes their decision-, state-, and answer-layer
consequences separately observable.

We first exercise the harness on MGP-6 v2, a $`180`$-item, English,
synthetic pilot. The collection was authored by the same project that
implemented the reference policy and has only one independent human
re-annotation of its test split. It is therefore a diagnostic
instrument, not an independently established benchmark. Rather than
treating a held-out item split as sufficient, we explicitly test whether
scenario metadata predicts the action and whether item-level inference
understates within-template dependence.

Our contributions and findings are:

1.  We formalize the three write actions and release a layered evaluator
    for action correctness, state invariants, lineage, stale retrieval,
    selective risk, and asymmetric write costs.

2.  We add train/dev-fitted shortcut baselines and
    template-family/minimal-pair cluster bootstrap. Conflict type alone
    predicts every held-out test action; type alone predicts $`96.7\%`$.
    This is direct evidence that the current pilot does not identify
    general evidence reasoning.

3.  On the held-out test split, a transparent reference policy reaches
    $`0.8889`$ accuracy and a structured LLM policy reaches $`0.9000`$;
    the paired family-cluster interval includes zero. Zero observed
    reference-policy false commits has a non-zero finite-sample upper
    bound and trades against missed updates, so the preferred policy
    changes with the cost matrix.

This reframing turns a weakness into a falsifiable result: an item-level
test split can look clean while a family label still determines the
answer. The released artifacts make that failure visible and specify the
gate for a successor collection: independent construction, all three
actions within each conflict family, blinded multi-human annotation,
trajectory-level cases, and a hidden test set frozen after policy
development.

# Related Work

We position ASK against five clusters. For each we name the nearest
precedent and state precisely what we build on. Our claim concerns the
operationalization and controlled evaluation of a particular
combination, not priority for any individual component.

#### Agent memory systems with write operations.

MemGPT/Letta (Packer et al. 2023), Mem0 (Chhikara et al. 2025), A-MEM
(Xu et al. 2025), and RMM (Tan et al. 2025) manage a persistent store
with per-item operations (add/update/delete/no-op, or merge-vs-add).
Memory-R1 (Yan et al. 2025) is the clearest prior formalization of
memory writes as a discrete action space, learned by RL. We do not claim
to introduce the action space. The differences we defend are that (i)
`NOOP` in these systems means “nothing new,” not “too ambiguous to
commit,” so there is no uncertainty-driven refusal; and (ii) they are
primarily rewarded at the answer level, without a shared diagnostic that
separately scores the write and its resulting state. Our released rule
is a transparent reference policy, not a claim of a new learning
algorithm.

#### Write-time conflict resolution and lineage.

Zep/Graphiti (Rasmussen et al. 2025) invalidates contradicted graph
edges with bi-temporal timestamps rather than deleting them — the
strongest shipped prior on supersession-with-history. TOKI (Wang 2026)
argues, formally, that contradiction resolution *is* write-time
concurrency control, and types the heuristic family (including an
*await-confirmation* operator functionally equivalent to
<span class="smallcaps">Abstain</span>) as bitemporal operators with
audit rows. FadeMem (Wei et al. 2026) classifies new-vs-old memory pairs
and applies decay/fusion. Relative to these, storing lineage or
provenance is not new; our distinct piece is to make the write a
*governed, scored* decision with an abstain option, and to measure
lineage integrity separately from the action label. Reddy and Challaram
(2026) independently report that deterministic conflict resolution beats
LLM judgment on a consolidation benchmark, motivating independent tests
of transparent policies rather than validating our author-designed pilot
by analogy.

#### Typed memory.

MemGuard (Ha et al. 2026) assigns each memory an explicit functional
role at write time to prevent contamination, and MemOS (Li et al. 2025)
types memory levels. Typed memory is therefore precedented; what we add
is a measured ablation of typing inside the pilot, reported as a
mechanism diagnostic rather than an independently identified causal
effect.

#### Diagnostics and evaluation for memory.

HaluMem (Chen et al. 2025) is the nearest prior on operation-level
evaluation, separately scoring extraction, update, and QA for
hallucinations; we do not claim to introduce operation-level evaluation.
STALE (Chao et al. 2026) probes *frozen agents at read time* for
recognition of stale beliefs and shares MGP-6 v2’s construct names
(implicit conflict, premise resistance), but defines no write actions,
abstention, or lineage. The Supersede environment (Patel 2026) isolates
the answer-level “supersession gap” on LongMemEval-M and trains the
behavior end-to-end. GateMem (Ren et al. 2026) uses the phrase “memory
governance” for authorization across principals — a different axis from
our epistemic write correctness. LongMemEval (Wu et al. 2025) and LoCoMo
(Maharana et al. 2024) are end-to-end QA benchmarks that cannot
attribute a failure to the write decision. MGP-6 v2 operationalizes
joint scoring of write-time
<span class="smallcaps">Keep</span>/<span class="smallcaps">Supersede</span>/<span class="smallcaps">Abstain</span>
decisions and resulting memory state; we do not claim that
operation-level or state-level evaluation itself is new.

#### Selective prediction, belief revision, knowledge editing.

The reject option (Chow 1970; El-Yaniv and Wiener 2010; Geifman and
El-Yaniv 2017) and learning to defer (Madras et al. 2018; Mozannar and
Sontag 2020) are the origin of <span class="smallcaps">Abstain</span>;
RSCB-MC (Iscan 2026) already applies abstention to memory *retrieval* in
coding agents. We therefore never claim to introduce abstention to
memory systems; we measure what an explicit abstain-on-write option
contributes within our controlled diagnostic and claim no priority for
the mechanism. AGM belief revision (Alchourrón et al. 1985) is the
intellectual ancestor of
<span class="smallcaps">Keep</span>/<span class="smallcaps">Supersede</span>;
we cite it as ancestry only and prove no postulate compliance. Knowledge
editing (Meng et al. 2022, 2023) governs *how* to change a parametric
belief and assumes the edit should happen; we govern *whether* to commit
an external write. Finally, PrefEval (Zhao et al. 2025) and PersonaMem
(Jiang et al. 2025) motivate testing preference changes on independently
constructed natural dialogue.

#### Scope of contribution.

Each component has named precedents: Memory-R1 for write actions; Zep
and TOKI for retained history; MemGuard and MemOS for typing;
deterministic policy work including Reddy and Challaram (2026); and
HaluMem and STALE for evaluation. We therefore make the narrower
contribution claim that this work operationalizes and audits an explicit
three-way policy — <span class="smallcaps">Keep</span>,
<span class="smallcaps">Supersede</span>, or
<span class="smallcaps">Abstain</span> — over typed, provenance-tracked
records with supersession lineage, and evaluates that implementation at
three separate layers: decision, stored state/lineage, and downstream
answer. The controlled conjunction, its validity checks, and the
measurements they enable are the contribution; update operations,
version history, provenance, typing, abstention, and operation-level
evaluation are not claimed as inventions.

# Problem Formulation

We formalize write-time memory governance for a single atomic semantic
slot, which is the unit MGP-6 v2 controls. This scoping is deliberate:
it isolates the write decision from retrieval and answer generation so
that the decision can be scored on its own.

## Memory records, state, and types

A memory record $`m`$ is a tuple
$`m = (\mathit{id}, \tau, v, c, \sigma, \pi, t, s)`$, where
$`\mathit{id}`$ is a unique identifier, $`\tau \in \mathcal{T}`$ is the
memory *type*, $`v`$ is the stored value (written in the auditable form
`slot = value`), $`c \in [0,1]`$ is a stored confidence,
$`\sigma \in \{\textsf{active}, \textsf{superseded}\}`$ is the record’s
*status*, $`\pi`$ is the supersession pointer (`supersedes_id`, possibly
null), $`t`$ is a validity timestamp, and $`s`$ is the record’s
*provenance* (the source event/turn that established it). We use three
types, ordered by expected durability:
``` math
\mathcal{T} = \{\textsf{stable\_pref},\ \textsf{episodic\_fact},\ \textsf{transient\_pref}\}.
```
A *memory state* $`M`$ is a set of records for the slot. A well-formed
state has at least one <span class="sans-serif">active</span> record
and, for a preference slot, exactly one active
<span class="sans-serif">stable_pref</span> record; every non-null
$`\pi`$ points at a retained <span class="sans-serif">superseded</span>
record.

## Candidate update and evidence

At a write step the agent extracts a *candidate update* $`u`$ (a
proposed new value with a type guess) from a *perturbation event*
against the current state $`M`$. The decision is driven by *evidence*
associated with $`u`$: the extraction confidence, the specificity and
recency of the supporting span, the presence of negation or hedging
markers, and the classified logical relation of $`u`$ to the active
record (support, contradiction, or independence). These evidence signals
are the inputs to the policy of
Section <a href="#sec:method" data-reference-type="ref"
data-reference="sec:method">5</a>; the formulation itself is agnostic to
how they are computed.

## Action space and transition function

The controller emits one action
$`a \in \mathcal{A} = \{\textsc{Keep}, \textsc{Supersede}, \textsc{Abstain}\}`$,
which induces a deterministic transition $`M' = \delta(M, u, a)`$:

- $`\delta(M, u, \textsc{Keep}) = M`$ for durable records: the prior
  active record is preserved unchanged. A *clear temporary* override may
  be added only as a separate <span class="sans-serif">active</span>
  <span class="sans-serif">transient_pref</span> record, never by
  mutating the durable one.

- $`\delta(M, u, \textsc{Supersede})`$ marks the prior active record
  <span class="sans-serif">superseded</span> and adds one
  <span class="sans-serif">active</span> successor whose $`\pi`$ points
  back at it. The prior value is *retained*, not deleted, and no longer
  active in the slot; exactly one active record of the successor’s type
  remains.

- $`\delta(M, u, \textsc{Abstain}) \equiv M`$ at the modeled field
  level: the state is byte-for-byte equivalent.
  <span class="smallcaps">Abstain</span> is a decision to *not commit*
  the candidate, distinct from committing a null value.

A transition is an *invalid commit* if it changes the active state on an
item whose gold action is <span class="smallcaps">Abstain</span>, or
otherwise violates a state-transition invariant
(Section <a href="#sec:mgp6" data-reference-type="ref"
data-reference="sec:mgp6">4</a>). This is the failure the abstention and
provenance machinery is designed to prevent.

## Four distinctions the formulation makes explicit

These distinctions are load-bearing and are frequently conflated in
memory systems; we make them explicit because MGP-6 v2 scores each.

<div class="description">

<span class="smallcaps">Keep</span> is a positive write-time decision to
retain the current active value in the presence of a candidate update;
it is not the same as a record simply not being retrieved at answer
time. <span class="smallcaps">Keep</span> operates on the state;
retrieval absence operates on a later read.

A no-op (e.g. Mem0’s `NOOP`) fires when the candidate carries *nothing
new*. <span class="smallcaps">Abstain</span> fires when the candidate
carries something potentially relevant but the evidence is *too weak or
ambiguous to commit* (unreliable source, non-atomic claim, referential
uncertainty). Both leave the state unchanged, but only
<span class="smallcaps">Abstain</span> is an uncertainty-driven refusal;
this is why we report an external
`NOOP`$`\to`$<span class="smallcaps">Abstain</span> mapping only as an
upper bound (Section <a href="#sec:results" data-reference-type="ref"
data-reference="sec:results">7</a>).

<span class="smallcaps">Abstain</span> in our formulation is a
*write-layer* non-commit: the store is not modified. It is distinct from
an answer-layer refusal to respond (as scored by end-task benchmarks),
which occurs downstream and does not change memory. MGP-6 v2 withholds
the evaluation query until the write is committed precisely so that
answer-time behavior cannot leak into the write decision.

<span class="smallcaps">Supersede</span> replaces the active value while
*preserving* the prior record as
<span class="sans-serif">superseded</span> with a lineage edge. Deletion
(and active forgetting) removes information and is explicitly out of
scope for this work; the reserved
<span class="sans-serif">forgotten</span> status never occurs in our
data.

</div>

## Objective

Let $`y`$ be the target action and let $`C(a,y)`$ be an
application-specific cost. The policy objective is
``` math
\begin{equation}
\pi^* = \arg\min_\pi\;\mathbb{E}[C(\pi(M,u),y)],
\end{equation}
```
subject to state and lineage invariants. The cost is intentionally not
assumed symmetric: committing on ambiguous evidence, missing a valid
update, and unnecessarily abstaining can have different consequences. We
therefore report the full action confusion and expected loss under
multiple pre-declared cost regimes rather than treating accuracy as a
universal utility. State validity, lineage integrity, stale retrieval,
and calibration remain separate outcomes; they are not folded into a
post-hoc scalar chosen after seeing test results.

# MGP-6 v2: A Decision-Level Diagnostic

MGP-6 v2 is an author-designed diagnostic slice for write-time memory
governance. We use the word *diagnostic* deliberately and throughout: it
is a pilot instrument for probing decision mechanisms, not a community
benchmark, an independent test collection, or a measure of general QA or
retrieval efficiency. All scenarios are synthetic, English-only, and
low-risk, and contain no real personal data.

## Conflict taxonomy and distribution

The pilot contains $`180`$ scenarios, $`30`$ for each of six scenario
families, with an action imbalance of $`90`$
<span class="smallcaps">Supersede</span>, $`66`$
<span class="smallcaps">Abstain</span>, and $`24`$
<span class="smallcaps">Keep</span> that we handle by reporting macro-F1
and per-action results rather than accuracy alone.

<div class="center">

| Type | Diagnostic condition | Rows | Gold action(s) |
|:---|:---|---:|:---|
| T1 | preference drift over time | 30 | 30 <span class="smallcaps">Supersede</span> |
| T2 | episodic factual correction | 30 | 30 <span class="smallcaps">Supersede</span> |
| T3 | stable-preference replacement | 30 | 30 <span class="smallcaps">Supersede</span> |
| T4 | ambiguity / referent uncertainty | 30 | 30 <span class="smallcaps">Abstain</span> |
| T5 | transient capture trap | 30 | 24 <span class="smallcaps">Keep</span>, 6 <span class="smallcaps">Abstain</span> |
| T6 | confidence laundering | 30 | 30 <span class="smallcaps">Abstain</span> |

</div>

T1–T3 target supersession under different durability regimes; a subset
of $`10`$ rows per type is *cue-free*
(<span class="sans-serif">implicit_conflict</span>), i.e. the
perturbation contains none of the explicit change cues (“now,” “instead
of,” “actually,” …) yet still fixes a mutually exclusive current value.
T4/T6 require <span class="smallcaps">Abstain</span> because evidence is
referentially uncertain or laundered through an unreliable source; T5
separates a durable preference (<span class="smallcaps">Keep</span>)
from a temporary override. Some supersession cases also have
minimal-pair T4 partners. These pairs test a narrow cue change, but they
do not remove the global shortcut: conflict type still determines the
action throughout v2.

## Query modes

Every scenario carries one query mode used only at the answer stage:
*direct recall* ($`108`$ items), *premise resistance* ($`45`$; the query
embeds the stale/unsupported value as a false presupposition that a
correct answer must reject), and *implicit application* ($`27`$; a
concrete task solvable only by using the active value, with neither
value named in the query). These modes let us measure whether a system
that makes the right write decision also refuses stale premises and
applies the active value in context.

## Splits

Splits are $`60`$ train / $`30`$ dev / $`90`$ test, stratified so each
type contributes $`10/5/15`$ rows and T5 contributes $`8/2`$, $`4/1`$,
$`12/3`$
<span class="smallcaps">Keep</span>/<span class="smallcaps">Abstain</span>.
No template-family identifier and no minimal-pair group crosses a split
boundary, which blocks literal family overlap. It does *not* block
construct leakage when the same family-to-action rule holds in every
split. We therefore treat the $`90`$-item test split as a held-out item
split only, never as independent validation.

## Pre-specified validity checks

Before comparing policies we fit lookup baselines on train+dev and
evaluate them on test using only (i) the six-way type, (ii) the finer
conflict type, and (iii) source/reliability/temporal metadata. We also
compute macro-accuracy and paired bootstrap intervals by
`template_family_id`; for `minimal_pair_group_id`, unpaired items are
singleton clusters. A shortcut baseline that approaches the full policy
is a failed construct-validity check, not a competitive result.

## Schema, invariants, and scoring

Each row provides a dialogue prefix, prior memory state, perturbation
event, source/temporal metadata, a gold action, an auditable gold memory
state, the query mode, the expected answer, and a regex judge
specification with required (`include`) and forbidden (`not_include`)
spans. Evaluation is two-stage: the write stage sees only the prefix,
prior state, and perturbation and commits an action and predicted state
*before* the query is revealed; the answer stage then answers from the
predicted state. A validator enforces the state-transition invariants of
Section <a href="#sec:actionspace" data-reference-type="ref"
data-reference="sec:actionspace">3.3</a> (one active record per slot,
retained superseded predecessors, single-successor lineage,
byte-equivalent <span class="smallcaps">Abstain</span> states,
active-only answers), and a released corpus prints
`VALIDATION PASSED: 180 examples, 0 errors`.

We score two families of metric (full definitions in
Appendix <a href="#app:metrics" data-reference-type="ref"
data-reference="app:metrics">13</a>): *decision-level* — action
accuracy, per-action and macro-F1, and the action false-commit rate on
gold-<span class="smallcaps">Abstain</span> items — and *memory-state* —
state invalid-commit on gold-<span class="smallcaps">Abstain</span>
items, five-condition lineage integrity on
<span class="smallcaps">Supersede</span> items, and stale-retrieval rate
(the fraction of answers surfacing a forbidden superseded value). Two
shipped forgetting-rate metrics saturate at $`1.0`$ for every system and
are excluded from all tables as uninformative.

## Annotation: one independent annotator plus a model audit panel

We are precise about the annotation evidence, which has two separate
components and must never be described as multi-annotator human
agreement.

<div class="description">

re-labelled the $`90`$-item test split against the annotation manual.
Raw agreement with gold is $`0.9889`$
($`\text{CI}_{95}\,[0.9667, 1.0]`$), Cohen’s $`\kappa = 0.98146`$
($`\text{CI}_{95}\,[0.93997, 1.0]`$), with exactly one disagreement
(`MGP6V2-T3-TEST-016`, an
<span class="sans-serif">implicit_conflict</span>
<span class="smallcaps">Supersede</span>$`\to`$<span class="smallcaps">Abstain</span>
case). This is $`n{=}1`$ annotator; the annotator’s human status rests
on author attestation, not on evidence in the released files.

(four distinct LLMs) independently labelled the same $`90`$ items:
Fleiss $`\kappa = 0.9815`$ across the panel, with the majority vote
matching gold on all $`90`$ items ($`88`$ unanimous). This is a model
audit, not human inter-annotator agreement.

</div>

The larger human review sheet ($`180`$ rows) exists but is unfilled; a
genuine multi-annotator human release is future work
(Section <a href="#sec:limitations" data-reference-type="ref"
data-reference="sec:limitations">8</a>). The panel and the single
annotator may share the manual’s reading because the labelling policy is
unambiguous by construction — a construct-validity caveat we carry
explicitly.

## Construction grounding

Scenario *shapes* were informed by inspecting real corpora — LongMemEval
knowledge-update items and its false-premise (`_abs`) questions, Memora
operation chains, GateMem’s machine-readable judge structure, and named
confidence-laundering patterns — but every released row is a newly
authored synthetic paraphrase; no source content is reused. This grounds
the failure modes without importing personal data, and it is the reason
MGP-6 v2 shares construct names (implicit conflict, premise resistance)
with concurrent read-side work (Chao et al. 2026), which we cite to
disambiguate.

# Reference Policies

The name ASK simply abbreviates the three actions
(<span class="smallcaps">Keep</span>/<span class="smallcaps">Supersede</span>/<span class="smallcaps">Abstain</span>);
it is not a claim that the action vocabulary is novel. The released
pilot includes two policies over this vocabulary and two shortcut
probes. All commit actions pass through the same deterministic state
transition and invariant validator.

## Transparent reference policy

The reference policy parses the raw perturbation text and prior state
with auditable lexical predicates. In priority order it (1)
<span class="smallcaps">Abstain</span>s on unattributed third-party,
laundered, garbled, or unconfirmed evidence; (2)
<span class="smallcaps">Abstain</span>s on a hedged temporary candidate;
(3) <span class="smallcaps">Keep</span>s the durable value and
optionally stores a separate transient note for a clear temporary
override; (4) <span class="smallcaps">Supersede</span>s when a usable
durable candidate conflicts with the active value; and (5) otherwise
<span class="smallcaps">Abstain</span>s. The complete predicates and
value parser are released in `benchmarks/mgp6/systems/`.

This policy is deterministic and inspectable, but it was written against
the same annotation manual and phrase generator as the pilot. It is
therefore a *reference implementation of the policy*, not an
independently learned method. A five-feature weighted scorecard exists
in the broader prototype code, but it did not generate the reported
MGP-6 predictions; we do not describe or claim it as the evaluated
method. This distinction removes an earlier implementation–manuscript
mismatch.

## State transition and lineage

On <span class="smallcaps">Supersede</span> the transition marks the
prior record superseded, appends one active successor, and points its
`supersedes_id` to the retained predecessor. On
<span class="smallcaps">Keep</span> a clear temporary override may be a
separate transient record; on <span class="smallcaps">Abstain</span> the
modeled state is unchanged. The evaluator scores these state properties
independently of the action, so a correct action with corrupted lineage
is not counted as a correct state transition.

## Structured and unstructured LLM policies

We also run the governance decision through a structured LLM policy
prompted with the typed state, candidate, evidence fields, and the three
action definitions, and an unstructured zero-shot policy that receives
the raw event and prior state without that scaffold. Both use
`qwen/qwen3.5-9b`. Because the prompt, candidate representation, and
pilot were author-designed together, even this comparison remains
diagnostic.

## Shortcut probes

The type-only and conflict-type-only probes learn a majority action for
each metadata value on train+dev and apply the lookup unchanged to test.
They never read the dialogue, prior value, or candidate evidence. Their
purpose is to test whether the collection rewards scenario recognition
without memory reasoning.

# Experimental Setup

## Systems

The main test comparison contains the transparent reference policy, the
structured LLM policy, and the unstructured zero-shot policy described
in Section <a href="#sec:method" data-reference-type="ref"
data-reference="sec:method">5</a>. Before interpreting them, we run
type-only, conflict-type-only, and source/reliability/temporal lookup
probes fitted on train+dev. Four structurally limited systems (no
memory, flat retrieval, recency, and naive overwrite) and component
ablations are retained as pilot mechanism checks in the appendix; they
are not competitive peers.

A six-demonstration LLM decision run produced $`174/180`$ predictions.
Aligning its six missing identifiers to `INVALID` yields a
coverage-aware audit, but the run is incomplete and excluded from every
comparison and hypothesis test.

Adapter runs for Mem0, Letta, Graphiti, and MemOS are preserved as
harness diagnostics in the artifact. Their native operations do not
match our action vocabulary, so mapped action accuracies are excluded
from the main empirical claim. A successor evaluation must compare
observable final state, stale retrieval, downstream answer, latency, and
cost under each system’s native API.

## Metrics and denominators

Primary decision-level metrics are computed over the held-out
$`90`$-item test: action accuracy, macro-F1, and per-action
precision/recall/F1. We report action false-commit rate over
gold-<span class="smallcaps">Abstain</span> items, missed-update rate
over gold-<span class="smallcaps">Supersede</span> items, and
unnecessary-abstention rate over
non-<span class="smallcaps">Abstain</span> items. A zero event count is
accompanied by a finite-sample upper bound.

Memory-state outcomes are lineage integrity (a five-condition per-item
score on gold-<span class="smallcaps">Supersede</span> cases) and
stale-retrieval rate. We additionally report top-label ECE/Brier,
risk–coverage, and expected loss under balanced, commit-averse, and
update-responsive cost matrices. Confidence results are descriptive
because neither policy was calibrated on an independent set. Full
formulas and commands are in
Appendix <a href="#app:metrics" data-reference-type="ref"
data-reference="app:metrics">13</a>.

## Statistical methods

Systems are paired by scenario id. The primary uncertainty estimate is a
$`10{,}000`$-replicate bootstrap over `template_family_id`; we repeat it
with minimal-pair groups plus singleton unpaired items. We report
family-macro and item-weighted estimates. Exact two-sided McNemar tests
are secondary because item independence is doubtful. No equivalence or
non-inferiority claim is made: no margin was pre-specified.

For zero observed action false commits we report the exact one-sided 95%
upper bound $`1-0.05^{1/n}`$ rather than interpreting the observed rate
as population zero. These calculations quantify uncertainty inside this
collection; they do not repair its construct leakage or establish
external generalization.

Annotation agreement is reported as Cohen’s $`\kappa`$ for one
independent human annotator against the author gold and, separately,
Fleiss $`\kappa`$ for a four-model audit panel. The latter is never
described as human inter-annotator agreement.

# Results on MGP-6 v2

All results below are recomputed from released per-item predictions. We
lead with validity checks because they determine how the policy scores
may be interpreted.

## The shortcut check fails

The conflict-type-only lookup fitted on train+dev reaches $`1.0000`$
accuracy and macro-F1 on test; the coarser six-way type lookup reaches
$`0.9667`$ accuracy and $`0.9471`$ macro-F1. Neither sees the dialogue
or memory state. Thus the held-out item split does not test whether a
system reasons about evidence quality, provenance, or temporal scope:
scenario recognition is sufficient. This failed check dominates every
policy comparison below.

| Probe              | Test accuracy | Macro-F1 | Unseen values |
|:-------------------|--------------:|---------:|--------------:|
| Six-way type only  |        0.9667 |   0.9471 |             0 |
| Conflict type only |        1.0000 |   1.0000 |             0 |

Shortcut probes fitted on train+dev and evaluated on the held-out test
split. These probes never read the dialogue or memory state.
{#tab:shortcut}

## Held-out policy comparison

| Policy | Accuracy | Family 95% CI | Macro-F1 | Action false-commit | Missed-update |
|:---|---:|---:|---:|---:|---:|
| Reference policy | 0.8889 | \[0.8125, 0.9688\] | 0.9145 | 0.0000 | 0.2222 |
| Structured LLM | 0.9000 | \[0.8333, 0.9688\] | 0.9040 | 0.0606 | 0.1556 |
| Unstructured zero-shot LLM | 0.6778 | \[0.5625, 0.7917\] | 0.6542 | 0.5758 | 0.2222 |

Held-out test results ($`n{=}90`$). Family CIs resample the 48 template
families and report family-macro accuracy. Action false-commit is over
33 gold-<span class="smallcaps">Abstain</span> items; missed-update is
over 45 gold-<span class="smallcaps">Supersede</span> items. The
shortcut result in
Table <a href="#tab:shortcut" data-reference-type="ref"
data-reference="tab:shortcut">1</a> limits interpretation of all rows.
{#tab:main}

On test, the reference policy reaches $`0.8889`$ accuracy/$`0.9145`$
macro-F1 and the structured LLM reaches $`0.9000`$/$`0.9040`$. The
reference-minus-LLM risk difference is $`-0.0111`$; the paired
template-family cluster interval $`[-0.094,0.063]`$ includes zero (exact
item-level McNemar: $`b=4,c=5,p=1.0`$). These data support neither
superiority nor non-inferiority. The unstructured zero-shot policy
reaches $`0.6778`$/$`0.6542`$, but that gap is itself evaluated on the
shortcut-leaking pilot and is not a general scaffold-effect estimate.

## Safety–responsiveness trade-off

The reference policy makes no action false commits on the 33 test
abstention items, but the exact one-sided 95% upper bound is $`0.0868`$,
not zero risk. It misses $`10/45`$ required updates ($`0.2222`$) and
unnecessarily abstains on $`10/57`$ non-abstention items ($`0.1754`$).
The structured LLM action false-commit rate is $`2/33=0.0606`$, while
its missed-update rate is $`7/45=0.1556`$. Consequently the reference
policy has lower expected loss under the commit-averse matrix ($`0.111`$
vs. $`0.189`$), but higher loss under the update-responsive matrix
($`0.556`$ vs. $`0.433`$). Safety is therefore cost-conditional, not an
absolute ordering. Top-label ECE is $`0.156`$ for the reference
confidence and $`0.302`$ for the LLM confidence; both are descriptive
because neither confidence was calibrated on an independent set.

## State and component diagnostics

Full-corpus ablations are retained only as within-generator mechanism
checks. Removing abstention raises invalid-commit from $`0.0`$ to
$`1.0`$; removing provenance yields $`0.606`$; removing typing drives
<span class="smallcaps">Keep</span> F1 to $`0.0`$. Removing lineage
leaves action accuracy unchanged at $`0.9222`$ but drops lineage
integrity $`0.8556\to0.3689`$. The last result demonstrates the central
measurement point: action accuracy alone cannot reveal a corrupted
transition history.

| Configuration | Action acc. | Macro-F1 | Induced failure signature |
|:---|---:|---:|:---|
| Full system | 0.9222 | 0.9399 | invalid-commit 0.0; lineage integrity 0.8556 |
| $`-`$ abstention | 0.5556 | 0.4278 | invalid-commit $`0.0 \to 1.0`$ |
| $`-`$ provenance | 0.7000 | 0.7428 | invalid-commit $`0.0 \to 0.606`$ |
| $`-`$ typing | 0.7889 | 0.5680 | <span class="smallcaps">Keep</span> F1 $`\to 0.0`$ |
| $`-`$ lineage | 0.9222 | 0.9399 | action unchanged; lineage integrity $`0.8556 \to 0.3689`$ |

Within-generator component ablations of the reference policy on MGP-6 v2
($`n{=}180`$). Each removal produces a distinct diagnostic signature.
Invalid-commit is over gold-<span class="smallcaps">Abstain</span>
items; lineage integrity is over
gold-<span class="smallcaps">Supersede</span> items. Values transcribed
from results-ledger version 1.1; these are not independent effect
estimates. {#tab:ablation}

The $`174/180`$ six-shot run remains incomplete and is excluded from all
comparisons. Mapped external-system action scores and non-homogeneous
downstream runs remain in the artifact audit only; neither supports a
main-paper capability claim.

# Discussion, Threats to Validity, and Reproducibility

## What the evidence supports

The evidence supports the usefulness of separating write, state, and
answer failures and the necessity of testing diagnostic shortcuts before
interpreting policy scores. It also supports within-pilot mechanism
observations, such as lineage corruption being invisible to action
accuracy. It does not support population accuracy, deployment safety,
reference-policy superiority, non-inferiority, or downstream benefit.

## Threats to validity

#### Internal and construct validity.

The same project designed the taxonomy, manual, generator, gold labels,
and reference policy. Conflict type perfectly predicts test actions, so
item holdout and high annotation agreement cannot establish construct
validity. Family-cluster bootstrap corrects one form of dependence but
cannot repair the deterministic family–label mapping.

#### External validity.

MGP-6 v2 is small, synthetic, English-only, single-step, and
single-slot. It lacks independent generation, natural dialogue,
multi-step trajectories, multiple model families, multiple seeds, and
native external-system comparisons. None of its rates estimates a
deployment population.

#### Annotation.

There is one independent human re-annotation of the test split plus a
four-model audit panel. Agreement may be high because the manual and
family-to-label mapping are deterministic. The model panel is not human
inter-annotator agreement, and one human annotator cannot establish
multi-annotator reliability or construct validity.

#### Statistical conclusion.

There are only 48 test template families, and cluster intervals are
correspondingly wide. The reference–LLM comparison is a null, not
evidence of equality. Confidence calibration and cost matrices were not
validated on independent data, so they expose trade-offs rather than
certify risk. The one-sided upper bound attached to zero action false
commits prevents a sample zero from being presented as a safety
guarantee.

## Ethics and scope

The pilot contains synthetic, low-risk scenarios with no real personal
data. Our target is epistemic write correctness. Memory poisoning,
multi-principal access control, privacy, deletion compliance, and
security governance are separate threat models that we do not test. We
make no production-safety claim.

## Successor-dataset gate

A successor release must be constructed after the evaluated policies and
thresholds are frozen; use an independent generator and hidden labels;
include <span class="smallcaps">Keep</span>,
<span class="smallcaps">Supersede</span>, and
<span class="smallcaps">Abstain</span> within every conflict family; add
adversarial minimal pairs and 5/10/20-step trajectories; obtain blinded
labels from at least three humans; and include natural or independently
paraphrased dialogue. The test set must remain sealed until all
development choices are fixed. These are requirements for stronger
claims, not future-work decorations.

## Reproducibility statement

The dataset, schema, validator, reference policies, and per-item
predictions are released. The construct-validity script regenerates
shortcut tables, family/minimal-pair cluster intervals, calibration,
risk–coverage, and cost sensitivity from those artifacts. The incomplete
six-shot run and mapped external adapters remain explicitly non-primary.
Reproduction commands are in
Appendix <a href="#app:repro" data-reference-type="ref"
data-reference="app:repro">14</a>. Independent construction, multi-human
annotation, and trajectory data are release gates for a successor
benchmark rather than boxes silently marked complete here.

# Conclusion

We separated memory writing from the state and answer layers it affects,
then used that separation to audit an author-designed pilot rather than
merely report its highest score. The central empirical result is
negative and useful: conflict type alone perfectly predicts the pilot’s
held-out actions, while the transparent reference policy and structured
LLM are statistically unresolved and exchange safety for responsiveness
under different costs. The release makes these limitations reproducible
through per-item predictions, shortcut probes, cluster-aware
uncertainty, finite-sample risk bounds, and lineage metrics. A credible
successor must be independently constructed, contain all actions within
each conflict family, use blinded multi-human labels, and test
multi-step natural trajectories. Until then, MGP-6 v2 is a pilot for
evaluating the evaluator, not evidence of general memory-governance
performance.

# Dataset Schema

Each MGP-6 v2 row is a JSON object. Exact field names are grouped below;
the machine-readable schema remains authoritative.

    identity: scenario_id, version, type, subtype, difficulty,
              split, quality_flags
    dialogue: base_dialogue_prefix, initial_memory_state,
              perturbation_event, semantic_slot
    evidence: evidence_source, source_reliability, temporal_scope,
              conflict_type, memory_age
    gold:     gold_action, gold_memory_state
    answer:   query_mode, evaluation_query, expected_answer,
              forbidden_answer_patterns, judge_spec
    audit:    rationale_notes, annotation_rule_ids, template_family_id,
              minimal_pair_group_id

A memory record contains the following fields:

    id, type, text, confidence, status, supersedes_id, valid_from,
    semantic_slot, source

The text field uses the auditable `slot = value` form; confidence lies
in $`[0,1]`$; and status is active or superseded. In v2, the judge’s
`not_include` list equals the forbidden-answer-pattern list. A correct
answer must satisfy every include regex and no not-include regex.
Scenario identifiers have the form `MGP6V2-TYPE-SPLIT-NNN`.

#### State-transition invariants (enforced by the validator).

Every state has $`\ge 1`$ active record; a preference slot has exactly
one active <span class="sans-serif">stable_pref</span>; every
`supersedes_id` points to a retained
<span class="sans-serif">superseded</span> record;
<span class="smallcaps">Supersede</span> retains the predecessor and
adds one active successor pointing back at it;
<span class="smallcaps">Keep</span> preserves the prior durable record
(a clear temporary override may be added only as a separate active
<span class="sans-serif">transient_pref</span>);
<span class="smallcaps">Abstain</span> leaves the state byte-for-byte
equivalent at the modeled field level; answers contain an active value
and no superseded or forbidden value; duplicate equivalent active
records are invalid.

# Annotation Process

The annotation manual encodes ten decision rules (R1–R10): require
direct-user evidence else abstain (R1); require same user/slot/topic
(R2); require an atomic self-contained claim (R3); durable lexical
change cues (R4); a reliable durable same-slot contradiction supersedes
(R5); a clear temporary override keeps durable memory while a hedged
temporary candidate abstains (R6); low-confidence/garbled/ laundered
evidence abstains (R7); expected answers use active memory only (R8);
preserve superseded records for lineage (R9); no duplicate active
memories for paraphrases (R10). Cue-free rows do not depend on R4 and
follow inferential certainty under R1–R3 and R5.

Annotation evidence has two components
(Section <a href="#sec:annotation" data-reference-type="ref"
data-reference="sec:annotation">4.6</a>), reported separately and never
conflated: (a) **one independent human annotator** over the $`90`$-item
test split — raw agreement $`0.9889`$ ($`\text{CI}\,[0.9667,1.0]`$),
Cohen’s $`\kappa = 0.98146`$ ($`\text{CI}\,[0.93997,1.0]`$), macro-F1
$`0.9913`$, one disagreement (`MGP6V2-T3-TEST-016`); and (b) a
**four-model audit panel** over the same items — Fleiss
$`\kappa = 0.9815`$, majority vote matching gold on all $`90`$ ($`88`$
unanimous). The $`180`$-row human review sheet is unfilled; a
multi-annotator human release is future work.

# Prompts

The extraction and relation-classification prompt templates are released
under `prompts/`; baseline answer prompts are packaged under
`src/ask/baselines/prompts/`. The combined prompt set is frozen; its
SHA-256 (computed as `sha256` over the sorted files, each contributed as
`relpath + NUL + bytes + NUL`) is recorded in
`artifacts/manifests/freeze_hashes.json` and reproduced in
Appendix <a href="#app:repro" data-reference-type="ref"
data-reference="app:repro">14</a>.

# Metric Formulas

Action canonicalization
(`KEPT`$`\to`$<span class="smallcaps">Keep</span>,
`NOOP`$`\to`$<span class="smallcaps">Abstain</span>,
unknown$`\to`$`INVALID`) is applied to both sides before comparison;
gold actions are only
<span class="smallcaps">Keep</span>/<span class="smallcaps">Supersede</span>/<span class="smallcaps">Abstain</span>,
so `INVALID`/`INVALID_COMMIT` predictions are always incorrect.

<div class="description">

$`\frac{1}{N}\sum_i \mathbf{1}[\,\text{canon}(g_i) = \text{canon}(p_i)\,]`$;
the primary denominator is the $`N=90`$ held-out test split.

unweighted mean of per-action F1 over
$`\{`$<span class="smallcaps">Keep</span>,
<span class="smallcaps">Supersede</span>,
<span class="smallcaps">Abstain</span>$`\}`$; an action’s F1 is $`0`$ if
precision$`+`$recall$`=0`$.

over gold-<span class="smallcaps">Abstain</span> items,
$`\frac{1}{|\text{ABS}|}\sum_{i\in\text{ABS}} \mathbf{1}[\,p_i \ne \textsc{Abstain}\,]`$;
lower is better. This is the denominator used in
Table <a href="#tab:main" data-reference-type="ref"
data-reference="tab:main">2</a> and the cost analysis.

over gold-<span class="smallcaps">Abstain</span> items, the fraction for
which the predicted state contains an active record outside the allowed
gold state. This separate state-level diagnostic catches a nominal
<span class="smallcaps">Abstain</span> that still writes memory and is
used in the full-corpus ablations.

fraction of gold-<span class="smallcaps">Supersede</span> items not
predicted as <span class="smallcaps">Supersede</span>.

fraction of non-<span class="smallcaps">Abstain</span> items predicted
as <span class="smallcaps">Abstain</span>. These make the cost of
conservative errors visible.

ten-bin top-label ECE, correctness Brier score, and accuracy/risk at
coverage $`0.25,0.50,0.75,1.00`$. These are descriptive without an
independent calibration set.

mean $`C(a,y)`$ under balanced, commit-averse, and update-responsive
matrices declared in the released audit script.

over gold-<span class="smallcaps">Supersede</span> items, mean of a
five-point row score: (1) old record marked
<span class="sans-serif">superseded</span>; (2) new record
<span class="sans-serif">active</span> with correct text; (3) new
record’s `supersedes_id` points at the old id; (4) old text no longer
active in the slot; (5) exactly one active record of the new type in the
slot.

over items declaring forbidden-answer patterns, the fraction whose
predicted answer matches any forbidden pattern; lower is better.

on premise-resistance items, the answer must include all required spans,
exclude all forbidden spans, and contain an explicit rejection token.

`over_forgetting_rate` and `under_forgetting_rate` saturate at $`1.0`$
for every system and never appear in a table.

</div>

#### Statistics.

The primary interval is a $`10{,}000`$-replicate cluster bootstrap over
template families, repeated with minimal-pair groups and singleton
unpaired items. Exact item-level McNemar is secondary. A zero action
false-commit count uses the one-sided upper bound $`1-0.05^{1/n}`$. No
equivalence or non-inferiority test is licensed because no margin was
pre-specified.

# Reproducibility Commands

#### Validate the dataset.

    python3 benchmarks/mgp6/validate_mgp6.py \
      --input benchmarks/mgp6/data/mgp6_v2.jsonl --strict
    # expects: VALIDATION PASSED: 180 examples, 0 errors.

#### Reproduce the validity, cluster, calibration, and cost audit.

    python3 scripts/analysis/audit_mgp6_validity.py
    # writes artifacts/analysis/mgp6_validity_audit.{json,md}

#### Audit bibliography and citation coverage.

    python3 scripts/release/audit_bibliography.py

#### Successor protocol.

The released v3 design is prospective: it is not evidence that
independent construction or three-human annotation has occurred.

<div id="refs" class="references csl-bib-body hanging-indent">

<div id="ref-alchourron1985agm" class="csl-entry">

Alchourrón, Carlos E., Peter Gärdenfors, and David Makinson. 1985. “On
the Logic of Theory Change: Partial Meet Contraction and Revision
Functions.” *Journal of Symbolic Logic* 50 (2): 510–30.
<https://doi.org/10.2307/2274239>.

</div>

<div id="ref-chao2026stale" class="csl-entry">

Chao, Hanxiang, Yihan Bai, Rui Sheng, Tianle Li, and Yushi Sun. 2026.
“STALE: Can LLM Agents Know When Their Memories Are No Longer Valid?”
*arXiv Preprint arXiv:2605.06527*, ahead of print.
<https://doi.org/10.48550/arXiv.2605.06527>.

</div>

<div id="ref-halumem2025" class="csl-entry">

Chen, Ding, Simin Niu, Kehang Li, et al. 2025. “HaluMem: Evaluating
Hallucinations in Memory Systems of Agents.” *arXiv Preprint
arXiv:2511.03506*, ahead of print.
<https://doi.org/10.48550/arXiv.2511.03506>.

</div>

<div id="ref-chhikara2025mem0" class="csl-entry">

Chhikara, Prateek, Dev Khant, Saket Aryan, Taranjeet Singh, and Deshraj
Yadav. 2025. “Mem0: Building Production-Ready AI Agents with Scalable
Long-Term Memory.” *arXiv Preprint arXiv:2504.19413*, ahead of print.
<https://doi.org/10.48550/arXiv.2504.19413>.

</div>

<div id="ref-chow1970reject" class="csl-entry">

Chow, C. K. 1970. “On Optimum Recognition Error and Reject Tradeoff.”
*IEEE Transactions on Information Theory* 16 (1): 41–46.
<https://doi.org/10.1109/TIT.1970.1054406>.

</div>

<div id="ref-elyaniv2010selective" class="csl-entry">

El-Yaniv, Ran, and Yair Wiener. 2010. “On the Foundations of Noise-Free
Selective Classification.” *Journal of Machine Learning Research* 11:
1605–41. <https://www.jmlr.org/papers/v11/el-yaniv10a.html>.

</div>

<div id="ref-geifman2017selective" class="csl-entry">

Geifman, Yonatan, and Ran El-Yaniv. 2017. “Selective Classification for
Deep Neural Networks.” *Advances in Neural Information Processing
Systems* 30.
<https://proceedings.neurips.cc/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html>.

</div>

<div id="ref-ha2026memguard" class="csl-entry">

Ha, Hyeonjeong, Jeonghwan Kim, Cheng Qian, et al. 2026. “MemGuard:
Preventing Memory Contamination in Long-Term Memory-Augmented Large
Language Models.” *arXiv Preprint arXiv:2605.28009*, ahead of print.
<https://doi.org/10.48550/arXiv.2605.28009>.

</div>

<div id="ref-iscan2026rscbmc" class="csl-entry">

Iscan, Mehmet. 2026. “Learning When to Remember: Risk-Sensitive
Contextual Bandits for Abstention-Aware Memory Retrieval in LLM-Based
Coding Agents.” *arXiv Preprint arXiv:2604.27283*, ahead of print.
<https://doi.org/10.48550/arXiv.2604.27283>.

</div>

<div id="ref-jiang2025personamem" class="csl-entry">

Jiang, Bowen, Zhuoqun Hao, Young Min Cho, et al. 2025. “Know Me, Respond
to Me: Benchmarking LLMs for Dynamic User Profiling and Personalized
Responses at Scale.” *Conference on Language Modeling*.
<https://openreview.net/forum?id=6ox8XZGOqP>.

</div>

<div id="ref-li2025memos" class="csl-entry">

Li, Zhiyu, Chenyang Xi, Chunyu Li, et al. 2025. “MemOS: A Memory OS for
AI System.” *arXiv Preprint arXiv:2507.03724*, ahead of print.
<https://doi.org/10.48550/arXiv.2507.03724>.

</div>

<div id="ref-madras2018defer" class="csl-entry">

Madras, David, Toniann Pitassi, and Richard Zemel. 2018. “Predict
Responsibly: Improving Fairness and Accuracy by Learning to Defer.”
*Advances in Neural Information Processing Systems* 31.
<https://proceedings.neurips.cc/paper/2018/hash/09d37c08f7b129e96277388757530c72-Abstract.html>.

</div>

<div id="ref-maharana2024locomo" class="csl-entry">

Maharana, Adyasha, Dong-Ho Lee, Sergey Tulyakov, Mohit Bansal, Francesco
Barbieri, and Yuwei Fang. 2024. “Evaluating Very Long-Term
Conversational Memory of LLM Agents.” *Proceedings of the 62nd Annual
Meeting of the Association for Computational Linguistics (Volume 1: Long
Papers)*, 13851–70. <https://doi.org/10.18653/v1/2024.acl-long.747>.

</div>

<div id="ref-meng2022rome" class="csl-entry">

Meng, Kevin, David Bau, Alex Andonian, and Yonatan Belinkov. 2022.
“Locating and Editing Factual Associations in GPT.” *Advances in Neural
Information Processing Systems* 35: 17359–72.
<https://proceedings.neurips.cc/paper_files/paper/2022/hash/6f1d43d5a82a37e89b0665b33bf3a182-Abstract-Conference.html>.

</div>

<div id="ref-meng2023memit" class="csl-entry">

Meng, Kevin, Arnab Sen Sharma, Alex Andonian, Yonatan Belinkov, and
David Bau. 2023. “Mass-Editing Memory in a Transformer.” *International
Conference on Learning Representations*.
<https://openreview.net/forum?id=MkbcAHIYgyS>.

</div>

<div id="ref-mozannar2020defer" class="csl-entry">

Mozannar, Hussein, and David Sontag. 2020. “Consistent Estimators for
Learning to Defer to an Expert.” *Proceedings of the 37th International
Conference on Machine Learning*, 7076–87.
<https://proceedings.mlr.press/v119/mozannar20b.html>.

</div>

<div id="ref-packer2023memgpt" class="csl-entry">

Packer, Charles, Sarah Wooders, Kevin Lin, et al. 2023. “MemGPT: Towards
LLMs as Operating Systems.” *arXiv Preprint arXiv:2310.08560*, ahead of
print. <https://doi.org/10.48550/arXiv.2310.08560>.

</div>

<div id="ref-park2023generative" class="csl-entry">

Park, Joon Sung, Joseph O’Brien, Carrie J. Cai, Meredith Ringel Morris,
Percy Liang, and Michael S. Bernstein. 2023. “Generative Agents:
Interactive Simulacra of Human Behavior.” *Proceedings of the 36th
Annual ACM Symposium on User Interface Software and Technology*.
<https://doi.org/10.1145/3586183.3606763>.

</div>

<div id="ref-patel2026supersede" class="csl-entry">

Patel, Vedant. 2026. “Supersede: Diagnosing and Training the
Memory-Update Gap in LLM Agents.” *arXiv Preprint arXiv:2606.27472*,
ahead of print. <https://doi.org/10.48550/arXiv.2606.27472>.

</div>

<div id="ref-rasmussen2025zep" class="csl-entry">

Rasmussen, Preston, Pavlo Paliychuk, Travis Beauvais, Jack Ryan, and
Daniel Chalef. 2025. “Zep: A Temporal Knowledge Graph Architecture for
Agent Memory.” *arXiv Preprint arXiv:2501.13956*, ahead of print.
<https://doi.org/10.48550/arXiv.2501.13956>.

</div>

<div id="ref-reddy2026deterministic" class="csl-entry">

Reddy, Vikas, and Sumanth Challaram. 2026. “Don’t Ask the LLM to Track
Freshness: A Deterministic Recipe for Memory Conflict Resolution.”
*arXiv Preprint arXiv:2606.01435*, ahead of print.
<https://doi.org/10.48550/arXiv.2606.01435>.

</div>

<div id="ref-ren2026gatemem" class="csl-entry">

Ren, Zhe, Yibo Yang, Yimeng Chen, et al. 2026. “GateMem: Benchmarking
Memory Governance in Multi-Principal Shared-Memory Agents.” *arXiv
Preprint arXiv:2606.18829*, ahead of print.
<https://doi.org/10.48550/arXiv.2606.18829>.

</div>

<div id="ref-tan2025rmm" class="csl-entry">

Tan, Zhen, Jun Yan, I-Hung Hsu, et al. 2025. “In Prospect and
Retrospect: Reflective Memory Management for Long-Term Personalized
Dialogue Agents.” *Proceedings of the 63rd Annual Meeting of the
Association for Computational Linguistics (Volume 1: Long Papers)*,
8416–39. <https://doi.org/10.18653/v1/2025.acl-long.413>.

</div>

<div id="ref-wang2026toki" class="csl-entry">

Wang, Ziming. 2026. “TOKI: A Bitemporal Operator Algebra for
Contradiction Resolution in LLM-Agent Persistent Memory.” *arXiv
Preprint arXiv:2606.06240*, ahead of print.
<https://doi.org/10.48550/arXiv.2606.06240>.

</div>

<div id="ref-fademem2026" class="csl-entry">

Wei, Lei, Xiao Peng, Xu Dong, Niantao Xie, and Bin Wang. 2026. “FadeMem:
Biologically-Inspired Forgetting for Efficient Agent Memory.” *arXiv
Preprint arXiv:2601.18642*, ahead of print.
<https://doi.org/10.48550/arXiv.2601.18642>.

</div>

<div id="ref-wu2025longmemeval" class="csl-entry">

Wu, Di, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai-Wei Chang, and Dong
Yu. 2025. “LongMemEval: Benchmarking Chat Assistants on Long-Term
Interactive Memory.” *International Conference on Learning
Representations*. <https://openreview.net/forum?id=UBvm2bIyxz>.

</div>

<div id="ref-xu2025amem" class="csl-entry">

Xu, Wujiang, Zujie Liang, Kai Mei, Hang Gao, Juntao Tan, and Yongfeng
Zhang. 2025. “A-MEM: Agentic Memory for LLM Agents.” *arXiv Preprint
arXiv:2502.12110*, ahead of print.
<https://doi.org/10.48550/arXiv.2502.12110>.

</div>

<div id="ref-yan2025memoryr1" class="csl-entry">

Yan, Sikuan, Xiufeng Yang, Zuchao Huang, et al. 2025. “Memory-R1:
Enhancing Large Language Model Agents to Manage and Utilize Memories via
Reinforcement Learning.” *arXiv Preprint arXiv:2508.19828*, ahead of
print. <https://doi.org/10.48550/arXiv.2508.19828>.

</div>

<div id="ref-zhao2025prefeval" class="csl-entry">

Zhao, Siyan, Mingyi Hong, Yang Liu, Devamanyu Hazarika, and Kaixiang
Lin. 2025. “Do LLMs Recognize Your Preferences? Evaluating Personalized
Preference Following in LLMs.” *International Conference on Learning
Representations*. <https://openreview.net/forum?id=QWunLKbBGF>.

</div>

</div>
