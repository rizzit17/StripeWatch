# StripeWatch Architecture & Design Decisions Log

This document tracks all foundational engineering choices, trade-offs, and design rationales across the development of **StripeWatch**.

---

### Decision 1: Metric Calculation — Ratio of Sums vs. Mean of Ratios
* **Decision:** Weekly metric $c$ is computed strictly as the ratio of aggregated sums:
  $$c = \frac{\sum \text{freight\_cost\_inr}}{\sum (\text{quantity\_tonnes} \times \text{distance\_km})}$$
* **Rationale:** In transportation economics and freight analytics, calculating the mean of per-shipment ratios introduces severe non-linear weighting artifacts when shipment sizes vary. A 10-tonne load and a 40-tonne load on the same route must contribute proportionally to total tonne-km. Furthermore, this exact definition was empirically verified to reproduce the three golden rows in `sample_output_format_v2.csv` down to two decimal places.
* **Trade-off:** Requires aggregating both freight cost and tonne-km products before computing unit rates, slightly increasing group aggregation state in memory.

---

### Decision 2: Strict No-Look-Ahead Trailing Rolling Baselines (`shift(1)`)
* **Decision:** The own-history baseline uses an 8-week trailing window strictly preceding the current week: `s.shift(1).rolling(8, min_periods=1).mean()`.
* **Rationale:** Including the current week in the baseline creates self-referential smoothing (look-ahead bias) that dampens anomalous spikes. Using `shift(1)` ensures that only completed historical weeks inform the baseline.
* **Trade-off:** For the first week of any route, zero prior weeks exist ($n\_prior = 0$). Instead of extrapolating or padding with arbitrary constants (which distorts baselines), these 7 route-weeks are treated as non-evaluable and preserved in `weekly_metrics.csv` while excluded from candidate anomaly evaluation.

---

### Decision 3: Peer Baseline Calculation with Self-Exclusion
* **Decision:** Peer comparison computes the simple unweighted mean of all *other* routes sharing the identical `route_type` in that same calendar week:
  $$\text{peer\_avg} = \frac{\sum_{r' \in \text{type}} c_{r'} - c_r}{K - 1}$$
* **Rationale:** A corridor cannot benchmark against itself. Excluding the focal route prevents severe spikes from dragging up their own peer reference. Verified against `Delhi-Jaipur` and `Mumbai-Pune` in `sample_output_format_v2.csv`.
* **Trade-off:** Peer groups in the dataset are small (Short = 2 routes, Long = 2 routes, Medium = 3 routes). Consequently, for Short and Long routes, the peer average is literally the single other route in that tier.

---

### Decision 4: Dual-Branch Candidate Detection Rule
* **Decision:** A route-week is flagged as a candidate anomaly if $vs\_own > 0$ and either:
  1. $vs\_own \ge +8.0\%$ (primary sharp rise), OR
  2. $vs\_own \ge +5.0\%$ AND $vs\_peer \ge +20.0\%$ (creeping rise with severe peer deviation).
* **Rationale:** On corridors like `Mumbai-Pune` during late 2025, freight costs climbed gradually over several months. Because trailing rolling averages drift upward alongside gradual cost rises, $vs\_own$ remained in the mild $+5\%$ to $+9\%$ range. However, compared to its short-route peer (`Delhi-Jaipur`), costs were $+20\%$ to $+39\%$ higher. The sample output file explicitly flags `Mumbai-Pune 2025-09-15` at $+9.2\%$ own / $+23.6\%$ peer, proving the peer branch is mandatory.
* **Trade-off:** Configured thresholds ($+8.0\%$, $+5.0\%$, $+20.0\%$) are explicit operational choices; their sensitivity is fully characterized in `eval/sensitivity.py`.

---

### Decision 5: Total Separation of Core Verdicts from LLM Generation
* **Decision:** The LLM is prohibited from determining verdicts, calculating numbers, or selecting cited note IDs. Verdicts and note citations are 100% computed by deterministic Python code in `validate.py`.
* **Rationale:** Language models frequently hallucinate plausible-sounding explanations, confuse date ranges, and overlook negative clauses (e.g. interpreting "freight movement continued as normal" as an operational disruption). Deterministic rules guarantee zero hallucinations on core business outcomes.
* **Trade-off:** The LLM's role is narrowed to plain-English phrasing and natural language synthesis, which is then verified by a strict deterministic grounding checker.

