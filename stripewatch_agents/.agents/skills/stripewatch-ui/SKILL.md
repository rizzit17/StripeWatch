---
name: stripewatch-ui
description: Use when building, changing or checking any StripeWatch web screen (Ledger, Route page, Ask) or its CSS, SVG chart, stamps or empty states. Reproduces the approved paper-slip design from design.md exactly.
---

# StripeWatch UI

Goal: build the web UI so it looks exactly like the approved mockups.

## Instructions
1. Read `design.md` in the project root fully before writing any UI code.
2. Create `web/index.html`, `web/app.css` and `web/app.js`.
   - Copy the CSS from design.md section 3 into `app.css` verbatim.
   - Copy the markup for each screen from sections 5, 6 and 7 as the starting point.
3. Load the three Google Fonts from the design.md link: Fraunces, DM Sans and JetBrains Mono.
4. Draw the weekly chart as hand-built inline SVG using the coordinate maths in design.md section 6. No chart library.
5. Fill all rows, notes, rejected-note reasons and answers from `/api/*`. Never hard-code results in the UI.
6. Build order: Ledger, then Route page, then Ask. If time is short, skip Ask (it stays a CLI command).
7. Finish with the visual acceptance test in design.md section 12 and save screenshots to `docs/screens/`.

## Constraints
- No purple or indigo, no gradients, no blurred shadows, no glow, no emoji.
- No React, Tailwind, build step or UI/chart libraries. JS under 12 KB.
- Only these colours: the nine tokens in design.md section 1.
- Verdict stamps always carry words (`FLAGGED`, `JUSTIFIED`); colour is never the only signal.
- Copy voice: plain, short, sentence case, no exclamation marks. Empty state: "No note found. I'd rather say so than guess."
- Respect `prefers-reduced-motion`. Keep keyboard focus visible and rows focusable.
- If a colour fails contrast (4.5:1 for stamp text), tell the user before changing it.
