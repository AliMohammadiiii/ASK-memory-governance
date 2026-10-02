#!/usr/bin/env python3
"""Post-hoc structural audit of MGP-6 v4.3 construction files (aggregates only).

Purpose
  Checks the documented construction of the benchmark on files the OWNER supplies (the public
  train and development files, or the private hidden inputs). It reads no model output and no
  prediction. It prints and stores only counts, booleans and split-level means. It never prints
  or stores item text, public ids, component ids, or per-item labels.

  The output is a post-hoc structural verification of the data. It must not be used to tune a
  prompt, a model or a controller, and it is not a performance evaluation.

Checks
  Part A (label free; needs only the model-facing record fields)
    per component : exactly nine items; dialogue lengths 9, 11 and 13 present, three items each;
                    exactly six distinct pooled evidence sentences, identical for all nine items;
                    one standing value; one proposed (requested) value; one principal; one slot
    per (component, length) triple : the three indexed pairs are disjoint, each has two
                    sentences, and their union is the six-sentence pool
  Part B (label dependent; runs only if the owner supplies labels)
    per component : three items per action; per triple one item per action
    per split and pooled : mean indexed message position by action, as exact fractions

  Part A never reads a label. Part B reads labels only to count and average; labels are not printed.

Input formats (as written by benchmarks/mgp6/mgp6_v4_3/source/build_mgp6_v43_final.py)
  records   : JSONL with public_id, memory_before{principal,memory_slot,standing_value}, dialogue[{text,...}],
              evaluation_query [, gold_action]   (public train.jsonl, dev.jsonl, private hidden_inputs.jsonl)
  labels    : JSONL with public_id and gold_action (private hidden_gold.jsonl), or --inline-labels
  component map (optional) : JSON {public_id: component_id} (private cluster_map_private.json) or JSONL
              with public_id and component_id. Without it, components are the groups of items that
              share (principal, memory_slot, standing_value).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

SCRIPT_VERSION = "hidden_structure_audit/1.0.0"
ACTIONS = ("KEEP", "SUPERSEDE", "ABSTAIN")
ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6}
ORDINAL_RE = re.compile(r"\b(first|second|third|fourth|fifth|sixth)\b", re.IGNORECASE)
EVIDENCE_RE = re.compile(
    r"(?:The|A) (first|second|third|fourth|fifth|sixth) message says:\s*(.*?)"
    r"(?=(?:\s+(?:The|A) (?:first|second|third|fourth|fifth|sixth) message says:)|$)",
    re.IGNORECASE,
)
INDEX_CUES = ("index", "indexed under", "export links", "index attaches")
REQUESTED_RE = re.compile(r"\brequested value is\s+(.+?)[.?!]?\s*$", re.IGNORECASE)
# Grammar copied from src/ask/eval/mgp6_v43.py (linked_evidence_view, _requested_value) at the baseline commit.


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_jsonl(path: Path):
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def parse_item(row: dict) -> dict:
    """Extract structure from one record; counts failures instead of raising."""
    indexed: set[int] = set()
    snippets: dict[int, str] = {}
    for turn in row["dialogue"]:
        text = turn.get("text") if isinstance(turn, dict) else None
        if not isinstance(text, str):
            continue
        normalized = text.casefold()
        if "message" in normalized and any(cue in normalized for cue in INDEX_CUES):
            indexed.update(ORDINALS[m.casefold()] for m in ORDINAL_RE.findall(normalized))
        for ordinal, snippet in EVIDENCE_RE.findall(text):
            snippets[ORDINALS[ordinal.casefold()]] = " ".join(snippet.split())
    requested = None
    for turn in reversed(row["dialogue"]):
        text = turn.get("text") if isinstance(turn, dict) else None
        if isinstance(text, str):
            m = REQUESTED_RE.search(text)
            if m:
                requested = m.group(1).strip(" .,:;!?\"'")
                break
    mb = row["memory_before"]
    positions = tuple(sorted(indexed))
    numbered_ok = set(snippets) == set(range(1, 7))
    pool = frozenset(snippets.values()) if numbered_ok else None
    pair = None
    if len(positions) == 2 and all(p in snippets for p in positions):
        pair = frozenset(snippets[p] for p in positions)
    return {
        "positions": positions if len(positions) == 2 else None,
        "n_indexed_found": len(positions),
        "numbered_ok": numbered_ok,
        "pool": pool,
        "pair": pair,
        "length": len(row["dialogue"]),
        "standing": str(mb.get("standing_value")),
        "principal": str(mb.get("principal")),
        "slot": str(mb.get("memory_slot")),
        "requested": requested,
    }


def proxy_key(item: dict) -> tuple:
    return (item["principal"], item["slot"], item["standing"])


def load_component_map(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except json.JSONDecodeError:
        pass
    mapping = {}
    for line in text.splitlines():
        if line.strip():
            row = json.loads(line)
            mapping[str(row["public_id"])] = str(row["component_id"])
    return mapping


def tally(counter: dict, name: str, passed: bool):
    entry = counter.setdefault(name, {"pass": 0, "of": 0})
    entry["of"] += 1
    entry["pass"] += int(bool(passed))


def audit(record_files, label_source, labels, component_map, expect_items, expect_components):
    items = {}              # public_id -> parsed item
    split_of = {}
    inline = {}
    parse_failures = Counter()
    n_rows = 0
    split_counts = {}
    for split, rows in record_files:
        split_counts[split] = len(rows)
        for row in rows:
            n_rows += 1
            pid = row["public_id"]
            if pid in items:
                parse_failures["duplicate_public_id"] += 1
                continue
            it = parse_item(row)
            items[pid] = it
            split_of[pid] = split
            if "gold_action" in row:
                inline[pid] = row["gold_action"]
            if it["n_indexed_found"] != 2:
                parse_failures["index_statement_not_two_positions"] += 1
            if not it["numbered_ok"]:
                parse_failures["numbered_snippets_not_exactly_six"] += 1
            if it["requested"] is None:
                parse_failures["requested_value_not_found"] += 1
    if label_source == "inline":
        labels = inline
    # components
    proxy_groups = defaultdict(list)
    for pid, it in items.items():
        proxy_groups[proxy_key(it)].append(pid)
    comp_source = "proxy(principal,memory_slot,standing_value)"
    groups = {("p",) + k: v for k, v in proxy_groups.items()}
    proxy_equals_map = None
    items_missing_from_map = None
    if component_map is not None:
        mapped = defaultdict(list)
        missing = 0
        for pid in items:
            if pid in component_map:
                mapped[component_map[pid]].append(pid)
            else:
                missing += 1
        items_missing_from_map = missing
        groups = {("m", k): v for k, v in mapped.items()}
        comp_source = "supplied component map"
        proxy_sets = {frozenset(v) for v in proxy_groups.values()}
        map_sets = {frozenset(v) for v in mapped.values()}
        proxy_equals_map = missing == 0 and proxy_sets == map_sets

    a: dict = {}
    b: dict = {}
    triples_total = 0
    mean_pos = {s: {act: [0, 0] for act in ACTIONS} for s in list(split_counts) + ["pooled"]}
    comp_equal_mean = {"equal": 0, "of": 0}
    labels_complete = labels is not None and all(pid in labels for pid in items)
    label_values_valid = labels_complete and all(labels[pid] in ACTIONS for pid in items)
    cut_across_splits = 0
    for gid, pids in groups.items():
        its = [items[p] for p in pids]
        tally(a, "component_has_nine_items", len(pids) == 9)
        lengths = Counter(i["length"] for i in its)
        tally(a, "component_lengths_9_11_13_present", set(lengths) == {9, 11, 13})
        tally(a, "component_three_items_per_length", dict(lengths) == {9: 3, 11: 3, 13: 3})
        pools = [i["pool"] for i in its]
        pool_ok = all(p is not None for p in pools) and len(set(pools)) == 1 and len(pools[0]) == 6
        tally(a, "component_one_pool_of_six_distinct_sentences_across_all_items", pool_ok)
        tally(a, "component_one_standing_value", len({i["standing"] for i in its}) == 1)
        tally(a, "component_one_proposed_value", len({i["requested"] for i in its}) == 1 and its[0]["requested"] is not None)
        tally(a, "component_one_principal_and_one_slot", len({i["principal"] for i in its}) == 1 and len({i["slot"] for i in its}) == 1)
        if len({split_of[p] for p in pids}) > 1:
            cut_across_splits += 1
        by_length = defaultdict(list)
        for pid in pids:
            by_length[items[pid]["length"]].append(pid)
        comp_triples_ok = True
        for length in (9, 11, 13):
            triple = by_length.get(length, [])
            triples_total += 1
            parsed = [items[p] for p in triple]
            ok_size = len(parsed) == 3
            tri_pool_ok = ok_size and all(i["pool"] is not None for i in parsed) and len({i["pool"] for i in parsed}) == 1 and len(parsed[0]["pool"]) == 6
            tally(a, "triple_three_items", ok_size)
            tally(a, "triple_pool_of_six_identical_for_the_three_items", tri_pool_ok)
            partition_ok = False
            if tri_pool_ok and all(i["pair"] is not None and len(i["pair"]) == 2 for i in parsed):
                pairs = [i["pair"] for i in parsed]
                disjoint = sum(len(p) for p in pairs) == len(frozenset().union(*pairs))
                partition_ok = disjoint and frozenset().union(*pairs) == parsed[0]["pool"]
            tally(a, "triple_indexed_pairs_partition_the_pool", partition_ok)
            comp_triples_ok &= partition_ok
        tally(a, "component_all_three_triples_partition_the_pool", comp_triples_ok)
        if label_source != "none":
            labs = [labels.get(p) for p in pids] if labels is not None else []
            have = labels_complete and label_values_valid
            if have:
                tally(b, "component_three_items_per_action", all(Counter(labs)[act] == 3 for act in ACTIONS) and len(labs) == 9)
                ok_tri = True
                for length in (9, 11, 13):
                    tl = [labels[p] for p in by_length.get(length, [])]
                    ok_tri &= sorted(tl) == sorted(ACTIONS)
                tally(b, "component_one_item_per_action_in_each_length", ok_tri)
                per_act = {act: [] for act in ACTIONS}
                for pid in pids:
                    it = items[pid]
                    if it["positions"] is None:
                        continue
                    for pos in it["positions"]:
                        per_act[labels[pid]].append(pos)
                        mean_pos[split_of[pid]][labels[pid]][0] += pos
                        mean_pos[split_of[pid]][labels[pid]][1] += 1
                        mean_pos["pooled"][labels[pid]][0] += pos
                        mean_pos["pooled"][labels[pid]][1] += 1
                if all(per_act[act] for act in ACTIONS):
                    fr = {act: Fraction(sum(per_act[act]), len(per_act[act])) for act in ACTIONS}
                    comp_equal_mean["of"] += 1
                    comp_equal_mean["equal"] += int(len(set(fr.values())) == 1)
    parse_block = {
        "items_read": n_rows,
        "items_distinct_ids": len(items),
        "failures": dict(parse_failures),
        "items_per_file": split_counts,
    }
    comp_block = {
        "n_components": len(groups),
        "definition": comp_source,
        "components_with_items_in_more_than_one_file": cut_across_splits,
        "proxy_partition_equals_supplied_map": proxy_equals_map,
        "items_missing_from_supplied_map": items_missing_from_map,
        "n_proxy_groups": len(proxy_groups),
        "triples_total": triples_total,
    }
    part_a = {k: {"pass": v["pass"], "of": v["of"], "all_pass": v["pass"] == v["of"]} for k, v in sorted(a.items())}
    result = {"parse": parse_block, "components": comp_block, "part_a_label_free": part_a}
    if label_source == "none":
        result["part_b_label_dependent"] = {"run": False, "reason": "no labels supplied"}
    elif not (labels_complete and label_values_valid):
        result["part_b_label_dependent"] = {"run": False, "reason": "labels missing for some items or values outside the three actions"}
    else:
        part_b = {k: {"pass": v["pass"], "of": v["of"], "all_pass": v["pass"] == v["of"]} for k, v in sorted(b.items())}
        means = {}
        for split, per in mean_pos.items():
            means[split] = {}
            for act, (s, n) in per.items():
                if n:
                    fr = Fraction(s, n)
                    means[split][act] = {"exact": f"{fr.numerator}/{fr.denominator}", "value": round(float(fr), 6), "n_positions": n}
            vals = {means[split][act]["exact"] for act in means[split]}
            means[split]["identical_across_actions"] = len(vals) == 1 and len(means[split]) == 3
        part_b_all = all(v["all_pass"] for v in part_b.values()) and all(m["identical_across_actions"] for m in means.values())
        result["part_b_label_dependent"] = {
            "run": True, "label_source": label_source, "checks": part_b,
            "mean_indexed_position_by_action": means,
            "components_with_equal_mean_position_across_actions_informational": comp_equal_mean,
            "all_pass_including_position_means_identical_across_actions": part_b_all,
        }
    result["all_part_a_checks_pass"] = (
        all(v["all_pass"] for v in part_a.values()) and not parse_failures and cut_across_splits == 0
    )
    expected = {}
    if expect_items is not None:
        expected["items_equal_expected"] = len(items) == expect_items
    if expect_components is not None:
        expected["components_equal_expected"] = len(groups) == expect_components
    result["expected_counts_checked"] = expected
    return result


def render(result: dict) -> str:
    lines = [f"{SCRIPT_VERSION}: post-hoc structural verification (aggregates only)"]
    p = result["parse"]
    lines.append(f"items read {p['items_read']}, distinct ids {p['items_distinct_ids']}, parse failures {p['failures'] or 'none'}")
    c = result["components"]
    lines.append(f"components {c['n_components']} ({c['definition']}); triples {c['triples_total']}; proxy equals supplied map: {c['proxy_partition_equals_supplied_map']}")
    lines.append("Part A (label free):")
    for k, v in result["part_a_label_free"].items():
        lines.append(f"  {k}: {v['pass']}/{v['of']}")
    pb = result["part_b_label_dependent"]
    if pb["run"]:
        lines.append("Part B (labels read for counting only):")
        for k, v in pb["checks"].items():
            lines.append(f"  {k}: {v['pass']}/{v['of']}")
        for split, m in pb["mean_indexed_position_by_action"].items():
            vals = ", ".join(f"{act}={m[act]['value']:.4f}" for act in ACTIONS if act in m)
            lines.append(f"  mean indexed position [{split}]: {vals}; identical across actions: {m['identical_across_actions']}")
    else:
        lines.append(f"Part B not run: {pb['reason']}")
    lines.append(f"all Part A checks pass: {result['all_part_a_checks_pass']}")
    return "\n".join(lines)


def verify_output(path: Path) -> int:
    """Recompute content_sha256 and the sidecar hash of a result file written by this script."""
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    claimed = data.pop("content_sha256", None)
    recomputed = sha256_bytes(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    sidecar = path.with_name(path.name + ".sha256")
    sidecar_ok = None
    if sidecar.exists():
        sidecar_ok = sidecar.read_text(encoding="utf-8").split()[0] == sha256_bytes(text.encode("utf-8"))
    print(f"content_sha256 matches: {claimed == recomputed}; sidecar matches file: {sidecar_ok}")
    return 0 if claimed == recomputed and sidecar_ok in (True, None) else 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--verify" in argv:
        return verify_output(Path(argv[argv.index("--verify") + 1]))
    ap = argparse.ArgumentParser(description=__doc__ + "\n  --verify FILE   recompute the hashes of a result file written by this script",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", action="append", required=True, type=Path, help="JSONL file (repeatable)")
    ap.add_argument("--split-names", help="comma-separated names for the record files (default: file stems)")
    ap.add_argument("--component-map", type=Path)
    ap.add_argument("--labels", type=Path, help="JSONL with public_id and gold_action")
    ap.add_argument("--inline-labels", action="store_true", help="use gold_action fields inside the record files")
    ap.add_argument("--expect-items", type=int)
    ap.add_argument("--expect-components", type=int)
    ap.add_argument("--out", type=Path, default=Path("hidden_structure_audit_result.json"))
    ap.add_argument("--debug", action="store_true", help="show full tracebacks (may contain data)")
    args = ap.parse_args(argv)
    try:
        if args.labels and args.inline_labels:
            raise SystemExit("choose --labels or --inline-labels, not both")
        names = args.split_names.split(",") if args.split_names else [p.stem for p in args.records]
        if len(names) != len(args.records) or len(set(names)) != len(names):
            raise SystemExit("--split-names must give one distinct name per record file")
        files, input_hashes = [], []
        for name, path in zip(names, args.records):
            raw = path.read_bytes()
            input_hashes.append({"split": name, "sha256": sha256_bytes(raw)})
            files.append((name, read_jsonl(path)))
        cmap = load_component_map(args.component_map) if args.component_map else None
        labels, label_source = None, "none"
        label_hash = None
        if args.labels:
            raw = args.labels.read_bytes()
            label_hash = sha256_bytes(raw)
            labels = {}
            for row in read_jsonl(args.labels):
                labels[str(row["public_id"])] = row["gold_action"]
            label_source = "file"
        elif args.inline_labels:
            label_source = "inline"
        result = audit(files, label_source, labels, cmap, args.expect_items, args.expect_components)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - never echo data
        if args.debug:
            raise
        sys.stderr.write(f"audit failed with {type(exc).__name__}; rerun with --debug on your own machine to see the traceback\n")
        return 2
    result["schema"] = "ask-hidden-structure-audit/1"
    result["script"] = {"version": SCRIPT_VERSION, "sha256": sha256_bytes(Path(__file__).read_bytes())}
    result["inputs"] = {
        "record_files": input_hashes,
        "component_map_sha256": sha256_bytes(args.component_map.read_bytes()) if args.component_map else None,
        "labels_source": label_source,
        "labels_file_sha256": label_hash,
    }
    result["statement"] = (
        "Post-hoc structural verification of construction files. Aggregates only. "
        "Not a performance evaluation and not to be used for any tuning."
    )
    body = json.dumps(result, sort_keys=True, separators=(",", ":"))
    result["content_sha256"] = sha256_bytes(body.encode("utf-8"))
    text = json.dumps(result, indent=1, sort_keys=True) + "\n"
    args.out.write_text(text, encoding="utf-8")
    file_hash = sha256_bytes(text.encode("utf-8"))
    args.out.with_name(args.out.name + ".sha256").write_text(f"{file_hash}  {args.out.name}\n", encoding="utf-8")
    print(render(result))
    print(f"content_sha256 (JSON without this field): {result['content_sha256']}")
    print(f"sha256 of {args.out.name}: {file_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
