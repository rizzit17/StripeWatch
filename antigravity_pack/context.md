# context.md — Ground truth about the data and the task

> Everything here was measured from the real files, not assumed. If code disagrees with this file, the code is wrong — unless a test proves this file wrong, in which case STOP and tell the user.

## 1. The task in one paragraph
FreightTiger "Smart Assistant That Watches Shipping Costs" (AI intern case study, 24 h). Group shipments by route, compute weekly cost per tonne-km, compare each week to (a) the route's own trailing history and (b) similar-length routes, flag unjustified rises, check a small notes file (RAG) for a real reason, and explain in plain English **without hallucinating**. Graded on: core logic, meaningful AI use, trust, reproducibility, cost, clean code, explainability.

## 2. Files given (put in `data/`)
| File | Rows | Purpose |
|---|---|---|
| `shipment_records.csv` | 2940 | Input data |
| `context_notes.csv` | 10 | Notes to retrieve over |
| `sample_output_format_v2.csv` | 3 | **Output contract** (columns, order, string formats). The PDF calls it `sample_output_format.csv`; the real file is `_v2`. |
| `FreightTiger_Intern_CaseStudy.pdf` | – | Requirements |

## 3. shipment_records.csv — measured facts
Columns: `shipment_id, origin, destination, route_type, material, quantity_tonnes, distance_km, freight_cost_inr, shipment_date, transporter`
- 2940 rows, **0 nulls, 0 duplicate ids, 0 non-positive qty/dist/cost**.
- Dates: 2024-01-01 → 2025-12-28. 2024-01-01 is a Monday. **104 Monday-start weeks.**
- **Route = `origin-destination`** (directional, hyphen, no spaces). Exactly 7 routes, each with exactly one `route_type`:

| Route | route_type | Shipments | Mean dist km |
|---|---|---|---|
| Mumbai-Pune | Short | 418 | 150 |
| Delhi-Jaipur | Short | 416 | 280 |
| Chennai-Bangalore | Medium | 410 | 350 |
| Kolkata-Bhubaneswar | Medium | 433 | 440 |
| Ahmedabad-Mumbai | Medium | 421 | 530 |
| Mumbai-Delhi | Long | 423 | 1400 |
| Delhi-Chennai | Long | 419 | 2184 |

- Every route has data in all 104 weeks, **3–5 shipments per route-week (mean ≈ 4)**.
- `distance_km` varies ±2% per shipment → compute cost/tonne-km as **ratio of sums**: `sum(freight_cost_inr) / sum(quantity_tonnes * distance_km)` per route-week. NOT mean of per-shipment ratios.
- Peer groups are tiny: **Short = 2 routes, Long = 2 routes, Medium = 3 routes.** So "similar routes" for a Short/Long route is literally ONE other route. Mention this limitation in the README.
- Distractors (do not use in core logic): `material`, `transporter`. `Coromandel Carriers` appears only on Delhi-Chennai (89 rows) and is cheaper (~2.08 vs ~2.7 avg). Do not build transporter logic.

## 4. Baseline definitions (VERIFIED against the sample file)
Weeks = Monday–Sunday, `week_of` = Monday date. Weekly metric `c` = ratio of sums (above).

