#!/usr/bin/env python3
"""MGP-6 v4.3 PUBLIC DEV split: evidence routing x decision prompt (2 x 2), with the manuscript's own model settings.

Runs only on the public development split (180 items) that is tracked in the ASK repository. No hidden items, no LongMemEval data.
Reads the API key from an environment variable (default OPENROUTER_API_KEY). The key is never written to any file.
Does not write inside the repository (bytecode writing is disabled; all outputs go to --out).

Cells (builders and prompt files are the repository's own):
  A_zero_payload : full public payload + one-line decision prompt       (manuscript decision_zero_shot)
  B_live_routed  : router-extracted evidence + live-controller prompt   (manuscript live_model_controller, model output before the guard)
  D_zero_routed  : router-extracted evidence + one-line prompt          (routing only)
  E_live_payload : full public payload + live-controller prompt         (prompt only; diagnostic, the prompt text says two indexed messages)
B_guarded is computed afterwards, with no extra calls, by applying the repository's own apply_live_controller_guard to B outputs;
it is the construction behind the tracked live_model_controller row.
Tracked reference values on this split (manuscript model): decision_zero_shot accuracy 0.3389, live_model_controller accuracy 0.8444.
"""
import sys, os, json, time, hashlib, argparse, threading, queue, urllib.request, urllib.error, platform, datetime
sys.dont_write_bytecode = True
ap = argparse.ArgumentParser()
ap.add_argument('--repo', required=True, help='path to the ASK repository (read only)')
ap.add_argument('--out', required=True, help='output directory (outside the repository)')
ap.add_argument('--model', default='qwen/qwen3.5-9b')
ap.add_argument('--base-url', default='https://openrouter.ai/api/v1')
ap.add_argument('--api-key-env', default='OPENROUTER_API_KEY')
ap.add_argument('--reasoning-effort', default='none', help="'none' (manuscript setting) or 'omit' to send no reasoning field")
ap.add_argument('--no-response-format', action='store_true', help='do not request response_format=json_object (for gateways that reject it)')
ap.add_argument('--repeats', type=int, default=1)
ap.add_argument('--concurrency', type=int, default=4)
ap.add_argument('--seed', type=int, default=4301)
ap.add_argument('--no-seed', action='store_true', help='do not send a seed (some providers reject it)')
ap.add_argument('--max-tokens', type=int, default=128, help='manuscript setting is 128; use 1024 for models that reason before answering')
ap.add_argument('--limit', type=int, default=0, help='run only this many pending calls (testing)')
ap.add_argument('--timeout', type=float, default=120.0, help='seconds to wait for one HTTP response')
ap.add_argument('--ping', action='store_true', help='send one tiny non-dataset request, print the reply and timing, then exit')
ap.add_argument('--extra-body', default='', help="JSON object of extra top-level request fields, for example '{\"reasoning_effort\":\"low\"}'")
ap.add_argument('--ping-item', default='', help='send the real prompt of one public dev item, as CELL:INDEX (for example A_zero_payload:0), print tokens and finish_reason, then exit')
ap.add_argument('--quiet', action='store_true', help='no per-call lines (progress bar only)')
ap.add_argument('--abort-after-invalid', type=int, default=8, help='stop the run after this many consecutive empty or invalid replies (0 disables)')
a = ap.parse_args()
repo = os.path.abspath(os.path.expanduser(a.repo)); out = os.path.abspath(os.path.expanduser(a.out))
if os.path.commonpath([repo, out]) == repo:
    sys.exit('refusing to write inside the repository: choose --out outside ' + repo)
