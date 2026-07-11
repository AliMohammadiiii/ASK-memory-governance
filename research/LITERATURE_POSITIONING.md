# Literature Positioning and Citation Map

## Positioning statement

The project is positioned at the intersection of retrieval-augmented language modeling, long-term memory agents, privacy-aware information lifecycle management, selective prediction, benchmark documentation, and reproducible evaluation. Its distinguishing unit is the **governed memory transition**: a model may propose an action, but policy code authorizes it, a store adapter executes it, a verifier checks it, and an audit event records it.

## Research strands

### Retrieval and memory architecture

Retrieval-augmented generation and large external memories show how models can access information beyond a single prompt [@lewis2020retrieval; @borgeaud2022improving]. Generative-agent and memory-manager systems demonstrate the usefulness of persistent episodic or hierarchical memory [@park2023generative; @packer2023memgpt; @zhong2023memorybank]. The KSA contribution is complementary: it asks whether the retained or retrieved information is authorized and whether mutation semantics are verifiable.

### Long-context limitations

Longer context does not imply uniform use of evidence [@liu2024lost]. This supports evaluating downstream answers separately from the policy and state layers: a correct memory can still be ignored, and an unauthorized memory can still produce a correct answer.

### Selective prediction

Selective classification provides the conceptual basis for abstention, risk–coverage curves, and thresholded automation [@geifman2017selective]. KSA extends the motivation to memory side effects, where the cost of a wrong autonomous action may exceed the cost of clarification.

### Documentation and holistic evaluation

Datasheets, model cards, and holistic evaluation motivate explicit construct, split, subgroup, limitation, and artifact documentation [@gebru2021datasheets; @mitchell2019modelcards; @liang2023holistic]. MGP-6 is therefore accompanied by a data card, annotation ledger, evaluator contract, and status-aware experiment registry.

### Privacy, leakage, and forgetting

Training-data extraction and membership inference illustrate why persistent information can create privacy risks [@carlini2021extracting; @shokri2017membership]. Machine unlearning addresses model-parameter influence, whereas the present controller primarily governs external memory state [@cao2015unlearning]. The thesis explicitly avoids claiming that deleting an external record removes information from model parameters or third-party systems.

### Responsible deployment

Risk taxonomies and governance frameworks emphasize documentation, monitoring, and contextual controls [@bender2021dangers; @weidinger2022taxonomy; @nist2023airmf]. KSA operationalizes a subset of these concerns through least-privilege mutation, target resolution, policy versioning, auditability, and abstention.

## Novelty boundary

The work does not claim to invent retrieval, long-term agent memory, machine unlearning, selective classification, or dataset documentation. Its novelty lies in integrating them around explicit keep/forget/update/ignore/abstain actions, a deterministic authorization boundary, state-transition verification, corrected asymmetric forgetting metrics, and one evidence ledger shared by code, papers, and thesis.
