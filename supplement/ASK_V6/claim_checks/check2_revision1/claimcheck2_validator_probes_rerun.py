"""Deterministic adversarial probes of the ASK reference validator and replay binding.

Runs against an exported copy of the baseline commit f6bf66e4766d769727edf6b42c76b9977b14978a
(git archive -> /tmp/cc2_base). No model/API calls. Each probe constructs a valid transition with
apply_transition, then produces a self-consistent tampered post-state (digests and event recomputed)
and asks whether ASKInvariantValidator.validate rejects it.
Expected = what the manuscript/validator docstring implies ("Validate state, lineage, event
completeness, and action semantics"). Observed = actual behavior.
"""
from __future__ import annotations
import json, sys, hashlib, dataclasses
from dataclasses import replace
sys.path.insert(0, "/tmp/cc2_base/src")
from ask.protocol.core import (Action, StoreMode, ReplayScope, EvidenceReference, ConfigurationIdentity,
    CandidateRecord, MemoryRecord, PredecessorReference, DecisionTrace, TransitionEvent,
    apply_transition, ASKInvariantValidator, state_digest, stable_digest, evidence_set_digest, replay_transition)
from ask.protocol.adapters import ASKLMEAdapter
from ask.controller.score import ScorecardConfig, DEFAULT_SCORECARD_CONFIG
from ask.controller.features import FeatureSnapshot

H = lambda s: hashlib.sha256(s.encode()).hexdigest()
CFG = ConfigurationIdentity("cfg-A", "ask-mgp/v1", H("cfg-A"))
REFS = (EvidenceReference("turn-1", H("evidence turn 1")),)

def trace(action, refs=REFS, cfg=CFG, evidence_digest=None):
    return DecisionTrace(adapter_id="ASK-MGP", adapter_version=cfg.adapter_version,
        replay_scope=ReplayScope.COMPOSITION_AND_TRANSITION, configuration=cfg,
        evidence_references=refs, evidence_digest=evidence_digest or evidence_set_digest(refs),
        inputs={"model_proposal": action.value, "rule_proposal": action.value}, intermediates={},
        final_action=action, sufficient_fields=("model_proposal",))

def cand(rid="c1", value="new value", mtype="stable_pref"):
    return CandidateRecord(rid, mtype, value, 0.9, H("cand evidence"))

BASE_MULTI = (MemoryRecord("p1", "stable_pref", "old value", True, None, H("p1 ev")),
              MemoryRecord("u1", "episodic_fact", "unrelated fact", True, None, H("u1 ev")))
BASE_SLOT_HIST = (MemoryRecord("p0", "stable_pref", "oldest", False, None, H("p0 ev")),
                  MemoryRecord("p1", "stable_pref", "old value", True, PredecessorReference("p0"), H("p1 ev")))

def rebuild_event(ev, before, after, **changes):
    ev2 = replace(ev, before_digest=state_digest(before), after_digest=state_digest(after), **changes)
    body = {k: v for k, v in ev2.to_json_dict().items() if k not in ("event_id", "configuration", "metadata")}
    return replace(ev2, event_id=stable_digest(body))

def check(before, after, event, tr):
    try:
        ASKInvariantValidator().validate(before=before, after=after, event=event, trace=tr)
        return "ACCEPTED"
    except ValueError as exc:
        return f"REJECTED: {exc}"

results = []
def probe(pid, description, expected, before, after, event, tr):
    obs = check(before, after, event, tr)
    verdict = "AS_EXPECTED" if obs.startswith(expected) else "VALIDATOR_GAP" if expected == "REJECTED" else "UNEXPECTED_REJECTION"
    results.append(dict(probe_id=pid, description=description, expected=expected, observed=obs, verdict=verdict,
        before=[dataclasses.asdict(r) for r in before], after=[dataclasses.asdict(r) for r in after],
        event=event.to_json_dict()))

# ---- controls
t = trace(Action.SUPERSEDE)
after, ev = apply_transition(BASE_MULTI, action=Action.SUPERSEDE, store_mode=StoreMode.MULTI_RECORD, prior_record_id="p1", candidate=cand(), trace=t)
probe("C01", "Control: builder-produced SUPERSEDE (multi-record)", "ACCEPTED", BASE_MULTI, after, ev, t)
ta = trace(Action.ABSTAIN)
a_after, a_ev = apply_transition(BASE_MULTI, action=Action.ABSTAIN, store_mode=StoreMode.MULTI_RECORD, prior_record_id="p1", candidate=cand(), trace=ta)
probe("C02", "Control: builder-produced ABSTAIN", "ACCEPTED", BASE_MULTI, a_after, a_ev, ta)

# ---- SUPERSEDE tampering
def sup_variant(pid, desc, mutate, **evchanges):
    new_after = mutate(list(after))
    probe(pid, desc, "REJECTED", BASE_MULTI, tuple(new_after), rebuild_event(ev, BASE_MULTI, tuple(new_after), **evchanges), t)
