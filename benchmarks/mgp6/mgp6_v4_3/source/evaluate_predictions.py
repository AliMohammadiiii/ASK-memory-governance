#!/usr/bin/env python3
from __future__ import annotations
import collections, json, random, statistics, sys
from pathlib import Path

LABELS = ["KEEP", "SUPERSEDE", "ABSTAIN"]

def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]

def score(y, p):
    cm = {a:{b:0 for b in LABELS} for a in LABELS}
    for a,b in zip(y,p): cm[a][b]+=1
    per={}
    for c in LABELS:
        tp=cm[c][c]; fp=sum(cm[a][c] for a in LABELS if a!=c); fn=sum(cm[c][b] for b in LABELS if b!=c)
        precision=tp/(tp+fp) if tp+fp else 0.0; recall=tp/(tp+fn) if tp+fn else 0.0
        f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
        per[c]={"precision":precision,"recall":recall,"f1":f1,"support":sum(cm[c].values())}
    return {"accuracy":sum(a==b for a,b in zip(y,p))/len(y),"macro_f1":statistics.mean(x["f1"] for x in per.values()),"per_class":per,"confusion_matrix":cm}

def main(gold_path, prediction_path):
    gold=read_jsonl(gold_path); pred=read_jsonl(prediction_path)
    gm={x["public_id"]:x for x in gold}; pm={x["public_id"]:x for x in pred}
    if set(gm)!=set(pm):
        raise SystemExit(json.dumps({"error":"ID coverage mismatch","missing":sorted(set(gm)-set(pm))[:20],"extra":sorted(set(pm)-set(gm))[:20]},indent=2))
    if any(x.get("action") not in LABELS for x in pred): raise SystemExit("Invalid action")
    ids=sorted(gm); result=score([gm[i]["gold_action"] for i in ids],[pm[i]["action"] for i in ids])
    clusters=collections.defaultdict(list)
    for i in ids: clusters[gm[i]["component_id"]].append(i)
    rng=random.Random(4301); acc=[]; mf=[]; keys=sorted(clusters)
    for _ in range(5000):
        sample=[rng.choice(keys) for _ in keys]; chosen=[i for c in sample for i in clusters[c]]
        s=score([gm[i]["gold_action"] for i in chosen],[pm[i]["action"] for i in chosen]); acc.append(s["accuracy"]); mf.append(s["macro_f1"])
    acc.sort(); mf.sort(); result["cluster_bootstrap_95_ci"]={"accuracy":[acc[125],acc[4874]],"macro_f1":[mf[125],mf[4874]],"replicates":5000}
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__":
    if len(sys.argv)!=3: raise SystemExit("Usage: evaluate_predictions.py hidden_gold.jsonl predictions.jsonl")
    main(sys.argv[1],sys.argv[2])
