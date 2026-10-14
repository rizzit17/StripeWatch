---
trigger: always_on
---
# precaution.md — READ BEFORE EVERY MILESTONE. Anti-hallucination rules + the can't-miss checklist.

You are building a graded case study. A confident wrong answer scores **worse** than "I couldn't find one." When unsure: stop, state the doubt, ask the user, or pick the more conservative option and document it.

## PART A — Rules that prevent hallucination
1. **Source of truth order:** (1) the 4 provided files, (2) `context.md`, (3) `systemdesign.md`, (4) these docs. Never invent columns, files, notes, dates, routes, numbers, library APIs or CLI flags.
2. **Look before you claim.** Open the real CSVs and print `head()`, `shape`, `dtypes` before writing code that depends on them. Never "remember" values; recompute.
3. **Verify every library call** you aren't 100% sure of by running a 3-line snippet or reading installed docs (`help()`). Pin versions in `requirements.txt` after they actually work.
4. **Never claim something passed unless you ran it** and saw the output. Paste real test output into `output/eval_report.md`. No "should work", no fake logs, no fabricated token counts.
5. **The LLM never decides a verdict, a note id, or a number.** Verdict = `validate.py`. Numbers = pandas. LLM = wording only, and is grounding-checked.
6. **A note supports a rise only if ALL hold:** it raises cost · covers THIS route (or ALL routes) · its window overlaps THIS week · magnitude is plausible · (universal notes) the route isn't a peer outlier. Otherwise → unexplained.
7. **Semantic similarity is NOT evidence.** N006/N008/N009/N010/N005/N007 are traps: they mention routes/disruptions but say costs were normal/unaffected. They must be retrieved and rejected, never cited as a cause.
8. **Do not tune thresholds to hit the expected answer.** Thresholds are in `config.py` and were chosen on principle (context.md §6). If results ≠ `context.md §7`, report the diff to the user; do not bend code.
9. **Do not use the model's world knowledge as a reason** ("monsoon", "diesel hike", "GST", "festival") unless the cited note says so.
10. **No silent fallbacks.** If a fallback triggers (TF-IDF, template, no LLM), log it in `output/run_log.txt` and the README.
11. **Do not touch input files.** Treat `data/*.csv` as read-only. Don't "fix" the sample output file.
12. **Don't add features that weren't requested** (transporter analytics, forecasting, auth, Docker, DBs). Scope = prd.md.

## PART B — Numeric traps (get these wrong and core logic scores zero)
- [ ] `route = origin + "-" + destination` (e.g. `Delhi-Jaipur`), directional.
- [ ] Use the given `route_type`; do NOT bucket distances yourself.
- [ ] `c = sum(cost) / sum(qty × dist)` per route-week (ratio of sums). NOT mean of shipment ratios.
- [ ] `week_of` = Monday; group dates into weeks BEFORE any computing.
- [ ] vs_own: mean of previous ≤8 **weekly c values**, strictly before current week, `shift(1)` first. Fewer priors → use what exists; 0 priors → skip row. No padding.
- [ ] vs_peer: same week, same route_type, other routes only, simple mean of their weekly c.
- [ ] Percentages computed from unrounded values, then formatted `+x.x%`.
- [ ] Golden rows reproduce: 4.17 / +35.5 / +21.0 (Delhi-Jaipur 2024-11-11); 3.29 / +29.5 / +22.5 (Ahmedabad-Mumbai 2025-01-20); 3.98 / +9.2 / +23.6 (Mumbai-Pune 2025-09-15).

## PART C — Output contract traps
- [ ] File name `output/output.csv`; header EXACTLY = header of `sample_output_format_v2.csv` (read it, assert equal).
- [ ] `flagged` is only `Yes` or `No (justified)`.
- [ ] `matched_note_id` filled (e.g. `N002`) ONLY when justified; truly empty otherwise (not "None", "nan", "N/A").
- [ ] `reason` starts with the verdict, restates note content + dates when justified, and also states why near-miss notes were rejected when relevant.
- [ ] Float formatting 2 dp; dates ISO; no index column; no trailing blank columns.

