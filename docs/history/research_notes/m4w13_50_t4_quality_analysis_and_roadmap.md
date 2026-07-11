# m4w13 50-question T4 quality run — analysis & improvement roadmap

Run: `runs/m4w13_50_t4_quality`, controller, qwen3.5:9b answerer, llama3.2:3b
extractor, phi3.5:3.8b classifier/judge, MiniLM embedder, A10G, 3 shards.
Overall **50.0% (25/50)**. Abstention 7/7, single-session-assistant 4/5,
knowledge-update 7/12, multi-session 5/12, single-session-user 4/6,
single-session-preference 2/3, **temporal-reasoning 3/12 (weakest)**.

## The decisive measurement
- **Gold-session retrieval recall = 49/50 (98%).** The supporting session is
  almost always in the answer prompt.
- **24/50 are wrong even though the gold session WAS retrieved.**
- 1 question only failed because retrieval missed the gold session.

So retrieval-of-session is **solved**. The bottleneck is now downstream:
answer-step reasoning and the granularity of what we store/retrieve. Optimizing
retrieval recall further is wasted effort; the gains are in the 24 "evidence
present, answer wrong" cases.

Supporting stats:
- Extraction emits **exactly 1 item per turn** for 1523/1598 turns. Near-constant
  → the extractor is writing one paraphrase per turn, not atomic facts. Exact
  numbers/dates/units can be blurred or dropped.
- Relation labels are now healthy (support 46 / contradict 7 / supersede 2 /
  unclear 30 over 85 calls) — the similarity gate works and cut relation calls
  ~3×. Supersede fired on 7 questions (4 correct).
- Latency: median 123 s/question, max 238 s.

---

## Problems, ranked by expected payoff. (★ = needs your ideation/research, not just code.)

### P1 ★ Answer-step reasoning is the real ceiling (≈24 questions)
The answerer has the right session but: picks the wrong turn, miscomputes
arithmetic ("21" when gold is "14 days between"), mis-orders events, or hedges to
"Unknown". This is where most points are.
Ideas to explore:
- **Two-step answer**: let the answerer reason (chain-of-thought) over the
  retrieved dated memories, then a second cheap call extracts the final short
  span. Today it must do retrieve→reason→format in one shot.
- **Question decomposition** for multi-hop ("between X and Y", "order of A,B,C"):
  rewrite into sub-questions, retrieve per sub-question, then combine.
- **Deterministic compute for counting/duration/order** (see P4): don't ask the
  LLM to do date arithmetic; have it emit the relevant dated events and compute
  the delta in Python.
- **Stronger answerer** (thesis profile llama3:8b, or a 14B) — measure the gap.

### P2 ★ Fact granularity in extraction (1 vague item/turn)
A turn like "I spent $2,300 on 12 cameras… about $192 each" should yield several
atomic facts with the exact figures; right now it yields one paraphrase. For
counting/total/difference questions the precise number is what matters.
Ideas:
- Allow 0..N atomic facts per turn; reward verbatim preservation of
  numbers/dates/units/proper nouns.
- Store the **raw source turn** alongside the abstracted fact, and retrieve/show
  both (the orchestrator already keeps `source_turn`; surface it at answer time).
- Type-aware extraction: store events as structured `(event, date, value)` slots,
  not free text — this also feeds P4.

### P3 ★ Turn-level retrieval precision (session recall 98%, turn precision unknown)
The right session is retrieved, but the *exact turn* may not be in the answer
top-k, or it's buried among assistant-context chunks.
Ideas:
- **Hybrid retrieval** = dense (MiniLM) + lexical (BM25). Names, dollar amounts,
  model numbers ("Fitbit Charge 3") need exact-token matching that dense misses.
- **Rerank** the top-k with a cross-encoder before the answer prompt.
- **Expand-the-gold-session**: once a session ranks high, include all its
  user-fact turns (you already have a neighbor window; make it session-aware).
- Tune the assistant-context chunking so it helps assistant questions without
  crowding out short user-fact turns.

### P4 ★ Temporal reasoning needs structure + an anchor date (3/12 today)
Two failure modes:
- **Order / duration between two events**: dates are in the prompt but a 9B model
  mis-arithmetic. Solve with a deterministic temporal step (parse the two dated
  memories, compute the delta in code).
- **"How many months/weeks ago…"**: needs the **question reference date**, which
  the cleaned dataset has (`question_date`) but the current slice dropped during
  slice-building. Fix end-to-end: capture it in the loader → rebuild the slice →
  render "Today's date is …" in the answer prompt. Without the anchor these are
  unanswerable in principle.

### P5 ★ The controller's contribution is under-demonstrated
Supersede fired only 7/50; the thesis story (Keep/Supersede/Abstain governance)
is barely exercised on this slice, so 50% absolute under-sells it.
Ideas:
- Report the **controller vs baselines delta** on the SAME slice (run b1 no-memory,
  b2 flat-vector, b3 recency, b4 naive-overwrite, controller). The headline is
  "+X points over naive-overwrite", not the absolute number.
- Use **MGP-6** (your supersession-designed benchmark) to show the mechanism where
  it matters; LongMemEval-S has few real contradictions.
- Build a small **knowledge-update-heavy** eval slice to stress Supersede.

### P6 Model tier caps extraction/relation quality
llama3.2:3b / phi3.5:3.8b are weak at slot/value reasoning. The `thesis` profile
(llama3:8b) is the citable one.
Ideas: run the final number on `--model-profile thesis`; few-shot the relation
prompt; or distil a small relation classifier from a strong-teacher dev set.

### P7 Judge fragility (methodology risk, already flagged)
Same-tier local judge (phi3.5) with token-guards. Fine for development, not for
the final claim.
Ideas: re-grade the final run with phi4:14b or an API judge; report agreement.

### P8 Latency / efficiency (123 s median)
Mostly the answerer + 32 extractions/question. The relation gate already helped.
Ideas: cache turn embeddings (the per-candidate FlatVectorStore is rebuilt every
time); batch extraction calls; skip extraction on turns the prefilter didn't pick
(already done) and consider a cheaper extractor.

---

## Suggested order of attack (highest leverage first)
1. **P4 deterministic temporal + question_date** — concrete, bounded, directly
   lifts the weakest competency.
2. **P1 two-step answer / decomposition** — targets the 24 "present-but-wrong".
3. **P2 atomic-fact extraction** — feeds P1 and P4.
4. **P5 baselines delta + MGP-6** — reframes the thesis claim so 50% isn't the
   headline.
5. **P3 hybrid retrieval** — incremental once the above land.

Everything up to here kept retrieval-of-session at ~98%; do not spend more on
recall. The points are downstream.
