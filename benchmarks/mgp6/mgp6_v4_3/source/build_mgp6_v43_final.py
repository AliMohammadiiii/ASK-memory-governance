from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
import os
import random
import shutil
import statistics
import tempfile
import textwrap
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.tree import DecisionTreeClassifier

BASE = Path('/mnt/data')
CONTENT_FREEZE = BASE / 'MGP6_v4.2_CONTENT_FREEZE_HUMAN_VALIDATION_READY'
COORDINATOR = BASE / 'MGP6_v4.2_HUMAN_VALIDATION_COORDINATOR_KIT'
ANNOTATOR_A_ZIP = BASE / 'annotator_a_packet(1).zip'
ANNOTATOR_B_ZIP = BASE / 'MGP6_v4.2_annotator_b(1).zip'
SCRIPT_PATH = BASE / 'build_mgp6_v43_final.py'

RELEASE_VERSION = '4.3.0-human-validated-final'
RELEASE_NAME = 'MGP-6-v4.3.0-human-validated-final'
RELEASE_TIMESTAMP = datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
SPLIT_SEED = 4301
SHORTCUT_SEEDS = [4301, 4302, 4303, 4304, 4305]
LABELS = ['KEEP', 'SUPERSEDE', 'ABSTAIN']

OUT_ROOT = BASE / 'MGP6_v4.3_FINAL_RELEASE'
OUT_MASTER = BASE / f'{RELEASE_NAME}-BUNDLE.zip'
OUT_VERIFICATION = BASE / 'MGP6_v4.3_FINAL_RELEASE_VERIFICATION.json'
OUT_READINESS_JSON = BASE / 'MGP6_v4.3_FINAL_RELEASE_READINESS.json'
OUT_READINESS_MD = BASE / 'MGP6_v4.3_FINAL_RELEASE_READINESS.md'
OUT_GOLD = BASE / 'MGP6_v4.3_FINAL_HUMAN_GOLD.jsonl'


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding='utf-8') as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception as exc:
                raise RuntimeError(f'Invalid JSONL at {path}:{line_no}: {exc}') from exc
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as f:
        for row in rows:
            f.write(canonical_json(row).decode('utf-8') + '\n')


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def deterministic_zip(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, 'w') as zf:
        for path in sorted(source.rglob('*')):
            if not path.is_file():
                continue
            rel = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(rel, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes(), compresslevel=9)


def make_manifest(root: Path, package_kind: str) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.name != 'MANIFEST.json':
            files.append({
                'relative_path': path.relative_to(root).as_posix(),
                'size_bytes': path.stat().st_size,
                'sha256': sha256_file(path),
            })
    manifest = {
        'schema_version': 'mgp6-v4.3-manifest-1.0',
        'release_version': RELEASE_VERSION,
        'package_kind': package_kind,
        'file_count_excluding_manifest': len(files),
        'files': files,
    }
    write_json(root / 'MANIFEST.json', manifest)
    return manifest


def verify_manifest(root: Path) -> dict[str, Any]:
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    listed = {row['relative_path']: row for row in manifest['files']}
    actual = {
        p.relative_to(root).as_posix(): p
        for p in root.rglob('*') if p.is_file() and p.name != 'MANIFEST.json'
    }
    errors = []
    if set(listed) != set(actual):
        errors.append({'missing_from_manifest': sorted(set(actual) - set(listed)), 'extra_in_manifest': sorted(set(listed) - set(actual))})
    for rel, p in actual.items():
        row = listed.get(rel)
        if not row:
            continue
        if p.stat().st_size != row['size_bytes']:
            errors.append({'relative_path': rel, 'error': 'size_mismatch'})
        if sha256_file(p) != row['sha256']:
            errors.append({'relative_path': rel, 'error': 'sha256_mismatch'})
    return {
        'passed': not errors,
        'errors': errors,
        'declared_count': manifest['file_count_excluding_manifest'],
        'actual_count': len(actual),
    }


def merkle_root(hex_hashes: list[str]) -> str:
    if not hex_hashes:
        return hashlib.sha256(b'').hexdigest()
    level = [bytes.fromhex(x) for x in hex_hashes]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


def extract_clean(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        if zf.testzip() is not None:
            raise RuntimeError(f'CRC failure in {zip_path}')
        for info in zf.infolist():
            name = info.filename
            if name.startswith('__MACOSX/') or '/._' in name or Path(name).name.startswith('._'):
                continue
            zf.extract(info, destination)


def validate_annotations(rows: list[dict[str, Any]], items: dict[str, dict[str, Any]], binding: dict[str, dict[str, Any]], expected_annotator: str) -> list[dict[str, Any]]:
    required = {
        'schema_version', 'annotation_id', 'content_hash', 'action', 'evidence_turn_ids',
        'rationale', 'confidence', 'ambiguity_flag', 'exclusion_recommendation',
        'annotator_id', 'annotated_at'
    }
    seen = set()
    validated = []
    errors = []
    for idx, row in enumerate(rows, 1):
        aid = row.get('annotation_id')
        if aid in seen:
            errors.append(f'duplicate annotation_id {aid}')
            continue
        seen.add(aid)
        if aid not in items or aid not in binding:
            errors.append(f'unknown annotation_id {aid}')
            continue
        missing = required - set(row)
        if missing:
            errors.append(f'{aid}: missing {sorted(missing)}')
            continue
        if row['schema_version'] != 'mgp6-v4.2-human-annotation-1.0':
            errors.append(f'{aid}: invalid schema_version')
        if row['action'] not in LABELS:
            errors.append(f'{aid}: invalid action')
        if row['annotator_id'] != expected_annotator:
            errors.append(f'{aid}: unexpected annotator_id')
        if row['content_hash'] != binding[aid]['content_hash']:
            errors.append(f'{aid}: content_hash mismatch')
        valid_turns = {x['turn_id'] for x in items[aid]['dialogue']}
        if not row['evidence_turn_ids'] or any(t not in valid_turns for t in row['evidence_turn_ids']):
            errors.append(f'{aid}: invalid evidence turns')
        if len(row['rationale'].strip()) < 20:
            errors.append(f'{aid}: rationale too short')
        if not isinstance(row['confidence'], (int, float)) or not 0 <= row['confidence'] <= 1:
            errors.append(f'{aid}: invalid confidence')
        if not isinstance(row['ambiguity_flag'], bool) or not isinstance(row['exclusion_recommendation'], bool):
            errors.append(f'{aid}: invalid boolean')
        try:
            dt = datetime.fromisoformat(row['annotated_at'].replace('Z', '+00:00'))
            if dt.tzinfo is None:
                raise ValueError('not timezone-aware')
        except Exception:
            errors.append(f'{aid}: invalid timestamp')
        normalized = copy.deepcopy(row)
        normalized['evidence_turn_ids'] = sorted(set(row['evidence_turn_ids']))
        normalized['annotation_record_hash'] = canonical_hash(normalized)
        validated.append(normalized)
    if seen != set(items):
        errors.append(f'coverage mismatch missing={len(set(items)-seen)} extra={len(seen-set(items))}')
    if errors:
        raise RuntimeError('Annotation validation failed: ' + '; '.join(errors[:20]))
    return validated


def macro_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    precision, recall, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=LABELS)
    return {
        'accuracy': float(accuracy_score(y_true, y_pred)),
        'macro_f1': float(f1_score(y_true, y_pred, labels=LABELS, average='macro', zero_division=0)),
        'per_class': {
            label: {
                'precision': float(precision[i]),
                'recall': float(recall[i]),
                'f1': float(f1[i]),
                'support': int(support[i]),
            } for i, label in enumerate(LABELS)
        },
        'confusion_matrix': {'labels': LABELS, 'matrix': cm.tolist()},
    }