## PART D — THE COMPLETE "CAN'T-MISS" CHECKLIST (case-study deliverables)
Tick each in `output/SUBMISSION_CHECKLIST.md` with evidence (file path or test output).
1. [ ] Group by route + given route_type. 
2. [ ] Weekly (Mon–Sun) cost per tonne-km tracked per route.
3. [ ] vs own history (trailing 8 prior weeks, no look-ahead; fewer-weeks case documented in README).
4. [ ] vs similar routes (same week, same route_type, self excluded).
5. [ ] Flag rule implemented, documented, thresholds in one place.
6. [ ] RAG: notes embedded in a vector store; retrieval log saved.
7. [ ] Every justified row cites exact note id in `matched_note_id` AND the reason text; note passes route+time+effect checks.
8. [ ] No note → unexplained → `flagged=Yes`, blank id. No guessing.
9. [ ] Plain-English explanation per row, grounded (grounding checker passes 100%).
10. [ ] Stretch: plain-English Q&A over its own results (or explicitly documented as not done).
11. [ ] Eval harness + labeled set + sensitivity; "why I trust it" written.
12. [ ] Reproducibility: 3 untouched runs, identical flags/numbers/note ids/verdicts; temperature 0 declared; diff saved.
13. [ ] Cost: open-source/free models; token log for ONE full cold-cache run (input tokens, output tokens, #calls, rough $ at published rate).
14. [ ] Clean, readable, organised code (small modules, type hints, docstrings, no dead code, tests).
15. [ ] README: how it works, how it was built, how we convinced ourselves it's right, assumptions A1–A5, limitations.
16. [ ] Walkthrough doc (10 min): problem → pipeline → trap notes → numbers → trust → cost → trade-offs → what next.
17. [ ] Output CSV matches `sample_output_format_v2.csv` exactly.
18. [ ] Zip/repo ready: no secrets, `.env.example` only, instructions to run in ≤3 commands.

## PART E — Milestone gates (stop and verify; do not continue if red)
| Gate | After | Must be true |
|---|---|---|
| G0 | env setup | `pip install -r requirements.txt` works; data files load |
| G1 | weekly+baselines | golden 3 rows exact; 728 route-weeks; 721 evaluable; Monday test; no-look-ahead test |
| G2 | detect | 19 candidates; equals context.md §7 set |
| G3 | notes+retrieve+validate | adversarial suite 100%; positive controls pass; N001×2, N002×1 justified; rest unexplained |
| G4 | explain+ground | all 19 reasons pass grounding; corrupted samples all fail |
| G5 | outputs | contract assertion passes; token_log.json has real counts (or 0 calls with `provider=none`) |
| G6 | repro | 3-run diff identical on non-reason columns |
| G7 | docs | README + WALKTHROUGH + checklist complete |
| G8 | (optional) ask + UI | grounded, refuses when no evidence |

## PART F — Things that look right but are wrong (previous-mistake catalogue)
- Citing N001 for Chennai-Bangalore 2025-03-10/03-17 ("flood" feels right; but window ended 2025-03-08 and N009 says normal).
- Citing N003 (diesel) for Mumbai-Pune's slow creep (N003 says ≈5–7% and hits all routes equally).
- Citing N006 for Mumbai-Pune Sept-2025 because the date is near (it says "no disruptions").
- Using the note's CSV `date` as the whole window (N001's real window is in its text).
- Calling a justified row "No" without "(justified)", or putting a note id on a flagged row.
- Computing peer avg including the route itself, or weighting by shipment count.
- Using `rolling(8)` without `shift(1)` (look-ahead leak) or padding with NaN→0.
- Reporting token counts from memory instead of provider usage metadata.
- Letting a temperature>0 LLM choose between notes.
- Saying "all tests pass" without running them.

## PART G — When to stop and ask the user
- Candidate count ≠ 19 after correct implementation.
- Any gold-row verdict differs.
- Library/model download blocked (offer TF-IDF fallback and tell the user).
- You need an API key or provider choice.
- You are tempted to change a threshold or a rule.
