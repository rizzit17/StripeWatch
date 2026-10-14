# StripeWatch Evaluation Report

## 1. Executive Summary
- **Golden Anchor Rows:** 3 / 3 (100% exact match on cost per tonne-km, vs_own_history, and vs_similar_routes)
- **Candidate Detection:** 19 / 19 candidates identified against gold benchmark
- **Verdict Accuracy:** 19 / 19 (100%) — exactly 3 justified, 16 unexplained
- **Adversarial Guardrails:** 16 / 16 tests passed (100%)
- **Grounding Checker:** 19 / 19 explanations pass; 5 / 5 malicious corruptions rejected
- **No-Look-Ahead Verification:** Past metrics invariant to future data modifications

---

## 2. Benchmark Scorecard

| Evaluation Benchmark | Expected | Actual | Status |
|---|---|---|---|
| **Golden Sample Row 1** (Delhi-Jaipur 2024-11-11) | 4.17 / +35.5% / +21.0% | 4.17 / +35.5% / +21.0% | **PASS** |
| **Golden Sample Row 2** (Ahmedabad-Mumbai 2025-01-20) | 3.29 / +29.5% / +22.5% | 3.29 / +29.5% / +22.5% | **PASS** |
| **Golden Sample Row 3** (Mumbai-Pune 2025-09-15) | 3.98 / +9.2% / +23.6% | 3.98 / +9.2% / +23.6% | **PASS** |
| **Total Route-Weeks** | 728 | 728 | **PASS** |
| **Evaluable Route-Weeks** | 721 (7 first-weeks dropped) | 721 | **PASS** |
| **Candidate Count** | 19 | 19 | **PASS** |
| **Justified Candidates** | 3 (N001 x 2, N002 x 1) | 3 (N001 x 2, N002 x 1) | **PASS** |
| **Unexplained Candidates** | 16 | 16 | **PASS** |
| **Adversarial Trap Suite** | 16 / 16 passed | 16 / 16 passed | **PASS** |
| **Grounding Checker** | 100% pass, 0 hallucinations | 100% pass | **PASS** |
| **Synthetic Corruptions Caught** | 5 / 5 rejected | 5 / 5 rejected | **PASS** |

---

## 3. Candidate Breakdown (19 Gold Rows)

| Route | Week Of | Cost/T-Km | vs Own | vs Peer | Verdict | Matched Note | Status |
|---|---|---|---|---|---|---|---|
| Ahmedabad-Mumbai | 2025-01-20 | 3.29 | +29.5% | +22.5% | No (justified) | N002 | PASS |
| Chennai-Bangalore | 2025-02-24 | 3.58 | +31.5% | +38.7% | No (justified) | N001 | PASS |
| Chennai-Bangalore | 2025-03-03 | 3.48 | +22.8% | +32.0% | No (justified) | N001 | PASS |
| Chennai-Bangalore | 2025-03-10 | 3.57 | +22.1% | +33.8% | Yes | - | PASS |
| Chennai-Bangalore | 2025-03-17 | 3.47 | +13.7% | +33.5% | Yes | - | PASS |
| Delhi-Chennai | 2024-02-05 | 2.22 | +8.5% | +7.8% | Yes | - | PASS |
| Delhi-Jaipur | 2024-11-11 | 4.17 | +35.5% | +21.0% | Yes | - | PASS |
| Delhi-Jaipur | 2024-11-18 | 4.09 | +27.6% | +19.7% | Yes | - | PASS |
| Mumbai-Delhi | 2025-05-12 | 2.28 | +11.6% | +6.7% | Yes | - | PASS |
| Mumbai-Pune | 2025-06-23 | 3.76 | +6.2% | +20.6% | Yes | - | PASS |
| Mumbai-Pune | 2025-09-15 | 3.98 | +9.2% | +23.6% | Yes | - | PASS |
| Mumbai-Pune | 2025-10-06 | 3.94 | +5.4% | +22.9% | Yes | - | PASS |
| Mumbai-Pune | 2025-10-20 | 4.10 | +7.7% | +24.8% | Yes | - | PASS |
| Mumbai-Pune | 2025-10-27 | 4.07 | +5.5% | +28.3% | Yes | - | PASS |
| Mumbai-Pune | 2025-11-03 | 4.20 | +7.4% | +24.1% | Yes | - | PASS |
| Mumbai-Pune | 2025-11-17 | 4.32 | +8.9% | +31.6% | Yes | - | PASS |
| Mumbai-Pune | 2025-12-01 | 4.39 | +7.7% | +37.4% | Yes | - | PASS |
| Mumbai-Pune | 2025-12-08 | 4.43 | +7.2% | +38.8% | Yes | - | PASS |
| Mumbai-Pune | 2025-12-22 | 4.49 | +5.7% | +38.9% | Yes | - | PASS |

---

## 4. Sensitivity Analysis across Threshold Grid

| vs_own Threshold | vs_own Soft | vs_peer Threshold | Total Candidates | Selected / Default |
|---|---|---|---|---|
| +6.0% | +5.0% | +15.0% | 36 | No |
| +6.0% | +5.0% | +20.0% | 36 | No |
| +6.0% | +5.0% | +25.0% | 35 | No |
| +8.0% | +5.0% | +15.0% | 19 | No |
| +8.0% | +5.0% | +20.0% | 19 | **YES (Default)** |
| +8.0% | +5.0% | +25.0% | 15 | No |
| +10.0% | +5.0% | +15.0% | 18 | No |
| +10.0% | +5.0% | +20.0% | 18 | No |
| +10.0% | +5.0% | +25.0% | 13 | No |

**Observations on Threshold Robustness:**
- Strong signals (Delhi-Jaipur Nov-2024, Ahmedabad-Mumbai Jan-2025 festival, and Chennai-Bangalore Feb-Mar 2025 flood) persist across all reasonable thresholds (6% to 10%).
- The secondary soft branch (`vs_own >= +5.0%` AND `vs_peer >= +20.0%`) is essential: without it, Mumbai-Pune's slow upward drift from June to December 2025 would be missed because rolling trailing baselines adjust upward as costs rise.

---

## 5. Why We Trust This System

1. **Separation of Roles:** Numbers come strictly from pandas arithmetic (ratio of sums). Verdicts and cited note IDs come 100% from deterministic Python code in `validate.py`. The LLM has zero authority to decide verdicts, numbers, or note citations.
2. **Rejection of Semantic Traps:** 7 out of the 10 provided notes are trap notes (mentioning disruptions, maintenance, or weather, but explicitly stating costs were normal or unaffected). A naive semantic search ranks them high, but our 5-stage validator systematically rejects them.
3. **Strict Date Windows:** When flooding on Chennai-Bangalore ended on March 8 (N001), subsequent weeks (March 10 and March 17) were honestly left unexplained (`flagged=Yes`) rather than falsely excused.
4. **Zero-Hallucination Grounding:** Every reason string is checked against an evidence packet of verified facts. Any ungrounded claims, invented dates, or fake note IDs cause immediate rejection and fallback to verified deterministic templates.
