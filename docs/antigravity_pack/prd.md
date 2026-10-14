# prd.md — Product Requirements: "StripeWatch" (FreightTiger cost watchdog)

## 1. Product
**StripeWatch** is a small assistant that reads shipment records week by week, notices when a route's cost per tonne-km is rising oddly, checks a notes file for a genuine reason, and explains itself in plain English — or says honestly "I couldn't find one."

One-line pitch for the walkthrough: *"It would rather say 'I don't know' than invent a reason."*

## 2. User & use
- **Primary user:** a FreightTiger evaluator/ops analyst reviewing transporter costs.
- **Demo user (the intern, Abhi):** needs a 10-minute walkthrough, so the project must be explainable in 5 diagrams-worth of ideas.

## 3. Goals / Non-goals
**Goals:** correct numbers · no fabricated reasons · identical results on repeat · tiny LLM spend · clean readable code · output CSV matches contract exactly.
**Non-goals:** forecasting, transporter-level analysis, auth, databases beyond the vector store, cloud deployment, fancy charts libraries.

## 4. Requirements checklist (mapped to the PDF — every line must be satisfied)

### 4.1 CORE (must)
| ID | Requirement (from PDF) | Acceptance test |
|---|---|---|
| C1 | Group by route (origin+destination) and by given `route_type` (do not derive buckets) | 7 routes; route_type taken from the column |
| C2 | Cost per tonne-km = total cost / (qty × distance), week by week | Golden rows 4.17 / 3.29 / 3.98 reproduce |
| C3 | Weeks Mon–Sun, `week_of` = Monday; group dates into weeks BEFORE computing | 104 weeks/route; Monday check test |
| C4 | vs own history = trailing 8-week avg, strictly prior weeks, fewer if <8, state in README, no padding | Test with a route's week 3 uses 2 priors; no look-ahead test |
| C5 | vs similar routes = same week, same route_type, other routes only (exclude self) | Test: self excluded; golden % match |
| C6 | Flag rising + out-of-ordinary vs own history or peers | 19 candidates match `context.md §7` |

### 4.2 BONUS / AI (must attempt — it's the point of an *AI* intern role)
| ID | Requirement | Acceptance test |
|---|---|---|
| A1 | Before flagging, check notes for a real reason using retrieval (vector DB / RAG) | Retrieval log shows top-k per candidate |
| A2 | Plain-English explanation per flag, grounded in the retrieved note — not invented | Grounding check passes on 100% of rows |
| A3 | Stretch: ask questions in plain English ("why did Chennai-Bangalore get pricier in March?") and answer from own results | `ask` CLI + UI; refuses when no evidence |

### 4.3 GUARDRAILS (graded harshly)
| ID | Guardrail | Acceptance test |
|---|---|---|
| G1 | Every "justified" verdict cites the exact note; note must match ROUTE and TIME; "no effect" notes don't count | Adversarial tests (see precaution.md) |
| G2 | No supporting note → unexplained. Never guess | Rows 2025-03-10 / 03-17 (Chennai-Bangalore) stay `Yes` |
| G3 | Spot-check-proof: reason text must reflect the note's content and dates; `matched_note_id` filled for justified, blank otherwise | Grounding check |
| G4 | Show an eval harness / labeled set and say why you trusted it | `eval/` + README section |
| G5 | Reproducible: 3 untouched runs → identical flags, numbers, cited note, verdict (wording may vary) | `scripts/repro_check.sh` diff = empty on contract columns |
| G6 | If anything is random: state setting (temperature 0), why, show it doesn't move the verdict | README + repro result |
| G7 | Cost: prefer open-source/free tier; report total input tokens, output tokens, #LLM calls, rough cost at published rate for ONE full run | `output/token_log.json` + README table |

### 4.4 DELIVERABLES (exact list from PDF)
1. Working code (repo).
2. `output/output.csv` matching `sample_output_format_v2.csv` columns/order/types exactly (incl. `matched_note_id`).
3. `README.md`: how it works, how it was built, how we convinced ourselves it's right.
4. Reproducibility check across 3 runs (diff or confirming note) → `output/repro_report.md`.
5. Token/cost log for one full run → `output/token_log.json` (+ table in README).
6. 10-min walkthrough → `docs/WALKTHROUGH.md` (talk track + trade-offs).

## 5. Functional spec (what the app does)
1. `python -m stripewatch run` → reads `data/`, writes `output/output.csv`, `output/weekly_metrics.csv`, `output/results.json`, `output/token_log.json`, `output/retrieval_log.jsonl`.
2. `python -m stripewatch eval` → runs golden/adversarial/grounding tests; prints a score table; writes `output/eval_report.md`.
3. `python -m stripewatch repro` → runs 3 times in fresh processes, diffs, writes `output/repro_report.md`.
4. `python -m stripewatch ask "why did Chennai-Bangalore get pricier in March?"` → answers only from `results.json`.
5. `python -m stripewatch serve` → minimal local web UI (see design.md): Ledger, Route page, Ask box.

## 6. Priorities & time budget (24 h hard limit — be ruthless)
| Priority | Work | Budget |
|---|---|---|
| P0 | Core pipeline + golden tests + output.csv | 4 h |
| P0 | Notes structuring + retrieval + validator + verdicts | 4 h |
| P0 | Eval harness + repro + token log | 3 h |
| P0 | README + walkthrough doc | 2 h |
| P1 | LLM explanations with grounding check + template fallback | 2 h |
| P1 | `ask` stretch | 2 h |
| P2 | Minimal web UI | 3 h |
| Buffer | Final clean-run, zip | 2 h |

If time runs short: cut P2, then `ask`. Never cut P0 or guardrails.

## 7. Success metrics
- Golden 3 rows exact. 19/19 candidate rows match `context.md §7` verdicts.
- 0 fabricated reasons in grounding check; 0 wrong-note matches in adversarial suite.
- 3 runs: byte-identical on the 7 non-reason columns + verdict + note id.
- Whole-file LLM usage ≤ ~40 calls, ≈ $0 on free tier.
