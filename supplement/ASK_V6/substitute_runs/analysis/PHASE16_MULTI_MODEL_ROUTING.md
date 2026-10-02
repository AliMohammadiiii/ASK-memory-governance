> CORRECTION 2026-10-02 (independent claim check 2, CC2-D-04): all accuracies and contrasts in 16.3 to 16.5 use the stored actions, which were produced by an uncommitted working-tree change to `parse_action_response` in `src/ask/eval/mgp6_v43.py` (strict removal of a JSON Markdown fence; file time 2026-10-02T11:00:26Z; a `.bak_before_json_fence` copy exists). The parser at the baseline commit rejects fenced replies. Under that parser, 49 of 1,440 (Gemini low), 471 of 1,440 (medium) and 212 of 720 (high) replies are invalid; GLM and gpt-oss are unaffected. The Gemini-high cell A value (0.961) and the sign reversal for Gemini high therefore hold under the fence-tolerant rule only (see 16.10). Read findings 4 and 7 of 16.5 with this qualification.

# Phase 16: multi-model routing x prompt decomposition on the public development split (exploratory)

Date: 2026-10-02. Qualifies the Phase 13 conclusion that the prompt, not routing, accounts for most of the development gain: it is reproduced for Gemini 3.8 Flash at low and medium reasoning (one model, two settings) and not for GLM 5.3 Flash, gpt-oss-120b or Gemini 3.8 Flash at high reasoning (fence-tolerant parsing); it is not general.

## 16.1 Question and design
Phase 13 decomposed the development-split contrast of the manuscript (live controller versus zero-shot policy) into two factors on one substitute model. Phase 16 repeats the same four-cell design on four further configurations to test whether the Phase 13 split generalizes. Cells: A = full public payload + one-line prompt; D = router-extracted pair + one-line prompt; E = full payload + live prompt (mismatched diagnostic cell); B = routed pair + live prompt; B_guarded = B after the repository's guard on model ABSTAIN outputs. Views and prompts are the repository builders at the baseline commit (read-only). Public development items only (180); the hidden split was not touched. Runner: `run_dev_routing_check.py`; analysis: `analyze_multi_model.py` -> `multi_model_analysis.json`. Result files store public item ids, cell, repeat, predicted action, prompt SHA-256, usage counters and the first 120 characters of the model output; no benchmark text.

## 16.2 Configurations
| Configuration | Gateway name | Repeats | max new tokens | Seed sent | Window (UTC) |
|---|---|---|---|---|---|
| Gemini 3.8 Flash low | ag/gemini-3.8-flash-low | 2 | 512 | no | 2026-10-01 16:59-17:16 |
| Gemini 3.8 Flash medium | ag/gemini-3.8-flash-medium | 2 | 4096 | yes (4301) | 2026-10-02 11:01-11:44 |
| Gemini 3.8 Flash high | ag/gemini-3.8-flash-high | 1 | 4096 | yes (4301) | 2026-10-02 11:50-12:39 |
| GLM 5.3 Flash | ocg/glm-5.3-flash | 2 | 4096 | no | 2026-10-02 09:58-10:47 |
| gpt-oss-120b medium | ag/gpt-oss-120b-medium | 2 | 4096 | yes (4301) | 2026-10-02 09:37-09:55 |

All: temperature 0, local 9Router gateway. Gemini low, medium and high are three reasoning settings of one model, not three models. The manuscript model (qwen/qwen3.5-9b) was not run (exact reproduction needs paid OpenRouter access; not authorised).

## 16.3 Accuracy (mean over repeats; n = 180)
| Configuration | A payload+one-line | D routed+one-line | E payload+live | B routed+live | B + guard |
|---|---|---|---|---|---|
| Gemini 3.8 Flash low | 0.761 | 0.792 | 0.881 | 0.892 | 0.928 |
| Gemini 3.8 Flash medium | 0.808 | 0.811 | 0.889 | 0.883 | 0.922 |
| Gemini 3.8 Flash high | 0.961 | 0.917 | 0.867 | 0.850 | 0.900 |
| GLM 5.3 Flash | 0.503 | 0.797 | 0.783 | 0.861 | 0.889 |
| gpt-oss-120b medium | 0.339 | 0.658 | 0.575 | 0.742 | 0.767 |

