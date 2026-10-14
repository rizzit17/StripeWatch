# Retrieval Evaluation Report: Dense vs Sparse RAG

**Dataset:** 19 Candidate Route-Weeks | **Corpus:** 10 Context Notes (N001–N010)

---

## 1. Side-by-Side Comparison (ChromaDB vs TF-IDF)

| Evaluation Metric | ChromaDB (Dense: all-MiniLM-L6-v2) | TF-IDF (Sparse n-gram keyword) |
|---|:---:|:---:|
| **Recall@1 (Justified Target Note)** | **0 / 3** (0.0%) | **2 / 3** (66.7%) |
| **Recall@3 (Justified Target Note)** | **3 / 3** (100.0%) | **3 / 3** (100.0%) |
| **Trap Notes Surfaced in Top-3** | **33** | **33** |
| **Surfaced Notes Rejected by Validator** | **54** | **54** |

---

## 2. Analysis & Key Findings

1. **Both retrievers achieve 100% Recall@3 on true causes:** On all 3 justified events (Ahmedabad festival N002 and Chennai flood N001), both dense semantic embeddings and sparse TF-IDF successfully place the true cause in the top candidates.
2. **Dense retrieval surfaces semantic distractors:** Chroma embeddings frequently rank notes N006, N008, and N010 in the top-3 because they contain high semantic overlap with freight disruptions (e.g. mentioning 'highway', 'transport', 'monsoon'), despite explicitly stating that costs were normal.
3. **The Essential Role of the Validator:** Over the 19 candidates, Chroma surfaced a rejected note 54 times, and TF-IDF surfaced a rejected note 54 times. In 100% of these cases, the deterministic 5-step validator intervened and rejected the decoy.

---

## 3. Guiding Architectural Law

> **Retrieval ranks, the validator decides.**
>
> In our pipeline, retrieval surfaced candidate notes 54 times that the validator correctly and systematically rejected. Vector search alone is insufficient for high-stakes freight auditing; mathematical and temporal validation is what makes the system trustworthy.
