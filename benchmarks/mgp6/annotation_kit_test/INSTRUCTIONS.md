# MGP-6 v2 Blind Annotation Instructions

You are labelling memory *write* decisions for a personal-assistant memory
system. For each item you see:

1. **Earlier dialogue**, what the user said in previous sessions.
2. **Current memory**, the record(s) the system currently stores.
3. **New event**, one new piece of information arriving now.

Choose exactly ONE action per item (column `annotator_action`):

- **SUPERSEDE**, the new event reliably states a *durable* replacement value
  for the same slot, coming from the user. The stored value should be
  replaced (old record retained as history).
- **KEEP**, the stored durable value should remain authoritative. Use this
  when the new event is only a clear *temporary* override ("just for
  tonight", "my usual still stands") or does not durably change the slot.
- **ABSTAIN**, do not commit. Use when evidence is not directly from the
  user (unattributed note, forum post, third party), is garbled or
  low-confidence, is a tool/assistant guess the user never confirmed, or is
  a hedged/uncertain temporary candidate.

Rules of engagement:

- Follow the decision procedure in `annotation_manual_v2.md` (provided
  separately). Read it fully BEFORE starting.
- Label independently. Do not discuss items with the dataset author until
  all labels are submitted.
- Do not consult the dataset file or any system output.
- If you are torn between two actions, pick the one the manual's decision
  tree yields, and note your hesitation in `annotator_notes`.
- Optionally fill `annotator_value` (the new slot value you would store, for
  SUPERSEDE/KEEP-with-override) and `annotator_confidence` (0-1).

Fill the columns in `annotation_sheet.csv` and save as
`annotation_sheet_filled.csv` in the same folder.
