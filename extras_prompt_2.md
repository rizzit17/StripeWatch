# extras_prompt_2.md — Trust + UI differentiators for StripeWatch (paste into Antigravity)

## ROLE AND SITUATION
You are continuing the finished **StripeWatch** repo (FreightTiger AI-intern case study). Core pipeline, tests, eval, repro, README and the base UI exist and pass. A first upgrade prompt (`extras_prompt.md`: Try-to-fool-it console, excess ₹, Notes page, attribution, CI, synthetic benchmark, retrieval eval, creep tag, ablation, watch mode) may already be applied or in progress. **This prompt adds three backend features and eight UI features on top.** Where it depends on something from `extras_prompt.md` and that isn't present, the dependency is named; implement the minimal version stated here and keep going.

Re-read first: `AGENTS.md`, `.agents/rules/precaution.md` (always on), `context.md`, `design.md`. They all still apply.

## HARD CONSTRAINTS (violating any = stop and report)
1. Do **not** change `output/output.csv` (byte-identical), its 8-column contract, thresholds (8 / 5 / 20), validator rules, `data/*.csv`, or the 19-row gold set (3 justified, 16 flagged).
2. All additions are **supplementary**: new modules, files, API routes, screens, columns in `results.json` / `weekly_metrics.csv`. Nothing here may influence a verdict, a matched note id, or any number in `output.csv`.
3. **LLM use:** only Backend A below may call an LLM, and only from its own script with its own cache and its own token log (`output/baseline_token_log.json`). The main `run` must still make exactly the same LLM calls as before (19, or 0 with `LLM_PROVIDER=none`) and `output/token_log.json` must not change.
4. Everything else is deterministic: fixed seeds, stable sorts, same result on 3 runs. Runtime state (review queue, localStorage) is excluded from reproducibility hashes.
5. Never claim something works without running it. Paste real output into the reports. No invented numbers; where I give expected values they are *checks*, not constants to hard-code.
6. No new runtime dependencies in `requirements.txt`. Browser testing tools go in `requirements-dev.txt` only (e.g. Playwright) and are optional; if they can't be installed, say so and test manually with a written checklist.
7. UI follows `design.md` exactly: paper / slip / ink / tiger / stamp palette, Fraunces + DM Sans + JetBrains Mono, hard 3px offset shadows, **no gradients (including radial), no purple/indigo/violet, no blur, no emoji, no UI or chart libraries**. One extra flat token is allowed: `--tiger-soft:#F2D3A0`. Everything must work at 390 px and 980 px and with `prefers-reduced-motion`.
8. New features describe *evidence from the data*; they never state a cause for a rise that isn't in a cited note.
9. Security basics: render all user/note text with `textContent` (never `innerHTML` with data), bind the dev server to `127.0.0.1` by default, no secrets in any built file.

## PHASE 0 — Quick verification (report in 5 lines)
- `git status` clean; `pytest -q` green; `python -m stripewatch run` leaves `output/output.csv` unchanged (`git diff --stat output/output.csv` empty).
- Note which `extras_prompt.md` features already exist (`/api/validate`, `/api/notes`, Notes page, `creep_tag`, `excess_inr`, attribution). List them; do not rebuild them.

---

# BACKEND

## BACKEND A — Hallucination baseline test (P0)
**Purpose:** show, with numbers, what a plain LLM does with no notes, versus StripeWatch.
- Script `eval/hallucination_baseline.py`, CLI `python -m stripewatch eval --hallucination`. Requires an LLM provider/key; if none is configured, print a clear message, exit 0, write nothing, and tell the user.
- **Naive prompt** (fixed, stored in the script, temperature 0, same provider and model as the main pipeline, ≤ 80 output tokens): give only route, week_of, cost_per_tonne_km, vs-own %, vs-peers %, and ask: "In under 40 words, explain why this route's freight cost rose that week." No notes, no instructions about honesty — it is the baseline.
- Run it on the **16 unexplained rows** (from `results.json`). Separate cache file `.cache/baseline_cache.json`. Log calls/tokens to `output/baseline_token_log.json` (real usage metadata, `cached` flags, mark estimates as `estimated: true`).
- **Scoring (deterministic, no LLM judge):**
  1. Classify each naive answer with a fixed, committed lexicon in the script: *asserts a cause* if it contains any of: diesel, fuel, toll, monsoon, rain, flood, festival, surcharge, strike, shortage, demand, holiday, weather, road, congestion, driver, tax. *Hedged* if it contains: cannot determine, unclear, insufficient, no information, not enough, unknown. Otherwise *other*. (Hedged wins over cause only if it contains no lexicon cause word.)
  2. For the 16 rows no note passes the validator, so every *asserts a cause* answer is an **unsupported claim**. Report the count and rate.
  3. Run StripeWatch's real `ground.py` on each naive answer using the row's evidence packet: report how many unsupported-cause answers the checker **rejects** (catch rate).
  4. For comparison, scan StripeWatch's own 16 `reason` texts with the same lexicon. Print every hit with its sentence and label it `mentioned as rejected near-miss` only if the sentence contains one of: rejected, excluded, cannot explain, does not, not describe, lacks, outside, different route, no overlap; otherwise `claims a cause`. Expected: 0 `claims a cause`. If not 0, stop and report.
