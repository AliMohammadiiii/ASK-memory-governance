# Independent confirmation protocol

Status: `NOT_EXECUTED`.

Publication gate: `B4_CONFIRMATION = BLOCKED_PENDING_INDEPENDENT_HUMAN_ANNOTATION`.

This directory defines a new, prospective confirmation path. It contains no
independent labels and does not satisfy any publication gate merely by existing.
The packet builder removes all gold/design fields, shuffles records with a
recorded seed, replaces source identifiers with blinded IDs, and emits a
cryptographic commitment. Annotation must be performed by people who did not
author the gold labels or tune the evaluated controller.

Required sequence:

1. Freeze hypotheses, primary metrics, exclusions, model/controller versions,
   sample size, and analysis plan before inspecting confirmation labels.
2. Build and audit the label-free packet with `build_blind_packet.py`.
3. Obtain explicit participation and redistribution consent; do not place
   identities in the repository.
4. Collect at least two independent annotations per item, plus confidence and
   rationale, using `annotation.schema.json`.
5. Adjudicate disagreements without modifying original rows.
6. Reveal the committed mapping only after annotation is frozen.
7. Run the preregistered analysis and emit a signed report under `reports/`.

Do not call model APIs from confirmation tooling. Paid inference requires
separate explicit authorization.
