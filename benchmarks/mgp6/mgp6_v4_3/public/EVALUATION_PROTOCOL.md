# Evaluation Protocol

Submit one JSON object per line with exactly:

```json
{"public_id":"MGP43-...","action":"KEEP"}
```

Allowed actions are `KEEP`, `SUPERSEDE`, and `ABSTAIN`. The evaluator rejects missing, duplicate, unknown, or extra IDs.

Report accuracy, macro-F1, per-class precision/recall/F1, confusion matrix, and component-cluster bootstrap confidence intervals. Do not tune on hidden gold.