os.makedirs(out, exist_ok=True)
key = os.environ.get(a.api_key_env)
if not key: sys.exit(f'environment variable {a.api_key_env} is not set')
sys.path.insert(0, os.path.join(repo, 'src'))
from ask.eval.mgp6_v43 import load_public_records, build_system_prompt, parse_action_response, apply_live_controller_guard
DEV = os.path.join(repo, 'benchmarks/mgp6/mgp6_v4_3/public/dev.jsonl')
CFG = os.path.join(repo, 'configs/experiments/mgp6_v43')
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
EXPECT_DEV = 'd4dbf740d9fa5239829842e2ab6f5ce67b11d6d909628ff38f4a19fc0242cde5'
dev_sha = sha(DEV)
if dev_sha != EXPECT_DEV: print('WARNING: dev.jsonl sha256 differs from the tracked value', dev_sha, file=sys.stderr)
zero = open(os.path.join(CFG, 'decision_system_prompt.txt'), encoding='utf-8').read(); live = open(os.path.join(CFG, 'live_model_controller_prompt.txt'), encoding='utf-8').read()
recs = load_public_records(DEV)
assert len(recs) == 180, len(recs)
CELLS = {'A_zero_payload': lambda r: build_system_prompt(r, 'decision_zero_shot', zero),
         'B_live_routed': lambda r: build_system_prompt(r, 'live_model_controller', live),
         'D_zero_routed': lambda r: build_system_prompt(r, 'live_model_controller', zero),
         'E_live_payload': lambda r: build_system_prompt(r, 'decision_zero_shot', live)}
RES = os.path.join(out, 'results.jsonl'); lock = threading.Lock(); done = set()
if os.path.exists(RES):
    for l in open(RES, encoding='utf-8'):
        if l.strip():
            j = json.loads(l)
            retry = j.get('action') == 'FAILED' or (j.get('action') == 'INVALID' and (j.get('finish_reason') == 'length' or 'max_tokens' not in j) and j.get('max_tokens', 0) < a.max_tokens)
            if not retry: done.add((j['public_id'], j['cell'], j['repeat']))   # transport failures and cut-off replies are retried on resume with a larger --max-tokens
q = queue.Queue()
for rep in range(a.repeats):
    for cell in CELLS:
        for r in recs:
            if (r.public_id, cell, rep) not in done: q.put((r, cell, rep))
if a.limit:
    keep = [q.get() for _ in range(min(a.limit, q.qsize()))]; q = queue.Queue(); [q.put(k) for k in keep]
total = q.qsize(); counter = {'n': 0}
print('pending calls:', total, flush=True)
def call(prompt):
    return call_raw([{'role': 'user', 'content': prompt}])
def call_raw(messages):
    body = {'model': a.model, 'messages': messages, 'temperature': 0, 'max_tokens': a.max_tokens, 'stream': False}
    if not a.no_seed: body['seed'] = a.seed
    if not a.no_response_format: body['response_format'] = {'type': 'json_object'}
    if a.reasoning_effort != 'omit': body['reasoning'] = {'effort': a.reasoning_effort}
    if a.extra_body: body.update(json.loads(a.extra_body))
    req = urllib.request.Request(a.base_url.rstrip('/') + '/chat/completions', data=json.dumps(body).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=a.timeout) as resp: return json.loads(resp.read().decode())

def log(msg):
    sys.stderr.write(msg + '\n'); sys.stderr.flush()
if a.ping:
    t0 = time.time()
    try:
        j = call_raw([{'role': 'user', 'content': 'Reply with exactly this JSON and nothing else: {"action":"KEEP"}'}])
        log(f"PING ok in {time.time()-t0:.1f}s | returned_model={j.get('model')} | reply={str((j['choices'][0]['message'].get('content') or ''))[:200]!r} | usage={j.get('usage')}")
    except urllib.error.HTTPError as e:
        body = ''
        try: body = e.read().decode()[:400]
        except Exception: pass
        log(f"PING HTTP {e.code} after {time.time()-t0:.1f}s | {body}")
    except Exception as e:
        log(f"PING failed after {time.time()-t0:.1f}s | {type(e).__name__}: {e}")
    sys.exit(0)