- Output `eval/hallucination_report.md`: a table (rows: naive LLM / StripeWatch; columns: n, asserted unsupported cause, hedged, other, caught by grounding check); 3 naive answers quoted verbatim and labelled model output; and a "what this proves and doesn't" paragraph (n = 16, one model, one prompt, a crude lexicon; it demonstrates the risk, not a general rate).
- Add a 4-line summary to the README and the walkthrough. Do not predict the outcome; report what you get.
- Tests (no network): lexicon classifier on 8 canned strings; scoring function on a canned set; script exits cleanly with no provider.

## BACKEND B — Human review queue (P1)
**Purpose:** the sample output says "worth a human review" — let a human act on it, without touching verdicts.
- State file `.state/review_state.json` (gitignored; commit `data/review_state.example.json`). Schema: `{"<route>|<week_of>": {"status": "open|confirmed|dismissed", "note": "<= 280 chars", "updated_at": "ISO-8601"}}`. Default for every candidate row = `open` (not stored).
- API: `GET /api/review` (all 19 candidates merged with status), `PUT /api/review/{route}/{week_of}` body `{status, note}`. Validate: row must be one of the 19 candidates; status in enum; note ≤ 280 chars, control characters stripped; reject extra keys (400). Atomic write (temp file + rename). Server binds 127.0.0.1.
- Export: `GET /api/review/export.csv` and `python -m stripewatch review-export` → `output/review_export.csv` with columns `route,week_of,verdict,matched_note_id,review_status,review_note`. This is **not** `output.csv` and never replaces it.
- UI: Ledger gets a "Review" column: a small stamp-style control cycling `OPEN` (dashed border) / `CONFIRMED` / `DISMISSED` (words, not colour only), a status filter next to the verdict filter, and one line under the summary: `N of 16 flagged rows reviewed`. Route-page slips get a note textarea (280 char counter, saves on blur) labelled "Your review (stored on this computer)". Verdict stamps are unaffected.
- Static demo mode (see UI-8): same UI, state in `localStorage` (try/catch, falls back to memory), plus "Download review CSV" via Blob.
- Tests: valid/invalid PUTs (bad status, non-candidate row, long note, extra key), atomic write, export columns, state excluded from `repro` hashes, verdict columns unchanged after reviews.

## BACKEND C — Abstention stat (P0, small)
- Add to `results.json["summary"]`: `abstention: {unexplained, total, rate, usable_notes, total_notes, notes_cited: ["N001","N002"], notes_usable_never_cited: ["N003"]}` computed from data (usable notes = those whose structured effect is `raises`).
- Show in the UI summary line: "Left 16 of 19 unexplained on purpose: only 3 of 10 notes can justify a rise." (numbers from the API), in the README "Trust" section, and in the walkthrough as a one-liner: "High abstention is the design, not a bug."
- Test: values derived from data, not hard-coded; string renders from API values.

---

# UI (all per `design.md`)

New nav: `Ledger · Calendar · Routes · Ask · Notes · Try to fool it` (+ "Take the tour" link and "?" shortcut hint in the header/footer). Keep `app.js` under 40 KB and `app.css` under 16 KB; report sizes.

