# StripeWatch: 10-Minute Walkthrough Guide

Hi! This guide is written for the Round 2 technical interview. It explains what StripeWatch is, how it was built, why certain choices were made, how we tested it, and what trade-offs were made.

---

## 1. The Problem, in Plain Terms

When companies hire transport trucks to move goods across India, the freight cost usually depends on two things: how far the truck travels, and how much weight it is carrying. Over time, that cost can quietly creep up.

Sometimes a cost increase happens for a completely genuine reason:
* A sudden regional flood blocks the highway, forcing trucks onto a 100 km detour.
* A major festival causes acute driver shortages and temporary surcharges.
* Diesel prices increase nationwide by ₹5/litre.

Other times, a transporter simply hikes rates for no clear reason.

**The goal of StripeWatch:**
Watch shipping records week by week, spot when a route's cost per tonne-kilometre is rising unusually, search a collection of context notes using retrieval (RAG) to see if there is an official reason, and write a plain-English explanation.

**The core rule:**
*"It would rather say 'I don't know' than invent a fake reason."*

---

## 2. End-to-End Pipeline Architecture

StripeWatch is built with a clear separation of duties: **math and business logic are 100% deterministic code; the language model only writes human-friendly phrasing.**

```
shipment_records.csv
        │
        ▼
[ 1. Loader & Schema Validator ] ──► Asserts 2,940 rows, 0 nulls, positive numbers
        │
        ▼
[ 2. Weekly Aggregator ] ──────────► Groups into Monday-aligned weeks; computes c = sum(cost)/sum(tk)
        │
        ▼
[ 3. Baseline Calculator ] ────────► Computes vs_own (trailing <=8 prior weeks, shift(1))
        │                            and vs_peers (same week & type, self-excluded)
        ▼
[ 4. Candidate Detector ] ─────────► Spots 19 candidate anomalies via dual-branch rule
        │
        ▼
[ 5. Vector Retriever (RAG) ] ─────► ChromaDB + SentenceTransformers ranks all 10 context notes
        │
        ▼
[ 6. Deterministic Validator ] ────► Pure Python checks: route, time window, effect, magnitude, scope
        │
        ▼
[ 7. Evidence Packet Builder ] ────► Creates strict JSON of verified facts only
        │
        ▼
[ 8. Explainer & Grounding Guard] ─► Gemini 3.1 Flash Lite (temp 0) rewrites packet;
        │                            ground.py verifies 0 hallucinations before accepting
        ▼
[ 9. Writers & Artifacts ] ────────► output/output.csv (exact match with contract)
                                     output/weekly_metrics.csv, results.json, token_log.json
```

---

## 3. The Seven "Trap Notes" (Why Vector Search Alone Fails)

In the real world, semantic search will pull up documents that sound relevant even when they do not explain the problem.

`context_notes.csv` has 10 notes. Only 3 can ever justify a cost rise:
* **N001:** Chennai-Bangalore flood (Feb 24 to Mar 8, 2025) — **JUSTIFIED**
* **N002:** Ahmedabad-Mumbai festival surcharge (week of Jan 20, 2025) — **JUSTIFIED**
* **N003:** Nationwide diesel hike (May 5 to Jun 29, 2025, capped at ~7%) — **JUSTIFIED (with limits)**

The remaining **7 notes are deliberate traps**:
1. **N004 (Toll Plaza):** Located on a corridor not present in our dataset.
2. **N005 (Mumbai-Delhi Maintenance):** Note explicitly states carriers confirmed trip costs were *not* affected.
3. **N006 (Quarterly Report):** Notes stable demand with *no major disruptions*.
4. **N007 (Delhi-Jaipur Bypass):** Bypass completed; improved road conditions and *lowered* costs.
5. **N008 (Kolkata-Bhubaneswar Rain):** Pre-monsoon showers occurred, but freight movement continued *as normal*.
6. **N009 (Chennai-Bangalore Reopening):** Highway reopened to normal on Mar 17; marks the *end* of the disruption, so it cannot justify a rise.
7. **N010 (Vehicle Tracking Mandate):** Compliance costs were *absorbed internally without a rate change*.

