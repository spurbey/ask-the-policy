# OP-05: "Ask the Policy Book" — Implementation Plan, Architecture & Experiment Registry

This document serves as the **single source of truth** for our architecture, design assumptions, technical decisions, and live experiment registry. Every milestone, experiment run, benchmark score, and architectural update is recorded here.

---

## 1. System Architecture Blueprint

```
                     ┌─────────────────────────────────────────────────────────┐
                     │              Incoming Request: POST /ask                 │
                     │       { id, question, role, as_of: "YYYY-MM-DD" }        │
                     └────────────────────────────┬────────────────────────────┘
                                                  │
                                                  ▼
                     ┌─────────────────────────────────────────────────────────┐
                     │            1. Temporal & Validity Resolution            │
                     │  - Parse question.as_of (default: current date)         │
                     │  - Build supersedes/amendment DAG from manifest.jsonl   │
                     │  - Flag active vs superseded vs unreleased documents    │
                     └────────────────────────────┬────────────────────────────┘
                                                  │
                                                  ▼
                     ┌─────────────────────────────────────────────────────────┐
                     │            2. Hybrid Retrieval (All-Corpus)             │
                     │  - Search over ALL 391 passages (unfiltered by role)    │
                     │  - Lexical (BM25) + Dense Semantic Score                │
                     │  - Rank fusion / Top-K candidate extraction             │
                     └────────────────────────────┬────────────────────────────┘
                                                  │
                                                  ▼
                     ┌─────────────────────────────────────────────────────────┐
                     │        3. Two-Stage RBAC Security Gatekeeper            │
                     │  - Compare Top Match doc_role vs requester.role         │
                     │  - Hierarchy: public (0) < ops (1) < legal (2)          │
                     └─────────────┬─────────────────────────────┬─────────────┘
                                   │                             │
                     Top Match > Requester Role     Top Match <= Requester Role
                                   │                             │
                                   ▼                             ▼
                 ┌────────────────────────────────┐ ┌──────────────────────────┐
                 │  Return: status=not_permitted  │ │  4. Out-of-Corpus Audit  │
                 │  - answer: "Not permitted..."  │ │  - Retrieval score < θ ? │
                 │  - citations: []               │ └────────────┬─────────────┘
                 │  - ZERO doc text exposed       │              │
                 └────────────────────────────────┘      Below θ │ Above θ
                                       ┌─────────────────────────┘       │
                                       ▼                                 ▼
                     ┌────────────────────────────────┐ ┌──────────────────────────┐
                     │ Return: status=not_in_corpus   │ │ 5. Contradiction &       │
                     │ - answer: "Not in policy..."   │ │    Internal Policy Merge │
                     │ - citations: []                │ │ - Harbour internal policy│
                     │ - ZERO hallucinated facts      │ │   binds before regulator │
                     └────────────────────────────────┘ └────────────┬─────────────┘
                                                                     │
                                                                     ▼
                                                        ┌──────────────────────────┐
                                                        │ 6. LLM Generation &      │
                                                        │    Verbatim Quote Snap   │
                                                        │ - Budget Model Prompt    │
                                                        │ - Exact Substring Slicer │
                                                        │ - NFKC match check       │
                                                        └────────────┬─────────────┘
                                                                     │
                                                                     ▼
                                                        ┌──────────────────────────┐
                                                        │ Return: status=answered  │
                                                        │ - gold-aligned answer    │
                                                        │ - 100% verbatim citations│
                                                        └──────────────────────────┘
```

---

## 2. Hard Constraints & Benchmark Targets (from `grader.py`)