## UI-1 Lorry calendar heatmap — new screen `#/calendar` (P0)
- Hand-built inline SVG, `viewBox="0 0 820 230"`, `width="100%"`. Rows = the 7 routes grouped by `route_type` (small mono group labels SHORT / MEDIUM / LONG on the left); columns = the 104 weeks; cell 6×18 px with 1 px gap; route labels in DM Sans 12 px, month/quarter ticks on top in mono 11 px.
- Cell encoding (words in legend, not colour alone): normal week = `--rule` fill; not evaluable (first week) = dotted `--rule` outline, no fill; **flagged** candidate = `--stamp-red` fill; **justified** candidate = `--slip` fill + 2 px `--stamp-green` stroke; if `creep_tag` exists in `weekly_metrics.csv`, a sustained-peer-gap week gets a `--tiger-soft` underline bar (2 px) under the cell, legend "peer gap sustained 4 weeks". If the column is missing, omit the bar and the legend item.
- Candidate cells (19) are focusable (`tabindex="0"`); hover/focus shows a flat slip tooltip (week, route, ₹/t-km, vs own, vs peers, verdict, note id). Click/Enter → `#/route/<route>?week=<week_of>`. Non-candidate cells show the same tooltip on hover only (no focus stops, to keep keyboard use sane).
- Under the chart: one sentence from data ("Mumbai-Pune shows 10 flagged weeks since Jun 2025, 2 of 7 routes had flood- or festival-type spikes…" — build it from the data; do not hand-write counts) and a `<details>` data table alternative.
- Visual acceptance: the 4 Chennai-Bangalore flood weeks (2 green rings then 2 red cells) and the Mumbai-Pune cluster late in 2025 must be visible at a glance.

## UI-2 Paper trail strip (P0)
- A row of 5 tickets shown on every evidence slip (Route page), in the Try-to-fool-it result, and in the Ledger row detail: **Spotted → Searched → Route → Window → Effect and size**.
  1. Spotted: `+22.1% own · +33.8% peers` (candidate rule).
  2. Searched: the top-3 retrieved note ids as chips.
  3. Route: does the note's scope match? `PASS` / `FAIL`.
  4. Window: does the note's dates overlap the week? `PASS` / `FAIL`, with the note's window in mono.
  5. Effect and size: raises cost and within the stated size? `PASS` / `FAIL`.
- For a justified row show the strip for the cited note (all PASS). For an unexplained row show the strip for the **closest rejected note** (first one with the most passing checks; tie → lowest id) with a label "Closest note: N001" and the first failing ticket stamped `FAIL`; the later tickets show `—` (not evaluated).
- Tickets are separated by `border-right: 2px dotted var(--rule)` (no notches, no gradients). Stamps carry words. On ≤ 560 px the strip becomes a vertical list.
- Data: `results.json` rows need `retrieved: [{id, score}]` and `checks` per retrieved note (`effect_is_cost_rise`, `route_in_scope`, `window_overlaps`, `magnitude_ok`, `not_peer_outlier_for_universal`) plus `why_not`. Add these to `results.json` if absent (no change to `output.csv`). Ticket 5 combines effect + magnitude (+ the universal-outlier check) and its tooltip lists the sub-checks.
- Tests: strip data for Chennai-Bangalore 2025-03-10 shows `N001` closest with Window = FAIL; Ahmedabad-Mumbai 2025-01-20 shows N002 all PASS.

## UI-3 Evidence highlight (P0)
- Extend `data/notes_structured.json` (hand-authored, no LLM) with `evidence_spans` (for notes that can justify) and `negating_spans` (for the others): exact substrings of the raw note text.
  - N001 evidence: "Heavy flooding on the Chennai-Bangalore highway", "Feb 24 to Mar 8", "higher trip costs". N001 window-end span (used when rejected for window): "Roads were passable again by Mar 9".
  - N002 evidence: "temporary surcharge", "regional festival week".
  - N003 evidence: "roughly 5-7%". 
  - Negating spans: N004 "not part of this dataset"; N005 "costs were not significantly affected"; N006 "no major disruptions reported"; N007 "improved road conditions"; N008 "freight movement remained normal"; N009 "returned to normal conditions"; N010 "absorbed by transporters without a rate change".
  - Verify each substring occurs **exactly once** in its note's raw text; if any doesn't, fix the span (never edit the note text) and report.
- UI: wherever a note is shown (justified slip, rejected near-miss list, Notes page, fool-it result), render the full original text with spans wrapped in `<mark>` styled `background:var(--highlight)`; justified slips highlight evidence spans, rejected ones highlight the negating/window-end span with a small mono tag `why rejected`. Build DOM with text nodes (no `innerHTML` with data).
- Tests: every span exists exactly once; rendering helper splits text correctly with overlapping/adjacent spans.