- **vs_own_history** = `c / mean(c of the previous up-to-8 weeks of the same route) - 1`. Strictly prior weeks only. Mean of the *weekly* values (not pooled). If <8 prior weeks exist use what exists (1–7 priors); if 0 prior weeks, the row cannot be evaluated (route's first week) — skip it and say so in README. Never pad or extrapolate.
- **vs_similar_routes** = `c / mean(c of OTHER routes with same route_type, same week) - 1` (simple mean of the other routes' weekly `c`).

**Golden anchor (must reproduce exactly — these are the 3 rows in the sample file):**
| route | week_of | cost_per_tonne_km | vs_own | vs_similar |
|---|---|---|---|---|
| Delhi-Jaipur | 2024-11-11 | 4.17 | +35.5% | +21.0% |
| Ahmedabad-Mumbai | 2025-01-20 | 3.29 | +29.5% | +22.5% |
| Mumbai-Pune | 2025-09-15 | 3.98 | +9.2% | +23.6% |

I verified these three match to the shown precision with the definitions above. Build `tests/test_golden_sample.py` around them first.
Counts: 728 route-weeks, 721 evaluable (7 first-weeks have no history).

## 5. context_notes.csv — all 10 notes, structured by a human (answer key)
Raw columns: `note_id,date,applies_to,note`. `applies_to` is either a route string or `All Routes`. The CSV only has ONE date; real windows live inside the note text. Hand-verified structure (store as `data/notes_structured.json`; the LLM may *cross-check* it but must never overwrite it):

| id | scope | effect on cost | window used by validator | can justify a rise? |
|---|---|---|---|---|
| N001 | Chennai-Bangalore | raises (flood detours) | 2025-02-24 → 2025-03-08 (passable from Mar 9) | **YES** |
| N002 | Ahmedabad-Mumbai | raises (festival surcharge) | the festival week = week of 2025-01-20 (note date is a Monday; Assumption A2) | **YES** |
| N003 | ALL routes | raises ≈5–7% (diesel) | starts 2025-05-05, assumed to stay visible vs own-history for 8 weeks (to 2025-06-29; Assumption A3) | **YES, capped** |
| N004 | none in dataset | toll plaza on routes NOT in dataset | – | NO (out of scope) |
| N005 | Mumbai-Delhi | none — "costs not significantly affected" | ~2024-07-29 + 1 week | NO |
| N006 | ALL | none — "stable demand, no disruptions" | quarter | NO |
| N007 | Delhi-Jaipur | none/lower (roads improved) | 2024-05-20 | NO |
| N008 | Kolkata-Bhubaneswar | none — "freight movement normal" | quarter ~2025-06-09 | NO |
| N009 | Chennai-Bangalore | none — "returned to normal" | 2025-03-17 | NO (it marks the END of the disruption) |
| N010 | ALL | none — "absorbed… without a rate change" | 2025-10-27 | NO |

**Only N001, N002, N003 can ever justify anything.** Seven notes are deliberate traps (wrong route, "no effect", wrong time, or out of scope). A retriever will happily surface them because they are semantically close. The validator (section 7 of systemdesign.md) must reject them.

## 6. Flag rule (our decision; configurable constants in `config.py`)
A route-week is a **candidate** (a rise that "looks out of the ordinary") iff:
`vs_own > 0` AND ( `vs_own >= +8.0%` OR ( `vs_own >= +5.0%` AND `vs_similar >= +20.0%` ) )

Why the second branch: Mumbai-Pune creeps up slowly from Jun→Dec 2025; its own trailing average drifts up with it so `vs_own` looks mild (+5–9%) while it is +20–39% above its peer. The sample file itself flags Mumbai-Pune 2025-09-15 at only +9.2% own / +23.6% peers, so the peer branch is required.

Candidates then get a verdict: `Yes` (unexplained → flagged) or `No (justified)` (matched a valid note). Output CSV contains **candidate rows only**, like the sample (which has only unusual rows). Also emit a supplementary `output/weekly_metrics.csv` with every evaluable route-week (not part of the contract).

## 7. EXPECTED RESULT under the rule above (hand-computed gold set — 19 candidate rows)
| route | week_of | c | vs_own | vs_sim | expected verdict | note |
|---|---|---|---|---|---|---|
| Delhi-Chennai | 2024-02-05 | 2.22 | +8.5 | +7.8 | Yes | noise-level; no note |
| Delhi-Jaipur | 2024-11-11 | 4.17 | +35.5 | +21.0 | Yes | no note (N007 is May 2024, "improved roads") |
| Delhi-Jaipur | 2024-11-18 | 4.09 | +27.6 | +19.7 | Yes | no note |
| Ahmedabad-Mumbai | 2025-01-20 | 3.29 | +29.5 | +22.5 | **No (justified)** | **N002** |
| Chennai-Bangalore | 2025-02-24 | 3.58 | +31.5 | +38.7 | **No (justified)** | **N001** |
| Chennai-Bangalore | 2025-03-03 | 3.48 | +22.8 | +32.0 | **No (justified)** | **N001** |
| Chennai-Bangalore | 2025-03-10 | 3.57 | +22.1 | +33.8 | **Yes** | after N001 window (ended Mar 8); N001 itself says passable from Mar 9 → trap |
| Chennai-Bangalore | 2025-03-17 | 3.47 | +13.7 | +33.5 | **Yes** | N009 says "normal" — not a reason → trap |
| Mumbai-Delhi | 2025-05-12 | 2.28 | +11.6 | +6.7 | Yes | diesel N003 says ~5–7%; +11.6% overshoots cap (7+3=10) |
| Mumbai-Pune | 2025-06-23 | 3.76 | +6.2 | +20.6 | Yes | all-routes N003 cannot explain a peer-relative gap |
| Mumbai-Pune | 2025-09-15 | 3.98 | +9.2 | +23.6 | Yes | N006 is a "no disruption" note → trap (sample file agrees) |
| Mumbai-Pune | 2025-10-06 | 3.94 | +5.4 | +22.9 | Yes | |
| Mumbai-Pune | 2025-10-20 | 4.10 | +7.7 | +24.8 | Yes | |
| Mumbai-Pune | 2025-10-27 | 4.07 | +5.5 | +28.3 | Yes | N010 "no rate change" → trap |
| Mumbai-Pune | 2025-11-03 | 4.20 | +7.4 | +24.1 | Yes | |
| Mumbai-Pune | 2025-11-17 | 4.32 | +8.9 | +31.6 | Yes | |
| Mumbai-Pune | 2025-12-01 | 4.39 | +7.7 | +37.4 | Yes | |
| Mumbai-Pune | 2025-12-08 | 4.43 | +7.2 | +38.8 | Yes | |
| Mumbai-Pune | 2025-12-22 | 4.49 | +5.8 | +38.9 | Yes | |

**Totals: 19 candidates = 3 justified (N001×2, N002×1) + 16 flagged.** Numbers are from my pandas check; the pipeline must reproduce them (±0.05 on percentages from rounding). If the pipeline yields a different set, investigate — do NOT tweak thresholds to match. Tell the user about any difference.

Story for the demo: Delhi-Jaipur Nov-2024 spike (unexplained), Ahmedabad-Mumbai festival spike (justified N002), Chennai-Bangalore flood (justified for 2 weeks, honestly NOT justified for the 2 weeks after the note's own end date), and Mumbai-Pune slow creep from mid-2025 that no note explains.

## 8. Output contract (from sample_output_format_v2.csv)
Header, exact order: `route,week_of,cost_per_tonne_km,vs_own_history,vs_similar_routes,flagged,matched_note_id,reason`
- `week_of`: `YYYY-MM-DD`
- `cost_per_tonne_km`: float, 2 decimals (4.17)
- `vs_own_history`: `+35.5% vs this route's past average` (signed, 1 decimal)
- `vs_similar_routes`: `+21.0% vs similar-length routes this week`
- `flagged`: exactly `Yes` or `No (justified)`
- `matched_note_id`: `N002` or EMPTY (never "None"/"NA")
- `reason`: starts with the verdict; if justified, names the note id, restates its content and its dates; if not, says what was (not) found. Quote from the sample: *"No matching note found for this route or date range. Cost rise looks unexplained and worth a human review."*
- UTF-8, comma-separated, quoted only where needed, one header row, no index column.

## 9. Assumptions to write in README (do not hide them)
- A1: Only evaluable weeks are scored; each route's first week has no history.
- A2: N002 window = the week of its date.
- A3: N003 stays a valid explanation for 8 weeks after 2025-05-05, only while the rise is ≤ 7%+3pp and the route is not also a peer outlier.
- A4: Peer groups are 2–3 routes; peer averages are noisy.
- A5: The candidate thresholds (8 / 5 / 20 %) are our choice; include the sensitivity table from `eval/sensitivity.py`.