sup_variant("S01", "SUPERSEDE: retained predecessor value altered while deactivated",
    lambda a: [replace(r, value="REWRITTEN HISTORY") if r.record_id == "p1" else r for r in a])
sup_variant("S02", "SUPERSEDE: retained predecessor memory_type altered",
    lambda a: [replace(r, memory_type="episodic_fact") if r.record_id == "p1" else r for r in a])
sup_variant("S03", "SUPERSEDE: retained predecessor evidence_digest altered",
    lambda a: [replace(r, evidence_digest=H("forged")) if r.record_id == "p1" else r for r in a])
sup_variant("S04", "SUPERSEDE: unrelated active record deleted",
    lambda a: [r for r in a if r.record_id != "u1"])
sup_variant("S05", "SUPERSEDE: unrelated record value mutated",
    lambda a: [replace(r, value="silently changed") if r.record_id == "u1" else r for r in a])
sup_variant("S06", "SUPERSEDE: successor value differs from candidate value",
    lambda a: [replace(r, value="not what the candidate said") if r.record_id == "c1" else r for r in a])
sup_variant("S07", "SUPERSEDE: unrelated record deactivated",
    lambda a: [replace(r, active=False) if r.record_id == "u1" else r for r in a])
sup_variant("S08", "SUPERSEDE: extra unannounced active record inserted",
    lambda a: a + [MemoryRecord("x9", "episodic_fact", "injected", True, None, None)])
sup_variant("S09", "SUPERSEDE: event predecessor_record_id field wrong (points to unrelated record)",
    lambda a: a, predecessor_record_id="u1")
sup_variant("S10", "SUPERSEDE: event candidate_record_id field wrong",
    lambda a: a, candidate_record_id="zzz")
# S11: prior already inactive before (standalone validator)
before_inactive = tuple(replace(r, active=False) if r.record_id == "p1" else r for r in BASE_MULTI)
aft11 = tuple(list(before_inactive) + [MemoryRecord("c1", "stable_pref", "new value", True, PredecessorReference("p1"), H("cand evidence"))])
probe("S11", "SUPERSEDE of a prior that was already inactive before the transition", "REJECTED", before_inactive, aft11, rebuild_event(ev, before_inactive, aft11), t)
# S12 single-slot history truncation: delete oldest inactive ancestor and rewrite p1 predecessor to None
ts = trace(Action.SUPERSEDE)
s_after, s_ev = apply_transition(BASE_SLOT_HIST, action=Action.SUPERSEDE, store_mode=StoreMode.SINGLE_SLOT_VERSIONED, prior_record_id="p1", candidate=cand(), trace=ts)
probe("C03", "Control: builder-produced single-slot SUPERSEDE with history", "ACCEPTED", BASE_SLOT_HIST, s_after, s_ev, ts)
trunc = tuple(replace(r, predecessor=None) if r.record_id == "p1" else r for r in s_after if r.record_id != "p0")
probe("S12", "SINGLE_SLOT SUPERSEDE: older inactive ancestor deleted and lineage pointer rewritten", "REJECTED", BASE_SLOT_HIST, trunc, rebuild_event(s_ev, BASE_SLOT_HIST, trunc), ts)

# ---- KEEP tampering (multi-record, no admission)
tk = trace(Action.KEEP)
k_after, k_ev = apply_transition(BASE_MULTI, action=Action.KEEP, store_mode=StoreMode.MULTI_RECORD, prior_record_id="p1", candidate=cand(), trace=tk)
probe("C04", "Control: builder-produced multi-record KEEP without admission", "ACCEPTED", BASE_MULTI, k_after, k_ev, tk)
def keep_variant(pid, desc, mutate, prior="p1", mode=StoreMode.MULTI_RECORD, **evchanges):
    na = tuple(mutate(list(k_after)))
    e = rebuild_event(k_ev, BASE_MULTI, na, prior_record_id=prior, store_mode=mode, **evchanges)
    probe(pid, desc, "REJECTED", BASE_MULTI, na, e, tk)
keep_variant("K01", "MULTI KEEP (keep_admitted_candidate=False): candidate silently inserted",
    lambda a: a + [MemoryRecord("c1", "stable_pref", "new value", True, None, H("cand evidence"))])
keep_variant("K02", "MULTI KEEP: unrelated record deleted", lambda a: [r for r in a if r.record_id != "u1"])
keep_variant("K03", "MULTI KEEP: unrelated record value mutated", lambda a: [replace(r, value="changed") if r.record_id == "u1" else r for r in a])
keep_variant("K04", "MULTI KEEP with prior_record_id=None: compared prior rewritten", lambda a: [replace(r, value="changed") if r.record_id == "p1" else r for r in a], prior=None)
keep_variant("K05", "TEMPORAL_EVENT KEEP: arbitrary mutation of unrelated record", lambda a: [replace(r, value="changed") if r.record_id == "u1" else r for r in a], mode=StoreMode.TEMPORAL_EVENT)