## UI-4 Week scrubber (P1)
- On the Route page chart, a draggable **truck marker** (the 28 px truck SVG from `design.md`) sits on the x-axis and snaps to weeks. Pointer events (mouse + touch, 40 px hit area), plus keyboard: `←/→` step one week, `Shift+←/→` jump 4, `Home/End` first/last. The element has `role="slider"`, `aria-valuemin/max/now`, `aria-valuetext="week of 2025-03-10, flagged"`.
- A "week slip" below the chart updates live for **any** week: week_of, ₹/t-km, own average, peer average, shipments (n), vs own, vs peers, and the verdict stamp if the week is a candidate, otherwise "Normal this week" (or "Not enough history" for the first week). If an evidence slip exists for that week, scroll/link to it.
- Deep link `?week=YYYY-MM-DD` positions the marker. No animation beyond snapping (respect reduced motion). Data from the existing `/api/route/{route}` (all weekly rows).

## UI-5 Print as docket (P1)
- "Print docket" button on each evidence slip and "Print summary" on the Ledger. `@media print` styles: white background, no nav/buttons/shadows, ink text, slip borders 1.5 px, `break-inside: avoid`, A4 portrait margins 16 mm, fonts fall back to system if not loaded.
- Docket content: wordmark and "StripeWatch evidence docket", run id, route, week, numbers, verdict stamp, the cited note (with highlight rendered as underline in print), the paper trail strip (as a text-friendly row), review status/note if any, and the footer "Generated from output/results.json, run <id>. Same numbers on 3 runs." Dotted top border as the "perforation".
- Implementation: set `document.body.dataset.print = "<slip id>"` then `window.print()`, CSS shows only that slip; clear the attribute on `afterprint`.
- Deliver a sample `docs/screens/docket_Chennai-Bangalore_2025-03-10.pdf` generated via headless Chromium print if available; otherwise state it wasn't generated.

## UI-6 Guided tour (P1)
- "Take the tour" link; also `?tour=1`. Six steps with coach marks (flat slip tooltip with a border-built arrow, solid dim overlay `rgba(29,27,22,.45)`, no blur, no animation under reduced motion). Next / Back / Skip; `Esc` closes; focus is trapped in the coach mark and restored on close; dismissal remembered in `localStorage` (try/catch). Steps navigate between screens by hash:
  1. Summary strip: "19 cost rises spotted. Only 3 have a note that really explains them."
  2. A Ledger row: "Each row is one route-week. Click one to see the evidence."
  3. Route chart: "Green rings have a justified note. Red dots don't. Drag the truck to move between weeks."
  4. Paper trail strip: "Every verdict passes five checks. A note must match the route, the window and the effect."
  5. Try to fool it: "Pick any note and any week. It tells you exactly why it fails."
  6. Footer: "Same numbers on 3 runs. The model only writes the wording."
- Numbers in step 1 come from the API. Total tour JS < 4 KB.

## UI-7 Keyboard shortcuts (P2)
- `j` / `k` move focus down/up Ledger rows, `Enter` opens, `/` goes to Ask and focuses the input, `g` then `l`/`c`/`n`/`f`/`a` go to Ledger/Calendar/Notes/Fool/Ask, `?` opens a slip-style shortcuts sheet, `Esc` closes any sheet/tour. Ignore shortcuts when typing in input/textarea/select or with ctrl/meta/alt held. Footer hint "press ? for shortcuts". The sheet is a native `<dialog>`.

