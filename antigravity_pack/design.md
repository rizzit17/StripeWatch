# design.md — StripeWatch UI spec (pixel-reproducible)

> This file reproduces the 3 approved mockups (Ledger, Route page, Ask). Use the CSS and markup below **verbatim** as the starting point. Do not "improve", re-theme, or swap fonts/colours. Where the spec gives exact values, use exactly those.

## 0. Concept
A warm **paper consignment slip**: ink-black text, one tiger-orange accent, rubber-stamp verdicts, hard-offset flat shadows, a tiny line-drawn truck and three tiger stripes as the only decoration. Calm, small, a little cute — a clerk with a good pencil, not a "dashboard".

**Hard NO list:** purple/indigo/violet anywhere · gradients (the only allowed `radial-gradient` is none — we use none) · blurred shadows, glow, glassmorphism · emoji · sparkle/"AI-powered" copy · identical rounded-card grids · Inter/Roboto look · dark mode by default · stock illustrations · charts libraries · React/Tailwind/build step.

## 1. Tokens (flat colours only) — put at top of `web/app.css`
```css
:root{
  --paper:#F6F0E4;      /* page / frame background */
  --slip:#FFFDF7;       /* cards, slips, table container */
  --ink:#1D1B16;        /* text, borders, shadows */
  --ink-soft:#6B665A;   /* secondary text, axis labels, header cells */
  --rule:#D9D0BC;       /* hairlines, dotted dividers, frame border */
  --tiger:#E4932A;      /* sole accent: stripes, truck cab, active-tab underline */
  --stamp-red:#C8452D;  /* FLAGGED stamp, flagged dots, "need a human" number */
  --stamp-green:#2E7A5B;/* JUSTIFIED stamp, justified rings, "justified" number */
  --highlight:#FBE6A8;  /* row hover, note-id chips, cited-note highlight */
}
```
Colour is never the only signal: every stamp carries words (`FLAGGED` / `JUSTIFIED`); chart dots are paired with legend text.

## 2. Fonts
Load in `<head>` (and `@import` fallback is fine):
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600&family=DM+Sans:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```
| Role | Family | Weight | Used for |
|---|---|---|---|
| Display | `'Fraunces', serif` | 600 | wordmark, page titles, big numbers |
| Body/UI | `'DM Sans', sans-serif` | 400 / 500 | everything else |
| Data | `'JetBrains Mono', monospace` | 400 / 500 | dates, ₹/t-km, %, note ids, stamps, footer |

Fallbacks must keep the page usable offline (system serif / sans / ui-monospace). Only two weights per family; no italics.

## 3. Complete CSS (`web/app.css`) — copy exactly
```css
*{box-sizing:border-box}
html,body{margin:0;background:var(--paper);color:var(--ink);font-family:'DM Sans',sans-serif;font-size:16px;line-height:1.5}
.sw{max-width:980px;margin:0 auto;padding:20px;background:var(--paper)}        /* page frame; on desktop wrap in a 1px var(--rule) border + 12px radius if embedded */
.big{font-family:'Fraunces',serif;font-weight:600}
.mono{font-family:'JetBrains Mono',monospace;font-size:12px}
.sub{margin:0 0 16px;font-size:13px;color:var(--ink-soft)}

/* slip = the one card style */
.slip{background:var(--slip);border:1.5px solid var(--ink);border-radius:4px;box-shadow:3px 3px 0 var(--ink);padding:12px 14px}

/* brand */
.brand{display:flex;align-items:center;gap:10px;margin-bottom:4px}
.brand .name{font-size:22px}
.stripes{display:flex;gap:3px;transform:skewX(-20deg)}
.stripes i{display:block;width:4px;height:16px}
.stripes i:nth-child(odd){background:var(--tiger)}
.stripes i:nth-child(even){background:var(--ink)}

