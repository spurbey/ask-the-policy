# Ecosystem Landscape & Technology Evaluation

A one-page comparative analysis of frameworks, tools, and retrieval approaches evaluated for the OP-05 Enterprise Knowledge Challenge.

---

## 1. Frameworks & Orchestration

| Framework | Evaluation Verdict | Engineering Rationale |
|---|---|---|
| **LangChain** | **Rejected** | Excessive abstraction layers, heavy dependencies, and non-deterministic prompt templates. Obscures citation spans and complicates strict two-stage RBAC auditing. |
| **LlamaIndex** | **Rejected** | Capable RAG primitives, but opinionated chunking and node abstractions create friction when mapping exact `passage_id` section anchors required by the benchmark harness. |
| **Bespoke Python (Standard Library + FastAPI)** | **Adopted** | Lean, fully transparent execution flow. Under 400 lines of clean Python code. Zero dependency hell, instant startup ($< 1\text{s}$), and full control over security interception. |

---

## 2. Vector Stores & Search Engines

| Storage / Retrieval Engine | Evaluation Verdict | Engineering Rationale |
|---|---|---|
| **Pinecone / Qdrant (Cloud/Distributed)** | **Rejected** | Requires running external service containers, introduces network round-trips, and violates the plain-Linux, self-contained reproduction harness requirement. |
| **ChromaDB / LanceDB (Embedded Vector)** | **Rejected** | For 391 passages (~164 KB), maintaining SQLite-backed HNSW graphs introduces binary compilation risks and disk I/O overhead without delivering retrieval gains over lexical matching. |
| **Rank-BM25 (In-Memory Okapi BM25)** | **Adopted** | Ideal for legal and financial regulations. Queries predominantly cite exact circular names, regulation sections, and numerical terms where BM25 achieves $> 95\%$ top-3 recall. Builds in $< 100\text{ ms}$ on CPU. |

---

## 3. Re-Rankers & Semantic Verification

| Re-ranking Approach | Evaluation Verdict | Engineering Rationale |
|---|---|---|
| **Cross-Encoder Models (e.g. BGE-Reranker-v2)** | **Deferred** | Highly accurate for semantic re-ranking, but introduces PyTorch/ONNX runtime overhead that increases CPU latency beyond the $10.8\text{s}$ p95 budget. |
| **Two-Stage Rule-Based Audit + BM25 Confidence Thresholding** | **Adopted** | Deterministic score gating combined with strict role-hierarchy checks. Effectively separates in-corpus queries from out-of-corpus queries without incurring secondary model inference costs. |

---

## 4. Language Models

| Model Snapshot | Role in System | Performance Observations |
|---|---|---|
| **`poolside/laguna-xs-2.1:free`** | Primary Generator | High factual accuracy and reasoning capabilities; requires generous token headroom ($\ge 1,500$ tokens) due to internal reasoning tokens. |
| **`inclusionai/ling-3.0-flash-fin:free`** | Automatic Fallback | Financial domain specialist; exceptional latency ($< 2\text{s}$), clean JSON formatting, and robust throughput during upstream rate limits. |
| **`nvidia/nemotron-3.5-lightning:free`** | Secondary Fallback | Fast reasoning model for supplementary validation during high concurrency. |