if a.ping_item:
    cell_, idx_ = a.ping_item.split(':'); r_ = recs[int(idx_)]; prompt_ = CELLS[cell_](r_)
    t0 = time.time()
    try:
        j = call(prompt_); ch = j['choices'][0]; txt = ch['message'].get('content') or ''
        try: act = parse_action_response(txt)
        except Exception: act = 'INVALID'
        log(f"PING-ITEM {cell_} item {idx_} ({r_.public_id[-8:]}): {act} in {time.time()-t0:.1f}s | finish={ch.get('finish_reason')} | completion_tokens={(j.get('usage') or {}).get('completion_tokens')} | reasoning_tokens={((j.get('usage') or {}).get('completion_tokens_details') or {}).get('reasoning_tokens')} | reply={txt[:80]!r} | extra_body={a.extra_body or '-'}")
    except urllib.error.HTTPError as e:
        body = ''
        try: body = e.read().decode()[:300]
        except Exception: pass
        log(f"PING-ITEM HTTP {e.code} after {time.time()-t0:.1f}s | {body}")
    except Exception as e:
        log(f"PING-ITEM failed after {time.time()-t0:.1f}s | {type(e).__name__}: {e}")
    sys.exit(0)

stop = threading.Event(); inflight = {}; consec = {'n': 0}; t_start = time.time()
class _Bar:
    """Fallback progress bar used when tqdm is not installed."""
    def __init__(self, total): self.total = total; self.n = 0
    def _draw(self):
        w = 28; f = int(w * self.n / max(1, self.total)); el = time.time() - t_start
        eta = (el / self.n * (self.total - self.n)) if self.n else 0
        sys.stderr.write(f"\r[{'#' * f}{'.' * (w - f)}] {self.n}/{self.total}  elapsed {el:.0f}s  eta {eta:.0f}s   "); sys.stderr.flush()
    def update(self, k=1): self.n += k; self._draw()
    def write(self, msg): sys.stderr.write("\r" + " " * 78 + "\r" + msg + "\n"); self._draw()
    def close(self): sys.stderr.write("\n")
try:
    from tqdm import tqdm
    pbar = tqdm(total=total, unit='call', file=sys.stderr, dynamic_ncols=True)
except Exception:
    pbar = _Bar(total)
def say(msg):
    (pbar.write if hasattr(pbar, 'write') else log)(msg)
def heartbeat():
    while not stop.is_set():
        time.sleep(10)
        now = time.time()
        if inflight:
            old = max(inflight.values(), key=lambda v: now - v[2])
            say(f"  ... {len(inflight)} request(s) in flight; longest {now - old[2]:.0f}s ({old[0]} {old[1]}); timeout is {a.timeout:.0f}s")
