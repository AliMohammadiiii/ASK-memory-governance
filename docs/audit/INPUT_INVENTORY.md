# Input inventory

Audit date: 2026-07-13. This inventory records the materials supplied for the final-release audit without copying private workstation paths into public artifacts. The external:// prefix is a logical pointer, not a network URL.

## Supplied materials

| Input | Public-safe pointer | Type | Size / extent | SHA-256 | Audit role |
|---|---|---|---:|---|---|
| LongMemEval replay and top-up family | external://Master/ask_controller/runs/lme_m last version/ | directory | 508 files; 2,410,997,121 logical bytes | tree: 6e10915aefb613305af70e7fda83764fde03e7bc0c892de9556476fae09b3d4d | Primary evidence for the v8 failure replay, incomplete top-ups, and adjudicated construction |
| LongMemEval v7 five-system run | external://Master/ask_controller/runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v7/ | directory | 1,144 files; 2,307,852,573 logical bytes | tree: 9023a31b72a20d140f768d8cae3ecd3df14d1d337a296227c3cb2befcb5c7666 | Primary evidence for contaminated v7 controller and baseline diagnostics |
| MGP-6 annotation package | external://Downloads/MGP6_annotation_complete_package.zip | ZIP | 63,883 bytes | 97f4f1b2a2dfa719eea1b9c92cf4466bd53b3b269ec6b91480b42b200dbd508d | Annotation-source package; raw independent-human labels require separate redistribution consent |
| Andreas Vlachos research report | external://Downloads/andreas_vlachos_research_report_en.md | Markdown | 103,612 bytes | 06033bd8e098142c747b73d28ea393f2fde465dd6fef1370ed08289281624e09 | Literature and prospective-supervisor background input |
| Cambridge proposal with audits | external://Downloads/Ali_Mohammadi_Cambridge_PhD_Proposal_and_Audits.docx | Word document | 60,587 bytes | fae4c120203a4cf81ec193cb4a74569e9eb0d0b20a811e027b59a86d9342ff5c | Proposal and application-audit source |
| Cambridge proposal | external://Downloads/Ali_Mohammadi_Cambridge_PhD_Proposal.docx | Word document | 47,192 bytes | 8b815bd2af564fd5764316a95deeb4fa5a93a48f9f48a551ed2662df6ab43532 | Proposal source |
| Curriculum vitae | external://Downloads/Ali_Mohammadi_CV (1).docx | Word document | 13,481 bytes | 1ed670e21682afcae2436ea6f74e28206f4d0f0bab98ddd67481d6e5c30646e5 | CV source |
| MGP-6 / LongMemEval narrative report | external://Master/MGP6_LongMemEval_Final_Report_EN.md | Markdown | 33,279 bytes | ef34f04651fc34a1b66d35b92f132e67904949647a911f782ac4397de0dc9eaa | Secondary narrative source; never authoritative over raw evidence or the results ledger |
| Master completion brief | external://CodexAttachment/9b4fa9b1-693e-4daa-859c-45afba45e08c/pasted-text.txt | text | 36,238 bytes | b49a400a740f28de664a99623a8068ad87e34611647c7abc10c43491386863f2 | Scope, acceptance criteria, and requested deliverables |

Directory extents and tree digests were measured from the supplied working directories. The tree method hashes, for every regular file sorted by relative POSIX path, the path, NUL, byte size, NUL, file SHA-256, and newline; the resulting stream is then SHA-256 hashed. Individual evidence paths are classified in RUN_CLASSIFICATION.csv and ARTIFACT_TRUTH_TABLE.csv. The ControllerRun archive below is an associated cold archive, not asserted to be byte-identical to either live directory.

## Immutable archives discovered during reconstruction

| Archive | Bytes | SHA-256 | Disposition |
|---|---:|---|---|
| ControllerRun.zip | 179,738,189 | 618a1c5159a28bd4df2d4ee0660d095758fb268f57cc9f7c58f11e3608c0fbd0 | Private evidence archive; do not publish without a separate privacy and license scan |
| ASKCodes.zip | 809,821 | a076ecb68e99070a09a4bc2e6dcbd4c1a787402a3833a88cd473ac01ae00da01 | Authoritative implementation source archive |
| baselineScore.zip | 300,191,890 | 7930d21603a64f41c73d13fcd9ae8673bbe76dd2528d0a49704d83e347760748 | Historical baseline outputs; selectively release only classified aggregate evidence |
| docs.zip | 18,268,132 | f54a9eecdf7db2725383e26b7dd256b43de3fc31fec5592a8b5a568317ba4a2e | Historical documentation archive |
| mgp6_v2_COMPLETE_2026-07-11.zip | 1,309,244 | 76594b2895e619e240072f5a6bff42580fd27ba0d518c74e14190575f1e739ec | MGP-6 source snapshot; public contents remain subject to LICENSE-DATA.md |

The machine-readable archive manifest is artifacts/manifests/source_archives.json.

## Dataset identity

| Dataset artifact | Rows | Bytes | SHA-256 | Redistribution |
|---|---:|---:|---|---|
| benchmarks/mgp6/data/mgp6_v2.jsonl | 180 | 381,119 | 870705e71170026fc2e75dcc5b275f9a99ca3cc5501f054c2ac0d1a013b4a583 | Author-created dataset; governed by LICENSE-DATA.md |
| external://Master/ask_controller/data/slices/longmemeval_m_full.jsonl | 500 | 2,638,798,639 | 89a0745fba506c37407da74f004515ba8a337a2aadc9ba9ba543030483223942 | External data; not redistributed |
| external://Master/ask_controller/runs/lme_m_openrouter_qwen_gemma_minilm_strat30_seed0_v7/range_0_179.jsonl | 180 | 950,452,379 | f10b4fb4173d3e2d9310d90c2b6bf8f5e7b147cea1d04affa9037b1b9fe6787d | Deterministic seed-0, 30-per-competency slice; not redistributed |

The 180-item slice contains 180 unique records and exactly matches deterministic seed-0 selection of 30 items from each of six competencies.

## Secret handling

An OpenRouter credential was supplied for external execution. It is intentionally absent from this inventory, was not written to repository files, and must not be copied into manifests, logs, prompts, or release packages. The credential returned HTTP 403 before inference and should not be reused. Only the non-secret outcome is recorded: the frozen final-1.1 run remains externally_pending.

## Evidence gaps

- The two live run directories are now bound by content-tree digests in artifacts/manifests/source_archives.json. Preserve the directories read-only and recompute the same method before accepting any relocated copy.
- Written redistribution consent for the independent annotator's raw per-item labels was not supplied. The two raw CSVs are still present in the tracked candidate set, despite the intended public policy. The public release must remove them, retain only non-identifying aggregates and source hashes, and avoid exposing them through Git history unless consent is recorded.
- LongMemEval redistribution rights were not established. The public repository must retain hashes, IDs, and preparation instructions, not the source JSONL.
- The narrative report and office documents are secondary authoring inputs; their claims require verification against artifacts/results_ledger.json and RUN_CLASSIFICATION.csv.
- Historical runs do not consistently carry a single manifest containing embedding model, prompt/config hashes, seed, and code revision. Those fields must remain explicitly unavailable rather than being inferred from filenames. The pending final-1.1 protocol closes this gap through artifacts/manifests/freeze_hashes.json and its homogeneity verifier.
