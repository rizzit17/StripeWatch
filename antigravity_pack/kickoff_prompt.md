# kickoff_prompt.md — paste this into Antigravity (after dropping all files into the workspace)

```
Build the FreightTiger case-study project end to end.

Workspace contains: master_prompt.md, precaution.md, context.md, prd.md, architecture.md, systemdesign.md, design.md, and the 4 given files (shipment_records.csv, context_notes.csv, sample_output_format_v2.csv, FreightTiger_Intern_CaseStudy.pdf).

Do this, in order:
1. Read master_prompt.md fully, then precaution.md, context.md, prd.md, architecture.md, systemdesign.md. Read design.md when you reach the UI phase.
2. Open the 3 CSVs and the PDF and confirm the facts in context.md (row counts, 7 routes, 104 weeks, the 3 golden sample rows). If anything differs, stop and tell me.
3. Reply with a 10-line plan, then start Phase 0 and follow the phases and gates in master_prompt.md.
4. Re-read precaution.md at every gate. Never claim a test passed unless you ran it. Never invent notes, numbers or reasons. The LLM only writes wording; numbers come from pandas and verdicts from validate.py.
5. If results differ from context.md §7 (19 candidates: 3 justified, 16 flagged), stop and report the diff — do not change thresholds.
6. Ask me only for: which free LLM provider/key to use (default LLM_PROVIDER=none), or if a download is blocked.

Finish with: output/output.csv, README.md, eval + repro reports, token_log.json, docs/WALKTHROUGH.md, output/SUBMISSION_CHECKLIST.md.
```
