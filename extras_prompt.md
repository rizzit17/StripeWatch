# extras_prompt.md — Differentiator upgrade for StripeWatch (paste into Antigravity)

## ROLE AND SITUATION
You are continuing work on the finished **StripeWatch** repo (FreightTiger AI-intern case study). The core pipeline, tests, eval, repro, README and UI exist and pass. Your job now is to add a small set of **differentiators that make the project's trustworthiness visible**, without risking anything already graded.

Re-read before starting: `AGENTS.md`, `.agents/rules/precaution.md` (always on), `context.md`, `design.md`. They still apply.

## HARD CONSTRAINTS (violating any of these = stop and report)
1. Do **not** change `output/output.csv` contents, the 8 column contract, the candidate thresholds (8 / 5 / 20), the validator rules in `validate.py`, `notes_structured.json`, or the 19-row gold set. All 19 rows, 3 justified / 16 flagged must stay identical.
2. All additions are **supplementary**: new modules, new columns in `output/weekly_metrics.csv` / `output/results.json`, new UI screens, new reports. Nothing new may influence a verdict, a matched note id, or a number in `output.csv`.
3. No new LLM calls in any new feature (all of them must be deterministic and free). `token_log.json` must not change.
4. Everything new is deterministic: fixed seeds, stable sorts, same result on 3 runs.
5. Never claim something works without running it. Paste real output into the reports. No invented numbers.
6. Do not add dependencies beyond what is already in `requirements.txt`, except dev tooling for CI. No new JS/CSS libraries. UI follows `design.md` exactly (paper/ink/tiger palette, slips, stamps, Fraunces / DM Sans / JetBrains Mono; no purple, no gradients, no emoji).
7. Never state a cause for a rise that isn't in a cited note. New features describe *evidence from the data* (e.g. "spread across all transporters"), never causes.

## PHASE 0 — Verify earlier fixes (do first, report results in 5 lines)
Confirm each is done; fix any that aren't:
- [ ] `output/token_log.json` comes from a **cold-cache** run (all `per_call.cached == false`, `cache_hits == 0`) and the README section 5 numbers match that file exactly.
- [ ] `python -m stripewatch repro` clears `.cache/` and `.chroma/` for each of the 3 runs; the report states verdicts, note ids and numbers are identical and says honestly whether `reason` wording differed.
- [ ] README/docs contain no `file:///` links (relative links only).
- [ ] "Near misses" in reasons list only notes that match the route or overlap the week (no N003 for a 2024 week, no Kolkata note for Delhi-Chennai); no repeated sentences.
- [ ] Repo has no duplicate folders (`stripewatch_agents/`, `AI Intern Case Study/`); pack docs live under `docs/`.
- [ ] README has one honest line that AI coding tools were used and where decisions are explained.

## FEATURE 1 — "Try to fool it" console (P0)
**Purpose:** let an evaluator attack the validator live.
- Backend: `POST /api/validate` body `{route, week_of, note_id}` → returns `{row: {c, vs_own_pct, vs_peer_pct, is_candidate}, note: {id, scope, effect, start, end, mag_max}, checks: {effect_is_cost_rise, route_in_scope, window_overlaps, magnitude_ok, not_peer_outlier_for_universal}, justified, why_not}` by calling the real `validate.validate()` — no re-implementation. If the week isn't a candidate, still run the validator and add `"note": "This week was not a candidate; showing what the validator would say."`
- Also `GET /api/weeks?route=` (evaluable weeks) and `GET /api/notes` (already structured notes).
- UI: new screen `#/fool` (nav: Ledger · Routes · Ask · Try to fool it). Three controls (route select, week select, note select), a Run button, preset chips, and a result slip showing the 5 checks as a list with `PASS` / `FAIL` stamps (words, not colour only), the final stamp, and the plain-English `why_not`.
- Preset chips (each must give exactly this result — add as tests):
  1. Chennai-Bangalore 2025-03-10 + N001 → rejected: window ended 2025-03-08
  2. Chennai-Bangalore 2025-03-17 + N009 → rejected: note does not describe a cost rise
  3. Mumbai-Pune 2025-09-15 + N006 → rejected: note says no disruption
  4. Mumbai-Pune 2025-09-15 + N001 → rejected: different route
  5. Mumbai-Delhi 2025-05-12 + N003 → rejected: +11.6% exceeds the 7% + 3pp cap
  6. Mumbai-Pune 2025-06-23 + N003 → rejected: nationwide note can't explain a +20.6% peer gap
  7. Any route + N004 → rejected: out of scope
  8. Ahmedabad-Mumbai 2025-01-20 + N002 → accepted (positive control)
- Tests: `tests/test_fool_api.py` covering all 8 presets via the API.

