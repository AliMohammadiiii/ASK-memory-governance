"""Re-run of the phase 6 tampering probes against an exported ASK tree (baseline or patched).

Usage: python run_probes_patched.py --tree /tmp/p17_val --out PROBE_RESULTS_PATCHED.json [--legacy-event-id]

The probe definitions follow phase6_validator/adversarial_validator_probes.py (S01-S12, K01-K05,
I01, I02, controls C01-C04, replay probes R01-R05). Differences from the phase 6 script:

1. Tampered events are re-identified with the event-id formula that apply_transition uses
   (configuration_id and configuration_sha256 included). The phase 6 helper omitted both
   fields, so its recomputed ids differ from builder ids. A validator that recomputes event ids
   would then reject every phase 6 probe for that reason alone. --legacy-event-id reproduces
   the phase 6 formula so the effect can be measured.
2. The validator is called with the candidate and the frozen configuration mapping when the
   tree's validate() accepts those arguments (patched tree). On the baseline tree it is called
   as in phase 6.
3. Positive controls C05-C08 are added (KEEP with admission, single-slot KEEP, SUPERSEDE in
   temporal_event mode, replay round trip).
No model, network or paid calls. Nothing is written inside the ASK tree.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import inspect
import json
import sys
from dataclasses import replace

ap = argparse.ArgumentParser()
ap.add_argument("--tree", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--legacy-event-id", action="store_true")
args = ap.parse_args()
sys.path.insert(0, f"{args.tree}/src")

from ask.controller.features import FeatureSnapshot  # noqa: E402
from ask.controller.score import DEFAULT_SCORECARD_CONFIG, ScorecardConfig  # noqa: E402
from ask.protocol.adapters import ASKLMEAdapter  # noqa: E402
from ask.protocol.core import (  # noqa: E402
    ASKInvariantValidator,
    Action,
    CandidateRecord,
    ConfigurationIdentity,
    DecisionTrace,
    EvidenceReference,
    MemoryRecord,
    PredecessorReference,
    ReplayScope,
    StoreMode,
    apply_transition,
    evidence_set_digest,
    replay_transition,
    stable_digest,
    state_digest,
)

H = lambda s: hashlib.sha256(s.encode()).hexdigest()  # noqa: E731
PATCHED_API = "candidate" in inspect.signature(ASKInvariantValidator.validate).parameters


def local_config_digest(mapping) -> str:
    payload = json.dumps(mapping, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


CFG_MAPPING = {"adapter_version": "ask-mgp/v1", "parameters": {"example": 1}}
CFG = ConfigurationIdentity("cfg-A", "ask-mgp/v1", local_config_digest(CFG_MAPPING))
REFS = (EvidenceReference("turn-1", H("evidence turn 1")),)


def true_event_id(ev) -> str:
    body = {
        "action": ev.action.value, "store_mode": ev.store_mode.value,
        "prior_record_id": ev.prior_record_id, "candidate_record_id": ev.candidate_record_id,
        "resulting_record_id": ev.resulting_record_id, "predecessor_record_id": ev.predecessor_record_id,
        "configuration_id": ev.configuration.configuration_id, "configuration_sha256": ev.configuration.sha256,
        "evidence_digest": ev.evidence_digest, "before_digest": ev.before_digest,
        "after_digest": ev.after_digest, "keep_admitted_candidate": ev.keep_admitted_candidate,
    }
    return stable_digest(body)


def legacy_event_id(ev) -> str:
    body = {k: v for k, v in ev.to_json_dict().items() if k not in ("event_id", "configuration", "metadata")}
    return stable_digest(body)


EVENT_ID = legacy_event_id if args.legacy_event_id else true_event_id


def trace(action, refs=REFS, cfg=CFG, evidence_digest=None):
    return DecisionTrace(adapter_id="ASK-MGP", adapter_version=cfg.adapter_version,
        replay_scope=ReplayScope.COMPOSITION_AND_TRANSITION, configuration=cfg,
        evidence_references=refs, evidence_digest=evidence_digest or evidence_set_digest(refs),
        inputs={"model_proposal": action.value, "rule_proposal": action.value}, intermediates={},
        final_action=action, sufficient_fields=("model_proposal",))


def cand(rid="c1", value="new value", mtype="stable_pref"):
    return CandidateRecord(rid, mtype, value, 0.9, H("cand evidence"))


CAND = cand()
BASE_MULTI = (MemoryRecord("p1", "stable_pref", "old value", True, None, H("p1 ev")),
              MemoryRecord("u1", "episodic_fact", "unrelated fact", True, None, H("u1 ev")))
BASE_SLOT_HIST = (MemoryRecord("p0", "stable_pref", "oldest", False, None, H("p0 ev")),
                  MemoryRecord("p1", "stable_pref", "old value", True, PredecessorReference("p0"), H("p1 ev")))


def rebuild_event(ev, before, after, **changes):
    ev2 = replace(ev, before_digest=state_digest(before), after_digest=state_digest(after), **changes)
    return replace(ev2, event_id=EVENT_ID(ev2))


def check(before, after, event, tr, candidate=CAND):
    kwargs = {}
    if PATCHED_API:
        kwargs = {"candidate": candidate, "configuration": CFG_MAPPING}
    try:
        rep = ASKInvariantValidator().validate(before=before, after=after, event=event, trace=tr, **kwargs)
        return {"result": "ACCEPTED", "codes": [], "message": "",
                "unverified": list(getattr(rep, "unverified", ()) or ())}
    except ValueError as exc:
        return {"result": "REJECTED", "codes": list(getattr(exc, "codes", ())), "message": str(exc),
                "unverified": []}


results = []


def probe(pid, description, expected, before, after, event, tr, candidate=CAND):
    obs = check(before, after, event, tr, candidate)
    ok = obs["result"] == expected
    verdict = "AS_EXPECTED" if ok else ("VALIDATOR_GAP" if expected == "REJECTED" else "UNEXPECTED_REJECTION")
    results.append(dict(probe_id=pid, description=description, expected=expected, observed=obs["result"],
        reason_codes=obs["codes"], message=obs["message"], verdict=verdict,
        before=[dataclasses.asdict(r) for r in before], after=[dataclasses.asdict(r) for r in after],
        event=event.to_json_dict()))


# controls (builder produced)
t = trace(Action.SUPERSEDE)
after, ev = apply_transition(BASE_MULTI, action=Action.SUPERSEDE, store_mode=StoreMode.MULTI_RECORD,
                             prior_record_id="p1", candidate=CAND, trace=t)
assert ev.event_id == true_event_id(ev), "harness event-id formula differs from builder"
probe("C01", "Control: builder-produced SUPERSEDE (multi-record)", "ACCEPTED", BASE_MULTI, after, ev, t)
ta = trace(Action.ABSTAIN)
a_after, a_ev = apply_transition(BASE_MULTI, action=Action.ABSTAIN, store_mode=StoreMode.MULTI_RECORD,
                                 prior_record_id="p1", candidate=CAND, trace=ta)
probe("C02", "Control: builder-produced ABSTAIN", "ACCEPTED", BASE_MULTI, a_after, a_ev, ta)


def sup_variant(pid, desc, mutate, **evchanges):
    new_after = tuple(mutate(list(after)))
    probe(pid, desc, "REJECTED", BASE_MULTI, new_after, rebuild_event(ev, BASE_MULTI, new_after, **evchanges), t)


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
before_inactive = tuple(replace(r, active=False) if r.record_id == "p1" else r for r in BASE_MULTI)
aft11 = tuple(list(before_inactive) + [MemoryRecord("c1", "stable_pref", "new value", True,
                                                    PredecessorReference("p1"), H("cand evidence"))])
probe("S11", "SUPERSEDE of a prior that was already inactive before the transition", "REJECTED",
      before_inactive, aft11, rebuild_event(ev, before_inactive, aft11), t)
ts = trace(Action.SUPERSEDE)
s_after, s_ev = apply_transition(BASE_SLOT_HIST, action=Action.SUPERSEDE, store_mode=StoreMode.SINGLE_SLOT_VERSIONED,
                                 prior_record_id="p1", candidate=CAND, trace=ts)
probe("C03", "Control: builder-produced single-slot SUPERSEDE with history", "ACCEPTED", BASE_SLOT_HIST, s_after, s_ev, ts)
trunc = tuple(replace(r, predecessor=None) if r.record_id == "p1" else r for r in s_after if r.record_id != "p0")
probe("S12", "SINGLE_SLOT SUPERSEDE: older inactive ancestor deleted and lineage pointer rewritten", "REJECTED",
      BASE_SLOT_HIST, trunc, rebuild_event(s_ev, BASE_SLOT_HIST, trunc), ts)

tk = trace(Action.KEEP)
k_after, k_ev = apply_transition(BASE_MULTI, action=Action.KEEP, store_mode=StoreMode.MULTI_RECORD,
                                 prior_record_id="p1", candidate=CAND, trace=tk)
probe("C04", "Control: builder-produced multi-record KEEP without admission", "ACCEPTED", BASE_MULTI, k_after, k_ev, tk)


def keep_variant(pid, desc, mutate, prior="p1", mode=StoreMode.MULTI_RECORD, **evchanges):
    na = tuple(mutate(list(k_after)))
    e = rebuild_event(k_ev, BASE_MULTI, na, prior_record_id=prior, store_mode=mode, **evchanges)
    probe(pid, desc, "REJECTED", BASE_MULTI, na, e, tk)


keep_variant("K01", "MULTI KEEP (keep_admitted_candidate=False): candidate silently inserted",
    lambda a: a + [MemoryRecord("c1", "stable_pref", "new value", True, None, H("cand evidence"))])
keep_variant("K02", "MULTI KEEP: unrelated record deleted", lambda a: [r for r in a if r.record_id != "u1"])
keep_variant("K03", "MULTI KEEP: unrelated record value mutated",
    lambda a: [replace(r, value="changed") if r.record_id == "u1" else r for r in a])
keep_variant("K04", "MULTI KEEP with prior_record_id=None: compared prior rewritten",
    lambda a: [replace(r, value="changed") if r.record_id == "p1" else r for r in a], prior=None)
keep_variant("K05", "TEMPORAL_EVENT KEEP: arbitrary mutation of unrelated record",
    lambda a: [replace(r, value="changed") if r.record_id == "u1" else r for r in a], mode=StoreMode.TEMPORAL_EVENT)

bad_id = replace(ev, event_id=H("arbitrary"))
probe("I01", "Event id not equal to digest of event body", "REJECTED", BASE_MULTI, after, bad_id, t)
t_bad = trace(Action.SUPERSEDE, evidence_digest=H("not the reference-set digest"))
ev_bad = replace(ev, evidence_digest=t_bad.evidence_digest)
probe("I02", "Trace evidence_digest does not equal digest of its evidence_references", "REJECTED",
      BASE_MULTI, after, rebuild_event(ev_bad, BASE_MULTI, after), t_bad)

# additional positive controls
tka = trace(Action.KEEP)
ka_after, ka_ev = apply_transition(BASE_MULTI, action=Action.KEEP, store_mode=StoreMode.MULTI_RECORD,
                                   prior_record_id="p1", candidate=CAND, trace=tka, admit_candidate_on_keep=True)
probe("C05", "Control: builder-produced multi-record KEEP with candidate admission", "ACCEPTED", BASE_MULTI, ka_after, ka_ev, tka)
ks_after, ks_ev = apply_transition(BASE_SLOT_HIST, action=Action.KEEP, store_mode=StoreMode.SINGLE_SLOT_VERSIONED,
                                   prior_record_id="p1", candidate=CAND, trace=tka)
probe("C06", "Control: builder-produced single-slot KEEP with history", "ACCEPTED", BASE_SLOT_HIST, ks_after, ks_ev, tka)
tt_after, tt_ev = apply_transition(BASE_MULTI, action=Action.SUPERSEDE, store_mode=StoreMode.TEMPORAL_EVENT,
                                   prior_record_id="p1", candidate=CAND, trace=t)
probe("C07", "Control: builder-produced SUPERSEDE in temporal_event mode (multi-record rules only)", "ACCEPTED",
      BASE_MULTI, tt_after, tt_ev, t)
rp_after, rp_ev = replay_transition(BASE_MULTI, event=ev, candidate=CAND, trace=t)
probe("C08", "Control: replay_transition reproduces the preserved SUPERSEDE event", "ACCEPTED", BASE_MULTI, rp_after, rp_ev, t)

# ---- configuration identity / replay probes
replay_results = []
lme_zero = ConfigurationIdentity("lme", "ask-lme-scorecard/v1", "0" * 64)
feat = FeatureSnapshot(c=0.95, e=0.85, f=0.0, r=-1.0, rho=0.6)
sup = dict(DEFAULT_SCORECARD_CONFIG.theta_sup)
ab = dict(DEFAULT_SCORECARD_CONFIG.theta_abs)
cfgB = ScorecardConfig(weights=DEFAULT_SCORECARD_CONFIG.weights,
                       theta_sup={k: v + 0.01 for k, v in sup.items()}, theta_abs={k: v + 0.01 for k, v in ab.items()})
cfgC = ScorecardConfig(weights=DEFAULT_SCORECARD_CONFIG.weights,
                       theta_sup={k: v + 5 for k, v in sup.items()}, theta_abs=dict(ab))


def attempt(fn):
    try:
        out = fn()
        return {"result": "ACCEPTED", "codes": [], "message": f"{out}"}
    except ValueError as exc:
        return {"result": "REJECTED", "codes": list(getattr(exc, "codes", ())), "message": str(exc)}


ad_zero = ASKLMEAdapter(lme_zero)
if hasattr(ad_zero, "verify_configuration_identity"):
    r01 = attempt(ad_zero.verify_configuration_identity)
    r01["step"] = "ASKLMEAdapter(identity sha256=0*64).verify_configuration_identity()"
    # same identity through the validator
    act, tr0 = ad_zero.decide(features=feat, memory_type="episodic_fact", evidence_references=REFS,
                              prior_record_id="p1", candidate_record_id="c1")
    tz = replace(t, configuration=lme_zero, adapter_version="ask-lme-scorecard/v1")
    after_z, ev_z = apply_transition(BASE_MULTI, action=Action.SUPERSEDE, store_mode=StoreMode.MULTI_RECORD,
                                     prior_record_id="p1", candidate=CAND, trace=tz)
    r01v = attempt(lambda: ASKInvariantValidator().validate(
        before=BASE_MULTI, after=after_z, event=ev_z, trace=tz, candidate=CAND,
        configuration=ad_zero.frozen_configuration()))
    r01v["step"] = "validator.validate(configuration=frozen mapping) on a transition carrying the zero identity"
    replay_results.append(dict(probe_id="R01", description="ConfigurationIdentity sha256='0'*64 verified against its frozen configuration",
                               expected="REJECTED", **r01, validator_path=r01v))
else:
    act, tr0 = ad_zero.decide(features=feat, memory_type="episodic_fact", evidence_references=REFS,
                              prior_record_id="p1", candidate_record_id="c1")
    replay_results.append(dict(probe_id="R01", description="ConfigurationIdentity sha256='0'*64 verified against its frozen configuration",
                               expected="REJECTED", result="ACCEPTED", codes=[],
                               message="object constructed; no verification step exists in this tree", step="constructor"))

# R02: thresholds shifted by +0.01, same identity object, action unchanged
act_a, tr_a = ad_zero.decide(features=feat, memory_type="episodic_fact", evidence_references=REFS,
                             prior_record_id="p1", candidate_record_id="c1")
adB = ASKLMEAdapter(lme_zero, config=cfgB)
r02_default = attempt(lambda: adB.replay(tr_a).value)
if PATCHED_API:
    bound_default = ASKLMEAdapter.bound("lme")
    act_b, tr_b = bound_default.decide(features=feat, memory_type="episodic_fact", evidence_references=REFS,
                                       prior_record_id="p1", candidate_record_id="c1")
    adB_same_identity = ASKLMEAdapter(bound_default.configuration, config=cfgB)
    r02_strict = attempt(lambda: adB_same_identity.replay(tr_b, strict=True).value)
    adB_own_identity = ASKLMEAdapter.bound("lme", config=cfgB)
    r02_strict_own = attempt(lambda: adB_own_identity.replay(tr_b, strict=True).value)
    r02_control = attempt(lambda: bound_default.replay(tr_b, strict=True).value)
    replay_results.append(dict(probe_id="R02", description="Replay under thresholds shifted +0.01 (action unchanged)",
        expected="REJECTED", result=r02_strict["result"], codes=r02_strict["codes"], message=r02_strict["message"],
        step="strict replay, shifted config keeps the identity of the default config",
        default_replay_unchanged_behavior=r02_default,
        strict_replay_shifted_config_with_its_own_identity=r02_strict_own,
        strict_replay_unshifted_control=r02_control))
else:
    replay_results.append(dict(probe_id="R02", description="Replay under thresholds shifted +0.01 (action unchanged)",
        expected="REJECTED", result=r02_default["result"], codes=[], message=r02_default["message"], step="replay"))

# R03: shift that flips the action (detected by action mismatch in both trees)
act_c, tr_c = ad_zero.decide(features=feat, memory_type="episodic_fact", evidence_references=REFS,
                             prior_record_id="p1", candidate_record_id="c1")
r03 = attempt(lambda: ASKLMEAdapter(lme_zero, config=cfgC).replay(tr_c).value)
replay_results.append(dict(probe_id="R03", description="Replay under a configuration whose theta_sup shift flips the action",
                           expected="REJECTED", result=r03["result"], codes=r03["codes"], message=r03["message"], step="replay"))
missing = [f for f in tr_a.sufficient_fields if f not in tr_a.inputs and f not in tr_a.intermediates]
replay_results.append(dict(probe_id="R04", description="Declared sufficient_fields absent as keys in trace inputs/intermediates",
                           expected="NOT_ADDRESSED_BY_PATCH", result="UNCHANGED", codes=[], message=json.dumps(missing), step="inspection"))

summary = {
    "tree": args.tree, "patched_api_detected": PATCHED_API, "legacy_event_id_formula": args.legacy_event_id,
    "python": sys.version.split()[0],
    "tamper_total": sum(1 for r in results if r["expected"] == "REJECTED"),
    "tamper_rejected": sum(1 for r in results if r["expected"] == "REJECTED" and r["observed"] == "REJECTED"),
    "tamper_accepted": [r["probe_id"] for r in results if r["expected"] == "REJECTED" and r["observed"] == "ACCEPTED"],
    "controls_total": sum(1 for r in results if r["expected"] == "ACCEPTED"),
    "controls_accepted": sum(1 for r in results if r["expected"] == "ACCEPTED" and r["observed"] == "ACCEPTED"),
    "unexpected_control_rejections": [r["probe_id"] for r in results if r["verdict"] == "UNEXPECTED_REJECTION"],
}
out = dict(summary=summary, validator_probes=results, configuration_and_replay_probes=replay_results)
json.dump(out, open(args.out, "w"), indent=2, default=str)
print(json.dumps(summary))
for r in results:
    print(r["probe_id"], r["expected"], "->", r["observed"], r["reason_codes"])
for r in replay_results:
    print(r["probe_id"], r["expected"], "->", r["result"], r["codes"])
