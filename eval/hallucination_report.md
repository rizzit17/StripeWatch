# Hallucination Baseline Evaluation: Naive LLM vs StripeWatch

## 1. Summary Comparison Table

Evaluated on the **16 unexplained route-weeks** where no context note supported the cost increase.

| Pipeline | N | Asserted Unsupported Cause | Hedged | Other | Caught by Grounding Check |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Naive LLM (no notes, raw prompt)** | 16 | 16 (100.0%) | 0 | 0 | 16/16 (100.0%) |
| **StripeWatch (RAG + Guardrails)** | 16 | **0 (0.0%)** | 0 | 16 | 0 false flags (100% valid) |

## 2. Sample Naive LLM Outputs (Verbatim Model Completions)

### Example 1: Chennai-Bangalore (2025-03-10)
> "The 22.1% cost surge during the week of March 10, 2025, was driven by localized supply-demand imbalances and infrastructure bottlenecks, causing rates to significantly decouple from historical averages and peer route benchmarks."

- **Lexicon Verdict**: `asserts a cause`
- **Caught by Grounding Check**: `True` (['Unexplained text missing standard explanation phrase from: [\'no matching note\', "couldn\'t find", \'no supporting note\', \'unexplained\', \'flagged for review\', \'no genuine justification\', \'flagged\', \'worth a human review\']'])

### Example 2: Chennai-Bangalore (2025-03-17)
> "Freight costs surged due to localized supply-demand imbalances and operational inefficiencies. The 13.7% weekly spike, significantly outpacing peer routes, reflects acute capacity constraints and rising fuel or toll surcharges specific to the Chennai-Bangalore corridor during that period."

- **Lexicon Verdict**: `asserts a cause`
- **Caught by Grounding Check**: `True` (['Unexplained text missing standard explanation phrase from: [\'no matching note\', "couldn\'t find", \'no supporting note\', \'unexplained\', \'flagged for review\', \'no genuine justification\', \'flagged\', \'worth a human review\']'])

### Example 3: Delhi-Chennai (2024-02-05)
> "Freight costs rose due to an 8.5% increase over historical averages, significantly outpacing peer routes by 7.8%. This suggests localized supply chain disruptions or capacity constraints specific to the Delhi-Chennai corridor during the week of February 5th."

- **Lexicon Verdict**: `asserts a cause`
- **Caught by Grounding Check**: `True` (['Unexplained text missing standard explanation phrase from: [\'no matching note\', "couldn\'t find", \'no supporting note\', \'unexplained\', \'flagged for review\', \'no genuine justification\', \'flagged\', \'worth a human review\']'])

## 3. What This Proves and Doesn't

**What this proves**: A naked foundation model provided with numeric anomaly statistics but no contextual ground truth exhibits an immediate propensity to hallucinate domain-specific causes (e.g. diesel spikes, seasonal surges, or toll increases) to satisfy prompt queries. StripeWatch's strict deterministic validator and bidirectional grounding verification effectively eliminate unsupported cause claims (0 unsupported assertions across all 16 unexplained rows), actively catching and suppressing ungrounded narratives.

**What this doesn't prove**: This benchmark evaluates a sample of N = 16 unexplained rows with a single zero-shot prompt template and a deterministic keyword lexicon. It demonstrates the structural risk of ungrounded LLM usage in production freight auditing, rather than establishing an exhaustive universal hallucination rate across all arbitrary model families.