## FEATURE 2 — Excess-spend estimate and priority ranking (P0)
- Definition: `excess_inr = max(0, (c − own_avg) × tonne_km)` per route-week, rounded to whole ₹. Add to `weekly_metrics.csv` and `results.json`. Document the formula and that it's an *estimate vs own trailing baseline* (it understates slow creep because the baseline drifts up).
- Expected totals on the 19 candidate rows (verify, tolerance ±₹500): about **₹1,28,127** across the 16 flagged rows and **₹77,960** across the 3 justified rows. If yours differ by more, stop and explain.
- UI Ledger: add an "Excess ₹" column (mono, Indian digit grouping, e.g. `₹33,215`), a toggle "Sort by: week / excess ₹", and one line under the summary strip: `Estimated excess on unexplained rises: ₹1.28 lakh`. Route page: per-slip excess line.
- Tests: formula unit test on one known row; non-negative; totals within tolerance.

## FEATURE 3 — Notes page (P0)
- Screen `#/notes`: all 10 notes in slips: id chip, raw note text, scope, effect, window, and a stamp `CAN JUSTIFY` / `CAN'T JUSTIFY` / `CAN JUSTIFY (CAPPED)` with the one-line reason from `notes_structured.json["rationale"]`.
- Header line: "3 of 10 notes can ever justify a cost rise. The other 7 are close in wording but say costs weren't affected, apply elsewhere, or mark the end of a disruption."
- Data from `/api/notes`; nothing hard-coded in the UI.