**How StripeWatch solves this:**
Retrieval surfaces the top 3 notes for every candidate row. But our deterministic validator (`validate.py`) applies 5 sequential checks:
1. `effect == "raises"` (rejects N005, N006, N007, N008, N009, N010)
2. `scope == route or scope == "ALL"` (rejects N004)
3. `start <= week_end and end >= week_start` (rejects N001 for weeks after March 8)
4. `vs_own_pct <= mag_max + 3% tolerance` (rejects N003 if a route rose +11.6%)
5. `not (scope == "ALL" and vs_peer >= 20%)` (rejects N003 if a route is an outlier above peers)

---

### 3.1 The 2-Minute Live Attack Demonstration ("Try to Fool It" Console)

In a live interview, we can open the web UI at `#/fool` and invite the evaluator to attack the validator:
* **Preset 1 (Chennai-Bangalore 2025-03-10 + N001 — The Expired Disruption Attack):**
  A naive LLM or human reviewer would think: *"There was a flood in Chennai recently, so this spike must be justified."*
  StripeWatch's 5-stage gate checks the exact factual window: N001's flood disruption window ended on **March 8, 2025**. The consignment week started on **March 10, 2025**.
  * Check 1 (Effect describes rise): **PASS**
  * Check 2 (Route in scope): **PASS**
  * Check 3 (Window overlaps week): **FAIL** (*Window ended 2025-03-08, week started 2025-03-10*)
  * Check 4 (Magnitude within tolerance): **PASS**
  * Check 5 (Universal note peer outlier): **PASS**
  * **Final Verdict:** **REJECTED** — the anomaly remains flagged as unexplained.
* **Preset 8 (Ahmedabad-Mumbai 2025-01-20 + N002 — The Grounded Control):**
  Festival surcharge week matches corridor, active dates (Jan 20–26), and magnitude.
  * All 5 checks **PASS** → **JUSTIFIED** stamp.

---

### 3.2 The 60-Second "Paper Trail and Highlight" Segment

On every consignment slip on the Route page, StripeWatch displays an auditable **5-ticket paper trail**:
$$\text{Spotted} \longrightarrow \text{Searched} \longrightarrow \text{Route} \longrightarrow \text{Window} \longrightarrow \text{Effect and Size}$$

* **Auditability at a Glance:** For justified rises, all 5 tickets show green `PASS` stamps. For unexplained rises, StripeWatch displays the paper trail for the **closest rejected note** (e.g. `N001` on Chennai-Bangalore 2025-03-10), marking the exact failing ticket with a red `FAIL` stamp and leaving subsequent checks un-evaluated (`—`).
* **Evidence Highlighting (`<mark>`):** Notes are rendered in their raw, unaltered text with hand-authored exact substrings wrapped in `<mark>`:
  * Justified notes highlight key **evidence spans** (e.g. *"Heavy flooding on the Chennai-Bangalore highway"*).
  * Rejected notes highlight the exact **negating spans** (e.g. *"costs were not significantly affected"* or *"Roads were passable again by Mar 9"*) paired with a small mono `why rejected` badge.

---

### 3.3 The 60-Second "Plain LLM vs StripeWatch" Benchmark

What happens if an engineering team simply feeds shipment numbers to a standard LLM without deterministic validation? We ran a controlled benchmark (`eval/hallucination_report.md`) prompting Gemini on all 16 unexplained rows without context notes:
* **Naive LLM (No Notes):** In **16 out of 16 rows (100.0%)**, the plain LLM invented a plausible external cause (diesel price hikes, monsoon flooding, driver shortages, GST compliance). It never once stated it lacked evidence.
* **Catch Rate by StripeWatch Grounding Checker:** **16 out of 16 (100.0%)** of the naive LLM's hallucinated explanations were caught and rejected by our factual grounding guardrail.
* **StripeWatch Pipeline:** In all 16 unexplained rows, StripeWatch asserted **zero unsupported causes (0.0%)**, honestly abstaining and flagging the rise for human review.