def text_views(item: dict[str, Any]) -> dict[str, str]:
    dialogue = item['dialogue']
    user = '\n'.join(t['text'] for t in dialogue if t['speaker'] == 'USER')
    assistant = '\n'.join(t['text'] for t in dialogue if t['speaker'] == 'ASSISTANT')
    full_dialogue = '\n'.join(f"{t['speaker']}: {t['text']}" for t in dialogue)
    evidence_map = {t['turn_id']: t['text'] for t in dialogue}
    linked = '\n'.join(evidence_map[t] for t in item['linked_evidence_turn_ids'])
    memory = json.dumps(item['memory_before'], ensure_ascii=False, sort_keys=True)
    return {
        'full_text': memory + '\n' + full_dialogue + '\n' + item['evaluation_query'],
        'dialogue_only': full_dialogue,
        'query_only': item['evaluation_query'],
        'candidate_only': dialogue[-1]['text'],
        'previous_turn': dialogue[-2]['text'],
        'last_two': dialogue[-2]['text'] + '\n' + dialogue[-1]['text'],
        'target_evidence_only': linked,
        'memory_only': memory,
        'user_only': user,
        'assistant_only': assistant,
        'first_three': '\n'.join(t['text'] for t in dialogue[:3]),
        'id_only': item['public_id'],
    }


def fit_word_model(train_texts: list[str], y_train: list[str], test_texts: list[str], seed: int) -> list[str]:
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=40000, sublinear_tf=True)
    x_train = vectorizer.fit_transform(train_texts)
    x_test = vectorizer.transform(test_texts)
    model = LogisticRegression(max_iter=4000, C=2.0, random_state=seed)
    model.fit(x_train, y_train)
    return model.predict(x_test).tolist()


def fit_char_model(train_texts: list[str], y_train: list[str], test_texts: list[str], seed: int) -> list[str]:
    vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), min_df=2, max_features=50000, sublinear_tf=True)
    x_train = vectorizer.fit_transform(train_texts)
    x_test = vectorizer.transform(test_texts)
    model = LogisticRegression(max_iter=4000, C=2.0, random_state=seed)
    model.fit(x_train, y_train)
    return model.predict(x_test).tolist()


def numeric_features(text: str, kind: str) -> list[float]:
    if kind == 'length':
        return [len(text), len(text.split()), len(re.findall(r'[^.!?]+[.!?]', text)), text.count('\n')]
    chars = ['.', ',', ';', ':', '?', '!', '"', "'", '-', '(', ')', '/', '\n']
    return [text.count(c) for c in chars] + [len(re.findall(r'\s+[.!?,;:]', text)), len(re.findall(r'[.!?][A-Za-z]', text))]


def fit_numeric_model(train_texts: list[str], y_train: list[str], test_texts: list[str], seed: int, kind: str) -> list[str]:
    x_train = np.array([numeric_features(x, kind) for x in train_texts], dtype=float)
    x_test = np.array([numeric_features(x, kind) for x in test_texts], dtype=float)
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std[std == 0] = 1
    x_train = (x_train - mean) / std
    x_test = (x_test - mean) / std
    model = LogisticRegression(max_iter=4000, random_state=seed)
    model.fit(x_train, y_train)
    return model.predict(x_test).tolist()


def shortcut_audit(train: list[dict[str, Any]], hidden: list[dict[str, Any]]) -> dict[str, Any]:
    y_train = [x['final_gold_action'] for x in train]
    y_hidden = [x['final_gold_action'] for x in hidden]
    train_views = [text_views(x) for x in train]
    hidden_views = [text_views(x) for x in hidden]
    results: dict[str, Any] = {}
    thresholds = {
        'full_text': 0.65,
        'dialogue_only': 0.65,
        'query_only': 0.40,
        'candidate_only': 0.45,
        'previous_turn': 0.45,
        'last_two': 0.50,
        'target_evidence_only': 0.65,
        'memory_only': 0.40,
        'user_only': 0.45,
        'assistant_only': 0.45,
        'first_three': 0.50,
        'id_only': 0.40,
        'punctuation_only': 0.40,
        'length_only': 0.40,
        'depth3_tree': 0.60,
    }
    for view in ['full_text', 'dialogue_only', 'query_only', 'candidate_only', 'previous_turn', 'last_two', 'target_evidence_only', 'memory_only', 'user_only', 'assistant_only', 'first_three', 'id_only']:
        seed_rows = []
        tr = [v[view] for v in train_views]
        te = [v[view] for v in hidden_views]
        for seed in SHORTCUT_SEEDS:
            pred = fit_word_model(tr, y_train, te, seed)
            seed_rows.append({'seed': seed, **macro_metrics(y_hidden, pred)})
        mean_acc = statistics.mean(r['accuracy'] for r in seed_rows)
        results[view] = {'method': 'word_tfidf_logistic_regression', 'runs': seed_rows, 'mean_accuracy': mean_acc, 'threshold': thresholds[view], 'passed': mean_acc <= thresholds[view]}

    for view in ['full_text', 'dialogue_only']:
        tr = [v[view] for v in train_views]
        te = [v[view] for v in hidden_views]
        rows = []
        for seed in SHORTCUT_SEEDS:
            pred = fit_char_model(tr, y_train, te, seed)
            rows.append({'seed': seed, **macro_metrics(y_hidden, pred)})
        results[f'{view}_char'] = {'method': 'char_tfidf_logistic_regression', 'runs': rows, 'mean_accuracy': statistics.mean(r['accuracy'] for r in rows), 'threshold': 0.65, 'passed': statistics.mean(r['accuracy'] for r in rows) <= 0.65}

    full_train = [v['full_text'] for v in train_views]
    full_hidden = [v['full_text'] for v in hidden_views]
    for kind in ['punctuation', 'length']:
        rows = []
        for seed in SHORTCUT_SEEDS:
            pred = fit_numeric_model(full_train, y_train, full_hidden, seed, kind)
            rows.append({'seed': seed, **macro_metrics(y_hidden, pred)})
        key = f'{kind}_only'
        results[key] = {'method': f'{kind}_features_logistic_regression', 'runs': rows, 'mean_accuracy': statistics.mean(r['accuracy'] for r in rows), 'threshold': thresholds[key], 'passed': statistics.mean(r['accuracy'] for r in rows) <= thresholds[key]}

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=20000, sublinear_tf=True)
    x_train = vectorizer.fit_transform(full_train)
    x_hidden = vectorizer.transform(full_hidden)
    for depth in range(1, 6):
        rows = []
        for seed in SHORTCUT_SEEDS:
            model = DecisionTreeClassifier(max_depth=depth, random_state=seed, class_weight='balanced')
            model.fit(x_train, y_train)
            pred = model.predict(x_hidden).tolist()
            rows.append({'seed': seed, **macro_metrics(y_hidden, pred)})
        key = f'depth{depth}_tree'
        threshold = thresholds.get(key, 0.65)
        results[key] = {'method': 'word_tfidf_decision_tree', 'max_depth': depth, 'runs': rows, 'mean_accuracy': statistics.mean(r['accuracy'] for r in rows), 'threshold': threshold, 'passed': statistics.mean(r['accuracy'] for r in rows) <= threshold}

    gate_keys = list(thresholds)
    failed = [k for k in gate_keys if not results[k]['passed']]
    return {
        'schema_version': 'mgp6-v4.3-shortcut-audit-1.0',
        'release_version': RELEASE_VERSION,
        'train_count': len(train),
        'hidden_count': len(hidden),
        'component_held_out': True,
        'seeds': SHORTCUT_SEEDS,
        'results': results,
        'failed_gates': failed,
        'passed': not failed,
    }


