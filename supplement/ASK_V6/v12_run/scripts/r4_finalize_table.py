#!/usr/bin/env python3
"""R4: final BASELINE_OVERRIDES_TABLE.csv (one row per overridden item) and BASELINE_OVERRIDES_COUNTS.csv (counts per system before/after)."""
import csv, json, hashlib, sys, os
RUN = sys.argv[1]
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
rows = list(csv.DictReader(open('BASELINE_OVERRIDES_TABLE.csv')))
orig = {r['location']: r for r in json.load(open('handoff/r4_orig_backups.json'))}
out = []
for r in rows:
    b = r['system']; sd = r['shard_dir']
    top_o = f'{b}/judgments.jsonl.pre_adjudication.orig'; sh_o = f'{sd}/judgments.jsonl.pre_adjudication.orig'
    s_orig = orig[sd]
    out.append(dict(system=b, shard=sd.split('/')[1], item_id=r['item_id'], competency=r['competency'],
        original_verdict='correct' if r['original_verdict_correct'] == 'True' else 'incorrect', overridden_verdict='correct' if r['overridden_verdict_correct'] == 'True' else 'incorrect', direction=r['direction'],
        original_verdict_confirmed_by_orig_backup=True, 
        counts_before_override_system=orig[b]['orig_correct'], counts_after_override_system=orig[b]['current_correct'], counts_before_override_shard=s_orig['orig_correct'], counts_after_override_shard=s_orig['current_correct'],
        override_fields_in_merged_judgments='judge_overridden;judge_original_correct;judge_original_rationale', override_fields_in_shard_judgments=r['override_fields_in_shard_judgments'],
        other_fields_changed_with_override='correct;judge_score;judge_rationale', override_fields_in_report_json='no (report.json carries no override marker)', merged_report_reflects='after override', shard_report_reflects='before override (shard report not regenerated)',
        backup_top_level_judgments=top_o, backup_top_level_judgments_sha256=sha(f'{RUN}/{top_o}'), backup_shard_judgments=sh_o, backup_shard_judgments_sha256=sha(f'{RUN}/{sh_o}'),
        original_rationale_len=r['original_rationale_len'], current_rationale_len=r['current_rationale_len'], marked_adjudicated_flag='no ("adjudicated" field absent)',
        executable_script_in_run_dir='none (not in run dir, not in backup repo history, not in public repo)', documented_in_baseline_commit='docs/audit/CONTROLLERRUN_FAILURE_LEDGER.md F10 (v7 tree, "five verdicts overridden", manual, no executable adjudication manifest); reports/ERROR_TAXONOMY.md F10',
        identical_copy_in_providerpool_run=True))
with open('BASELINE_OVERRIDES_TABLE.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
cnt = []
for b in ('b1', 'b2', 'b3', 'b4'):
    o = orig[b]; s = json.load(open('handoff/r4_baseline_summary.json'))[b]
    cnt.append(dict(system=b, n=180, correct_before_override=o['orig_correct'], correct_after_override=o['current_correct'], n_rows_overridden=o['n_rows_changed'], accuracy_before=round(o['orig_correct'] / 180, 4), accuracy_after=round(o['current_correct'] / 180, 4),
        report_json_overall_accuracy_x180=round(s['report_overall_accuracy'] * 180, 3), backup_report_x180=o['report_orig_acc_x_n'], judgments_sha256_current=o['judgments_current_sha256'], judgments_sha256_orig_backup=o['judgments_orig_sha256']))
with open('BASELINE_OVERRIDES_COUNTS.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(cnt[0].keys())); w.writeheader(); w.writerows(cnt)
print(len(out), 'override rows;', len(cnt), 'system rows')
