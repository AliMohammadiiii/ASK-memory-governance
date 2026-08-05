---
ai_generated: true
artifact_status: protocol_draft
---

# AI-provisional annotation protocol

The `annotate-ai-provisional` target reads only blind items. It never reads constructor labels,
source locators, source action flags, continuity keys, or source labels. It writes three immutable
machine-generated passes and one majority consensus file under `data/derived/ai_provisional/`.

The local reproducible implementation is a deterministic offline provisional controller. It is not
an independent human annotator, does not reproduce a paid model API call, and does not create gold.
Every row is tagged `AI_PROVISIONAL_NOT_GOLD`, `human_verified: false`, and
`requires_human_review: true`.

Human review is mandatory for action disagreement, any exclusion, low confidence, differing
resulting values, differing evidence spans, privacy findings, content removal/restoration, and
cross-session preference items.