/* stamp verdicts */
.st{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.06em;padding:2px 6px;border:1.5px solid;border-radius:3px;transform:rotate(-3deg)}
.st.flag{color:var(--stamp-red);border-color:var(--stamp-red)}
.st.ok{color:var(--stamp-green);border-color:var(--stamp-green)}
@keyframes thunk{from{transform:scale(1.15) rotate(-4deg);opacity:.2}to{transform:scale(1) rotate(-3deg);opacity:1}}
.st{animation:thunk .12s ease-out 1}

/* note-id chip */
.chip{font-family:'JetBrains Mono',monospace;font-size:11px;border:1px solid var(--ink);border-radius:3px;padding:1px 5px;background:var(--highlight)}
.chip.plain{background:var(--slip)}

/* summary strip */
.summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:18px}
.summary .slip{padding:10px 14px}
.summary .num{font-size:34px;line-height:1.1}
.summary .lbl{font-size:12px;color:var(--ink-soft)}
.num.green{color:var(--stamp-green)} .num.red{color:var(--stamp-red)}

/* filter bar */
.filters{display:flex;gap:12px;align-items:center;margin-bottom:8px;font-size:13px}
.filters label{color:var(--ink-soft)}
.filters select{font:inherit;font-size:13px;width:150px;background:var(--slip);color:var(--ink);border:1px solid var(--ink);border-radius:3px;padding:3px 6px}
.filters .tabs{margin-left:auto}
.filters .tabs button{font:inherit;font-size:13px;background:none;border:0;padding:0 2px;margin-left:10px;color:var(--ink);cursor:pointer}
.filters .tabs button[aria-pressed="true"]{font-weight:500;border-bottom:2px solid var(--tiger)}

/* ledger table */
.ledger{padding:6px 10px}
.ledger table{width:100%;border-collapse:collapse;font-size:13px}
.ledger th{text-align:left;font-weight:500;color:var(--ink-soft);font-size:11px;padding:8px 10px;border-bottom:1.5px solid var(--ink)}
.ledger td{padding:9px 10px;border-bottom:1px dotted var(--rule)}
.ledger tr.r{cursor:pointer}
.ledger tr.r:hover td{background:var(--highlight)}

.footer{margin:14px 0 0;color:var(--ink-soft);font-size:11px}