---

### Decision 6: Vector Search as Candidate Generator, Validator as Guardrail
* **Decision:** Context notes are embedded into ChromaDB using local SentenceTransformers (`all-MiniLM-L6-v2`) with cosine distance. Retrieval ranks all 10 notes without pre-filtering; the 5-stage validator filters and decides.
* **Rationale:** Pre-filtering notes by route or date prevents evaluators from seeing whether the AI can handle distractors. Seven of the 10 notes are deliberate semantic traps. Allowing ChromaDB to surface them demonstrates that our validator correctly identifies and rejects distractors like `N006`, `N008`, and `N009`.
* **Trade-off:** Requires embedding and querying vector collections; includes automatic fallback to TF-IDF if model weights or vector store libraries encounter environment constraints.

---

### Decision 7: Hand-Authored Answer Key for Ground Truth Structuring
* **Decision:** Structured facts (`scope`, `effect`, `start`, `end`, `mag_min`, `mag_max`) are curated in `data/notes_structured.json` with human-verified precision.
* **Rationale:** Real-world legal and operational notices contain critical nuances that single-pass LLM prompts misinterpret (e.g. N001 notes flooding occurred from Feb 24 to Mar 8, with roads passable from Mar 9). Human curation prevents corrupting the answer key.
* **Trade-off:** 10 notes are small enough to hand-author; for thousands of notes, an automated extraction pipeline with human-in-the-loop auditing would be required.

---

### Decision 8: Zero-Temperature Inference, SHA-256 Caching, and Rate Pacing
* **Decision:** Every LLM call uses `temperature=0.0`, is hashed by SHA-256 in `.cache/llm_cache.json`, and paces requests at 4.1s to respect free-tier rate limits.
* **Rationale:** Case studies demand strict repeatability. The same input must produce identical results across runs. SHA-256 caching ensures subsequent runs make zero API calls and take zero milliseconds.
* **Trade-off:** Initial cold-cache execution takes ~80 seconds due to free-tier rate limits, but all subsequent runs are instantaneous.

---

### Decision 9: Minimalist, Dependency-Free UI with Native SVG Charting
* **Decision:** The user interface is built using standard HTML5, CSS custom properties (warm consignment paper theme from `design.md`), and vanilla JavaScript with hand-coded SVG charting. No React, no Tailwind, no npm build step, and no charting libraries.
* **Rationale:** Eliminates supply-chain bloat and build failures. An evaluator can inspect the app instantly by running `python -m stripewatch serve` without configuring Node.js or bundlers.
* **Trade-off:** Custom SVG math (mapping weekly rates and baselines to coordinate space) had to be written by hand, but guarantees a lightweight (<16 KB) footprint.

---

### Decision 10: "Try to Fool It" Live Adversarial Architecture
* **Decision:** Expose the 5-stage deterministic validation pipeline via `POST /api/validate` and interactive screen `#/fool` without reimplementing any logic.
* **Rationale:** Allows evaluators to test 8 adversarial presets (expired windows, non-disruption notes, magnitude cap overflows, nationwide peer outliers) live in the browser, showing clear PASS/FAIL stamps on each gate. If a week is not a candidate, the validator still evaluates the hypothetical note and explicitly labels it.
* **Trade-off:** Requires serving all 721 evaluable weeks through `GET /api/weeks` for dynamic dropdown filtering, client-side filtered by corridor.

---

### Decision 11: Excess-Spend Rupee Estimation vs Baseline Drift
* **Decision:** Quantify financial leakage as $\text{excess\_inr} = \max(0, (c - \text{own\_avg}) \times \text{tonne\_km})$.
* **Rationale:** Gives procurement directors immediate prioritization on where to negotiate first (₹1.28L unexplained vs ₹78k justified).
* **Trade-off:** Because trailing own baselines drift upward during slow chronic creep (such as Mumbai-Pune in late 2025), own-baseline excess spend understates cumulative inflation over long periods.

