# StripeWatch: agent instructions

This is a 24-hour FreightTiger AI-intern case study. Build it end to end, carefully.

1. Read `master_prompt.md` first and follow its phases and gates.
2. Then read `context.md`, `prd.md`, `architecture.md` and `systemdesign.md`. Read `design.md` only at the UI phase.
3. `.agents/rules/precaution.md` is always on. Never invent notes, numbers or reasons; never claim a test passed unless you ran it.
4. The LLM only writes wording. Numbers come from pandas; verdicts and cited note ids come from `validate.py`.
5. Skills available: `stripewatch-ui` (screens) and `stripewatch-eval` (tests, repro, token log).
6. If results differ from `context.md` section 7 (19 candidates: 3 justified, 16 flagged), stop and report. Do not change thresholds.