/* route page */
.route-head{display:flex;align-items:baseline;gap:10px;margin-bottom:12px}
.route-head .title{font-size:22px}
.route-head .tag{border:1px solid var(--ink);padding:0 5px;border-radius:3px}
.route-head .range{color:var(--ink-soft);margin-left:auto}
.chart{margin-bottom:16px}
.legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--ink-soft);font-size:11px}
.legend .g{color:var(--stamp-green)} .legend .r{color:var(--stamp-red)}
.slips{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.slip .row{display:flex;justify-content:space-between;align-items:center}
.slip p{margin:6px 0;font-size:13px;line-height:1.5}
.cited{background:var(--highlight);padding:8px 10px;border-radius:3px;border:1px dashed var(--ink)}
.cited .chip{background:var(--slip)}
.rejected{font-size:12px;color:var(--ink-soft);margin-bottom:0}

/* ask */
.ask-title{font-size:22px;margin-bottom:12px}
.askbox{display:flex;gap:10px;align-items:center;padding:8px 12px;margin-bottom:10px}
.askbox input{flex:1;font:inherit;font-size:14px;border:0;background:transparent;color:var(--ink);outline:none}
.askbox button{font:inherit;font-size:13px;background:var(--ink);color:var(--slip);border:0;border-radius:3px;padding:5px 12px;cursor:pointer}
.examples{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}
.ex{font:inherit;font-size:12px;border:1px dashed var(--ink);border-radius:14px;padding:3px 10px;background:transparent;color:var(--ink);cursor:pointer}
.answer{padding:14px 16px}
.answer p{margin:0 0 6px;font-size:14px;line-height:1.55}
.answer .based{border-top:2px dotted var(--rule);margin-top:10px;padding-top:8px}
.answer .based .k{color:var(--ink-soft)}
.empty{display:flex;align-items:center;gap:10px;margin-top:18px;color:var(--ink-soft);font-size:13px}

/* a11y + motion */
:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.sr-only{position:absolute;left:-9999px}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
@media (max-width:560px){.summary{grid-template-columns:1fr}.ledger{overflow-x:auto}}
```

## 4. Reusable SVG & snippets

**Truck mark (34×20, used in header):**
```html
<svg width="34" height="20" viewBox="0 0 34 20" aria-hidden="true"><rect x="1" y="6" width="17" height="9" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.5"/><path d="M18 8h6l4 4v3H18z" fill="#E4932A" stroke="#1D1B16" stroke-width="1.5"/><circle cx="8" cy="17" r="2.5" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.5"/><circle cx="24" cy="17" r="2.5" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.5"/></svg>
```
**Truck with question flag (34×22, empty / "no evidence" state):**
```html
<svg width="34" height="22" viewBox="0 0 34 22" aria-hidden="true"><rect x="1" y="7" width="17" height="9" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.5"/><path d="M18 9h6l4 4v3H18z" fill="#E4932A" stroke="#1D1B16" stroke-width="1.5"/><circle cx="8" cy="18" r="2.5" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.5"/><circle cx="24" cy="18" r="2.5" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1.5"/><path d="M6 7V1h6l-1.5 2L12 5H7" fill="#FFFDF7" stroke="#1D1B16" stroke-width="1"/></svg>
```
**Brand block:**
```html
<div class="brand">[truck svg]<span class="big name">StripeWatch</span><span class="stripes" aria-hidden="true"><i></i><i></i><i></i></span></div>
<p class="sub">a cost watchdog that doesn't make things up</p>
```
Wheels may rotate (CSS, 6 s linear infinite) **only while loading**; static otherwise; disabled under reduced motion.

## 5. Screen A — The Ledger (route `#/`)
Structure (top to bottom):
```html
<main class="sw">
  <h2 class="sr-only">StripeWatch ledger: N cost rises, J justified and F needing review</h2>
  [brand block]
  <section class="summary">
    <div class="slip"><div class="big num">19</div><div class="lbl">rises spotted</div></div>
    <div class="slip"><div class="big num green">3</div><div class="lbl">justified by a note</div></div>
    <div class="slip"><div class="big num red">16</div><div class="lbl">need a human look</div></div>
  </section>
  <div class="filters">
    <label for="route">Route</label>
    <select id="route"><option>All routes</option>…</select>
    <span class="tabs"><button aria-pressed="true">All</button><button aria-pressed="false">Flagged</button><button aria-pressed="false">Justified</button></span>
  </div>
  <div class="slip ledger"><table>
    <tr><th>Week of</th><th>Route</th><th>₹/t-km</th><th>vs own</th><th>vs peers</th><th>Verdict</th><th>Note</th></tr>
    <tr class="r" tabindex="0">
      <td class="mono">2024-11-11</td><td>Delhi-Jaipur</td><td class="mono">4.17</td>
      <td class="mono">▲ +35.5%</td><td class="mono">+21.0%</td>
      <td><span class="st flag" aria-label="Flagged">FLAGGED</span></td><td>—</td></tr>
    <tr class="r" tabindex="0">
      <td class="mono">2025-01-20</td><td>Ahmedabad-Mumbai</td><td class="mono">3.29</td>
      <td class="mono">▲ +29.5%</td><td class="mono">+22.5%</td>
      <td><span class="st ok" aria-label="Justified by note N002">JUSTIFIED</span></td><td><span class="chip">N002</span></td></tr>
  </table></div>
  <p class="mono footer">notes: 10 · LLM calls: 29 · temp 0 · identical on 3 runs ✓</p>
</main>
```
Rules: use real `<table>`, `<th scope="col">`. Every delta is written with a leading `▲ ` only in the "vs own" column; sign always shown (`+`/`-`, 1 decimal). Number cells are mono. Row click/Enter → `#/route/<route>?week=<week_of>`. Footer values come live from `token_log.json` and `repro_report.md` (show `identical on 3 runs ✓` only if the repro report says IDENTICAL).
Summary numbers come from `/api/summary`; "rises spotted" = candidate rows.

## 6. Screen B — Route page (route `#/route/Chennai-Bangalore`)
```html
<main class="sw">
  <h2 class="sr-only">Route page for Chennai-Bangalore …</h2>
  <div class="route-head"><span class="big title">Chennai-Bangalore</span><span class="mono tag">MEDIUM</span><span class="mono range">Jan to Apr 2025</span></div>
  <div class="slip chart">
    [svg chart]
    <div class="mono legend"><span>━ weekly ₹/t-km</span><span>┅ own 8-week average</span><span class="g">◯ justified</span><span class="r">● flagged</span></div>
  </div>
  <div class="slips">[one .slip per candidate week]</div>
</main>
```
**Chart SVG (hand-built, no library).** `viewBox="0 0 640 190"`, `width="100%"`, `role="img"`, `aria-label` = one-sentence summary. Exact styling:
- Grid: 3 horizontal lines, `stroke="#D9D0BC"`, `stroke-dasharray="2 4"`, from x=40 to x=620.
- Y mapping (mockup): `y = 30 + (3.6 − value) × 100` → ticks 3.6→30, 3.1→80, 2.6→130. For other routes pick 3 "nice" ticks 0.5 apart covering min..max and keep the same 100 px per 1.0 unit scale **if range ≤ 1.6**, otherwise scale to fit 30..130.
- X mapping: `x = 60 + i × (540 / (n − 1))` for week index i of n plotted weeks. Default window = 16 weeks around the first flagged week (user can switch to "all 104 weeks": then drop dots' radius to 4).
- Axis labels: `font-family="JetBrains Mono,monospace" font-size="11" fill="#6B665A"`; y labels at x=4 (y+4); 3 x-labels at y=170.
- Own-average line: `stroke="#6B665A" stroke-width="1.2" stroke-dasharray="5 4" fill="none"` (the 8-prior-week average per week).
- Weekly line: `stroke="#1D1B16" stroke-width="1.8" fill="none"`.
- Flagged week dot: `<circle r="6" fill="#C8452D"/>`. Justified week ring: `<circle r="6" fill="#FFFDF7" stroke="#2E7A5B" stroke-width="2.5"/>`.
- Hover/focus on a dot shows a flat slip tooltip (`.slip` style, 12px mono text: week, ₹/t-km, vs own, vs peers, verdict). Dots are focusable (`tabindex="0"`).
- Under the chart, a `<details><summary>Data table</summary>…</details>` text alternative.

**Evidence slips (one per candidate week):**
Justified:
```html
<div class="slip">
  <div class="row"><span class="mono">week of 2025-03-03</span><span class="st ok" aria-label="Justified by note N001">JUSTIFIED</span></div>
  <p><span class="mono">3.48 ₹/t-km</span> · +22.8% vs own · +32.0% vs peers</p>
  <p class="cited"><span class="chip plain">N001</span> {the note's own text, trimmed to ≤ 2 sentences}</p>
</div>
```
Flagged:
```html
<div class="slip">
  <div class="row"><span class="mono">week of 2025-03-10</span><span class="st flag" aria-label="Flagged">FLAGGED</span></div>
  <p><span class="mono">3.57 ₹/t-km</span> · +22.1% vs own · +33.8% vs peers</p>
  <p>No matching note found. Looks unexplained, worth a human look.</p>
  <p class="rejected">Closest notes I rejected:<br><span class="chip plain">N001</span> window ended Mar 8<br><span class="chip plain">N009</span> says route was back to normal</p>
</div>
```
Text in `.cited` and in "rejected" lines comes from the pipeline (`results.json` → note text + `why_not`), never typed by hand in the UI. If a row has no near-misses, omit the "rejected" paragraph.

## 7. Screen C — Ask (route `#/ask`)
```html
<main class="sw">
  <h2 class="sr-only">Ask screen …</h2>
  <div class="big ask-title">Ask about a route or month</div>
  <div class="slip askbox"><input aria-label="Your question" placeholder="Why did Chennai-Bangalore get pricier in March?"><button>Ask</button></div>
  <div class="examples"><button class="ex">Which routes have no explanation?</button><button class="ex">What happened in Jan 2025?</button><button class="ex">Is Mumbai-Pune still rising?</button></div>
  <div class="slip answer">
    <p>{answer text, ≤ 80 words, grounded}</p>
    <div class="mono based"><span class="k">Based on rows:</span> 2025-02-24 <span class="chip">N001</span> · 2025-03-03 <span class="chip">N001</span> · 2025-03-10 · 2025-03-17</div>
  </div>
  <div class="empty">[truck-with-flag svg]<span>No note found. I'd rather say so than guess.</span></div>
</main>
```
- The input row looks like a slip (hard shadow). The submit button is the only solid-ink filled control in the app.
- The `.empty` line shows ONLY when the answer has no evidence (then hide the `.answer` slip or replace its text with the refusal sentence from `ask.py`).
- Example chips fill the input and submit. Row dates/ids in "Based on rows" link to `#/route/<route>?week=<date>`.
- Show a loading state: truck wheels rotate, text "Looking through the rows…" (ellipsis = in progress only).

## 8. Navigation
No sidebar. A single quiet text row under the brand block: `Ledger · Routes · Ask` (DM Sans 13px, `--ink-soft`; current page `--ink` with `border-bottom:2px solid var(--tiger)`). Routes link opens the route list = the select in the Ledger. Hash router in ~20 lines of vanilla JS.

## 9. Copy voice
Plain, warm, short. Sentence case. No exclamation marks, no emoji, no "AI-generated". Examples: "Looks unexplained, worth a human look." · "Matches note N001 (flood, Feb 24 to Mar 8)." · "No note found. I'd rather say so than guess." Labels have no trailing period; body sentences do.

## 10. Responsive & accessibility
- ≥ 980px: centred 980px column. ≤ 560px: summary becomes 1 column, ledger scrolls horizontally inside its slip, slips stack.
- Semantic HTML; keyboard focus ring `2px solid var(--ink)` offset 2px; rows focusable and activate on Enter; tap targets ≥ 40px on mobile for buttons/chips.
- Contrast: ink on paper/slip ≥ 12:1; stamp text on slip must be ≥ 4.5:1 (verify `#C8452D` and `#2E7A5B` on `#FFFDF7`; if one fails, darken by ≤ 8% lightness and tell the user).
- Respect `prefers-reduced-motion` (no stamp thunk, no wheel spin).

## 11. Implementation constraints
- Files: `web/index.html`, `web/app.css` (section 3 verbatim), `web/app.js` (vanilla, < 12 KB), no frameworks, no build step, no chart/UI libraries, no external assets except the Google Fonts link.
- Data only from `/api/*` (see systemdesign §16). No secrets in the browser.
- Time-box 3 h. Build order: Screen A → Screen B (chart + slips) → Screen C. If behind schedule, drop C (Ask stays CLI).

## 12. Visual acceptance test (do this before calling the UI done)
Seed the UI with the fixtures used in the approved mockups and confirm they look the same:
1. **Ledger:** summary shows `19 / 3 / 16`; five rows — Delhi-Jaipur 2024-11-11 (FLAGGED, —), Ahmedabad-Mumbai 2025-01-20 (JUSTIFIED, N002), Chennai-Bangalore 2025-03-03 (JUSTIFIED, N001), Chennai-Bangalore 2025-03-10 (FLAGGED), Mumbai-Pune 2025-09-15 (FLAGGED). (These are real pipeline rows from `context.md §7`; the UI must render them from `/api/rows`, not hard-coded.)
2. **Route page (Chennai-Bangalore):** two green rings (02-24, 03-03), two red dots (03-10, 03-17), grey dashed own-average line, black weekly line; right slip shows the rejected-notes list (N001 window ended Mar 8; N009 says normal).
3. **Ask:** the March question returns an answer that cites N001 for 02-24 and 03-03, and says 03-10 and 03-17 stay unexplained, with a "Based on rows" line.
4. Take a screenshot of each screen at 980px and 390px wide and save to `docs/screens/` for the README.
5. Check against the NO list in section 0: no purple, no gradients, no blurred shadows, no emoji.