## 16.4 Paired contrasts (difference in accuracy, 95% paired item-level bootstrap, 10,000 resamples, seed 0; component clustering ignored)
| Configuration | prompt given payload (E-A) | prompt given routed (B-D) | routing given one-line (D-A) | routing given live (B-E) | total (B-A) |
|---|---|---|---|---|---|
| Gemini 3.8 Flash low | +0.119 (0.047, 0.192) | +0.100 (0.039, 0.164) | +0.031 (-0.017, 0.081) | +0.011 (-0.031, 0.053) | +0.131 (0.061, 0.200) |
| Gemini 3.8 Flash medium | +0.081 (0.017, 0.144) | +0.072 (0.011, 0.136) | +0.003 (-0.042, 0.047) | -0.006 (-0.042, 0.031) | +0.075 (0.011, 0.142) |
| Gemini 3.8 Flash high | -0.094 (-0.144, -0.044) | -0.067 (-0.128, -0.006) | -0.044 (-0.083, -0.006) | -0.017 (-0.061, 0.022) | -0.111 (-0.167, -0.061) |
| GLM 5.3 Flash | +0.281 (0.211, 0.353) | +0.064 (0.014, 0.117) | +0.294 (0.228, 0.364) | +0.078 (0.028, 0.125) | +0.358 (0.286, 0.431) |
| gpt-oss-120b medium | +0.236 (0.142, 0.331) | +0.083 (0.019, 0.147) | +0.319 (0.253, 0.386) | +0.167 (0.094, 0.236) | +0.403 (0.317, 0.489) |

## 16.5 Findings (observation level; association language only)
1. The split between routing and prompt is not stable across configurations, and the sign of the total change B minus A is not stable (+0.131, +0.075, -0.111, +0.358, +0.403).
2. Gemini low and medium reproduce the Phase 13 pattern (prompt gain 0.07 to 0.12; routing difference -0.01 to +0.03 with intervals including 0).
3. GLM 5.3 Flash and gpt-oss-120b show large routing gains under the one-line prompt (+0.29, +0.32) and smaller gains under the live prompt (+0.08, +0.17); the prompt gain is also smaller on routed evidence than on the full payload. Each factor's gain shrinks when the other is present (sub-additive).
4. Gemini high (one repeat) reverses the ordering: the one-line prompt on the full payload scored 0.961, the highest cell of any configuration; the live prompt is associated with -0.094 and -0.067, routing with -0.044 (interval -0.083 to -0.006) and -0.017 (interval includes 0). Under the live prompt this configuration predicted ABSTAIN for 84 (E) and 81 (B) of 180 items, with 60 gold ABSTAIN items (counts from the run log).
5. Zero-shot floor (cell A) spans 0.339 (gpt-oss-120b; 177 of 180 predicted SUPERSEDE in the first repeat) to 0.961. Statements that a zero-shot or full-context policy is at chance are model-specific.
6. In all five configurations the guard raised the accuracy of cell B (by +0.036, +0.039, +0.050, +0.028 and +0.025 in the order of 16.3); the guard is a repository component and is not part of the routing or prompt factors.
7. Observation without inference, tolerant parsing only: the cell A accuracy of Gemini high (0.961; 0.478 under the baseline parser) equals one of the two development accuracies (0.95 and 0.961) recorded for the post-final successor configuration in the tracked analysis. The two are different models and prompts and were produced under different procedures; no comparison is claimed. The point recorded here is that the development split by itself does not require the structured prompt or the router to reach about 0.96 for a model of this strength, so the hidden accuracy 0.848 of the frozen qwen3.5-9b controller describes that controller and model, not the difficulty of the task for current models. No hidden-split run of any substitute configuration was made or is authorised.

## 16.6 Limitations
- Substitute models, hosted through a gateway with undocumented routing and possible added prefix; returned model revisions unreported; reasoning settings differ; max_tokens differs between Phase 13 (512) and later runs (4096).
- Prompt-token counts in usage are about 2,500 to 3,100 per call for non-reasoning-count settings (the prompts themselves are shorter), which suggests a gateway prefix of about 2,000 tokens (inferred). For Gemini high the gateway's prompt-token field also appears to include reasoning tokens (example call: prompt 4,658, reasoning 2,034, completion 12), so the prefix cannot be attributed exactly.
- Item-level bootstrap ignores the clustering of the 180 items into 20 components of 9 items; intervals are likely too narrow.
- Development is the tuning split of the live prompt; cells E and B are optimistic. Cell E is mismatched by construction.
- Two repeats at temperature 0 give two draws per item; seeds were sent only where the provider accepted them and determinism was not tested.
- Gemini high has one repeat.

