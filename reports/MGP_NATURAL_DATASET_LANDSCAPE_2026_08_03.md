# MGP-Natural Dataset Landscape

Search cutoff: 2026-08-03

Status: `AUDITED_SCOPED_REVIEW`.

## Scope and conclusion

This report audits public benchmark and dataset artifacts that are close to the
MGP-Natural contract or could supply real conversations for later annotation.
It corrects the supplied search report using primary papers, official
repositories, dataset cards, and license files. It is not an exhaustive
systematic review and does not support a priority claim.

The target contract is candidate-level `KEEP`, `SUPERSEDE`, or `ABSTAIN` at
write time, with material uncertainty mapped to no commit, attributable
evidence, a resulting state, explicit lineage, and downstream evaluation over
natural conversation.

Among the public artifacts retrieved and audited by the cutoff date, none
implements that complete contract. Several evaluate memory revision,
stale-state resistance, operation traces, access control, persistent
sycophancy, or answer-time abstention. Those are substantive neighbors, not
equivalent datasets.

No numerical similarity score is reported. The scores in the supplied report
were author judgments without a published rubric or reproducible calculation.
The tiers below are qualitative and each comparison identifies the missing
features directly.

## Qualitative landscape

### Tier 1: closest operational or governance artifacts

| Artifact | Verified overlap | Material difference from MGP-Natural |
|---|---|---|
| [MemPatch-Bench](https://github.com/yuchenzhu-research/MemPatch) | Candidate-like post-admission revision, operation labels, state maps, evidence IDs, and transitions. Its policy includes `MARK_UNRESOLVED` for verified conflict and `ESCALATE` for overbroad writes. | The main release is synthetic and the 184 source-backed cases come from GitHub histories, not personal chat. Its ten-operation contract is not the MGP ternary contract, and unresolved or blocked state can itself be written. No independent paper or DOI for this title was found. |
| [Personal Agent Sycophancy Benchmark](https://arxiv.org/abs/2607.10526) | Directly tests an accept, commit, clear-context, and reuse chain. It records commit surface, response stance, role upgrade, attribution removal, and six persistence-related ratings. | Its 1,600 episodes are controlled renderings, not natural conversations. It measures harmful commitment and later reuse, not a normative per-candidate `KEEP/SUPERSEDE/ABSTAIN` label or supersession lineage. Its data terms are not a blanket MIT grant. |
| [GateMem](https://arxiv.org/abs/2606.18829) | Tests utility, requester-specific access control, and active forgetting over 91 episodes and 2,218 checkpoints. Revision, authorization change, and deletion occur in natural-language episodes. | Episodes are synthetic. Gold actions are query-time `answer`, `answer_redacted`, `refuse`, and `no_memory`, not write-time actions. It has no candidate/prior-state contract, evidence-span gold, resulting-state gold, or lineage. |

MemPatch-Bench is the closest released operation-level artifact. Personal Agent
Sycophancy Benchmark is the closest observed commit-boundary failure artifact.
GateMem is the closest released output-level governance benchmark. These three
claims describe different axes and are not a single rank ordering.

The acronym PASB is ambiguous. [Personalized Agent Security
Bench](https://arxiv.org/abs/2602.08412) is a separate synthetic OpenClaw attack
harness for leakage, tool action, persistence, extraction, and memory-edit
success. It is a security near-miss, not the persistent-sycophancy dataset and
not a correct-write benchmark.

### Tier 2: strong construct and supervision neighbors

| Artifact | Verified overlap | Material difference from MGP-Natural |
|---|---|---|
| [MemOps](https://arxiv.org/abs/2607.12893) | `Remember`, `Forget`, `Update`, `Reflect`, and trajectory traces include old/new values, triggers, and evidence spans. Tentative or retracted values are not treated as normal commitments. | Conversations and backgrounds are generated. It has no independent `KEEP` action and no uncertainty-based ternary `ABSTAIN`; its primary tasks are operation tracing and QA. |
| [MemSyco-Bench](https://arxiv.org/abs/2607.01071) | Tests current versus outdated preference use, evidence conflict, scope control, and memory-update semantics across 1,550 cases. | Histories are simulated and the evaluated output is an open-ended answer. Policy annotations are not predicted write operations, and there is no resulting-state or lineage gold. |
| [ES-MemEval](https://arxiv.org/abs/2602.01885) | Includes evolving-state conflict, user modeling, evidence, and explicit insufficient-information abstention. It has a peer-reviewed [WWW 2026 record](https://doi.org/10.1145/3774904.3792143). | Longitudinal users are synthetic composites with human refinement. Abstention is at answer time. Upstream ESConv content adds a non-commercial rights layer that must be preserved or excluded. |
| [CareCallmem](https://aclanthology.org/2022.findings-emnlp.276/) | Supervised memory operations `PASS`, `REPLACE`, `APPEND`, and `DELETE` make it a direct predecessor for redundancy and replacement. | Conversations are task-elicited human-bot episodes, not deployed natural logs. There is no `ABSTAIN`, and published data terms prohibit the modification and redistribution needed for an MGP relabeling release without permission. |

### Tier 3: useful conceptual or diagnostic neighbors

- [WRIT](https://github.com/markmhendrickson/writ) has persistence fixtures,
  prior values, provenance, and a small number of probe-level abstention cases.
  Its fixtures are authored or generated tests, not natural chat, and it has no
  candidate-level gold ternary action. It is unrelated to arXiv `2606.02908`.
- [MemStrata](https://arxiv.org/abs/2606.26511) describes duplicate, novel,
  supersede, temporal validity, and `superseded_by` lineage. The public
  repository available at the cutoff does not expose the claimed complete
  benchmark artifact, calibration release, or a verifiable data license.
- [STALE](https://huggingface.co/datasets/STALEproj/STALE) is a synthetic
  conflict and answer benchmark under CC BY 4.0, not a write-action dataset.
- [HaluMem](https://huggingface.co/datasets/IAAR-Shanghai/HaluMem) has update
  metadata over synthetic sessions but uses CC BY-NC-ND 4.0 and has no ternary
  write target.
- [Memora](https://arxiv.org/abs/2604.20006) exposes construction traces such as
  add, update, delete, and no-memory, while its benchmark scores downstream
  remembering, reasoning, and recommending. The released dataset is
  Apache-2.0.
- [LongMemEval](https://arxiv.org/abs/2410.10813), MemoryAgentBench, AMemGym,
  EvoMemBench, Mem2ActBench, RealMem, PERMA, and WritePolicyBench provide useful
  downstream, synthetic, or system-level diagnostics. None supplies natural
  candidate-level MGP gold with evidence, resulting state, and lineage.

## Real-conversation sources for label-later construction

The operational source matrix is
`reports/MGP_NATURAL_SOURCE_MATRIX.csv`. It pins source versions where possible
and records interaction origin, continuity, access, terms, privacy risk, a
GO/AMBER/RED decision, and intended use. The matrix contains 13 reviewed sources:
9 are `AMBER`, 4 are `RED`, and none is `GO`. This is an engineering risk
classification, not legal advice.

### Recommended acquisition order

1. **StudyChat, AMBER:** the strongest first pilot for real human-LLM
   interactions. It contains opt-in university-course usage with multi-turn and
   pseudonymous continuity and is published under CC BY 4.0. Access is gated.
   Dialogue-only use still requires accepted access terms, removal of grades,
   submissions, assignment identifiers, precise timestamps, and stable user
   linkage, followed by a new manual privacy review. The repository did not
   accept those terms or download the corpus during this audit.
2. **Wikipedia Talk or WikiConv, AMBER:** the strongest public human-human edit
   lineage track and the source family underlying the current feasibility seed.
   It supports corrections, deletions, restorations, and revision linkage, but
   it is editorial discussion rather than assistant memory. Attribution,
   share-alike, identity, timestamp, and deleted-content handling are required.
3. **ThoughtTrace, AMBER:** a consented and ethics-reviewed human-LLM study with
   repeated-user conversations and rich correction or preference signals. Its
   mental-state, reaction, timestamp, and demographic metadata are sensitive and
   should not enter annotation packets.
4. **SWE-chat, AMBER:** the strongest developer-agent state and outcome lineage.
   The dataset is gated and marked ODC-BY, but that database license does not
   automatically clear embedded prompts, code, repository content, model output,
   paths, diffs, or identities. Use label and pointer outputs only until those
   rights are resolved source by source.
5. **PRISM Alignment, WildChat, Chatbot Arena 33K, and Trace Commons, AMBER:**
   useful secondary pilots with mixed model-output terms, sensitive metadata,
   weak or risky user linkage, or best-effort anonymization. They are not default
   redistribution sources.

`LMSYS-Chat-1M`, OpenAssistant, ShareGPT mirrors, and CareCallmem are `RED` for a
public MGP-Natural source release. The reasons differ: non-transferable custom
terms, constructed rather than operational dialogue, weak consent/provenance
chains, or explicit modification and redistribution restrictions.

Stack Exchange PostHistory is `AMBER` as a human edit-lineage source, not as
assistant chat. Each revision must retain its date-dependent CC BY-SA treatment.
The current Stack Exchange data-access and acceptable-use path must be reviewed
before machine-learning benchmark construction.

## Corrections to the supplied research report

The supplied report is evidence input, not a final literature table. The audit
found these material corrections:

- GateMem, Personal Agent Sycophancy Benchmark, MemSyco-Bench, and ES-MemEval
  were omitted or placed too low despite strong construct overlap.
- MemPatch-Bench has substantial no-commit overlap through `MARK_UNRESOLVED` and
  `ESCALATE`; it should not be described as having no analogue to `ABSTAIN`.
- No independent public paper or DOI for MemPatch-Bench was verified. An artifact
  self-description is not a peer-reviewed publication record.
- WRIT was conflated with an unrelated paper.
- Several citation identifiers, release states, and license claims for STALE,
  MemOps, Memora, PERMA, LongMemEval, and other neighbors were incorrect or
  outdated.
- The claim that two query families produced no new candidates and established
  search saturation is false because the audit recovered substantive missed
  artifacts.
- License labels are source-specific operational evidence, not a legal opinion
  and not automatic clearance for underlying content.

## Claim boundary for paper use

The following scoped statement is supported:

> Among the verified benchmarks, several test memory revision, stale-state
> resistance, operation traces, persistent commitment, governance, or downstream
> abstention. None combines natural conversation with candidate-level
> KEEP/SUPERSEDE/ABSTAIN supervision, uncertainty-based no-commit semantics,
> attributable evidence, resulting state, and explicit lineage.

It must be paired with the search cutoff and the phrase "among the public
artifacts retrieved and audited." It must not be rewritten as first, only,
state of the art, exhaustive, universal, or proof of novelty.

The result of this source search is a governed acquisition plan, not a new
dataset. No gated terms were accepted, no third-party conversation corpus was
downloaded, and no transcript was added to the repository. Human access,
privacy, rights, annotation, and continuity-split gates remain explicit.