## FEATURE 4 — Attribution check (P1)
**Purpose:** show from data whether an unexplained rise is route-wide or concentrated, without claiming a cause.
- Module `stripewatch/attribution.py`. Group a route's candidate weeks into **episodes** (gap ≤ 3 weeks between consecutive candidate weeks). For each episode and each group dimension (`transporter`, `material`): mean cost per tonne-km (ratio of sums) of shipments in the episode weeks vs the same group's shipments in the **8 weeks before the episode starts**. Report % change per group and the number of shipments.
- Groups with < 3 shipments in either window → label `too few shipments`. Single-week episodes → label `too few shipments to attribute` for the whole check (3–5 shipments per week is not enough).
- Verdict text (templated, no LLM): `Spread across all N transporters (rises between +a% and +b%)` if every eligible group's rise ≥ half the median group rise, else `Concentrated: <group> rose +x% vs +y% for the rest`. Never say why.
- Expected (verify, don't hard-code): the Mumbai-Pune 2025-09-15 to 2025-12-22 episode is route-wide across all five transporters (rises of roughly +12% to +17%).
- UI: one extra slip on the Route page titled "Where the rise sits". Outputs in `results.json["attribution"]`.
- Tests: synthetic data where one transporter carries the rise → `Concentrated`; uniform rise → `Spread`; < 3 shipments → `too few`.

## FEATURE 5 — CI + badge (P0)
- `.github/workflows/ci.yml`: Python 3.11, pip cache, install requirements, run `pytest -q`, `python -m stripewatch eval`, `python -m stripewatch repro` with `LLM_PROVIDER=none` (and `RETRIEVER=tfidf` if downloading the embedding model is slow or flaky in CI; add that switch in `config.py` if missing and document it). Fail the build if eval accuracy < 100% or repro isn't IDENTICAL.
- README badge at the top. Note in the README that CI uses template explanations (no API key in CI).

## FEATURE 6 — Synthetic injection benchmark (P1)
- `eval/synthetic_bench.py` (seed 42, deterministic). Work on an in-memory copy of the weekly table; never touch `data/` or `output/output.csv`.
- Inject 60 spikes into evaluable route-weeks that are not already candidates and not in the first 8 weeks of a route: multiply that week's `c` by 1 + U(0.05, 0.40) (seeded). Assign each a ground-truth note state: 20 **valid note** (matching route, window covers the week, effect raises, magnitude covers the rise), 20 **decoy note** (right route but window ends before the week, or a "no effect" note), 20 **no note**.
- Build the synthetic notes programmatically as structured objects (no LLM, no embeddings — this benchmark tests detection and `validate.py`, and the report must say so).
- Run the existing detection + validation functions. Report: detection recall overall and by injected magnitude bucket (5–10%, 10–20%, 20–40%); false candidates per 100 clean weeks (excluding the original 19); **wrongly justified count (decoys marked justified) — must be 0**; valid-note recall (justified correctly) and missed valid notes with the reason.
- Be honest: small injections (<8%) will often be missed by design; say so. Write `eval/synthetic_report.md` with real numbers and one paragraph "what this proves and what it doesn't".
- Add to `python -m stripewatch eval --synthetic` and to README.

## FEATURE 7 — Retrieval evaluation (P1)
- `eval/retrieval_eval.py`: for every candidate row (19) and the 8 preset fool-it cases, run the real retriever (k=3 and k=10). Report recall@1 and recall@3 for the truly relevant note (N001 / N002) on the 3 justified rows; and for all 19 rows how often a trap note (N004–N010 or wrong-route note) ranks above the relevant one or appears in the top 3.
- Compare **Chroma + all-MiniLM-L6-v2** against the **TF-IDF fallback** side by side. Report honestly even if TF-IDF does as well (10 notes is tiny).
- Write `eval/retrieval_report.md` ending with: "Retrieval ranks, the validator decides" and the count of times retrieval surfaced a note the validator then rejected.
- Deterministic: stable tie-break by `note_id`.

## FEATURE 8 — Creep early-warning and noise band (P1, supplementary only)
- Add to `weekly_metrics.csv`: `peer_gap_4w` = rolling 4-evaluable-week mean of `vs_peer_pct`; `creep_tag` = `peer_gap_4w >= 15`; `noise_pct` = (std of the previous up-to-8 weekly `c` ÷ `own_avg`) × 100 (strictly prior weeks); `rise_z` = `(c − own_avg)` ÷ std of the previous up-to-8 weeks (blank if < 3 prior weeks).
- These never change flags or verdicts. Report in `docs/DECISIONS.md`: for each route, the weeks tagged `creep_tag`. Expected: Mumbai-Pune first tagged around 2025-09-22 (rolling mean ≈ +15.6%). Report honestly any other route tagged (e.g. Chennai-Bangalore during the flood weeks) — don't hide or tune it.
- UI Route page: small tick marks under the chart for `creep_tag` weeks, legend "peer gap sustained 4 weeks"; optional light band for typical variation. Keep the design rules.
- README limitation: "weekly figures rest on 3–5 shipments, so single-week rises are noisy."

## FEATURE 9 — Provider ablation (P1)
- Script `scripts/ablation.sh` / `python -m stripewatch ablation`: run once with `LLM_PROVIDER=none` and once with `gemini` (cold cache); diff all columns except `reason` and the verdict + note id. Expected: identical. Write `output/ablation_report.md` with both runs' reason wording for 3 sample rows, and a cost table: calls, tokens, ₹/$ for each mode, plus "calls scale with the number of flagged rows, not with shipments (2,940)".
- If no API key is available, run only `none`, say so, and keep the last real Gemini numbers from `token_log.json`.

## FEATURE 10 — Weekly watch mode (P2)
- `python -m stripewatch watch --week YYYY-MM-DD`: evaluates only that Monday's route-weeks using strictly prior history, prints JSON of any candidates with verdict and matched note, and exits 0. Template explanations only (no LLM) unless `--explain`.
- Test: for each of the 19 gold weeks, `watch` returns the same verdict and note id as the full run. For a non-Monday date, exit with a clear error.

## UI CHANGES SUMMARY (all per design.md)
Nav: `Ledger · Routes · Ask · Notes · Try to fool it`. New/changed screens: Ledger (excess column + sort + one line), Route (attribution slip, creep ticks), Notes, Try to fool it. Re-take the six screenshots (390 and 980 wide) into `docs/screens/`, plus two new ones for Notes and Try to fool it. Keep `app.js` lean (< 16 KB total is acceptable for the added screens; say if exceeded).

## DOCS TO UPDATE
- `README.md`: add a "Beyond the brief" section (one short table: feature → what it shows → file) and keep it honest: what each one proves and does not prove.
- `docs/WALKTHROUGH.md`: add a 90-second "live attack" segment (Try to fool it with the Chennai-Bangalore 03-10 preset), a 60-second "money" segment (excess ₹), and a 60-second "how I know it's right" segment (synthetic benchmark + 3-run repro).
- `docs/DECISIONS.md`: one entry per feature with trade-offs.
- `output/SUBMISSION_CHECKLIST.md`: add the new items with evidence paths.

## ORDER AND TIME-BOX (stop each phase on a red gate)
1. Phase 0 verification — 20 min
2. Features 1, 3, 2 (UI + API) — 90 min
3. Feature 5 CI — 20 min
4. Features 6, 7 (benchmarks) — 90 min
5. Features 4, 8 (attribution, creep) — 60 min
6. Feature 9 (ablation) — 20 min; Feature 10 only if time remains
7. Docs + screenshots + final full run — 40 min

## GATES (run after each phase and paste the real output)
- `pytest -q` all green (existing 10 + new tests).
- `python -m stripewatch run` regenerates `output/output.csv` **byte-identical** to the committed one (`git diff --stat output/output.csv` shows no change).
- `python -m stripewatch eval` still 100%; `python -m stripewatch repro` IDENTICAL.
- `grep -rniE "gradient|purple|violet|indigo" web/` returns nothing.
- No new LLM calls: `llm_calls` in a fresh `run` equals 19 (or 0 with `none`).

## WHEN TO STOP AND ASK ME
- Any gold row, verdict, threshold or `output.csv` byte would change.
- An expected number above differs by more than the stated tolerance.
- A feature would need an LLM call, a new dependency, or a design change.

## FINAL REPORT FORMAT (concise bullets)
For each feature: done / skipped, files changed, the real test or report output (3 lines max), and any honest caveat. Then the final gate results and the list of new files.
