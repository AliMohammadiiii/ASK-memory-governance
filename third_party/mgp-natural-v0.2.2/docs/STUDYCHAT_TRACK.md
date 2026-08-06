# StudyChat Track

## Role in MGP-Natural

StudyChat is the primary natural human-LLM track. It supports write-time decisions over task state, active artifacts, corrections, uncertainty, and explicitly stated interaction preferences. Items are scoped; they are not uniformly claims about long-term personal memory.

## Source status in this execution

The attached archive is a sample derivative. It contains a 1,000-row candidate sample and 100 sampled long chats, plus aggregate metadata describing a larger source corpus. This repository therefore supports a defensible private pilot candidate pool and full-data ingestion, but it does not claim complete-corpus coverage or a full StudyChat release candidate.

The canonical Hugging Face identifier is `wmcnicho/StudyChat`. Access is gated on the current dataset page. The repository never accepts terms, captures tokens, or logs credentials on behalf of a user. `scripts/ingest_studychat.py` can use an already authorized environment or local cache; absent authorization it records the external action required.

## Source schema

Expected fields include `prompt`, `response`, `topic`, `messages`, `timestamp`, `chatId`, `userId`, `interactionCount`, `chatTitle`, `chatStartTime`, `chatTotalInteractionCount`, `llm_label`, and `semester`. In the supplied derivative, direct identifiers have already been represented as pseudonymous hash fields. The audit records actual schemas rather than assuming this list.

## Reconstruction rules

The ordering key is pseudonymous user, chat, interaction count, and stable row position. Timestamp is a consistency check. Prompt and response columns are canonical. A cumulative `messages` list is compared with the canonical prefix but cannot overwrite it.

A chat is flagged when interaction counts are missing or non-monotonic, histories begin partway through, cumulative histories revise prior turns, or the current prompt is absent from the expected final user turn. An anomaly is evidence about source quality, not permission to repair the source silently.

## State scopes

### Task and artifact state

Eligible slots include active file or dataset, selected algorithm, chosen implementation, variable name, output encoding, debugging hypothesis, task stage, explicit constraint, and correction to the active artifact. Transient implementation details are never represented as identity attributes.

### Session interaction preference

Eligible preferences are explicit and locally relevant, including response length, step-by-step guidance, no complete solution, code-only output, explanation-first behavior, and requested format. One-off assignment requirements are excluded unless they clearly function as the current interaction policy.

### Cross-session preference

This slice uses a stricter standard. Evidence must span distinct reconstructed chats for the same pseudonymous user, remain explicit, avoid copied assignment text, and be semantically consistent or explicitly updated. The evidence basis is categorized as repeated explicit preference, explicit correction, or continuation language.

## Existing `llm_label`

The source intent label may support sampling, descriptive statistics, retrieval assistance, and mining diagnostics. It is not MGP gold, evidence for a target action, an annotator-visible feature, or a benchmark prediction target.

## Known derivative findings

The supplied long-chat sample contains frequent cumulative-prefix conflicts and interaction-count gaps. This observation justifies canonical prompt-response reconstruction and conservative source-completeness rejection. It does not establish the prevalence of these anomalies in the full StudyChat corpus.

## Privacy boundary

The annotation packet excludes original user and chat identifiers, precise timestamps, unnecessary course metadata, source locators, titles, and constructor fields. Text is scanned and deterministically redacted before packet construction, then queued for manual review. Cross-session continuity remains private.

## Full-data gate

The full-data gate may be unblocked only by an authorized complete export or an already authorized local Hugging Face cache, followed by hash pinning, complete inventory, reconstruction, privacy review, continuity audit, and refreshed candidate statistics. Aggregate values in `stats.json` cannot substitute for these steps.

