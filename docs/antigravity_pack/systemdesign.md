# systemdesign.md — Algorithms, rules, prompts, schemas

## 1. Weekly metric
```python
df["route"] = df["origin"].str.strip() + "-" + df["destination"].str.strip()
df["week_of"] = (df["shipment_date"] - pd.to_timedelta(df["shipment_date"].dt.weekday, unit="D")).dt.normalize()
df["tk"] = df["quantity_tonnes"] * df["distance_km"]
w = df.groupby(["route","route_type","week_of"], as_index=False).agg(
        cost=("freight_cost_inr","sum"), tonne_km=("tk","sum"), n=("tk","size"))
w["c"] = w["cost"] / w["tonne_km"]          # ratio of sums
```
Assert: all `week_of` are Mondays; 7 routes × 104 weeks = 728 rows.

## 2. Baselines
```python
w = w.sort_values(["route","week_of"])
w["own_avg"]  = w.groupby("route")["c"].transform(lambda s: s.shift(1).rolling(8, min_periods=1).mean())
w["n_prior"]  = w.groupby("route").cumcount().clip(upper=8)
grp = w.groupby(["route_type","week_of"])["c"].agg(["sum","count"]).rename(columns={"sum":"s","count":"k"})
w = w.join(grp, on=["route_type","week_of"])
w["peer_avg"] = (w["s"] - w["c"]) / (w["k"] - 1)   # exclude self; k>=2 always in this data
w["vs_own_pct"]  = (w["c"]/w["own_avg"]  - 1) * 100
w["vs_peer_pct"] = (w["c"]/w["peer_avg"] - 1) * 100
w = w[w["n_prior"] > 0]                              # first week has no history → not evaluable
```
`shift(1)` is what guarantees **no look-ahead**. Guard: if `k == 1` set peer NaN and never flag on peer.
Peers use the **simple mean of the other routes' weekly `c`** (verified against the sample).

## 3. Candidate rule (config.py)
```python
FLAG_OWN_PCT        = 8.0    # strong own-history rise
FLAG_OWN_SOFT_PCT   = 5.0    # mild own rise ...
FLAG_PEER_PCT       = 20.0   # ... that is also a big peer gap
candidate = (vs_own > 0) & ((vs_own >= FLAG_OWN_PCT) | ((vs_own >= FLAG_OWN_SOFT_PCT) & (vs_peer >= FLAG_PEER_PCT)))
```
Expected: exactly **19** candidates (context.md §7). Apply thresholds to **unrounded** values.

## 4. Notes structuring
`data/notes_structured.json` is **hand-authored** (see context.md §5) — fields: `id, scope ("ALL"|route|"NONE"), effect ("raises"|"none"|"lowers"|"normalizes"), start, end (nullable), mag_min, mag_max (percent, nullable), rationale`.
Optional LLM cross-check (`python -m stripewatch check-notes`): ask the LLM (temp 0, JSON mode) to extract the same fields from each note's raw text; print a diff vs the hand file. **Disagreements are reported, never auto-applied.** This shows AI use without trusting AI.

## 5. Retrieval
- Documents: the 10 raw `note` texts with metadata `{id, applies_to, date}`.
- Query built from facts only: `f"{route} freight cost increase week of {week_of} reason"` (for All-Routes-aware retrieval also embed a second query `"nationwide freight cost increase {month} {year}"`; merge, dedupe by best score).
- k = 3, cosine, ties → lower `note_id`. Persist every retrieval to `output/retrieval_log.jsonl`:
  `{"route":..,"week_of":..,"query":..,"hits":[{"id":"N001","score":0.61,"accepted":true,"checks":{...}}]}`