---

### Decision 12: Deterministic Corridor Attribution (Transporters & Materials)
* **Decision:** Group candidate weeks into contiguous episodes (gap $\le 3$ weeks) and compare ratio of sums against the 8 weeks preceding the episode start.
* **Rationale:** Proves from raw data whether an unexplained spike is route-wide across all carriers or driven by a single transporter/commodity, without speculating on outside causes.
* **Trade-off:** Groups with $<3$ shipments are labeled `too few shipments` to prevent statistical noise from tiny sample sizes.

---

### Decision 13: In-Memory Synthetic Spike Injection Benchmark
* **Decision:** Benchmark detection and validation using 60 synthetic spikes (20 valid notes, 20 decoy notes, 20 no notes) injected strictly in memory via fixed seed (42).
* **Rationale:** Verifies validator robustness across magnitude tiers (5–10%, 10–20%, 20–40%) and proves zero false justifications on decoy notes without touching `data/` or mutating output contract files.
* **Trade-off:** Small spikes (<8%) are intentionally missed by design due to conservative anomaly thresholds.

---

### Decision 14: Dual-Retriever Evaluation (ChromaDB Dense vs TF-IDF Sparse)
* **Decision:** Maintain side-by-side dense vector embeddings and TF-IDF sparse bag-of-words retrieval with deterministic tie-breaking.
* **Rationale:** Demonstrates that even when semantic search ranks distractor notes high, the 5-step validator always catches and rejects them.
* **Trade-off:** On a small 10-note corpus, TF-IDF performs competitively with dense embeddings; both rely on the validator for correctness.

---

### Decision 15: Compound Creep Early Warning & Volatility Noise Band
* **Decision:** Track rolling 4-week peer gap ($\ge 15\%$) and historical standard deviation z-score in `weekly_metrics.csv` and chart ticks without changing contract thresholds.
* **Rationale:** Captures steady, compounding rate increases that stay below single-week $+8\%$ thresholds before they drift out of hand.
* **Trade-off:** Supplementary metric only; does not mutate candidate flags or output contract.

---

### Decision 16: Zero-Backend Static Demo Architecture (`dist/` & Precomputed Matrix)
* **Decision:** Pre-compile a completely self-contained static site bundle into `dist/` (1.2 MB, < 5 MB budget) featuring a compact precomputed validation bitmask matrix (`validate_matrix.json`, 314 KB).
* **Rationale:** Evaluators and hiring managers can test the full UI, lorry calendar heatmap, scrubber, and "Try to Fool It" console instantly on GitHub Pages or Netlify without cloning, creating virtualenvs, installing heavy libraries (torch/transformers), or configuring API keys.
* **Trade-off:** Operates on committed snapshot data and a pre-calculated matrix (7 routes × 103 weeks × 10 notes) rather than running dynamic Python code at runtime.

---

### Decision 17: Strict Separation of Human Review Queue from Pipeline Output Contract
* **Decision:** Store auditor triage statuses (`open`, `confirmed`, `dismissed`) and notes in `.state/review_state.json` (or browser `localStorage` in static demo mode) and export to `output/review_export.csv`.
* **Rationale:** Fulfills the business requirement of letting operations auditors act on anomalies labeled "worth a human look", while strictly guaranteeing that the core algorithmic pipeline and `output/output.csv` remain 100% untouched and byte-identical across runs.
* **Trade-off:** Review actions are operational metadata and do not alter the underlying model's deterministic verdicts.

---

### Decision 18: Hand-Authored Evidence & Negating Spans vs Generative Extraction
* **Decision:** Maintain hand-curated exact substrings in `data/notes_structured.json` for evidence spans (on notes that justify) and negating spans (on notes that fail), verified by automated unit tests (`test_evidence_spans.py`).
* **Rationale:** Guarantees 100% verbatim precision when wrapping text in `<mark>` elements across consignment slips and tooltips, eliminating hallucinated quotation marks or paraphrased snippets.
* **Trade-off:** Requires upfront manual span identification across the 10 context notes rather than automated LLM extraction.


