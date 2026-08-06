# License decision matrix

Status: `BLOCKED_HUMAN_LEGAL_DECISION`

| Material | Proposed public treatment | Current basis | Decision |
|---|---|---|---|
| ASK source code | Include under MIT | Root `LICENSE` | documented |
| Project documentation | Include under repository MIT notice | Root `LICENSE` | verify scope before release |
| MGP-6 v2 author-created data | Include under CC BY 4.0 | `LICENSE-DATA.md` | documented |
| MGP-6 v4.3 author-created data/labels | Withhold until an explicit grant is recorded | no complete v4.3 grant found | blocked |
| Independent annotator item labels | Exclude | written redistribution consent absent | blocked |
| Aggregate annotation statistics | Include only if non-identifying and reproducible | source hashes retained | human/legal review |
| Model outputs and rationales | Exclude by default | provider/output rights unresolved | blocked |
| LongMemEval data | Exclude; provide upstream acquisition instructions | third-party dataset | blocked for redistribution |
| MGP-Natural v0.1.0 parent archive | Exclude; retain only its pinned hash and aggregate audit | external candidate with Wikipedia-derived excerpts and unresolved release sign-offs | quarantined |
| MGP-Natural derived private packet and reveal map | Exclude | annotation blinding material, source-derived text, and private key material | private |
| MGP-Natural aggregate audit and verification receipts | Include after path and anonymity scans | no dialogue text, labels, source IDs, or private mapping | machine review pending |
| Vendored MGP-Natural v0.2.2 software | Include as a separated Apache-2.0 component with its original notice | supplied software only; upstream license excludes data/content | documented code boundary |
| MGP-Natural v0.2.2 private derived workspace | Exclude; retain only a path-neutral aggregate receipt | contains source-derived text, private mappings, and secrets; original raw-source archives unavailable | quarantined |
| Wikipedia discussion excerpts | Do not redistribute until attribution, revision-specific licensing, modification notice, and privacy review are approved | Wikimedia user contributions require source-aware CC BY-SA compliance | blocked human/legal review |
| Candidate real-chat corpora | Link upstream only; do not ingest or redistribute by default | corpus-specific access, content-rights, consent, and privacy terms | source-specific review |
| External-system outputs | Exclude unless individually cleared | mixed upstream terms | blocked |
| Paper text and figures | Venue license controls submission/publication | TMLR/JMLR requirements differ | author/legal decision |

No row marked “documented” overrides third-party rights or venue terms.
