---
name: stripewatch-eval
description: Use when writing or running StripeWatch tests, the eval harness, the 3-run reproducibility check, the token and cost log, or the submission checklist. Proves the pipeline is correct, trustworthy and reproducible.
---

# StripeWatch eval and proof

Goal: show with real output that the system is correct, grounded, reproducible and cheap to run.

## Instructions
1. Golden anchor first (`tests/test_golden_sample.py`). These three rows must match exactly:
   - Delhi-Jaipur 2024-11-11: 4.17, +35.5%, +21.0%
   - Ahmedabad-Mumbai 2025-01-20: 3.29, +29.5%, +22.5%
   - Mumbai-Pune 2025-09-15: 3.98, +9.2%, +23.6%
2. Core tests: week_of is always a Monday; no look-ahead (change future weeks, past rows stay identical); self excluded from peer average; a route's week 3 uses 2 prior weeks; first week is skipped.
3. Gold set: compare pipeline output to `eval/gold_candidates.csv` (built from context.md section 7). Expect 19 rows: 3 justified (N001 x2, N002 x1) and 16 flagged. Print a confusion table.
4. Adversarial verdict cases (`eval/adversarial_cases.json`, synthetic rows allowed). Each must be rejected:
   - Chennai-Bangalore 2025-03-10 vs N001 (window ended Mar 8)
   - Chennai-Bangalore 2025-03-17 vs N009 (says back to normal)
   - Mumbai-Pune 2025-09-15 vs N006 (no disruption)
   - Mumbai-Pune any week vs N001 or N002 (wrong route)
   - Mumbai-Pune 2025-06-23 vs N003 (peer outlier)
   - Mumbai-Delhi 2025-05-12 vs N003 (rise above the 5-7% cap)
   - Any route vs N004 (out of scope), Mumbai-Delhi vs N005 (no cost effect)
   - Ahmedabad-Mumbai 2025-01-27 vs N002 (outside the festival week)
   Positive controls that must pass: Ahmedabad-Mumbai 2025-01-20 with N002; Chennai-Bangalore 2025-02-24 and 2025-03-03 with N001.
5. Grounding: the checker passes on every real reason, and fails on five corrupted strings (wrong note id, invented percentage, invented cause like "monsoon", wrong date, justified without an id).
6. Sensitivity (`eval/sensitivity.py`): grid over the candidate thresholds; show which gold rows appear or disappear.
7. Reproducibility: run the pipeline 3 times in fresh processes (delete `.chroma/` between runs). Diff every column except `reason`, and compare cited note ids. Save `output/repro_report.md` with hashes and IDENTICAL or the diff.
8. Token log for one cold-cache run: `output/token_log.json` with calls, input tokens, output tokens, model, temperature 0 and cost at the published rate. Use provider usage metadata. If tokens are estimated, mark `"estimated": true`. Never write made-up zeros.
9. Fill `output/SUBMISSION_CHECKLIST.md` from precaution.md Part D, one line of evidence per item.

## Constraints
- Never say a test passed unless you ran it and saw the output. Paste real output into `output/eval_report.md`.
- Never change thresholds or the gold file to make results match. If they differ, stop and report the diff.
- The verdict, matched note id and numbers must be identical on every run; only the wording of `reason` may vary.