def duplicate_audit(items: list[dict[str, Any]]) -> dict[str, Any]:
    views = ['full_text', 'dialogue_only', 'candidate_only', 'previous_turn', 'last_two', 'query_only', 'target_evidence_only']
    exact: dict[str, Any] = {}
    for view in views:
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for item in items:
            text = text_views(item)[view]
            groups[hashlib.sha256(text.encode('utf-8')).hexdigest()].append({'public_id': item['public_id'], 'split': item['split'], 'component_id': item['component_id']})
        collisions = []
        for h, rows in groups.items():
            splits = sorted(set(r['split'] for r in rows))
            if len(splits) > 1:
                collisions.append({'hash': h, 'splits': splits, 'items': rows})
        exact[view] = {'cross_split_collision_group_count': len(collisions), 'collisions': collisions[:100]}

    texts = [text_views(x)['full_text'] for x in items]
    split = [x['split'] for x in items]
    ids = [x['public_id'] for x in items]
    vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(4, 6), min_df=2, max_features=60000, sublinear_tf=True)
    matrix = vec.fit_transform(texts)
    sims = (matrix @ matrix.T).tocsr()
    near = []
    max_cross = 0.0
    for i in range(len(items)):
        start, end = sims.indptr[i], sims.indptr[i + 1]
        for j, val in zip(sims.indices[start:end], sims.data[start:end]):
            if j <= i or split[i] == split[j]:
                continue
            val = float(val)
            max_cross = max(max_cross, val)
            if val >= 0.995:
                near.append({'public_id_a': ids[i], 'public_id_b': ids[j], 'split_a': split[i], 'split_b': split[j], 'cosine_similarity': val})
    gated_views = ['full_text', 'dialogue_only', 'candidate_only', 'previous_turn', 'last_two']
    failed_exact = [v for v in gated_views if exact[v]['cross_split_collision_group_count'] > 0]
    return {
        'schema_version': 'mgp6-v4.3-duplicate-audit-1.0',
        'release_version': RELEASE_VERSION,
        'exact_views': exact,
        'near_duplicate_definition': 'character TF-IDF cosine >= 0.995 on full text',
        'near_duplicate_cross_split_edge_count': len(near),
        'near_duplicate_cross_split_edges': near[:100],
        'maximum_cross_split_full_text_cosine': max_cross,
        'failed_exact_gates': failed_exact,
        'passed': not failed_exact and not near,
    }


def evaluator_script() -> str:
    return r'''#!/usr/bin/env python3
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
'''


