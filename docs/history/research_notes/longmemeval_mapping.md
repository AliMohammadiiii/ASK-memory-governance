# LongMemEval-S competency → KSA action mapping

**Source:** Wu et al. (2025), *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory*, §3 (task taxonomy).
**Purpose:** establishes which of the three controller actions {Keep, Supersede, Abstain} each LongMemEval competency primarily exercises. This is a **dominant-action** mapping — many sessions exercise more than one action; the table records the action whose correctness is decisive for the gold answer being scored correctly.

## 1. Action recap (proposal §I.5.5)

- **Keep** — the candidate memory does not warrant overwriting prior beliefs (low S_rev, no Abstain trigger). Includes "store as new" when there is no prior to compare against — i.e., the controller chooses *not* to revise existing memory and is free to add the new item.
- **Supersede** — the candidate explicitly contradicts a prior memory and the contradiction is corroborated/explicit/recent enough to flip belief (S_rev ≥ θ_sup).
- **Abstain** — the candidate's relation to prior memory is ambiguous (S_abs ≥ θ_abs, or relation_class = "unclear"). The controller declines to act; existing memory is preserved.

## 2. Mapping

| LongMemEval competency | Dominant KSA action | Rationale | Secondary actions exercised |
|---|---|---|---|
| **single-session-user** (a single fact stated by the user, recalled within the same session) | **Keep** | Candidate is a fresh user-stated fact with no prior to contradict. The controller's job is to commit the extraction and not let noise overwrite it. | Abstain (when extractor confidence is low) |
| **single-session-assistant** (a fact previously *output by the assistant* must be recalled later in the same session) | **Keep** | Same shape as single-session-user but the source is the assistant's own utterance. No revision pressure. | — |
| **single-session-preference** (the user states a preference once and expects it honored later in the same session) | **Keep** | A first-time preference statement; no prior to supersede. Demonstrates that Keep does not mean "do nothing" — it means "commit the new memory without revising priors." | Supersede (rare — only if the preference reverses something stated minutes earlier) |
| **multi-session** (information distributed across multiple prior sessions must be aggregated to answer) | **Keep** *(retrieval-dominant)* | Retrieval, not revision. Each session's facts were committed via Keep at extraction time; the question stresses recall, not the action policy. | — |
| **knowledge-update** (a fact stated in an earlier session is later updated by the user; the assistant must answer with the *new* value) | **Supersede** | The defining test of revision behavior. If the controller fails to mark the old fact `superseded` and link the new one, the answer will be wrong even with perfect retrieval. | Abstain (if the update is hedged or partial) |
| **temporal-reasoning** (the answer depends on *when* facts were stated and their `valid_from` ordering) | **Supersede** *(temporally-aware)* | Correct lineage via `supersedes_id` is what makes "what did I prefer in March?" answerable. Tests that the controller writes time-stamped supersedes rather than overwriting. | Keep (for facts that were never revised) |
| **abstention** (the user did not state a fact, and the assistant must refuse to fabricate one) | **Abstain** | Direct test of the Abstain action and its associated abstention behavior at answer time. Exercises the controller's "don't act on ambiguous evidence" precision bias. | — |

## 3. Coverage and stratification implications

To exercise all three controller actions on the 50-session slice, stratification across the seven competencies above is required. A naive uniform sample over LongMemEval-S would over-represent multi-session and single-session-* (the largest categories in S) and under-represent abstention and knowledge-update — exactly the categories that exercise Supersede and Abstain.

**Slicer choice:** stratify by competency, target ≥ 5 distinct competencies in the 50-session slice, with a **floor of 5 sessions** for `knowledge-update` and 5 for `abstention` (the two categories that load on Supersede and Abstain). The remaining ~40 slots are sampled proportionally over the other five competencies. This keeps the slice representative of LongMemEval-S's distribution while guaranteeing the slice can falsify the controller in both directions.

## 4. What this is *not*

- Not a perfect 1:1 mapping. A single LongMemEval session can exercise multiple actions (e.g., a knowledge-update session also Keeps subsidiary facts).
- Not a mapping of *gold answers* to actions. The mapping is on *which action's failure breaks the answer*. Many sessions can be answered correctly even with sub-optimal Keep/Supersede choices, as long as retrieval surfaces the right span.
- Not a substitute for MGP-6, which exists precisely because LongMemEval under-samples adversarial revision dynamics (rapid flips, half-retractions, proxy-of-proxy contradictions). MGP-6 is added in Month 3.

## 5. Decision: greenlight the slicer

≤ 20% of LongMemEval-S sessions resist clean mapping (the borderline cases are temporal-reasoning sessions with no explicit revision and multi-session sessions whose facts span the boundary between knowledge-update and single-session-*). This is below the §6 risk-3 escalation threshold; proceed with implementation without consulting the advisor.
