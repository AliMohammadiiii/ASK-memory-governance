#!/usr/bin/env python3
"""MGP-6 v4.3 public-dev input-routing / prompt decomposition (exploratory, substitute model).
Reads key from env NINEROUTER_API_KEY. Uses the baseline repo export in /tmp/askbase (git archive of f6bf66e).
Cells (all use repo builders; INPUT views and prompts are the repo's own):
  A_zero_payload : decision_zero_shot view (full public payload) + one-line decision prompt   (paper's zero-shot baseline construction)
  B_live_routed  : linked_evidence_view (router-extracted two messages) + live-controller prompt (paper's live controller, no guard)
  D_zero_routed  : linked_evidence_view + one-line decision prompt                               (routing without the detailed prompt)
  E_live_payload : full payload + live-controller prompt (prompt text says two indexed messages; MISMATCHED, diagnostic only)
Output: results.jsonl (public_id, cell, repeat, predicted action, prompt sha256, usage). No item text is stored.
"""
import sys, os, json, time, hashlib, datetime, threading, queue, requests
sys.path.insert(0, '/tmp/askbase/src')
from ask.eval.mgp6_v43 import load_public_records, build_system_prompt
OUT = sys.argv[1]; MODEL = sys.argv[2]; REPEATS = int(sys.argv[3]); CONC = int(sys.argv[4])
BASE = 'https://re6rnzc.abc-tunnel.us/v1'; KEY = os.environ['NINEROUTER_API_KEY']
CFG = '/tmp/askbase/configs/experiments/mgp6_v43/'
zero = open(CFG + 'decision_system_prompt.txt').read(); live = open(CFG + 'live_model_controller_prompt.txt').read()
recs = load_public_records('/tmp/askbase/dev.jsonl')
CELLS = {'A_zero_payload': lambda r: build_system_prompt(r, 'decision_zero_shot', zero),
         'B_live_routed': lambda r: build_system_prompt(r, 'live_model_controller', live),
         'D_zero_routed': lambda r: build_system_prompt(r, 'live_model_controller', zero),
         'E_live_payload': lambda r: build_system_prompt(r, 'decision_zero_shot', live)}
RES = os.path.join(OUT, 'results.jsonl'); lock = threading.Lock()
done = set()
if os.path.exists(RES):
    for l in open(RES):
        j = json.loads(l); done.add((j['public_id'], j['cell'], j['repeat']))
q = queue.Queue()
for rep in range(REPEATS):
    for cell in CELLS:
        for r in recs:
            if (r.public_id, cell, rep) not in done: q.put((r, cell, rep))
LIMIT = int(sys.argv[5]) if len(sys.argv) > 5 else None
if LIMIT:
    keep = [q.get() for _ in range(min(LIMIT, q.qsize()))]; q = queue.Queue(); [q.put(k) for k in keep]
print('tasks', q.qsize(), flush=True)
def parse(text):
    t = text or ''
    try:
        a, b = t.find('{'), t.rfind('}'); v = json.loads(t[a:b + 1]).get('action', '')
        v = str(v).strip().upper()
        if v in ('KEEP', 'SUPERSEDE', 'ABSTAIN'): return v
    except Exception: pass
    return 'INVALID'
def worker():
    while True:
        try: r, cell, rep = q.get_nowait()
        except queue.Empty: return
        prompt = CELLS[cell](r); ph = hashlib.sha256(prompt.encode()).hexdigest()
        rec = dict(public_id=r.public_id, cell=cell, repeat=rep, prompt_sha256=ph, requested_model=MODEL)
        for attempt in range(4):
            t0 = time.time()
            try:
                x = requests.post(BASE + '/chat/completions', headers={'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'}, timeout=180,
                                  json=dict(model=MODEL, stream=False, temperature=0, max_tokens=512, messages=[{'role': 'user', 'content': prompt}]))
                rec['http'] = x.status_code
                if x.status_code == 200:
                    j = x.json(); txt = j['choices'][0]['message'].get('content') or ''
                    rec.update(action=parse(txt), raw=txt[:120], returned_model=j.get('model'), usage=j.get('usage'), latency_s=round(time.time() - t0, 2), attempts=attempt + 1)
                    break
            except Exception as e:
                rec['error'] = repr(e)[:120]
            time.sleep(3 * (attempt + 1))
        else:
            rec.update(action='FAILED', attempts=4)
        rec['utc'] = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat() + 'Z'
        with lock: open(RES, 'a').write(json.dumps(rec) + '\n')
ts = [threading.Thread(target=worker) for _ in range(CONC)]
[t.start() for t in ts]; [t.join() for t in ts]
print('DONE', flush=True)