## 16.7 Runs not used
| Candidate | Outcome | Reason |
|---|---|---|
| ocg/qwen3.5-plus | 2 smoke rows only | reported unavailable in the owner's terminal (error body not stored) |
| ocg/deepseek-v4.1-flash | 8 rows | on three items reasoning consumed all 1,024 and then all 4,096 allowed tokens with no answer; one further item was answered at 1,024 tokens (claim check 2) |
| ocg/kimi-k2.5 | not run | unavailable |
| ocg/mimo-v2.6-flash | not run | 33.8 s for a one-line ping |
| ag/gemini-3.8-flash-high | included after completion | was still running at first analysis (471 to 535 rows), completed with 720 rows (one repeat) |
Gemini low (Phase 13) was run first and its accuracies had been inspected before the later configurations were chosen; those were chosen by availability through single-request pings. No completed run was dropped.

## 16.8 Effect on manuscript claims
- Replaces the Phase 13 statement that the prompt accounts for most of the gain (CS-22 text updated; the manuscript states model dependence including sign).
- The development contrast (live 0.844 versus 0.339) remains confounded (CS-11) and is not attributed to ASK components.
- Reversible: yes (exploratory; additional runs could change the description).

## 16.9 Provenance and hygiene
Output directories are listed in the README_RUN.md of this folder. The gateway key was supplied as an environment variable and is not stored in any file here; logs pasted into the chat contained the key and it should be rotated by the owner.

## 16.10 Parser sensitivity (added after claim check 2)
Script: `strict_parser_sensitivity.py` (imports the parser from a read-only export of the baseline commit); output: `strict_parser_sensitivity.json`. Rejected replies count as incorrect under the baseline parser. The `raw` field stores the first 120 characters of each reply, enough for these short replies.

| Configuration | rule | A payload+one-line | D routed+one-line | E payload+live | B routed+live | B minus A | rejected replies |
|---|---|---|---|---|---|---|---|
| Gemini 3.8 Flash low | fence-tolerant (primary) | 0.761 | 0.792 | 0.881 | 0.892 | +0.131 | 0 |
| Gemini 3.8 Flash low | baseline-commit parser | 0.714 | 0.772 | 0.856 | 0.883 | +0.169 | 49 of 1440 |
| Gemini 3.8 Flash medium | fence-tolerant (primary) | 0.808 | 0.811 | 0.889 | 0.883 | +0.075 | 0 |
| Gemini 3.8 Flash medium | baseline-commit parser | 0.406 | 0.600 | 0.578 | 0.808 | +0.403 | 471 of 1440 |
| Gemini 3.8 Flash high | fence-tolerant (primary) | 0.961 | 0.917 | 0.867 | 0.850 | -0.111 | 0 |
| Gemini 3.8 Flash high | baseline-commit parser | 0.478 | 0.767 | 0.567 | 0.783 | +0.306 | 212 of 720 |
| GLM 5.3 Flash | fence-tolerant (primary) | 0.503 | 0.797 | 0.783 | 0.861 | +0.358 | 0 |
| GLM 5.3 Flash | baseline-commit parser | 0.503 | 0.797 | 0.783 | 0.861 | +0.358 | 0 of 1440 |
| gpt-oss-120b medium | fence-tolerant (primary) | 0.339 | 0.658 | 0.575 | 0.742 | +0.403 | 0 |
| gpt-oss-120b medium | baseline-commit parser | 0.339 | 0.658 | 0.575 | 0.742 | +0.403 | 0 of 1440 |

Reading: the fence-tolerant rule measures the decision; the baseline rule also penalises formatting. Under the baseline parser B minus A is positive for all five configurations (Gemini high +0.305), so the sign reversal is specific to the tolerant rule. What holds under both rules: the split between routing and prompt differs among configurations; GLM and gpt-oss results do not depend on the rule. What does not hold under both rules: the statement that the one-line prompt on the full payload reaches about 0.96 for Gemini high. The paper reports both rules (Appendix F) and uses the tolerant rule as primary with this disclosure.

## 16.11 P17 addendum: cluster-aware intervals and parser provenance
Intervals in the paper now come from a component-level bootstrap (20 components of 9 items; 10,000 resamples; numpy default_rng(0); `cluster_analysis.py`, `phase16_cluster_analysis.json`). Item-level intervals reproduce 16.4 and are kept in the JSON. Parser provenance per run: Gemini low used the Phase 13 runner's own first-to-last-brace extraction; GLM 5.3 Flash and gpt-oss-120b ran before the working-copy edit of 2026-10-02 11:00:26 UTC with the unmodified repository parser; Gemini medium and high ran with the modified working copy (patch SHA-256 6d5deda5...). All stored actions equal json-fence-tolerant parsing. Under baseline-strict parsing B minus A is positive for all three Gemini settings (+0.169, +0.403, +0.306). All 14 July manuscript-model development run directories hold 180 replies that parse under the baseline parser with no fenced reply. Gemini high was run once (one repeat).