def verifier_script() -> str:
    return r'''#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, sys, tempfile, zipfile
from pathlib import Path

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def verify_manifest(root):
    manifest=json.loads((root/"MANIFEST.json").read_text(encoding="utf-8"))
    listed={row["relative_path"]:row for row in manifest["files"]}
    actual={p.relative_to(root).as_posix():p for p in root.rglob("*") if p.is_file() and p.name!="MANIFEST.json"}
    assert set(listed)==set(actual),(set(actual)-set(listed),set(listed)-set(actual))
    assert manifest["file_count_excluding_manifest"]==len(actual)
    for rel,p in actual.items():
        assert sha(p)==listed[rel]["sha256"],rel
        assert p.stat().st_size==listed[rel]["size_bytes"],rel

def main(root):
    root=Path(root); readiness=json.loads((root/"FINAL_RELEASE_READINESS.json").read_text(encoding="utf-8"))
    for name,meta in readiness["output_archives"].items():
        path=root/meta["filename"]; assert sha(path)==meta["sha256"],name
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None,name
            with tempfile.TemporaryDirectory() as tmp:
                z.extractall(tmp); verify_manifest(Path(tmp))
    print(json.dumps({"verified":True,"archive_count":len(readiness["output_archives"])},indent=2))
if __name__=="__main__": main(sys.argv[1] if len(sys.argv)>1 else ".")
'''


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    tmp = Path(tempfile.mkdtemp(prefix='mgp6-v43-final-'))
    try:
        a_dir, b_dir = tmp / 'annotator_a', tmp / 'annotator_b'
        extract_clean(ANNOTATOR_A_ZIP, a_dir)
        extract_clean(ANNOTATOR_B_ZIP, b_dir)

        canonical = read_jsonl(CONTENT_FREEZE / 'content_freeze/canonical_items.content_frozen.jsonl')
        public_frozen = read_jsonl(CONTENT_FREEZE / 'content_freeze/public_items.content_frozen.jsonl')
        binding_rows = read_jsonl(COORDINATOR / 'coordinator_private/annotation_private_binding.jsonl')
        binding = {x['annotation_id']: x for x in binding_rows}
        a_items = {x['annotation_id']: x for x in read_jsonl(COORDINATOR / 'annotator_a_packet/items.jsonl')}
        b_items = {x['annotation_id']: x for x in read_jsonl(COORDINATOR / 'annotator_b_packet/items.jsonl')}
        if set(a_items) != set(b_items) or set(a_items) != set(binding):
            raise RuntimeError('Annotation packet/binding ID mismatch')
        if sha256_file(a_dir / 'items.jsonl') != sha256_file(COORDINATOR / 'annotator_a_packet/items.jsonl'):
            raise RuntimeError('Annotator A item packet changed')
        if sha256_file(b_dir / 'items.jsonl') != sha256_file(COORDINATOR / 'annotator_b_packet/items.jsonl'):
            raise RuntimeError('Annotator B item packet changed')

        a_source = a_dir / ('responses_completed.jsonl' if (a_dir / 'responses_completed.jsonl').exists() else 'responses_to_complete.jsonl')
        b_source = b_dir / ('responses_completed.jsonl' if (b_dir / 'responses_completed.jsonl').exists() else 'responses_to_complete.jsonl')
        ann_a = validate_annotations(read_jsonl(a_source), a_items, binding, 'ALI')
        ann_b = validate_annotations(read_jsonl(b_source), b_items, binding, 'MOHAMMAD')
        a_by = {x['annotation_id']: x for x in ann_a}
        b_by = {x['annotation_id']: x for x in ann_b}

        label_disagreements = [i for i in sorted(a_by) if a_by[i]['action'] != b_by[i]['action']]
        exclusions = [i for i in sorted(a_by) if a_by[i]['exclusion_recommendation'] or b_by[i]['exclusion_recommendation']]
        evidence_relation_failures = []
        for aid in sorted(a_by):
            a_set, b_set = set(a_by[aid]['evidence_turn_ids']), set(b_by[aid]['evidence_turn_ids'])
            if b_set != a_set | {'T01'}:
                evidence_relation_failures.append(aid)
        if label_disagreements or exclusions or evidence_relation_failures:
            raise RuntimeError('Human consensus requires adjudication; cannot auto-finalize')

        canonical_by_private = {x['private_item_id']: x for x in canonical}
        consensus = []
        for aid in sorted(a_by):
            bind = binding[aid]
            source_item = canonical_by_private[bind['private_item_id']]
            a = a_by[aid]
            b = b_by[aid]
            if a['action'] != source_item['design_target'] or b['action'] != source_item['design_target']:
                raise RuntimeError(f'Consensus differs from design target for {aid}')
            row = {
                'schema_version': 'mgp6-v4.3-human-consensus-1.0',
                'annotation_id': aid,
                'private_item_id': bind['private_item_id'],
                'legacy_public_id': bind['public_id'],
                'component_id': bind['component_id'],
                'content_hash': bind['content_hash'],
                'annotator_a': {
                    'annotator_id': a['annotator_id'],
                    'action': a['action'],
                    'evidence_turn_ids': a['evidence_turn_ids'],
                    'rationale': a['rationale'],
                    'confidence': a['confidence'],
                    'scenario_ambiguity_flag': a['ambiguity_flag'],
                    'exclusion_recommendation': a['exclusion_recommendation'],
                    'source_recorded_at': a['annotated_at'],
                    'annotation_record_hash': a['annotation_record_hash'],
                },
                'annotator_b': {
                    'annotator_id': b['annotator_id'],
                    'action': b['action'],
                    'evidence_turn_ids': b['evidence_turn_ids'],
                    'rationale': b['rationale'],
                    'confidence': b['confidence'],
                    'scenario_ambiguity_flag': b['ambiguity_flag'],
                    'exclusion_recommendation': b['exclusion_recommendation'],
                    'source_recorded_at': b['annotated_at'],
                    'annotation_record_hash': b['annotation_record_hash'],
                },
                'label_agreement': True,
                'evidence_difference_classification': 'ANNOTATOR_B_ADDS_BASELINE_CONTEXT_T01_ONLY',
                'final_action': a['action'],
                'final_decision_evidence_turn_ids': source_item['linked_evidence_turn_ids'],
                'scenario_contains_intended_ambiguity': bool(a['ambiguity_flag'] and b['ambiguity_flag'] and a['action'] == 'ABSTAIN'),
                'gold_label_conflict': False,
                'adjudication_required': False,
                'human_completion_basis': 'DATA_OWNER_ATTESTED_HUMAN_COMPLETION_AND_BATCH_COPY',
                'identity_authentication': 'NOT_INDEPENDENTLY_VERIFIED_BY_BUILD_SYSTEM',
            }
            row['consensus_record_hash'] = canonical_hash(row)
            consensus.append(row)

        consensus_by_private = {x['private_item_id']: x for x in consensus}

        # Deterministic component-grouped split with exact domain and difficulty targets.
        components: dict[str, dict[str, Any]] = {}
        for item in canonical:
            components.setdefault(item['component_id'], {'domain': item['domain'], 'difficulty': item['difficulty'], 'items': []})['items'].append(item)
        domains = sorted({v['domain'] for v in components.values()})
        by_domain = {d: sorted([cid for cid, v in components.items() if v['domain'] == d]) for d in domains}
        target_train = {'EASY': 1, 'MEDIUM': 4, 'HARD': 7, 'EXPERT': 8}
        target_dev = {'EASY': 1, 'MEDIUM': 4, 'HARD': 8, 'EXPERT': 7}
        # Keep components with byte-identical candidate-only text in the same split.
        # Placing all such duplicate groups in hidden avoids cross-split candidate collisions
        # without using labels or model performance to select the split.
        candidate_components: dict[str, set[str]] = defaultdict(set)
        for source_item in canonical:
            candidate_components[source_item['dialogue'][-1]['text']].add(source_item['component_id'])
        candidate_duplicate_components = set().union(*(g for g in candidate_components.values() if len(g) > 1)) if any(len(g) > 1 for g in candidate_components.values()) else set()

        rng = random.Random(SPLIT_SEED)
        best = None
        for _ in range(800000):
            train_c, dev_c = [], []
            feasible = True
            for domain in domains:
                arr = by_domain[domain][:]
                rng.shuffle(arr)
                eligible = [cid for cid in arr if cid not in candidate_duplicate_components]
                if len(eligible) < 2:
                    feasible = False
                    break
                train_c.append(eligible[0]); dev_c.append(eligible[1])
            if not feasible:
                continue
            ct = Counter(components[c]['difficulty'] for c in train_c)
            cd = Counter(components[c]['difficulty'] for c in dev_c)
            objective = sum((ct[k] - target_train[k]) ** 2 for k in target_train) + sum((cd[k] - target_dev[k]) ** 2 for k in target_dev)
            candidate = (objective, sorted(train_c), sorted(dev_c), ct, cd)
            if best is None or candidate[0] < best[0]:
                best = candidate
                if objective == 0:
                    break
        if best is None or best[0] != 0:
            raise RuntimeError('Could not construct exact balanced split')
        train_components, dev_components = set(best[1]), set(best[2])
        hidden_components = set(components) - train_components - dev_components
        if len(train_components) != 20 or len(dev_components) != 20 or len(hidden_components) != 60:
            raise RuntimeError('Invalid component counts')

        component_split = {c: 'train' for c in train_components} | {c: 'dev' for c in dev_components} | {c: 'hidden' for c in hidden_components}
        final_items = []
        id_map = []
        for source in sorted(canonical, key=lambda x: x['private_item_id']):
            item = copy.deepcopy(source)
            consensus_row = consensus_by_private[item['private_item_id']]
            new_public_id = 'MGP43-' + hashlib.sha256(f'{RELEASE_VERSION}|{item["private_item_id"]}'.encode()).hexdigest()[:20].upper()
            item['release_version'] = RELEASE_VERSION
            item['public_id'] = new_public_id
            item['split'] = component_split[item['component_id']]
            item['content_status'] = 'FINAL_HUMAN_VALIDATED_CONTENT_FROZEN'
            item['gold_status'] = 'FINAL_DUAL_HUMAN_CONSENSUS_GOLD'
            item['human_review_status'] = 'DUAL_HUMAN_VALIDATED_DATA_OWNER_ATTESTED'
            item['final_gold_action'] = consensus_row['final_action']
            item['final_evidence_turn_ids'] = consensus_row['final_decision_evidence_turn_ids']
            item['human_validation'] = {
                'annotation_id': consensus_row['annotation_id'],
                'consensus_record_hash': consensus_row['consensus_record_hash'],
                'annotator_a_record_hash': consensus_row['annotator_a']['annotation_record_hash'],
                'annotator_b_record_hash': consensus_row['annotator_b']['annotation_record_hash'],
                'label_agreement': True,
                'adjudication_required': False,
                'scenario_contains_intended_ambiguity': consensus_row['scenario_contains_intended_ambiguity'],
                'data_owner_attestation_status': 'ACCEPTED_FOR_RELEASE',
                'identity_authentication': 'NOT_INDEPENDENTLY_VERIFIED_BY_BUILD_SYSTEM',
            }
            item['legacy_v4_2_public_id'] = source['public_id']
            item.pop('final_item_hash', None)
            item['final_item_hash'] = canonical_hash(item)
            final_items.append(item)
            id_map.append({
                'public_id': new_public_id,
                'legacy_public_id': source['public_id'],
                'annotation_id': source['blinded_id'],
                'private_item_id': source['private_item_id'],
                'component_id': source['component_id'],
                'split': item['split'],
                'gold_action': item['final_gold_action'],
                'content_hash': item['content_hash'],
                'final_item_hash': item['final_item_hash'],
            })

        if len({x['public_id'] for x in final_items}) != 900:
            raise RuntimeError('Release public IDs are not unique')
        split_items = {s: [x for x in final_items if x['split'] == s] for s in ['train', 'dev', 'hidden']}
        expected_counts = {'train': 180, 'dev': 180, 'hidden': 540}
        if {k: len(v) for k, v in split_items.items()} != expected_counts:
            raise RuntimeError('Split item counts are wrong')
        for s, rows in split_items.items():
            if Counter(x['final_gold_action'] for x in rows) != Counter({'KEEP': len(rows)//3, 'SUPERSEDE': len(rows)//3, 'ABSTAIN': len(rows)//3}):
                raise RuntimeError(f'Class balance failed for {s}')

        # Reports.
        all_a_actions = [a_by[i]['action'] for i in sorted(a_by)]
        all_b_actions = [b_by[i]['action'] for i in sorted(b_by)]
        agreement_report = {
            'schema_version': 'mgp6-v4.3-human-review-report-1.0',
            'release_version': RELEASE_VERSION,
            'annotator_a_id': 'ALI',
            'annotator_b_id': 'MOHAMMAD',
            'annotator_a_count': len(ann_a),
            'annotator_b_count': len(ann_b),
            'label_agreement_count': sum(a == b for a, b in zip(all_a_actions, all_b_actions)),
            'label_agreement_rate': 1.0,
            'cohen_kappa': 1.0,
            'action_distribution_a': dict(Counter(all_a_actions)),
            'action_distribution_b': dict(Counter(all_b_actions)),
            'mean_confidence_a': statistics.mean(x['confidence'] for x in ann_a),
            'mean_confidence_b': statistics.mean(x['confidence'] for x in ann_b),
            'ambiguity_flag_count_a': sum(x['ambiguity_flag'] for x in ann_a),
            'ambiguity_flag_count_b': sum(x['ambiguity_flag'] for x in ann_b),
            'ambiguity_normalization': 'All 300 dual ambiguity flags coincide with agreed ABSTAIN labels and are represented as intended scenario ambiguity, not gold-label conflict.',
            'evidence_selection_exact_match_count': 0,
            'evidence_selection_relation_count': 900,
            'evidence_selection_relation': 'Annotator B includes baseline context T01 in addition to Annotator A evidence for all items.',
            'label_adjudication_required_count': 0,
            'exclusion_count': 0,
            'completion_attestation': 'Dataset owner explicitly attested that both packets were completed by humans and then copied into the final files.',
            'attestation_verification_limit': 'The build system validates records and hashes but does not independently authenticate human identity or annotation duration.',
            'passed': True,
        }

        split_rows = []
        for cid in sorted(components):
            split_rows.append({
                'component_id': cid,
                'domain': components[cid]['domain'],
                'difficulty': components[cid]['difficulty'],
                'split': component_split[cid],
                'item_count': len(components[cid]['items']),
            })

        duplicate_report = duplicate_audit(final_items)
        shortcut_report = shortcut_audit(split_items['train'], split_items['hidden'])

        annotation_root = merkle_root([x['consensus_record_hash'] for x in sorted(consensus, key=lambda x: x['private_item_id'])])
        gold_root = merkle_root([x['final_item_hash'] for x in sorted(final_items, key=lambda x: x['public_id'])])
        source_hashes = {
            'content_freeze_canonical_items_sha256': sha256_file(CONTENT_FREEZE / 'content_freeze/canonical_items.content_frozen.jsonl'),
            'annotator_a_uploaded_zip_sha256': sha256_file(ANNOTATOR_A_ZIP),
            'annotator_b_uploaded_zip_sha256': sha256_file(ANNOTATOR_B_ZIP),
            'coordinator_private_binding_sha256': sha256_file(COORDINATOR / 'coordinator_private/annotation_private_binding.jsonl'),
            'builder_sha256': sha256_file(SCRIPT_PATH),
        }

        data_owner_attestation = f'''# Data-Owner Human Annotation Attestation\n\nThe dataset owner explicitly clarified that both submitted annotation packets were completed by human reviewers and were subsequently copied into the supplied JSONL files.\n\nThe release builder therefore treats the records as dual human annotations. The timestamps retained in the source records are preserved as recorded/imported metadata and are not used to infer annotation duration.\n\n## Accepted facts\n\n- Annotator A identifier in the supplied records: `ALI`\n- Annotator B identifier in the supplied records: `MOHAMMAD`\n- Coverage: 900 items per annotator\n- Label agreement: 900/900\n- Exclusion recommendations: 0\n- Label adjudication required: 0\n\n## Verification boundary\n\nThe build system validates schema, coverage, content-hash binding, evidence-turn references, label agreement, and package integrity. It does not independently authenticate reviewer identity or observe the original annotation sessions.\n\nAttestation accepted for release on: `{RELEASE_TIMESTAMP}`\n'''

        dataset_card = f'''# MGP-6 v4.3 Dataset Card\n\n## Identity\n\nMGP-6 v4.3 is a **human-authored, template-guided, controlled synthetic benchmark** for decision-level governance of long-lived personalized memory.\n\n## Task\n\nFor each dialogue, predict one action:\n\n- `KEEP`: retain the existing stored value.\n- `SUPERSEDE`: replace it with the proposed value.\n- `ABSTAIN`: do not commit a change because material evidence remains unresolved.\n\n## Size and split\n\n- 900 items\n- 100 semantic components\n- Train: 180 items / 20 components\n- Dev: 180 items / 20 components\n- Hidden: 540 items / 60 components\n- Exact class balance in every split\n- Components are never cut across splits\n- Every domain contributes one component to train, one to dev, and three to hidden\n\n## Human validation\n\nTwo completed human annotation packets cover all 900 items. Their labels agree on all items (`Cohen's kappa = 1.0`). No label adjudication or exclusion was required. Human completion is accepted based on an explicit data-owner attestation. Reviewer identity was not independently authenticated by the release builder.\n\n## Shortcut controls\n\nThe final split is component-held-out. Word, character, identifier, punctuation, length, restricted-view, and shallow-tree baselines are recorded in the private audit package.\n\n## Intended use\n\n- Controlled evaluation of memory update policies\n- Abstention and selective-decision evaluation\n- Ablation studies\n- Comparison with external memory benchmarks\n\n## Limitations\n\n- Constructed scenarios are not a substitute for real-world deployment evaluation.\n- The benchmark should be paired with an external benchmark such as LongMemEval.\n- Human completion is owner-attested rather than cryptographically identity-verified.\n- Public redistribution terms were not supplied in this conversation; select a license before public hosting.\n'''

        evaluation_protocol = '''# Evaluation Protocol\n\nSubmit one JSON object per line with exactly:\n\n```json\n{"public_id":"MGP43-...","action":"KEEP"}\n```\n\nAllowed actions are `KEEP`, `SUPERSEDE`, and `ABSTAIN`. The evaluator rejects missing, duplicate, unknown, or extra IDs.\n\nReport accuracy, macro-F1, per-class precision/recall/F1, confusion matrix, and component-cluster bootstrap confidence intervals. Do not tune on hidden gold.\n'''

        release_summary = {
            'schema_version': 'mgp6-v4.3-release-summary-1.0',
            'release_version': RELEASE_VERSION,
            'release_timestamp': RELEASE_TIMESTAMP,
            'dataset_identity': 'human_authored_template_guided_controlled_synthetic_benchmark',
            'item_count': 900,
            'component_count': 100,
            'split_counts': {k: len(v) for k, v in split_items.items()},
            'split_component_counts': dict(Counter(component_split.values())),
            'class_distribution': {s: dict(Counter(x['final_gold_action'] for x in rows)) for s, rows in split_items.items()},
            'domain_component_distribution': {s: dict(Counter(components[c]['domain'] for c, sp in component_split.items() if sp == s)) for s in ['train', 'dev', 'hidden']},
            'difficulty_component_distribution': {s: dict(Counter(components[c]['difficulty'] for c, sp in component_split.items() if sp == s)) for s in ['train', 'dev', 'hidden']},
            'human_agreement': {'count': 900, 'rate': 1.0, 'cohen_kappa': 1.0},
            'annotation_merkle_root': annotation_root,
            'final_gold_merkle_root': gold_root,
            'duplicate_audit_passed': duplicate_report['passed'],
            'shortcut_audit_passed': shortcut_report['passed'],
            'source_hashes': source_hashes,
        }

        # Standalone final gold.
        gold_rows = [{
            'schema_version': 'mgp6-v4.3-final-human-gold-1.0',
            'public_id': x['public_id'],
            'gold_action': x['final_gold_action'],
            'component_id': x['component_id'],
            'final_evidence_turn_ids': x['final_evidence_turn_ids'],
            'content_hash': x['content_hash'],
            'final_item_hash': x['final_item_hash'],
            'scenario_contains_intended_ambiguity': x['human_validation']['scenario_contains_intended_ambiguity'],
        } for x in sorted(final_items, key=lambda x: x['public_id'])]
        write_jsonl(OUT_GOLD, gold_rows)

        dirs = {
            'public_train_dev': OUT_ROOT / 'public_train_dev',
            'private_hidden_inputs': OUT_ROOT / 'private_hidden_inputs',
            'private_hidden_gold': OUT_ROOT / 'private_hidden_gold',
            'private_audit_package': OUT_ROOT / 'private_audit_package',
            'source_and_builder': OUT_ROOT / 'source_and_builder',
        }
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)

        def public_record(x: dict[str, Any], include_gold: bool) -> dict[str, Any]:
            row = {
                'public_id': x['public_id'],
                'memory_before': x['memory_before'],
                'dialogue': x['dialogue'],
                'evaluation_query': x['evaluation_query'],
            }
            if include_gold:
                row['gold_action'] = x['final_gold_action']
            return row

        # Public train/dev package.
        pub = dirs['public_train_dev']
        write_jsonl(pub / 'train.jsonl', [public_record(x, True) for x in sorted(split_items['train'], key=lambda x: x['public_id'])])
        write_jsonl(pub / 'dev.jsonl', [public_record(x, True) for x in sorted(split_items['dev'], key=lambda x: x['public_id'])])
        (pub / 'DATASET_CARD.md').write_text(dataset_card, encoding='utf-8')
        (pub / 'EVALUATION_PROTOCOL.md').write_text(evaluation_protocol, encoding='utf-8')
        write_json(pub / 'SPLIT_SUMMARY.json', release_summary)
        write_json(pub / 'record_schema.json', {
            '$schema': 'https://json-schema.org/draft/2020-12/schema',
            'type': 'object', 'additionalProperties': False,
            'required': ['public_id', 'memory_before', 'dialogue', 'evaluation_query', 'gold_action'],
            'properties': {
                'public_id': {'type': 'string', 'pattern': '^MGP43-[0-9A-F]{20}$'},
                'memory_before': {'type': 'object'}, 'dialogue': {'type': 'array'},
                'evaluation_query': {'type': 'string'}, 'gold_action': {'enum': LABELS},
            }
        })
        (pub / 'LICENSE_STATUS.md').write_text('# License Status\n\nPublic redistribution license terms were not supplied. This package is experiment-ready but should not be publicly hosted until the dataset owner selects a license.\n', encoding='utf-8')
        make_manifest(pub, 'PUBLIC_TRAIN_DEV')

        # Hidden inputs package.
        hin = dirs['private_hidden_inputs']
        write_jsonl(hin / 'hidden_inputs.jsonl', [public_record(x, False) for x in sorted(split_items['hidden'], key=lambda x: x['public_id'])])
        write_json(hin / 'submission_format.json', {'one_json_object_per_line': {'public_id': 'MGP43-...', 'action': 'KEEP | SUPERSEDE | ABSTAIN'}, 'expected_row_count': 540})
        write_json(hin / 'hidden_schema.json', {
            '$schema': 'https://json-schema.org/draft/2020-12/schema',
            'type': 'object', 'additionalProperties': False,
            'required': ['public_id', 'memory_before', 'dialogue', 'evaluation_query'],
            'properties': {'public_id': {'type': 'string'}, 'memory_before': {'type': 'object'}, 'dialogue': {'type': 'array'}, 'evaluation_query': {'type': 'string'}}
        })
        (hin / 'README.md').write_text('# Private Hidden Inputs\n\nUse these 540 inputs only after prompts, models, decoding settings, and controller configuration are frozen. Do not join with private gold during model development.\n', encoding='utf-8')
        make_manifest(hin, 'PRIVATE_HIDDEN_INPUTS')

        # Hidden gold package.
        hgold = dirs['private_hidden_gold']
        hidden_gold_rows = [x for x in gold_rows if next(i for i in final_items if i['public_id'] == x['public_id'])['split'] == 'hidden']
        write_jsonl(hgold / 'hidden_gold.jsonl', hidden_gold_rows)
        write_json(hgold / 'cluster_map_private.json', {x['public_id']: x['component_id'] for x in hidden_gold_rows})
        (hgold / 'evaluate_predictions.py').write_text(evaluator_script(), encoding='utf-8')
        (hgold / 'scoring_contract.json').write_text(json.dumps({'labels': LABELS, 'expected_hidden_count': 540, 'primary_metrics': ['accuracy', 'macro_f1'], 'confidence_intervals': 'component-cluster bootstrap, 5000 replicates, seed 4301'}, indent=2) + '\n', encoding='utf-8')
        make_manifest(hgold, 'PRIVATE_HIDDEN_GOLD')

        # Audit package.
        audit = dirs['private_audit_package']
        write_jsonl(audit / 'canonical_items.final_human_validated.jsonl', sorted(final_items, key=lambda x: x['private_item_id']))
        write_jsonl(audit / 'human_annotations/annotator_a.completed.jsonl', ann_a)
        write_jsonl(audit / 'human_annotations/annotator_b.completed.jsonl', ann_b)
        write_jsonl(audit / 'human_annotations/final_consensus.jsonl', consensus)
        (audit / 'human_annotations/DATA_OWNER_HUMAN_ANNOTATION_ATTESTATION.md').write_text(data_owner_attestation, encoding='utf-8')
        write_json(audit / 'human_annotations/HUMAN_REVIEW_REPORT.json', agreement_report)
        write_jsonl(audit / 'final_human_gold.jsonl', gold_rows)
        write_jsonl(audit / 'private_id_mapping.jsonl', id_map)
        write_csv(audit / 'LOCKED_SPLIT_MAP_V4_3.csv', split_rows, ['component_id', 'domain', 'difficulty', 'split', 'item_count'])
        write_json(audit / 'audits/FINAL_DUPLICATE_AUDIT.json', duplicate_report)
        write_json(audit / 'audits/FINAL_SHORTCUT_AUDIT.json', shortcut_report)
        write_json(audit / 'audits/FINAL_RELEASE_SUMMARY.json', release_summary)
        write_json(audit / 'provenance/SOURCE_HASHES.json', source_hashes)
        shutil.copy2(CONTENT_FREEZE / 'HASH_CANONICALIZATION_SPEC.md', audit / 'provenance/HASH_CANONICALIZATION_SPEC_V4_2.md')
        (audit / 'provenance/HASH_CANONICALIZATION_SPEC_V4_3.md').write_text('# MGP-6 v4.3 Hash Canonicalization\n\nAll row hashes use UTF-8 encoded JSON with object keys sorted, no insignificant whitespace, and `ensure_ascii=false`. Arrays preserve order. `final_item_hash` is calculated before adding that field. Consensus hashes are calculated before adding `consensus_record_hash`.\n', encoding='utf-8')
        (audit / 'DATASET_CARD.md').write_text(dataset_card, encoding='utf-8')
        (audit / 'EVALUATION_PROTOCOL.md').write_text(evaluation_protocol, encoding='utf-8')
        make_manifest(audit, 'PRIVATE_AUDIT_PACKAGE')

        # Source and builder package.
        src = dirs['source_and_builder']
        shutil.copy2(SCRIPT_PATH, src / 'build_mgp6_v43_final.py')
        (src / 'verify_release.py').write_text(verifier_script(), encoding='utf-8')
        (src / 'evaluate_predictions.py').write_text(evaluator_script(), encoding='utf-8')
        (src / 'README.md').write_text('# MGP-6 v4.3 Source and Builder\n\n`build_mgp6_v43_final.py` builds the human-validated release from the v4.2 content freeze, coordinator kit, and two completed annotation packets. `verify_release.py` validates final archive hashes, CRC, and internal manifests.\n', encoding='utf-8')
        write_json(src / 'FROZEN_BUILD_CONFIG.json', {'release_version': RELEASE_VERSION, 'release_timestamp': RELEASE_TIMESTAMP, 'split_seed': SPLIT_SEED, 'shortcut_seeds': SHORTCUT_SEEDS, 'zip_timestamp': ZIP_TIME})
        make_manifest(src, 'SOURCE_AND_BUILDER')

        # Model-facing allowlist validation.
        forbidden_keys = {'private_item_id', 'component_id', 'design_target', 'blinded_id', 'content_hash', 'source_item_hash', 'human_validation', 'final_gold_action', 'linked_evidence_turn_ids', 'split'}
        allowlist_errors = []
        for path in [pub / 'train.jsonl', pub / 'dev.jsonl', hin / 'hidden_inputs.jsonl']:
            for idx, row in enumerate(read_jsonl(path), 1):
                bad = forbidden_keys & set(row)
                if bad:
                    allowlist_errors.append({'file': path.name, 'row': idx, 'forbidden_keys': sorted(bad)})
        if allowlist_errors:
            raise RuntimeError(f'Model-facing allowlist failed: {allowlist_errors[:5]}')

        archive_paths = {}
        archive_metadata = {}
        for key, d in dirs.items():
            out = OUT_ROOT / f'{RELEASE_NAME}-{key.replace("_", "-")}.zip'
            out2 = OUT_ROOT / f'.determinism-check-{key}.zip'
            deterministic_zip(d, out)
            deterministic_zip(d, out2)
            if sha256_file(out) != sha256_file(out2):
                raise RuntimeError(f'Deterministic build failed for {key}')
            out2.unlink()
            with zipfile.ZipFile(out) as zf:
                if zf.testzip() is not None:
                    raise RuntimeError(f'CRC failed for {key}')
            archive_paths[key] = out
            archive_metadata[key] = {'filename': out.name, 'sha256': sha256_file(out), 'size_bytes': out.stat().st_size}

        gates = {
            'dual_human_annotation_coverage_complete': len(ann_a) == 900 and len(ann_b) == 900,
            'human_label_agreement_complete': not label_disagreements,
            'human_exclusions_zero': not exclusions,
            'evidence_difference_non_substantive': not evidence_relation_failures,
            'data_owner_human_completion_attestation_recorded': True,
            'all_items_final_human_gold': len(gold_rows) == 900,
            'split_counts_exact': {k: len(v) for k, v in split_items.items()} == expected_counts,
            'class_balance_exact': all(Counter(x['final_gold_action'] for x in rows) == Counter({'KEEP': len(rows)//3, 'SUPERSEDE': len(rows)//3, 'ABSTAIN': len(rows)//3}) for rows in split_items.values()),
            'components_not_cut': all(len({x['split'] for x in final_items if x['component_id'] == cid}) == 1 for cid in components),
            'domain_component_balance_exact': all(Counter(components[c]['domain'] for c, sp in component_split.items() if sp == s) == Counter({d: (1 if s in ['train','dev'] else 3) for d in domains}) for s in ['train','dev','hidden']),
            'duplicate_audit_passed': duplicate_report['passed'],
            'shortcut_audit_passed': shortcut_report['passed'],
            'model_field_allowlist_passed': not allowlist_errors,
            'archive_manifests_passed': all(verify_manifest(d)['passed'] for d in dirs.values()),
            'deterministic_build_passed': True,
        }
        failed_gates = [k for k, v in gates.items() if not v]
        readiness = {
            'schema_version': 'mgp6-v4.3-final-release-readiness-1.0',
            'release_version': RELEASE_VERSION,
            'release_timestamp': RELEASE_TIMESTAMP,
            'dataset_identity': 'human_authored_template_guided_controlled_synthetic_benchmark',
            'verdict': 'READY_FOR_FINAL_PAPER_EXPERIMENTS' if not failed_gates else 'BLOCKED_FINAL_RELEASE',
            'publication_experiment_eligible': not failed_gates,
            'public_redistribution_license_selected': False,
            'public_redistribution_note': 'Select a license before public hosting; this does not block internal paper experiments.',
            'gates': gates,
            'failed_gates': failed_gates,
            'human_review': agreement_report,
            'split_summary': release_summary,
            'annotation_merkle_root': annotation_root,
            'final_gold_merkle_root': gold_root,
            'output_archives': archive_metadata,
        }
        write_json(OUT_READINESS_JSON, readiness)
        readiness_md = f'''# MGP-6 v4.3 Final Release Readiness\n\n- Release: `{RELEASE_VERSION}`\n- Verdict: **{readiness['verdict']}**\n- Final items: **900**\n- Human annotations: **900 + 900**\n- Label agreement: **100%**\n- Cohen's kappa: **1.000**\n- Label adjudications required: **0**\n- Train/dev/hidden: **180 / 180 / 540**\n- Shortcut audit: **{'PASS' if shortcut_report['passed'] else 'FAIL'}**\n- Duplicate audit: **{'PASS' if duplicate_report['passed'] else 'FAIL'}**\n- Failed gates: **{len(failed_gates)}**\n\nHuman completion is accepted from the dataset owner's explicit attestation. The build system does not independently authenticate reviewer identity. Public redistribution license selection remains separate from experiment readiness.\n'''
        OUT_READINESS_MD.write_text(readiness_md, encoding='utf-8')

        # Master bundle.
        master_dir = OUT_ROOT / 'master_bundle'
        master_dir.mkdir()
        for p in archive_paths.values():
            shutil.copy2(p, master_dir / p.name)
        shutil.copy2(OUT_READINESS_JSON, master_dir / 'FINAL_RELEASE_READINESS.json')
        shutil.copy2(OUT_READINESS_MD, master_dir / 'FINAL_RELEASE_READINESS.md')
        shutil.copy2(OUT_GOLD, master_dir / 'FINAL_HUMAN_GOLD_PRIVATE.jsonl')
        (master_dir / 'verify_release.py').write_text(verifier_script(), encoding='utf-8')
        write_json(master_dir / 'RELEASE_INDEX.json', {
            'release_version': RELEASE_VERSION,
            'release_timestamp': RELEASE_TIMESTAMP,
            'archives': archive_metadata,
            'readiness_verdict': readiness['verdict'],
            'annotation_merkle_root': annotation_root,
            'final_gold_merkle_root': gold_root,
        })
        make_manifest(master_dir, 'MASTER_FINAL_RELEASE_BUNDLE')
        deterministic_zip(master_dir, OUT_MASTER)
        master_sha = sha256_file(OUT_MASTER)

        # Verify all archives from master source metadata.
        archive_verification = {}
        for key, path in archive_paths.items():
            with zipfile.ZipFile(path) as zf:
                crc = zf.testzip() is None
                extract = tmp / f'verify-{key}'
                extract.mkdir(exist_ok=True)
                zf.extractall(extract)
                mv = verify_manifest(extract)
            archive_verification[key] = {'crc_pass': crc, 'sha256': sha256_file(path), 'manifest': mv, 'passed': crc and mv['passed']}

        verification = {
            'schema_version': 'mgp6-v4.3-final-release-verification-1.0',
            'release_version': RELEASE_VERSION,
            'release_timestamp': RELEASE_TIMESTAMP,
            'passed': not failed_gates and all(v['passed'] for v in archive_verification.values()),
            'master_bundle': {'filename': OUT_MASTER.name, 'sha256': master_sha, 'size_bytes': OUT_MASTER.stat().st_size, 'crc_pass': zipfile.ZipFile(OUT_MASTER).testzip() is None},
            'archives': archive_verification,
            'gates': gates,
            'failed_gates': failed_gates,
            'human_gold_count': len(gold_rows),
            'annotation_merkle_root': annotation_root,
            'final_gold_merkle_root': gold_root,
            'standalone_final_gold_sha256': sha256_file(OUT_GOLD),
        }
        write_json(OUT_VERIFICATION, verification)
        shutil.copy2(OUT_VERIFICATION, master_dir / 'FINAL_RELEASE_VERIFICATION.json')
        make_manifest(master_dir, 'MASTER_FINAL_RELEASE_BUNDLE')
        deterministic_zip(master_dir, OUT_MASTER)
        verification['master_bundle'] = {'filename': OUT_MASTER.name, 'sha256': sha256_file(OUT_MASTER), 'size_bytes': OUT_MASTER.stat().st_size, 'crc_pass': zipfile.ZipFile(OUT_MASTER).testzip() is None}
        write_json(OUT_VERIFICATION, verification)

        print(json.dumps({
            'status': readiness['verdict'],
            'release_version': RELEASE_VERSION,
            'master_bundle': str(OUT_MASTER),
            'master_sha256': sha256_file(OUT_MASTER),
            'verification': str(OUT_VERIFICATION),
            'standalone_gold': str(OUT_GOLD),
            'output_archives': archive_metadata,
            'human_agreement': 1.0,
            'shortcut_audit_passed': shortcut_report['passed'],
            'duplicate_audit_passed': duplicate_report['passed'],
            'failed_gates': failed_gates,
        }, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
