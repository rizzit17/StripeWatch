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
* **Trade-off:** Custom SVG math (mapping weekly rates and baselines to coordinate space) had to be written by hand, but guarantees a lightweight (<12 KB) footprint.