## UI-8 Static demo build and hosting (P0)
- `scripts/build_static.py` → `dist/` with `index.html`, `app.css`, `app.js`, fonts link unchanged, and JSON snapshots in `dist/data/` of every API response the UI uses (summary, rows, per-route weekly series, notes, review defaults, weeks) **plus** `validate_matrix.json`: precomputed `validate()` output for every (route, week, note) combination — 7 routes × evaluable weeks × 10 notes, stored compactly (check bits + why_not code table), so **Try to fool it works with no backend**. Report the file size (budget: `dist/` under 5 MB).
- The UI has a "static mode": `window.STATIC_DEMO = true` set by the build; all `/api/*` calls map to relative `data/*.json` paths (relative URLs so it works under a GitHub Pages subpath). Ask: show 3 prebaked Q&A pairs generated at build time by the real `ask` module if an LLM key is available, else from the last cached answers; if neither exists, hide the free-text box and say "Ask works in the local app" — never fabricate answers. Review queue uses localStorage (Backend B). A small banner: "Static demo: a snapshot of the committed results. No API keys, no live model."
- Hosting: `.github/workflows/pages.yml` (build on push to main, publish `dist/` to GitHub Pages) and a `netlify.toml` (`publish = "dist"`, command `python scripts/build_static.py`). README "Live demo" section with the URL placeholder and one line on enabling Pages.
- Verify: serve `dist/` with `python -m http.server`, load every route in a headless browser (or a manual checklist) with zero console errors and zero failed requests; confirm `dist/` contains no `.env`, `.cache`, `.state`, keys or absolute local paths (grep for `AIza`, `GEMINI`, `c:/`, `/home/`, `Users/`).

---

## TESTING AND VISUAL CHECKS
- `pytest -q` stays green; add tests named in each feature. 
- If Playwright is installable (dev only): smoke tests that open each screen at 980 and 390 px, tab through with the keyboard, assert no console errors, assert the Calendar has 19 focusable cells, the scrubber changes the week slip on `→`, and the tour completes. Save screenshots to `docs/screens/` (Ledger, Calendar, Route with scrubber, paper trail strip, Notes, Fool-it, tour step, print preview) at both widths.
- Accessibility pass: keyboard-only walk through every screen; focus ring visible; stamps carry words; stamp text contrast ≥ 4.5:1 on `--slip` (if a colour fails, tell me before changing it); reduced-motion honoured; touch targets ≥ 40 px.

## ORDER AND TIME-BOX (stop a phase on a red gate)
1. Phase 0 — 15 min
2. Backend C, UI-3 spans, UI-2 data (`results.json` additions) — 60 min
3. UI-2 strip, UI-1 calendar — 90 min
4. UI-8 static build + Pages/Netlify config — 75 min
5. Backend A (hallucination baseline) — 60 min
6. UI-4 scrubber, Backend B review queue — 90 min
7. UI-5 print, UI-6 tour — 60 min
8. UI-7 shortcuts — 20 min
9. Docs, screenshots, final full run — 45 min

## GATES (run after each phase; paste real output)
- `pytest -q` green; `python -m stripewatch run` → `git diff --stat output/output.csv` empty; `python -m stripewatch eval` 100%; `python -m stripewatch repro` IDENTICAL; main `llm_calls` unchanged.
- `grep -rniE "gradient|purple|violet|indigo" web/ dist/` → nothing.
- `grep -rn "innerHTML" web/app.js` → none that take data (list any hits and justify).
- Bundle sizes reported: `app.js`, `app.css`, `dist/`.

## DOCS TO UPDATE
- `README.md`: a "Beyond the brief" table (feature → what it shows → file/URL), a "Trust" section with the abstention stat and the hallucination-baseline summary (real numbers), a "Live demo" section, and limitations (n = 16 for the baseline; heatmap shows only 19 candidate weeks; static demo = snapshot).
- `docs/WALKTHROUGH.md`: add a 2-minute "live attack" (Try to fool it → Chennai-Bangalore 2025-03-10 + N001), a 60-second "paper trail and highlight" segment, a 60-second "plain LLM vs StripeWatch" segment using the real report numbers, and the tour as a fallback if the talk runs long.
- `docs/DECISIONS.md`: one entry per feature with trade-offs (why a static demo, why the review queue never touches verdicts, why spans are hand-authored).
- `output/SUBMISSION_CHECKLIST.md`: new items with evidence paths.

## WHEN TO STOP AND ASK ME
- Any gold row, verdict, threshold, validator rule or `output.csv` byte would change.
- StripeWatch's own reasons show `claims a cause` hits.
- A span substring doesn't occur exactly once in its note.
- A feature needs a new runtime dependency, a new LLM call outside Backend A, or a design-token change beyond `--tiger-soft`.
- A static-demo file would contain a secret or local path.

## FINAL REPORT FORMAT (concise bullets)
Per feature: done / skipped, files changed, 3 lines of real test or report output, honest caveat. Then: final gate results, bundle sizes, screenshots list, live-demo URL (or the exact steps to enable it), and the list of new files.
