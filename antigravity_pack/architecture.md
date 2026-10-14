# architecture.md — How StripeWatch is built

## 1. Principle: the LLM never decides, it only writes
Numbers are pandas. Verdicts are deterministic code. Retrieval *suggests* notes; a **validator** *approves* them. The LLM only turns an already-decided **evidence packet** into one or two friendly sentences — and even that is checked.

```
shipment_records.csv ─► [1 loader+cleaner] ─► [2 weekly aggregator] ─► [3 baselines] ─► [4 candidate detector]
                                                                                              │ (19 rows)
context_notes.csv ─► [5 note structurer] ─► notes_structured.json                             ▼
                          │                                                         [6 retriever (embeddings + vector store)]
                          └──────────────► [7 validator: route · window · effect · magnitude · scope] ◄─┘
                                                                  │ verdict + matched_note_id (deterministic)
                                                                  ▼
                                              [8 evidence packet] ─► [9 explainer (LLM temp 0 | template)] ─► [10 grounding checker]
                                                                  │                                              │ fail → template
                                                                  ▼                                              ▼
                                                            [11 writer] → output.csv · weekly_metrics.csv · results.json · token_log.json
                                                                  │
                                          [12 ask (grounded Q&A)]  [13 eval harness]  [14 repro checker]  [15 web UI]
```

## 2. Tech choices (and why — you must be able to defend each in the walkthrough)
| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | pandas, fast to write, reviewer-friendly |
| Data | pandas | small data (2940 rows); exact control of weeks & baselines |
| Embeddings | `sentence-transformers` `all-MiniLM-L6-v2` (local, open-source, CPU) — fallback: TF-IDF if model download fails | free, deterministic, no API spend |
| Vector store | **ChromaDB** (local, persistent in `.chroma/`, cosine) — fallback FAISS-flat | explicit ask in the brief; recreate collection each run for determinism |
| LLM | **Config-driven provider** via env: `LLM_PROVIDER=gemini|groq|ollama|none`. Default free tier. `none` = template-only mode (0 calls) | brief prefers open-source/free; offline mode guarantees reproducibility |
| LLM params | `temperature=0`, `top_p=1`, fixed `max_output_tokens`, fixed prompt, response cache keyed by SHA-256 of (model+prompt) | determinism + cost |
| Config | `config.py` constants + `.env` | thresholds in ONE place |
| API/UI | FastAPI + one static HTML/CSS/JS page (no framework, no build step, no chart lib) | tiny, fast, distinctive (see design.md) |
| Tests | pytest | golden, unit, adversarial, grounding |

## 3. Repo layout
```
stripewatch/
├─ README.md
├─ requirements.txt            # pinned versions
├─ .env.example
├─ data/                       # the 3 given CSVs (+ notes_structured.json)
├─ stripewatch/
│  ├─ __init__.py  __main__.py  cli.py
│  ├─ config.py                # thresholds, paths, provider
│  ├─ loader.py                # read + validate input
│  ├─ weekly.py                # week_of, route, weekly c (ratio of sums)
│  ├─ baselines.py             # vs_own (trailing ≤8 prior), vs_peer (exclude self)
│  ├─ detect.py                # candidate rule
│  ├─ notes.py                 # load notes + structured facts
│  ├─ retrieve.py              # embeddings + chroma + top-k
│  ├─ validate.py              # deterministic note validator  ← the trust core
│  ├─ evidence.py              # evidence packet builder
│  ├─ explain.py               # LLM / template explanation
│  ├─ ground.py                # grounding checker
│  ├─ llm.py                   # provider adapter + cache + token accounting
│  ├─ writer.py                # CSV + JSON writers, format helpers
│  ├─ ask.py                   # grounded Q&A
│  └─ server.py                # FastAPI + static
├─ web/  index.html  app.css  app.js  assets/
├─ eval/
│  ├─ gold_candidates.csv      # the 19 expected rows (from context.md §7)
│  ├─ adversarial_cases.json   # wrong route / wrong window / no-effect / overshoot
│  ├─ run_eval.py   sensitivity.py
├─ tests/                      # pytest
├─ scripts/  repro_check.sh
├─ output/                     # generated: output.csv, weekly_metrics.csv, results.json, token_log.json, retrieval_log.jsonl, eval_report.md, repro_report.md
└─ docs/  WALKTHROUGH.md  DECISIONS.md
```

