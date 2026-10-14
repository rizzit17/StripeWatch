# StripeWatch — Smart Freight Cost Watchdog

[![StripeWatch CI](https://github.com/rizzit17/StripeWatch/actions/workflows/ci.yml/badge.svg)](https://github.com/rizzit17/StripeWatch/actions/workflows/ci.yml)

> A clean, trustworthy assistant built for the FreightTiger AI Intern Case Study. It monitors weekly freight costs per tonne-km, flags unexpected cost spikes, checks context notes for genuine real-world explanations, and explains its findings in plain English — without hallucinating.
>
> *Built with the assistance of AI coding tools; all architectural trade-offs, edge-case defenses, and core design decisions are documented in [`docs/DECISIONS.md`](docs/DECISIONS.md).*

---

## Quickstart (Run in 3 Commands)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the pipeline (reads data/, writes output/output.csv & artifacts)
python -m stripewatch run

# 3. Verify evaluation benchmarks and reproducibility
python -m stripewatch eval && python -m stripewatch repro
```

*Optional: Ask questions or launch the web UI:*
```bash
# Ask plain-English questions grounded in results
python -m stripewatch ask "Why did Chennai-Bangalore get pricier in March?"

# Launch the local web UI (Ledger, Interactive SVG Chart, Q&A)
python -m stripewatch serve
# Opens at http://localhost:8000
```

---

## 1. What It Does (The Core Problem)

Companies pay transporters to ship goods across corridors. The unit cost is measured in **₹ per tonne-km**:
$$\text{Cost per tonne-km} = \frac{\text{Total Freight Cost (INR)}}{\text{Weight (Tonnes)} \times \text{Distance (km)}}$$

Over time, that cost can quietly creep up on certain corridors.
* **Sometimes there is a real reason:** A bridge was flooded forcing a long detour, or a regional festival caused driver shortages and temporary surcharges.
* **Sometimes there is no reason at all:** A transporter just hiked rates, or fuel surcharges were misapplied.

StripeWatch watches shipments week by week, flags unusual rises against the route's own past average and similar-length peer routes, checks a collection of context notes using retrieval (RAG) to see if there is an official reason, and writes a short, plain-English explanation.

**The Golden Principle:**
*Numbers come from pandas. Verdicts come from deterministic code. The LLM only writes wording — and every explanation is strictly checked to guarantee zero hallucinated reasons.*

---

## 2. Key Results at a Glance

| Metric / Check | Value | Status |
|---|---|:---:|
| Total Shipment Records | 2,940 shipments (0 nulls, 0 duplicate IDs) | **VERIFIED** |
| Active Corridors | 7 routes (2 Short, 3 Medium, 2 Long) | **VERIFIED** |
| Weekly Aggregates | 728 route-weeks (all Monday-start) | **VERIFIED** |
| Evaluable Route-Weeks | 721 (7 first-weeks dropped; no prior history) | **VERIFIED** |
| **Golden Anchor Row 1** (Delhi-Jaipur 2024-11-11) | 4.17 ₹/t-km \| +35.5% vs own \| +21.0% vs peers | **EXACT MATCH** |
| **Golden Anchor Row 2** (Ahmedabad-Mumbai 2025-01-20) | 3.29 ₹/t-km \| +29.5% vs own \| +22.5% vs peers | **EXACT MATCH** |
| **Golden Anchor Row 3** (Mumbai-Pune 2025-09-15) | 3.98 ₹/t-km \| +9.2% vs own \| +23.6% vs peers | **EXACT MATCH** |
| **Total Candidates Spotted** | **19 candidate route-weeks** | **100% MATCH** |
| **Justified Rises** | **3 rows** (N001 x 2, N002 x 1) | **100% MATCH** |
| **Unexplained Rises** | **16 rows** (`flagged=Yes`, blank note ID) | **100% MATCH** |
| **Reproducibility** | 3 untouched runs $\rightarrow$ Byte-for-byte identical output CSV | **IDENTICAL** |

### Evaluation Criteria Scorecard (FreightTiger Case Study Rubric)

| Criterion (Case Study Brief) | How StripeWatch Fulfills It | Deliverable / Test |
|---|---|:---:|
| **1. Does the core logic work?** | Grouping by route & `route_type`, ratio of sums $\frac{\sum \text{cost}}{\sum (\text{qty} \times \text{dist})}$, Monday alignment, trailing 8 prior weeks (`shift(1)`), self-excluded peer average. | [`tests/test_golden_sample.py`](tests/test_golden_sample.py) (All 3 golden rows exact) |
| **2. Did you use AI meaningfully?** | ChromaDB + SentenceTransformers vector store for context notes; grounded LLM rewriting of factual evidence packets. | [`stripewatch/retrieve.py`](stripewatch/retrieve.py) & [`stripewatch/explain.py`](stripewatch/explain.py) |
| **3. Can we trust it?** | 5-step deterministic validator (`validate.py`). Traps N004–N010 are retrieved and rejected; zero invented reasons. | [`tests/test_adversarial.py`](tests/test_adversarial.py) & [`tests/test_grounding.py`](tests/test_grounding.py) |
| **4. Does it hold up on repeat?** | 3 untouched runs in fresh subprocesses produce identical flags, numbers, verdicts, and CSV hashes. | [`output/repro_report.md`](output/repro_report.md) |
| **5. Did you run it responsibly?** | Gemini 3.1 Flash Lite (`temp=0.0`), 19 calls, 5,514 in / 687 out tokens, $0 spend on free tier ($0.00062 notional). | [`output/token_log.json`](output/token_log.json) |
| **6. Is the code clean?** | 14 small typed modules, type hints, docstrings, zero dead code, 100% pytest pass rate. | [`stripewatch/`](stripewatch/) & [`tests/`](tests/) |
| **7. Can you explain your work?** | Clear narrative: problem $\rightarrow$ pipeline $\rightarrow$ trap notes $\rightarrow$ trust $\rightarrow$ cost $\rightarrow$ trade-offs. | [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md) & [`docs/DECISIONS.md`](docs/DECISIONS.md) |


---

## 3. How It Works (Pipeline Architecture)

```
shipment_records.csv
        │
        ▼
[ 1. loader.py ] ───────► Validates schema, no nulls, positive numbers
        │
        ▼
[ 2. weekly.py ] ───────► Groups into Monday-aligned weeks (ratio of sums)
        │
        ▼
[ 3. baselines.py ] ────► vs_own (trailing <=8 weeks, shift(1) no look-ahead)
        │                 vs_peer (same week & type, self-excluded)
        ▼
[ 4. detect.py ] ───────► Detects 19 candidates via dual-branch rule
        │
        ▼
[ 5. retrieve.py ] ─────► ChromaDB + SentenceTransformers ranks all 10 context notes
        │
        ▼
[ 6. validate.py ] ─────► 5 deterministic checks: route, time window, effect, magnitude, scope
        │
        ▼
[ 7. evidence.py ] ─────► Assembles factual evidence packet (JSON)
        │
        ▼
[ 8. explain.py ] ──────► Rewrites packet into concise plain English
        │                 ground.py verifies 100% adherence; falls back to template if failed
        ▼
[ 9. writer.py ] ───────► output/output.csv (exact contract match with sample_output_format_v2.csv)
```

### The 5-Check Deterministic Validator
Language models often make mistakes with dates, numbers, or subtle wording. In StripeWatch, whether a rise is **justified** or **unexplained** is never decided by an LLM. It is decided by `validate.py` using 5 strict checks:
1. **Effect Check:** The note must explicitly state it *raises* costs (`effect == "raises"`). Notes stating costs were "normal" or "not affected" are rejected.
2. **Route Scope:** The note must apply specifically to that corridor, or be a nationwide notice (`scope == "ALL"`).
3. **Time Window Overlap:** The note's disruption window must overlap the target Monday–Sunday week. For example, flooding note N001 ended on March 8, 2025; subsequent weeks starting March 10 and 17 are rejected and left unexplained.
4. **Magnitude Plausibility:** If a note mentions a percentage impact (e.g. diesel N003 mentions ~5–7%), a +11.6% rise exceeds the cap (7% + 3% tolerance) and is rejected.
5. **Universal Outlier Rule:** A nationwide shock hits all routes. If a corridor is +20% *above its peers*, a nationwide note cannot be the primary cause.

---

---

## 4. Trust & Anti-Hallucination Framework

### High Abstention by Design (The Abstention Stat)
> **"Left 16 of 19 unexplained on purpose: only 3 of 10 notes can justify a rise."**  
> *High abstention is the design, not a bug.*

A confident wrong answer in freight auditing is catastrophic: falsely attributing a rate spike to "monsoon flooding" when floodwaters receded days earlier leads shippers to overpay transporters without investigation. StripeWatch abstains whenever real-world evidence is absent.

### Hallucination Baseline Benchmark (`eval/hallucination_report.md`)
To measure the real-world risk of an ungrounded LLM, we evaluated a standard LLM prompted without context notes on all 16 unexplained cost spikes against StripeWatch:

| Evaluation Metric | Naive LLM (No Notes) | StripeWatch Pipeline |
|---|:---:|:---:|
| **Sample Size (Unexplained Rows)** | 16 | 16 |
| **Asserted Unsupported Causes** | **16 / 16 (100.0%)** | **0 / 16 (0.0%)** |
| **Hedged / Stated Insufficient Info** | 0 / 16 (0.0%) | 16 / 16 (100.0%) |
| **Caught by StripeWatch Grounding Checker** | **16 / 16 (100.0%)** | N/A (0 violations) |
| **Unsupported Cause Rate** | 100.0% | **0.0%** |

*Key finding:* When asked why freight costs rose on an unexplained week, an ungrounded LLM invents plausible external causes (diesel hikes, driver shortages, seasonal monsoon demand) 100% of the time. StripeWatch's strict 5-stage validator and grounding checker eliminate hallucinated causes entirely.

---

## 5. The 7 "Trap Notes" in the Dataset

Out of the 10 context notes in `context_notes.csv`, **7 are deliberate semantic traps**. Semantic vector search will rank them near the top because they mention keywords like "disruption", "maintenance", "rain", or route names. StripeWatch's validator systematically catches and rejects all 7:

* **N004 (Toll Plaza):** Located on a corridor not in our dataset. Rejected by route scope.
* **N005 (Mumbai-Delhi Maintenance):** Carriers confirmed trip costs were *not significantly affected*. Rejected by effect check.
* **N006 (Quarterly Report):** Notes stable demand with *no major disruptions*. Rejected by effect check.
* **N007 (Delhi-Jaipur Bypass):** New bypass completed, which *improved* road conditions and *lowered* turnaround times. Rejected by effect check.
* **N008 (Kolkata-Bhubaneswar Rain):** Pre-monsoon showers occurred, but freight continued *as normal*. Rejected by effect check.
* **N009 (Chennai-Bangalore Reopening):** Highway reopened to full traffic; marks the *end* of the disruption. Rejected by effect check.
* **N010 (Vehicle Tracking Mandate):** Compliance costs were *absorbed internally without a rate change*. Rejected by effect check.

---

## 6. Token Usage and Operating Cost

StripeWatch uses Google Gemini 3.1 Flash Lite (`temperature=0.0`) with disk caching. Token counts are recorded directly from the provider's API usage metadata.

| Metric | Measured Value |
|---|---|
| **Model** | `gemini-3.1-flash-lite` |
| **Sampling Temperature** | `0.0` (fully deterministic) |
| **Total LLM Calls (Cold Cache Full Run)** | 19 calls |
| **Prompt Input Tokens** | 5,514 tokens |
| **Completion Output Tokens** | 687 tokens |
| **Grounding Rejections** | 0 (all 19 generated explanations passed grounding) |
| **Actual Cash Spend** | **$0.00** (Free tier) |
| **Notional Cost at Published Pay-As-You-Go Rates** | **$0.00062** (< 1/10th of one US cent) |
| **Cached Re-Run Calls / Spend** | 0 calls / $0.00 (SHA-256 disk cache) |

---

## 7. Assumptions (A1–A5)

We state all assumptions openly rather than hiding them in code:
* **A1 (First Week Non-Evaluable):** The first calendar week for each route has zero prior historical weeks ($n\_prior = 0$). We do not pad with fake zeroes or extrapolate; we treat them as non-evaluable and exclude them from candidate anomaly detection.
* **A2 (Festival Window):** Context note N002 specifies a regional festival surcharge on Ahmedabad-Mumbai. We assume the window corresponds to the week of the note's date (week of 2025-01-20).
* **A3 (Diesel Shock Duration):** Note N003 describes a nationwide diesel hike starting 2025-05-05. We assume this rise remains visible against trailing own history for up to 8 weeks (until 2025-06-29), only if the rise is within magnitude tolerance ($\le 10\%$) and the route is not an outlier above peers.
* **A4 (Small Peer Groups):** The dataset contains only 7 routes. Short has 2 routes, Long has 2 routes, and Medium has 3 routes. This means for Short or Long routes, the peer average is literally the single other route in that tier. Peer comparisons are inherently noisier than own-history baselines.
* **A5 (Threshold Choice):** We chose $+8.0\%$ for strong own rises, $+5.0\%$ for soft own rises, and $+20.0\%$ for peer gaps. Our sensitivity analysis shows that core anomalies (Delhi-Jaipur spike, Ahmedabad festival, Chennai flood) are stable across thresholds from 6% to 10%.

---

## 8. Known Limitations

1. **Small RAG Corpus:** With only 10 notes, vector retrieval is small. However, structuring the RAG pipeline with ChromaDB and SentenceTransformers proves the architecture is ready to scale to thousands of carrier notices.
2. **Tiny Peer Groups:** With only 2 routes in the Short tier (`Mumbai-Pune` and `Delhi-Jaipur`), peer averages reflect pairwise route dynamics rather than broad market trends.
3. **Weekly Shipment Volume:** Weekly figures rest on 3–5 shipments, so single-week rises are noisy. Multi-week sustained creep is tracked via our rolling 4-week peer gap early warning.
4. **Baseline Sample Size:** The hallucination baseline evaluates $n = 16$ unexplained rows with a targeted lexicon; it demonstrates the real risk of ungrounded LLM inference rather than a universal rate across all logistics corridors.
5. **Static Demo Scope:** The web demo snapshot compiles precomputed evaluation matrices and JSON datasets without running a live backend model in the browser.

---

## 9. Beyond the Brief (Trust & UI Differentiators)

All supplementary differentiators are fully deterministic, require **zero new LLM calls** in the main pipeline (cost remains $0.00), and leave the core 19-row gold contract (`output/output.csv`) 100% byte-identical.

| Feature | What It Shows | What It Proves (and Doesn't) | File / Artifact |
|---|---|---|---|
| **Hallucination Baseline** | Direct comparison of ungrounded LLM vs StripeWatch on 16 unexplained rows | Proves plain LLMs hallucinate causes 100% of the time, caught 100% by grounding checker | [`eval/hallucination_report.md`](eval/hallucination_report.md) |
| **Human Review Queue** | Consignment audit workflow cycling `OPEN` / `CONFIRMED` / `DISMISSED` + 280-char notes | Lets auditors act on flags; stored in `.state/review_state.json` without modifying contract verdicts | [`stripewatch/review.py`](stripewatch/review.py), `output/review_export.csv` |
| **Abstention Metric** | Quantifies intentional abstention: 16/19 unexplained because 7/10 notes cannot justify | Proves high abstention is architectural intent, not a missing retrieval recall issue | `output/results.json`, [`stripewatch/paper_trail.py`](stripewatch/paper_trail.py) |
| **Lorry Calendar Heatmap** | 104-week SVG heatmap grouping 7 corridors by distance tier with candidate cells | Spots cross-corridor patterns (e.g. 4-week Chennai flood, late 2025 Mumbai-Pune creep) | Screen `#/calendar`, [`stripewatch/server.py`](stripewatch/server.py) |
| **Paper Trail Strip** | 5-ticket verification strip: `Spotted → Searched → Route → Window → Effect & Size` | Explains why closest notes were rejected with exact failing criteria; 0 hallucinations | Screen `#/route/...`, [`stripewatch/paper_trail.py`](stripewatch/paper_trail.py) |
| **Evidence & Negating Spans** | Text highlight wrapping exact substrings in `<mark>`: evidence vs negating reason | Gives auditable proof of why each note passed or failed without text generation | [`data/notes_structured.json`](data/notes_structured.json), Screen `#/notes` |
| **Week Scrubber Slider** | Draggable SVG truck marker stepping through 104 weeks with keyboard/touch support | Live week slip updates ₹/t-km, peer average, and anomaly status across any calendar week | Screen `#/route/...`, [`web/app.js`](web/app.js) |
| **Consignment Print Docket** | Clean `@media print` layout formatting evidence slips as physical consignor dockets | Produces verifiable audit paper dockets with perforation styling and run checksums | [`docs/screens/docket_Chennai-Bangalore_2025-03-10.pdf`](docs/screens/docket_Chennai-Bangalore_2025-03-10.pdf) |
| **Interactive Guided Tour** | 6-step coach mark tour explaining the UI, anomaly detection, and validation engine | Onboards non-technical users in 60 seconds with keyboard navigation (`Esc`, `j`/`k`, `?`) | Query `?tour=1`, [`web/app.js`](web/app.js) |
| **Static Demo Build** | Self-contained static bundle in `dist/` (< 2MB) with precomputed bitmask matrix | "Try to fool it" works completely offline without backend servers or API keys | [`scripts/build_static.py`](scripts/build_static.py), `dist/` |
| **Live Attack Console** | Evaluator playground exposing 5-stage validation against adversarial trap notes live | Demonstrates why decoys fail (window expired, no cost effect, wrong route, magnitude cap) | [`stripewatch/server.py`](stripewatch/server.py), `#/fool` |
| **Excess-Spend Estimation** | Prioritization by estimated rupee loss: $\max(0, (c - own\_avg) \times \text{tonne\_km})$ | Quantifies business impact (₹1.28L unexplained vs ₹78k justified) | [`stripewatch/baselines.py`](stripewatch/baselines.py), `output/weekly_metrics.csv` |
| **Context Notes Register** | Visual register of all 10 notes with rationale chips and justification stamps | Proves why only 3/10 notes can ever justify rises; doesn't invent external reasons | Screen `#/notes`, [`notes_structured.json`](data/notes_structured.json) |
| **Corridor Attribution** | Aggregates corridor episodes across transporters and materials | Reveals whether an unexplained rise is route-wide or concentrated without speculating | [`stripewatch/attribution.py`](stripewatch/attribution.py), `output/results.json` |
| **Synthetic Spike Benchmark** | Injects 60 controlled spikes (valid, decoy, none) in memory | Proves zero false justifications on decoy notes (0/20); small injections (<8%) missed | [`eval/synthetic_bench.py`](eval/synthetic_bench.py), [`eval/synthetic_report.md`](eval/synthetic_report.md) |
| **Retrieval Evaluation** | Dense (ChromaDB + all-MiniLM-L6-v2) vs Sparse (TF-IDF) comparison | Proves "Retrieval ranks, validator decides": trap notes ranked high are safely rejected | [`eval/retrieval_eval.py`](eval/retrieval_eval.py), [`eval/retrieval_report.md`](eval/retrieval_report.md) |
| **Creep Early-Warning** | Rolling 4-week peer gap ($\ge 15\%$) + standard deviation z-score | Flags sustained compound drift (Mumbai-Pune tagged 2025-09-22); supplementary | [`stripewatch/baselines.py`](stripewatch/baselines.py) |
| **Provider Ablation** | Side-by-side run of Deterministic Templates vs Gemini LLM | Proves exact byte-for-byte verdict and number invariance; LLM only writes wording | [`stripewatch/ablation.py`](stripewatch/ablation.py), [`output/ablation_report.md`](output/ablation_report.md) |
| **Weekly Watch Mode** | CLI command `python -m stripewatch watch --week YYYY-MM-DD` | Simulates production operation on incoming Monday batches without full recomputation | [`stripewatch/watch.py`](stripewatch/watch.py) |

---

## 10. Live Demo & Static Hosting

A zero-backend static demo is pre-compiled into `dist/` (1.2 MB, < 5 MB budget). It runs directly in the browser via GitHub Pages or Netlify without requiring Python or API keys:

* **Live Demo URL:** `https://rizzit17.github.io/StripeWatch/` *(or deployed via Netlify)*
* **How to Enable on GitHub Pages:**
  1. Push changes to GitHub repository.
  2. In GitHub repository settings: **Settings $\rightarrow$ Pages $\rightarrow$ Build and deployment**.
  3. Under **Source**, select **GitHub Actions** (the pre-configured `.github/workflows/pages.yml` workflow will automatically build and publish `dist/`).
* **Run Static Demo Locally:**
  ```bash
  # Build static bundle
  python scripts/build_static.py
  # Serve dist/ on port 8000
  python -m http.server 8000 --directory dist
  ```


---

## 9. Repo Structure

```
stripewatch/
├── README.md                      # This file
├── requirements.txt               # Pinned Python package dependencies
├── .env.example                   # Environment configuration template
├── pytest.ini                     # Pytest configuration
├── data/                          # Input data files
│   ├── shipment_records.csv       # 2,940 shipment records
│   ├── context_notes.csv          # 10 raw context notes
│   ├── sample_output_format_v2.csv# Target contract format
│   └── notes_structured.json     # Hand-verified structured facts
├── stripewatch/                   # Core Python package
│   ├── config.py                  # Thresholds, paths, and settings
│   ├── loader.py                  # Data loading and schema validation
│   ├── weekly.py                  # Monday-week aggregation (ratio of sums)
│   ├── baselines.py               # Trailing own history & peer baselines
│   ├── detect.py                  # Dual-branch anomaly candidate rule
│   ├── notes.py                   # Notes domain model and loader
│   ├── retrieve.py                # ChromaDB vector store + TF-IDF fallback
│   ├── validate.py                # 5-stage deterministic note validator
│   ├── evidence.py                # Factual evidence packet builder
│   ├── explain.py                 # LLM paraphrasing with template fallback
│   ├── ground.py                  # Strict anti-hallucination grounding checker
│   ├── llm.py                     # LLM adapter, SHA-256 caching, token log
│   ├── writer.py                  # Contract CSV & JSON writers
│   ├── ask.py                     # Grounded Q&A CLI
│   ├── repro.py                   # 3-run reproducibility checker
│   └── server.py                  # FastAPI server & static UI hosting
├── eval/                          # Evaluation harness & benchmarks
│   ├── gold_candidates.csv       # The 19 expected gold candidate rows
│   ├── adversarial_cases.json     # 16 adversarial trap unit tests
│   ├── run_eval.py                # Full evaluation harness runner
│   └── sensitivity.py             # Threshold sensitivity grid
├── tests/                         # Pytest test suite
│   ├── test_golden_sample.py      # Golden rows, Monday check, no-look-ahead
│   ├── test_adversarial.py        # Trap note rejection unit tests
│   └── test_grounding.py          # Grounding invariants & corruptions
├── output/                        # Generated output artifacts
│   ├── output.csv                 # Target submission CSV (19 rows)
│   ├── weekly_metrics.csv         # All 721 evaluable route-weeks
│   ├── results.json               # Detailed structured candidate findings
│   ├── token_log.json             # Real token counts and cost breakdown
│   ├── retrieval_log.jsonl        # Per-candidate top-3 RAG retrieval logs
│   ├── eval_report.md             # Automated evaluation scorecard
│   ├── repro_report.md            # Multi-run reproducibility verification
│   └── SUBMISSION_CHECKLIST.md    # Verified submission checklist
├── docs/                          # In-depth documentation & project assets
│   ├── WALKTHROUGH.md             # 10-minute talk track for Round 2
│   ├── DECISIONS.md               # Architectural decision record
│   ├── antigravity_pack/          # Context specifications and design system
│   ├── design_samples/            # Paper-slip UI samples and reference tokens
│   └── screens/                   # UI verification screenshots
└── web/                           # Lightweight Web UI (no build step)
    ├── index.html                 # Semantic consignment slip layout
    ├── app.css                    # Warm paper theme (design.md verbatim)
    └── app.js                     # Vanilla JS router and native SVG chart (<12KB)
```

---

## 10. Paper-Slip Web Interface (Pixel-Reproducible UI)

Per `design.md`, the UI replicates a warm physical consignment slip: ink-black text, tiger-orange accents, rubber-stamp verdicts, and hand-built inline SVG charts without external charting or UI libraries.

### Screen A — The Ledger (`#/`)
*Displays 19 candidate cost rises with stamp verdicts (`JUSTIFIED` in green, `FLAGGED` in red), route filtering, verdict tabs, and real-time KPI metrics.*

![Screen A Ledger 980px](docs/screens/screen_a_ledger_980.png)

### Screen B — Route Deep-Dive (`#/route/Chennai-Bangalore`)
*Hand-crafted inline SVG chart showing 8-week trailing own average (grey dashed), weekly ₹/t-km (solid black), justified green rings, and flagged red dots. Evidence slips below show matched notes and rejected near-misses.*

![Screen B Route 980px](docs/screens/screen_b_route_980.png)

### Screen C — Grounded Q&A (`#/ask`)
*Interactive natural language queries strictly anchored to pipeline evidence rows. If no note justifies a corridor/timeframe, it refuses to speculate ("No note found. I'd rather say so than guess.").*

![Screen C Ask 980px](docs/screens/screen_c_ask_980.png)

### Screen D — Context Notes Register (`#/notes`)
*Presents all 10 context notes in consignment slips with route scope, stated effect, disruption window, and justification stamps (`CAN JUSTIFY` vs `CAN'T JUSTIFY`).*

![Screen D Notes 980px](docs/screens/screen_d_notes_980.png)

### Screen E — "Try to Fool It" Live Validator (`#/fool`)
*Interactive adversarial console exposing the 5-step deterministic gate checks live. Evaluators can trigger 8 preset trap attacks (expired windows, nationwide peer outliers, non-disruption reports) or test custom combinations with immediate PASS/FAIL stamps.*

![Screen E Fool 980px](docs/screens/screen_e_fool_980.png)

### Mobile Responsive Views (390px Viewport)
*Full mobile fidelity with horizontal ledger scrolling, responsive controls, and stacked consignment slips.*

| Ledger (390px) | Route Deep-Dive (390px) | Grounded Ask (390px) | Notes (390px) | Fool Console (390px) |
|---|---|---|---|---|
| ![Ledger 390](docs/screens/screen_a_ledger_390.png) | ![Route 390](docs/screens/screen_b_route_390.png) | ![Ask 390](docs/screens/screen_c_ask_390.png) | ![Notes 390](docs/screens/screen_d_notes_390.png) | ![Fool 390](docs/screens/screen_e_fool_390.png) |