# ---- identity binding
bad_id = replace(ev, event_id=H("arbitrary"))
probe("I01", "Event id not equal to digest of event body", "REJECTED", BASE_MULTI, after, bad_id, t)
t_bad = trace(Action.SUPERSEDE, evidence_digest=H("not the reference-set digest"))
ev_bad = replace(ev, evidence_digest=t_bad.evidence_digest)
probe("I02", "Trace evidence_digest does not equal digest of its evidence_references", "REJECTED", BASE_MULTI, after, rebuild_event(ev_bad, BASE_MULTI, after), t_bad)

# ---- replay / configuration binding (LME adapter)
replay_results = []
lme_cfg = ConfigurationIdentity("lme", "ask-lme-scorecard/v1", "0" * 64)
adA = ASKLMEAdapter(lme_cfg)
feat = FeatureSnapshot(c=0.95, e=0.85, f=0.0, r=-1.0, rho=0.6)
act, tr = adA.decide(features=feat, memory_type="episodic_fact", evidence_references=REFS, prior_record_id="p1", candidate_record_id="c1")
replay_results.append(dict(probe_id="R01", description="ConfigurationIdentity sha256='0'*64 (not a digest of any config) accepted", observed="ACCEPTED (object constructed)", verdict="CONFIG_DIGEST_NOT_BOUND"))
import copy
sup = dict(DEFAULT_SCORECARD_CONFIG.theta_sup); ab = dict(DEFAULT_SCORECARD_CONFIG.theta_abs)
cfgB = ScorecardConfig(weights=DEFAULT_SCORECARD_CONFIG.weights, theta_sup={k: v + 0.01 for k, v in sup.items()}, theta_abs={k: v + 0.01 for k, v in ab.items()})
adB = ASKLMEAdapter(lme_cfg, config=cfgB)
try:
    out = adB.replay(tr); obs = f"ACCEPTED replay -> {out.value} although thresholds differ from logged intermediates {tr.intermediates['theta_sup']},{tr.intermediates['theta_abs']}"
except ValueError as exc:
    obs = f"REJECTED: {exc}"
replay_results.append(dict(probe_id="R02", description="Replay under adapter config with all thresholds shifted +0.01 (action unchanged)", observed=obs,
    verdict="THRESHOLDS_NOT_BOUND" if obs.startswith("ACCEPTED") else "BOUND"))
cfgC = ScorecardConfig(weights=DEFAULT_SCORECARD_CONFIG.weights, theta_sup={k: v + 5 for k, v in sup.items()}, theta_abs={k: v for k, v in ab.items()})
try:
    out = ASKLMEAdapter(lme_cfg, config=cfgC).replay(tr); obs = f"ACCEPTED -> {out.value}"
except ValueError as exc:
    obs = f"REJECTED: {exc}"
replay_results.append(dict(probe_id="R03", description="Replay under config whose theta_sup shift flips the action", observed=obs,
    verdict="DETECTED_ONLY_VIA_ACTION_MISMATCH"))
missing = [f for f in tr.sufficient_fields if f not in tr.inputs and f not in tr.intermediates]
replay_results.append(dict(probe_id="R04", description="Declared sufficient_fields absent as keys in trace inputs/intermediates", observed=json.dumps(missing), verdict="DECLARED_FIELDS_NOT_PRESENT" if missing else "OK"))
replay_results.append(dict(probe_id="R05", description="Logged trace action / theta values", observed=json.dumps({"action": act.value, "theta_sup": tr.intermediates["theta_sup"], "theta_abs": tr.intermediates["theta_abs"]}), verdict="INFO"))

# ---- durability: does the reference store persist anything?
import inspect
from ask.protocol import core as coremod
src = inspect.getsource(coremod)
dur = dict(probe_id="D01", description="Reference module performs file/database I/O for events",
    observed="open()/write/sqlite/fsync present" if any(tok in src for tok in ("open(", "sqlite3", "fsync", ".write(")) else "NO file or database I/O in ask.protocol.core",
    verdict="EVENT_IS_IN_MEMORY_OBJECT_ONLY")
out = dict(baseline="f6bf66e4766d769727edf6b42c76b9977b14978a", python=sys.version.split()[0],
    validator_probes=results, replay_probes=replay_results, durability_probes=[dur],
    summary={"validator_gaps": [r["probe_id"] for r in results if r["verdict"] == "VALIDATOR_GAP"],
             "as_expected": [r["probe_id"] for r in results if r["verdict"] == "AS_EXPECTED"]})
json.dump(out, open(sys.argv[1], "w"), indent=2, default=str)
for r in results: print(r["probe_id"], r["verdict"], "|", r["observed"][:90])
for r in replay_results + [dur]: print(r["probe_id"], r["verdict"], "|", r["observed"][:150])