| Metric | Minimum Passing Bar | Baseline Reference Score | Our Target |
|---|---|---|---|
| **Coverage** (In-corpus answered) | $\ge 0.87$ (87%) | 0.8908 | $\ge 0.90$ |
| **Answer Correctness** (Overall) | $\ge 0.88$ (88%) | 0.9151 | $\ge 0.90$ |
| **Contradiction Slice Accuracy** | $\ge 0.88$ (88%) | 0.8750 (failed ref) | $\ge 0.90$ |
| **Temporal Slice Accuracy** | $\ge 0.88$ (88%) | 0.7895 (failed ref) | $\ge 0.90$ |
| **Citation Verbatim Rate** | $\ge 0.92$ (92%) | 0.9340 | $\ge 0.96$ |
| **Citation Support Rate** | $\ge 0.82$ (82%) | 0.8384 | $\ge 0.86$ |
| **Out-of-Corpus Refusal Rate** | $\ge 0.95$ (95%) | 1.0000 | $1.0000$ |
| **Fabricated Citations** | **EXACTLY 0** | 0 | **0** |
| **Role Violations** (12-token overlap) | **EXACTLY 0** | 0 | **0** |
| **Role-Blocked Refusal Correctness**| $\ge 0.87$ (87%) | 0.9048 | $\ge 0.92$ |
| **Hardware & Cost** | Plain CPU (no GPU) | 1,005 in / 743 out tokens | Budget class (<10s p95) |

---

## 3. Key Design Assumptions

1. **The Corpus is Small (~164 KB, 391 Passages):**
   - We do not need heavy distributed vector databases (Pinecone, Qdrant, Milvus).
   - In-memory data structures (BM25 index + in-memory numpy embedding matrix or lightweight SQLite) will load in $<100\text{ ms}$ and search in $<5\text{ ms}$ on pure CPU.
2. **Deterministic Citation Guarantee:**
   - The LLM will **not** be trusted to type quotes character-for-character.
   - We will implement a deterministic substring matcher: take the passage text already in memory, find the best matching span, and pull the exact character slice. This guarantees a 100% match with `grader.py`'s NFKC normalization check.
3. **Two-Stage Security Filtering:**
   - Never pre-filter restricted documents before retrieval. Pre-filtering leads directly to a 0.00 score on `not_permitted` because the retriever falsely concludes the rule doesn't exist.
   - Always retrieve globally, inspect if the top match exceeds the requester's role, and intercept with a clean refusal containing empty citations.
4. **Temporal Freshness Invalidation:**
   - When a document is listed in another active document's `supersedes` array, its priority is demoted or invalidated for queries evaluated as current.

---

## 4. Technical Trade-offs & Discussion Points

### A. Embedding & Retrieval Strategy
* **Option 1: Pure BM25 (Lexical)**
  * *Pros:* 0 latency, 0 token cost, perfect at exact circular names, section IDs, acronyms (e.g., *"SEBI ICDR 2018"*, *"Regulation 16(a)"*).
  * *Cons:* Misses semantic paraphrasing when exact words don't match.
* **Option 2: Hybrid BM25 + Lightweight Local ONNX Embedding (`fastembed` / `all-MiniLM-L6-v2`)**
  * *Pros:* Runs completely offline on plain CPU without GPU, fast (~1s to embed all 391 passages), captures semantic intent.
  * *Cons:* Adds a small pip dependency.
* **Option 3: Hybrid BM25 + API Embedding (`text-embedding-3-small` / `text-embedding-004`)**
  * *Pros:* State-of-the-art semantic search, minimal code complexity.
  * *Cons:* Requires API keys at index build time (though 164 KB is only ~40k tokens = ~$0.001).

### B. LLM Selection
* Must be budget-class:
  * OpenAI `gpt-4o-mini` (reliable structured JSON output, fast).
  * Google `gemini-2.5-flash` (low latency, high reasoning capability).
  * Anthropic `claude-3-5-haiku` (concise, high precision).

---

## 5. Phased Implementation Roadmap

- [x] **Phase 1: Ingestion, Metadata DAG & Data Loader** (Completed: 2026-09-08)
  - [x] Parse `manifest.jsonl` and build document registry (role, effective_date, supersedes) (`src/indexer.py`).
  - [x] Parse `passages.jsonl` and link section anchors (`passage_id`).
  - [x] Unit tests verifying 34 documents and 391 passages loaded with zero missing relations (`tests/test_indexer.py`).