## 4. Module contracts (signatures — keep stub-compatible)
```python
# weekly.py
def to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """cols: route, route_type, week_of(date, Monday), cost, tonne_km, n_shipments, c"""
# baselines.py
def add_baselines(w: pd.DataFrame) -> pd.DataFrame:
    """adds own_avg, n_prior, peer_avg, vs_own_pct, vs_peer_pct (unrounded floats); drops rows with n_prior==0"""
# detect.py
def candidates(w: pd.DataFrame, cfg) -> pd.DataFrame
# notes.py
@dataclass class Note: id, date, applies_to, text, scope, effect, start, end, mag_min, mag_max
# retrieve.py
def top_k(query: str, k: int = 3) -> list[tuple[str, float]]   # (note_id, similarity), deterministic ties by note_id
# validate.py
@dataclass class Verdict: justified: bool, note_id: str|None, checks: dict[str,bool], why_not: str
def validate(row, note) -> Verdict
def decide(row, retrieved_notes) -> Verdict
# explain.py
def explain(packet: dict) -> tuple[str, dict]   # (text, usage)
# ground.py
def grounded(text: str, packet: dict) -> tuple[bool, list[str]]
```

## 5. Data flow detail
1. **Load & validate**: assert columns, no nulls, positive numbers, one route_type per route.
2. **Weekly**: `week_of = date - timedelta(days=date.weekday())`; groupby (route, route_type, week_of); `c = sum(cost) / sum(qty*dist)`.
3. **Baselines**: per-route sorted weeks; `own_avg = mean(c over previous ≤8 weeks)` (use `shift(1).rolling(8, min_periods=1)`); `n_prior` stored; peers: for each (route_type, week): `(sum_c - c) / (count - 1)`.
4. **Detect**: rule from context.md §6.
5. **Retrieve**: query text built from facts (route, week range, "cost increase", etc.); top-3 over **all 10 notes** (no filtering at retrieval so the retrieval log shows distractors being surfaced AND rejected — good demo material).
6. **Validate**: for each retrieved note in rank order apply the 5 checks (systemdesign §7). First passing note wins; prefer route-specific over ALL-routes; tie → lowest note_id.
7. **Evidence packet** (JSON) = row numbers + chosen note (id, text, dates) or list of rejected near-misses with reasons.
8. **Explain**: LLM paraphrases packet in ≤45 words; if provider none / error / grounding fail → deterministic template.
9. **Write**: contract CSV + extras.

## 6. Determinism strategy
- No randomness in numeric/verdict path. Stable sorts everywhere (`route`, `week_of`).
- Embedding model pinned; chroma collection rebuilt from scratch each run; ties broken by `note_id`.
- LLM: temp 0, cached; verdict & matched_note_id never depend on LLM output.
- CSV written with fixed float formatting; `\n` newlines; sorted by (week_of, route)? → **sort by `week_of`, then `route`** (sample order isn't sorted; sorting is fine and stable).

## 7. Cost strategy
- LLM calls only for (a) ≤10 optional note-structure cross-checks (cached) and (b) one explanation per candidate row (≈19). Total ≈ 29 calls, a few thousand tokens. Free tier ⇒ $0; still report the "published rate" estimate.
- `token_log.json` is written by `llm.py` for every call (prompt tokens, completion tokens, model, cached?).

## 8. Failure modes & responses
| Failure | Response |
|---|---|
| Embedding model not downloadable | TF-IDF retriever (same interface); log it |
| No LLM key / rate limit | template explanations; calls=0 logged; run still succeeds |
| LLM text fails grounding | discard, use template, count the rejection in the log |
| Candidate count ≠ 19 | do not "fix" — surface a warning and diff vs gold in eval report |