- Retrieval is NOT filtered by date/route — it ranks. Validation filters. (This is intentional and is the demo's key point: distractors like N006/N008/N009 rank high but are rejected.)

## 6. Verdict statuses
`justified` → CSV `flagged = "No (justified)"`, `matched_note_id = <id>`.
`unexplained` → CSV `flagged = "Yes"`, `matched_note_id = ""`.
There is no third status in the CSV. Near-misses (a note that is close but fails a check) are described in `reason` **without** being put in `matched_note_id`.

## 7. THE VALIDATOR — trust core (all must pass; implemented as pure function, 100% unit-tested)
```python
def validate(row, note) -> Verdict:
    week_start, week_end = row.week_of, row.week_of + 6 days
    checks = {
      "effect_is_cost_rise": note.effect == "raises",
      "route_in_scope":      note.scope == "ALL" or note.scope == row.route,
      "window_overlaps":     note.start <= week_end and (note.end is None or note.end >= week_start),
      "magnitude_ok":        note.mag_max is None or row.vs_own_pct <= note.mag_max + MAG_TOL_PP,   # MAG_TOL_PP = 3.0
      "not_peer_outlier_for_universal": not (note.scope == "ALL" and row.vs_peer_pct >= FLAG_PEER_PCT),
    }
    justified = all(checks.values())
```
- N003 window: `start=2025-05-05`, `end=2025-06-29` (8 weeks — Assumption A3). Others per context.md §5.
- Why `not_peer_outlier_for_universal`: a nationwide shock hits peers too, so it cannot explain a route being +20% *above* its peers.
- Why `magnitude_ok`: the note says ≈5–7%; a +30% rise is not explained by it.
- Selection: among accepted notes prefer route-specific over ALL; then earliest `note_id`. A row can cite exactly one note.
- `why_not` = first failing check in the fixed order above, in plain words (e.g. "N001 covers Chennai-Bangalore only until 2025-03-08; this week starts 2025-03-10").

## 8. Evidence packet (input to explainer; the ONLY facts the LLM may use)
```json
{
 "route":"Chennai-Bangalore","week_of":"2025-03-03","c":3.48,
 "vs_own_pct":22.8,"vs_peer_pct":32.0,"verdict":"justified",
 "note":{"id":"N001","text":"Heavy flooding ... Roads were passable again by Mar 9.","start":"2025-02-24","end":"2025-03-08"},
 "near_misses":[{"id":"N009","why_not":"says route returned to normal; not a reason for a rise"}]
}
```
For unexplained rows: `"note": null`, `near_misses` list up to 2.

## 9. Explainer
**Template (default, deterministic, also fallback):**
- justified: `Matches note {id} dated {date}: {note_gist}. The cost rise ({vs_own} vs own history) has a clear explanation for the window {start} to {end}.`
- unexplained: `No matching note found for this route or date range. {near_miss_sentence}Cost rise looks unexplained and worth a human review.`
`note_gist` comes from `notes_structured.json["rationale"]` (hand-written, ≤15 words) — never invented.

**LLM prompt (temperature 0, max 90 output tokens):**
```
You are rewriting a verdict for a freight-cost analyst. Use ONLY the JSON below. Do not add causes, numbers, dates or note ids that are not in it.
Start with "No (justified):" or "Flagged:". If justified, name the note id and its dates. If flagged, say no supporting note was found and mention near_misses only if present.
Max 45 words, plain English, no markdown.
JSON: {packet}
```

## 10. Grounding checker (`ground.py`) — runs on EVERY explanation (LLM or template)
Pass only if ALL true:
1. If justified: text contains `matched_note_id` and at least one date (any format) from the note's `start`/`end`/`date`. If unexplained: text must NOT contain any note id that isn't in `near_misses`, and must contain a phrase from {"no matching note","couldn't find","no supporting note","unexplained"}.
2. Every note id regex `N\d{3}` in text ∈ {packet note id} ∪ {near-miss ids}.
3. Every number with `%` in text ∈ numbers in the packet (±0.1).
4. Every date in text ∈ dates in the packet.
5. Starts with verdict word; ≤ 60 words.
Failure → fall back to template; increment `grounding_rejections` in token log.

## 11. Output writers
- `fmt_pct(x) -> f"{x:+.1f}%"`. `vs_own_history = f"{fmt_pct(vo)} vs this route's past average"`; `vs_similar_routes = f"{fmt_pct(vp)} vs similar-length routes this week"`.
- `cost_per_tonne_km = round(c, 2)` written with `f"{x:.2f}"`.
- Python 3.11: `df.to_csv(path, index=False, columns=CONTRACT_COLS, lineterminator="\n")`.
- After writing, **assert header == sample_output_format_v2.csv header** (read from file, not hard-coded) and that `flagged ∈ {"Yes","No (justified)"}`; `matched_note_id` empty iff flagged == "Yes".
- `weekly_metrics.csv` (extra): every evaluable route-week with unrounded metrics + `n_prior` + `is_candidate`.

## 12. Token log schema (`output/token_log.json`)
```json
{"run_id":"...","provider":"gemini","model":"...","temperature":0,
 "llm_calls":29,"cache_hits":0,"input_tokens":0,"output_tokens":0,
 "grounding_rejections":0,"rate_usd_per_1m_input":0.0,"rate_usd_per_1m_output":0.0,
 "estimated_cost_usd":0.0,"notional_cost_note":"free tier; at published paid rate would be ≈ $X",
 "per_call":[{"purpose":"explain","key":"N001|Chennai-Bangalore|2025-03-03","in":0,"out":0,"cached":false}]}
```
Token counts come from the provider's usage metadata; if unavailable, estimate with `tiktoken`/len//4 and mark `"estimated": true`. Never fabricate zeros when calls happened.
One "full run" for the brief = `run` with a cold cache.

## 13. Eval harness (`eval/run_eval.py`)
1. **Golden anchor**: 3 sample rows exact (cost, vs_own, vs_peer).
2. **Gold set**: compare pipeline candidates to `gold_candidates.csv` (19 rows): row-set equality, verdict equality, note id equality. Print confusion table.
3. **Adversarial verdict cases** (`adversarial_cases.json`, ≥12) unit-style, e.g.:
   - Chennai-Bangalore 2025-03-10 vs N001 → reject (window ended 03-08).
   - Mumbai-Pune any week vs N001/N002 → reject (wrong route).
   - Mumbai-Pune 2025-09-15 vs N006 → reject (effect none).
   - Mumbai-Delhi 2024-08 spike vs N005 → reject (costs not affected).
   - Mumbai-Pune 2025-12-08 vs N003 → reject (outside the 8-week window, and +38.8% vs peers).
   - Mumbai-Pune 2025-06-23 vs N003 → reject (inside window, +6.2% own is within cap, but +20.6% vs peers → universal note can't explain a peer gap).
   - Mumbai-Delhi 2025-05-12 vs N003 → reject (+11.6% own exceeds 7% + 3pp cap).
   - Chennai-Bangalore 2025-03-17 vs N009 → reject (normalizes).
   - Any route vs N004 → reject (out of scope).
   - Ahmedabad-Mumbai 2025-01-27 vs N002 → reject (outside festival week).
   - Positive controls: Ahmedabad-Mumbai 2025-01-20/N002 ✔, Chennai-Bangalore 2025-02-24 & 03-03/N001 ✔.
4. **Grounding**: run grounding checker on all produced reasons; also on 5 deliberately corrupted strings (wrong note id, invented 9% figure, invented "monsoon", wrong date, justified-without-id) → all must FAIL.
5. **Leakage/no-look-ahead test**: mutate future weeks; past rows must not change.
6. **Sensitivity** (`sensitivity.py`): grid over FLAG_OWN ∈ {6,8,10}, FLAG_PEER ∈ {15,20,25}: show #candidates and which gold rows appear/disappear. Report in README as "we chose 8/5/20 because…; results are stable for the strong signals (Delhi-Jaipur Nov-24, Chennai-Bangalore Feb–Mar-25, Ahmedabad-Mumbai Jan-25)".
7. Write `output/eval_report.md` with pass/fail table + one paragraph "why we trust it".

## 14. Repro check (`scripts/repro_check.sh` / `python -m stripewatch repro`)
Run `run` three times in fresh processes (delete `.chroma/` and `.cache/` between runs for runs 2 and 3 of the *retrieval* part; keep LLM cache OFF in one of the runs to prove temp-0 stability if a provider is configured). Compare **all columns except `reason`** byte-for-byte via `diff`, and compare `reason` for cited note ids. Write `output/repro_report.md` listing hashes and "IDENTICAL" or the diff. If a provider is used, also record whether wording differed.

## 15. Ask (stretch) — grounded Q&A
- Flow: parse question → extract `route?`, `month/year?` with simple rules (regex over known route names & month names; LLM extraction optional) → filter `results.json` → if empty, answer "I have no flagged or justified rows for that route/month" (no LLM call) → else build packet of matching rows (+ cited notes) → LLM (temp 0) answers in ≤80 words using only the packet → run the same grounding checker (ids, numbers, dates) → fallback to a templated answer listing rows.
- Never answers causal questions from model knowledge ("monsoon", "fuel") unless a retrieved note says so.
- Example: "why did Chennai-Bangalore get pricier in March?" → cites N001 for the week of 2025-03-03 (justified), and honestly says weeks of 2025-03-10 and 03-17 were flagged as unexplained.

## 16. HTTP API (FastAPI, only if time permits)
`GET /api/summary` · `GET /api/rows` (candidates) · `GET /api/route/{route}` (weekly series + candidates) · `GET /api/notes` · `POST /api/ask {question}` · static `/`.