---

### 3.4 Fallback Talk Track: The Guided Product Tour

If interview time is limited or the evaluator prefers an interactive walkthrough, click **"Take the tour"** in the top navigation or navigate to `?tour=1`:
* Six interactive coach marks step through:
  1. **Summary Strip:** Highlighting the abstention stat (16 left unexplained on purpose).
  2. **The Ledger:** Keyboard navigation (`j`/`k`, `Enter`).
  3. **Route Chart & Scrubber:** Dragging the SVG truck across 104 weeks to inspect live baselines.
  4. **The 5-Step Paper Trail:** Verifying the deterministic checks.
  5. **Try to Fool It:** Testing live adversarial attacks.
  6. **Token & Repro Footer:** Confirming zero temperature drift and 3-run determinism.


---

## 4. The Numbers (Reproduced Exactly)

### The 3 Golden Anchor Rows
The case study gave us `sample_output_format_v2.csv` with 3 sample rows. We verified that our pipeline matches them to the exact precision:
* **Delhi-Jaipur (2024-11-11):** 4.17 ₹/t-km | +35.5% vs own | +21.0% vs peers | **Yes** (unexplained)
* **Ahmedabad-Mumbai (2025-01-20):** 3.29 ₹/t-km | +29.5% vs own | +22.5% vs peers | **No (justified)** (N002)
* **Mumbai-Pune (2025-09-15):** 3.98 ₹/t-km | +9.2% vs own | +23.6% vs peers | **Yes** (unexplained)

### The Money Segment (Excess-Spend Prioritization)
A percentage rise alone does not tell a supply chain director where to look first. A +15% rise on a high-volume corridor costs far more than a +30% rise on a minor route.
StripeWatch calculates the estimated excess spend in Rupees for every route-week:
$$\text{excess\_inr} = \max(0, (c - \text{own\_avg}) \times \text{tonne\_km})$$
Across the 19 candidates:
* **Unexplained Anomaly Spend:** **₹1,28,126** (~₹1.28 lakh) of genuine financial leakage that procurement should audit immediately.
* **Justified Disruption Spend:** **₹77,959** (~₹78k) accounted for by verified real-world events.
*(Note: As baseline drifts upward during chronic multi-month creep like Mumbai-Pune, own-average excess spend understates long-term cumulative inflation, making the early-warning peer gap essential).*

### The Overall Outcome: 19 Candidate Rows
Out of 721 evaluable route-weeks, our dual-branch rule detects exactly **19 candidates**:
* **3 Justified Rows:**
  * `Ahmedabad-Mumbai 2025-01-20` → Justified by **N002** (festival surcharge)
  * `Chennai-Bangalore 2025-02-24` → Justified by **N001** (flooding week 1)
  * `Chennai-Bangalore 2025-03-03` → Justified by **N001** (flooding week 2)
* **16 Flagged Rows:**
  * `Chennai-Bangalore 2025-03-10` & `03-17`: Flooding ended March 8. The assistant honestly refuses to excuse these subsequent weeks and flags them as unexplained.
  * `Delhi-Jaipur Nov-2024`: Sharp spike (+35.5% and +27.6%) with no note in dataset. Flagged.
  * `Mumbai-Pune (Jun to Dec 2025)`: Steady creep (+20% to +38% above its peer `Delhi-Jaipur`). Flagged.

---

## 5. How We Convinced Ourselves It's Right (Trust & Eval)