- [x] **Phase 2: Baseline Retrieval & Measurement** (Completed: 2026-09-08)
  - [x] Implement BM25 baseline retriever (`src/retriever.py`).
  - [x] Implement basic prompt generator with budget LLM (`src/llm.py`, `src/baseline_pipeline.py`).
  - [x] Tested dev questions to diagnose exact failure modes (Role leakage on Q4, OOC hallucination on Q7).
  - [x] Record Run 01 metrics and baseline failure taxonomy in the Registry below.
- [x] **Phase 3: Two-Stage RBAC & Verbatim Span Slicer** (Completed: 2026-09-08)
  - [x] Implement `src/security.py`: Two-Stage RBAC Gatekeeper auditing global retrieval vs requester clearance.
  - [x] Implement `src/span_extractor.py`: Deterministic verbatim span extractor matching official `grader.py` normalization.
  - [x] Implemented unified `PolicyPipeline` in `src/pipeline.py`.
  - [x] Verified zero role violations on Q4 (`not_permitted`) and clean refusal on Q7 (`not_in_corpus`).
- [x] **Phase 4: Temporal Resolution & Out-of-Corpus Refusal** (Completed: 2026-09-08)
  - [x] Implement `src/temporal.py`: evaluate `as_of` date against document effective dates and `supersedes` edges.
  - [x] Implement confidence routing and out-of-corpus refusal in `src/pipeline.py`.
  - [x] Verified contradiction resolution (Harbour internal policy given 1.2x priority).
  - [x] Evaluated on 10-question slice achieving 100% deterministic score on official `grader.py`.
- [x] **Phase 5: Production Service (`POST /ask`) & Freshness Contract** (Completed: 2026-09-08)
  - [x] Implement FastAPI server with `POST /ask` and `GET /healthz` (`src/server.py`).
  - [x] Implement `scripts/reproduce.sh` and `scripts/reproduce.ps1` supporting `$CORPUS_DIR` and `$PORT`.
  - [x] Verified clean restart and dynamic corpus ingestion on test suite.
- [x] **Phase 6: Held-out Predictions & Documentation Dossier** (Completed: 2026-09-08)
  - [x] Implemented evaluation runner and verified against official `grader.py`.
  - [x] Created `MEMO.md` addressed to the Head of Compliance.
  - [x] Created `DECISIONS.md` documenting architecture trade-offs.
  - [x] Created `LANDSCAPE.md` reviewing evaluated technologies and frameworks.
  - [x] Created `EXPERIMENT_LOG.md` recording all iterations and official grader reports.
  - [x] Created `submission.yaml` and `results/manifest.json` conforming to `SUBMISSION_SCHEMA.md`.

---

## 6. Live Experiment Registry & Scorecard

| Run ID | Date | Configuration / Changes | Status / Observations | Next Steps |
|---|---|---|---|---|
| **Run-01 (Baseline)** | 2026-09-08 | Pure BM25 + Naive LLM prompt | **Diagnosed Core Failures:**<br>1. Role leakage on Q4.<br>2. Hallucination on Q7.<br>3. Punctuation mismatch on quotes. | Proceed to Phase 3. |
| **Run-02 (RBAC + Span Slicer)** | 2026-09-08 | `PolicyPipeline` with `SecurityGatekeeper` + `find_best_verbatim_span` | **Major Milestone Passed:**<br>1. Q1 (`answered`): 100% verbatim citation, correct answer.<br>2. Q4 (`not_permitted`): Correct refusal, 0 citations, 0 role leaks.<br>3. Q7 (`not_in_corpus`): Clean refusal, 0 citations, 0 hallucinations. | Proceed to Phase 4 & 5. |
| **Run-03 (Official Grader Slice)** | 2026-09-08 | Full pipeline on 10-question multi-class slice evaluated with official `grader.py` | **Official Grader Output:**<br>• `schema_valid_rate`: **1.0 (100%)**<br>• `citation_verbatim_rate`: **1.0 (100%)**<br>• `answered_rate_on_answerable`: **1.0 (100%)**<br>• `ooc_refusal_rate`: **1.0 (100%)**<br>• `not_permitted_rate`: **1.0 (100%)**<br>• `role_violations`: **0**<br>• `fabricated_count`: **0** | **Ready for Submission & Technical Review.** |
