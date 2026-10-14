# Provider Ablation Report: Template vs Gemini LLM Synthesis

**Purpose:** Verify that substituting the LLM with deterministic templates leaves all numeric calculations, candidate flags, verdicts, and cited note IDs 100% identical.

---

## 1. Non-Reason Invariance Check

| Column Checked | Template Mode (`LLM_PROVIDER=none`) | Gemini LLM Mode (`gemini-3.1-flash-lite`) | Status |
|---|---|---|:---:|
| `route` | Identical | Identical | **MATCH** |
| `week_of` | Identical | Identical | **MATCH** |
| `cost_per_tonne_km` | Identical | Identical | **MATCH** |
| `vs_own_history` | Identical | Identical | **MATCH** |
| `vs_similar_routes` | Identical | Identical | **MATCH** |
| `flagged` | Identical | Identical | **MATCH** |
| `matched_note_id` | Identical | Identical | **MATCH** |
| **All Non-Reason Columns** | **100% BYTE-FOR-BYTE IDENTICAL** | **100% BYTE-FOR-BYTE IDENTICAL** | **PASS** |

---

## 2. Reason Wording Comparison on Sample Rows

### Ahmedabad-Mumbai (2025-01-20) — Verdict: `No (justified)` | Note: `N002`
- **Deterministic Template:**
  > "Matches note N002 dated 2025-01-20: Regional festival week drove temporary surcharges and driver shortages. The cost rise has a clear explanation for the window 2025-01-20 to 2025-01-26."
- **Gemini 3.1 Flash Lite Paraphrase:**
  > "Matches note N002 for 2025-01-20 to 2025-01-26. The cost increase is justified by a regional festival week, which caused temporary transporter surcharges and limited truck availability on the Ahmedabad-Mumbai corridor."

### Chennai-Bangalore (2025-03-10) — Verdict: `Yes` | Note: `None`
- **Deterministic Template:**
  > "No matching note. Closest rejected: N001 (disruption window (2025-02-24 to 2025-03-08) does not overlap week of 2025-03-10); N009 (does not describe a cost rise (effect: 'normalizes')). Cost rise looks unexplained and worth a human review."
- **Gemini 3.1 Flash Lite Paraphrase:**
  > "No matching note was found for this corridor and date range. Near misses N001 and N009 were rejected because the disruption window does not overlap the week of 2025-03-10 and the note describes a normalization rather than a cost rise."

### Chennai-Bangalore (2025-03-17) — Verdict: `Yes` | Note: `None`
- **Deterministic Template:**
  > "No matching note. Closest rejected: N001 (disruption window (2025-02-24 to 2025-03-08) does not overlap week of 2025-03-17); N009 (does not describe a cost rise (effect: 'normalizes')). Cost rise looks unexplained and worth a human review."
- **Gemini 3.1 Flash Lite Paraphrase:**
  > "No matching note was found for this corridor and date range. Near misses N001 and N009 were rejected because the disruption window does not overlap the week of 2025-03-17 and the note describes a normalization rather than a cost rise."

---

## 3. Cost & Operating Profile

| Metric | Deterministic Template Mode (`none`) | Gemini Flash Lite Mode (`gemini`) |
|---|:---:|:---:|
| **LLM Calls** | **0** | **19 calls** |
| **Input Tokens** | **0** | **5,514** |
| **Output Tokens** | **0** | **687** |
| **Actual Spend** | **$0.00** (₹0.00) | **$0.00** (Free tier) |
| **Notional Cost (Pay-as-you-go)** | **$0.00** | **$0.00062** (~₹0.052) |
| **Scaling Characteristic** | Independent of dataset size | **Calls scale with candidate rows (19), NOT total shipments (2,940)** |

---

## 4. Key Takeaways

1. **Zero Hallucination Surface:** When `LLM_PROVIDER=none`, StripeWatch runs 100% offline with zero external network dependencies, producing contract-compliant reasons that pass every grounding check.
2. **Selective LLM Activation:** The LLM is only called on the 19 detected anomalies. Even across millions of raw shipments, LLM calls remain bounded by anomaly frequency rather than shipment volume.