We wrote a dedicated test suite with `pytest` and an evaluation harness (`eval/run_eval.py`):
1. **Golden Anchor Test:** Verifies the 3 sample rows match exact numbers.
2. **Gold Candidates Set Test:** Verifies all 19 rows match the expected verdicts and cited note IDs.
3. **No-Look-Ahead Leakage Test:** We modified future shipment records from June 2024 onwards and asserted that historical weekly baselines for earlier weeks remained identical.
4. **Peer Self-Exclusion Test:** Proved that on Short routes (where only 2 routes exist), `Mumbai-Pune`'s peer baseline equals `Delhi-Jaipur`'s weekly unit cost.
5. **Adversarial Suite (16 cases):** Unit tests verifying that every single trap note is correctly rejected when presented with mismatched dates, wrong routes, or unapproved magnitudes.
6. **Grounding Invariant Suite:** Tested that all 19 produced explanations contain zero hallucinations, and that 5 synthetic corruptions (fake note ID `N999`, invented `+78.5%` figure, invented future date `2029-08-15`, missing note ID, or missing unexplained phrase) are 100% caught and rejected.
7. **Synthetic Injection Benchmark (`eval/synthetic_bench.py`):** Injected 60 spikes into clean route-weeks in memory (20 valid notes, 20 decoy notes, 20 no notes). Result: **0 decoys wrongly justified (100% precision)**.
8. **Provider Ablation (`stripewatch/ablation.py`):** Verified byte-for-byte identical numbers and verdicts between deterministic template mode and Gemini LLM mode.
9. **Reproducibility Test:** Ran the pipeline 3 separate times in fresh processes (clearing disk cache between runs) and verified via SHA-256 that all numerical outputs and verdicts are identical.


---

## 6. Token Usage & Operating Cost

StripeWatch was designed to be practically free to run:
* **Model:** Google Gemini 3.1 Flash Lite (free tier via official `google-genai` SDK)
* **Temperature:** `0.0` (deterministic)
* **Total LLM Calls for a Full Run:** 19 calls (1 call per candidate row)
* **Input Tokens:** 4,979
* **Output Tokens:** 923
* **Actual Spend:** **$0.00**
* **Notional Cost at Published Pay-As-You-Go Rates:** **$0.00065** (under 1/10th of a single US cent)
* **Caching:** Every call is hashed by SHA-256 (`model + temp + max_tokens + prompt`). Any subsequent run takes 0 ms and uses 0 tokens.

---

## 7. Assumptions & Trade-offs We Made

1. **A1 (First-Week History):** The first week of every route has zero prior weeks ($n\_prior = 0$). We do not extrapolate or pad with arbitrary numbers; we treat them as non-evaluable and exclude them from candidate flagging.
2. **A2 (Festival Window):** Note N002 applies to the festival week corresponding to the week of its date (2025-01-20).
3. **A3 (Diesel Shock Duration):** Note N003 is assumed to remain visible against trailing own history for up to 8 weeks (until 2025-06-29), provided the cost rise is within tolerance ($\le 10\%$) and the route is not an outlier above its peers.
4. **A4 (Small Peer Groups):** There are only 7 routes in the dataset. Short and Long tiers have only 2 routes each. That means for a Short route, its peer average is simply the other short route. This makes peer averages naturally noisy.
5. **A5 (Threshold Choices):** We chose $+8.0\%$ for strong rises, $+5.0\%$ for soft rises, and $+20.0\%$ for peer gaps. Our sensitivity analysis shows that strong anomalies are invariant across a wide range of thresholds.

---

## 8. What We Would Build Next

If given more time and production data:
1. **Transporter-Level Decomposition:** Attribute cost anomalies between fuel indexation, loading weight efficiency, and transporter markup.
2. **Automated Structured Note Ingestion:** An automated pipeline that extracts scope, date windows, and disruption magnitude from unstructured carrier notices with human-in-the-loop validation.
3. **Dynamic Peer Weighting:** Weight peer routes by shipment volume and lane similarity rather than simple unweighted averages.
