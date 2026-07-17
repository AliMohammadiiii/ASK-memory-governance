# Final handoff

## Outcome

The repository, diagnostic paper, thesis review package, validity audit, and successor protocol are assembled and locally validated. The scientific framing is now deliberately narrower than the historical ledger: MGP-6 v2 fails a construct-validity gate, so its policy results are diagnostic rather than evidence of controller superiority or deployment safety.

Two confirmation tracks remain genuinely external: role-separated MGP-6 v3 construction with three blinded human annotators, and the homogeneous LongMemEval-M `final-1.1` run. The latter is `externally_pending` because the supplied hosted-model credential returned HTTP 403 before inference; no prediction from that attempt entered the ledger.

## Headline evidence

- MGP-6 v2 has 180 schema-valid scenarios, but conflict type alone reaches 1.0000 held-out accuracy and macro-F1; type alone reaches 0.9667 / 0.9471. This shortcut failure is the primary result.
- On the 90-item test split, the lexical reference policy reaches 0.8889 accuracy / 0.9145 macro-F1 versus 0.9000 / 0.9040 for the structured LLM. The paired template-family interval for the accuracy difference is [−0.0938, 0.0625], so neither superiority nor non-inferiority is supported.
- The reference policy has 0/33 observed action false commits on test, with a one-sided 95% upper bound of 0.0868; it misses 10/45 required updates. Cost matrices reverse the preferred policy between commit-averse and update-responsive settings.
- The six-shot row has 174 predictions. Coverage-aware alignment adds six `INVALID` predictions and yields 0.7833 / 0.7692, but the row remains `incomplete`.
- LongMemEval has no final result. Contaminated v7, selected failure replay, and incomplete top-up evidence are retained only for failure analysis; the historical 139/180 construction is not a performance result.
- Annotation evidence is one independent human plus a separate four-model panel, not multi-human IAA. Independent v3 data writing, three-human annotation, and hidden model runs remain unexecuted.

## Deliverables

- Public repository package: `final_release/repository/`
- Validity audit and run artifacts: `final_release/results/`
- Anonymous 16-page diagnostic paper: `final_release/paper/`
- Tagged 42-page thesis review PDF, editable DOCX, Persian companion material, and 60 defense Q&As: `final_release/thesis/`
- English and Persian defense decks: `final_release/presentation/`
- Cambridge application drafts: `final_release/phd_application/`
- Remaining actions and validation evidence: `final_release/reports/`

## Publication boundary

Historical run status does not override later validity evidence. Current MGP-6 v2 policy, ablation, and mapped-adapter values may appear only as explicitly labelled diagnostics led by the shortcut audit. LongMemEval values remain diagnostic, incomplete, invalid, failure-replay-only, or externally pending. The public package omits external data, run logs, model answers/judgments, private application files, raw independent-human labels pending written consent, and per-item model-annotation rationales.
