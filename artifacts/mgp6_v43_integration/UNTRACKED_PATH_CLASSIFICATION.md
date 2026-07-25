# Pre-existing untracked-path classification

No path below was deleted or overwritten. “Track” is a classification for a
future deliberate staging decision, never an instruction to run `git add .`.

| Path | Classification | Decision |
| --- | --- | --- |
| `Ali_Mohammadi_MGP6_v3_3_1_Final.zip` | historical archive to preserve but not modify | Leave untouched and untracked; do not treat it as a v4.3 input. |
| `Ali_Mohammadi_MGP6_v3_3_1_Final/` | historical archive to preserve but not modify | Leave untouched and untracked; it may contain historical source and audit material. |
| `artifacts/analysis/controller_v10_preflight_diagnostic.json` | generated report to track | Preserve for the existing research audit; not changed by this integration. |
| `artifacts/analysis/controller_v9_diagnostic_summary.json` | generated report to track | Preserve for the existing research audit; not changed by this integration. |
| `artifacts/mgp6_v43_integration/` | generated report to track | Required integration evidence; it was reviewed and staged deliberately in the v4.3 integration commit, never via `git add .`. |
| `deliverables/` | historical archive to preserve but not modify | Leave untouched; it contains older v3.3.1 delivery bundles and generated evidence. |
| `releases/MGP6_v3.3.1/` | historical archive to preserve but not modify | Leave untouched; do not revise or repackage it. |
| `releases/MGP6_v4.3.0/` | public release material | New safe release location; it contains only the verified public train/dev and source/builder archives, not the master or private archives. |
| `reports/RESULTS_LME_FINAL.md` | generated report to track | Preserve as a separate LongMemEval report; not edited. |
| `reports/figures/` | generated report to track | Preserve as existing reporting material; not edited. |
| `reports/tables/` | generated report to track | Preserve as existing reporting material; not edited. |

The existing tracked `paper/paper_1/sections/08_downstream_analysis.tex.bak_v11`
is a historical archive to preserve but not modify. Repository validation
allowlists this exact tracked artifact and continues to reject other `.bak`
pollution.