def worker():
    while not stop.is_set():
        try: r, cell, rep = q.get_nowait()
        except queue.Empty: return
        prompt = CELLS[cell](r)
        rec = dict(public_id=r.public_id, cell=cell, repeat=rep, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(), requested_model=a.model, action='FAILED')
        tag = f"{cell} r{rep} {r.public_id[-8:]}"
        parse_tries = 0
        for attempt in range(3):
            if stop.is_set(): return
            t0 = time.time(); inflight[threading.get_ident()] = (cell, r.public_id[-8:], t0)
            try:
                j = call(prompt); ch = j['choices'][0]; txt = (ch['message'].get('content') or ''); fin = ch.get('finish_reason')
                try: act = parse_action_response(txt)
                except Exception: act = 'INVALID'
                dt = time.time() - t0
                rec.update(action=act, raw=txt[:120], finish_reason=fin, max_tokens=a.max_tokens, returned_model=j.get('model'), provider=j.get('provider'), usage=j.get('usage'), latency_s=round(dt, 2), attempts=attempt + 1, utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
                rec.pop('error', None); rec.pop('http', None)
                if not a.quiet:
                    note = '' if act != 'INVALID' else ('  <- EMPTY/CUT OFF (finish_reason=length): raise --max-tokens' if fin == 'length' else '  <- reply could not be parsed')
                    say(f"  {tag} try{attempt+1}: {act:<9} {dt:5.1f}s  tokens={(j.get('usage') or {}).get('completion_tokens')}  finish={fin}  reply={txt[:50]!r}{note}")
                if act != 'INVALID':
                    consec['n'] = 0; break
                consec['n'] += 1
                if a.abort_after_invalid and consec['n'] >= a.abort_after_invalid:
                    say(f"STOPPING: {consec['n']} consecutive empty or invalid replies (max_tokens={a.max_tokens}). Raise --max-tokens (reasoning models need 4096 or more) or choose another model, then rerun the same command; cut-off rows are retried."); stop.set(); break
                parse_tries += 1
                if fin == 'length' or parse_tries >= 2: break      # a cut-off reply at temperature 0 will not change on retry; parse retries follow the manuscript's limit of 2
            except urllib.error.HTTPError as e:
                body = ''
                try: body = e.read().decode(errors='replace')[:200].replace('\n', ' ')
                except Exception: pass
                rec.update(http=e.code, error=str(e)[:100]); say(f"  {tag} try{attempt+1}: HTTP {e.code} after {time.time()-t0:.1f}s  {body}")
                time.sleep(2 * (attempt + 1))
            except Exception as e:
                rec.update(error=type(e).__name__); say(f"  {tag} try{attempt+1}: {type(e).__name__} after {time.time()-t0:.1f}s  {str(e)[:120]}")
                time.sleep(2 * (attempt + 1))
            finally:
                inflight.pop(threading.get_ident(), None)
        with lock:
            open(RES, 'a', encoding='utf-8').write(json.dumps(rec) + '\n'); counter['n'] += 1
            pbar.update(1)
ts = [threading.Thread(target=worker, daemon=True) for _ in range(a.concurrency)]
hb = threading.Thread(target=heartbeat, daemon=True); hb.start()
[t.start() for t in ts]
try:
    while any(t.is_alive() for t in ts): time.sleep(0.4)
except KeyboardInterrupt:
    stop.set(); say('Interrupted. Results written so far are kept; run the same command again to resume.')
stop.set(); pbar.close()
# ---- summary
_latest = {}
for l in open(RES, encoding='utf-8'):
    if l.strip(): _j = json.loads(l); _latest[(_j['public_id'], _j['cell'], _j['repeat'])] = _j   # a later row replaces an earlier failed one
rows = list(_latest.values())
gold = {r.public_id: r.gold_action for r in recs}; ACT = ['KEEP', 'SUPERSEDE', 'ABSTAIN']
byid = {r.public_id: r for r in recs}
def mf1(y, p):
    f = []
    for c in ACT:
        tp = sum(g == c and q_ == c for g, q_ in zip(y, p)); fp = sum(g != c and q_ == c for g, q_ in zip(y, p)); fn = sum(g == c and q_ != c for g, q_ in zip(y, p))
        f.append(0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return sum(f) / 3
summ = {'max_tokens': a.max_tokens, 'sent_seed': (not a.no_seed), 'reasoning_effort_arg': a.reasoning_effort, 'model': a.model, 'base_url': a.base_url, 'dev_sha256': dev_sha, 'python': platform.python_version(), 'n_rows': len(rows), 'cells': {},
        'tracked_reference_accuracy': {'decision_zero_shot': 0.3388888888888889, 'live_model_controller': 0.8444444444444444}}
for rep in range(a.repeats):
    for cell in list(CELLS) + ['B_guarded']:
        src = 'B_live_routed' if cell == 'B_guarded' else cell
        rr = {x['public_id']: x for x in rows if x['cell'] == src and x['repeat'] == rep}
        if len(rr) < 180: continue
        pred = []
        for i in gold:
            act = rr[i]['action']
            if cell == 'B_guarded' and act in ACT:
                act, _ = apply_live_controller_guard(byid[i], act)
            pred.append(act)
        y = [gold[i] for i in gold]
        summ['cells'][f'{cell}|repeat{rep}'] = {'accuracy': sum(g == p for g, p in zip(y, pred)) / 180, 'macro_f1': mf1(y, pred), 'invalid_or_failed': sum(p not in ACT for p in pred), 'pred_distribution': {c: pred.count(c) for c in ACT}}
done_per_cell = {c: sum(1 for x in rows if x['cell'] == c and x['repeat'] == 0 and x.get('action') in ACT) for c in CELLS}
summ['completed_ok_per_cell_repeat0'] = done_per_cell; log(f'valid replies per cell (repeat 0, of 180): {done_per_cell}')
json.dump(summ, open(os.path.join(out, 'summary.json'), 'w'), indent=1)
print(json.dumps(summ['cells'], indent=1)); print('tracked reference:', summ['tracked_reference_accuracy'])
