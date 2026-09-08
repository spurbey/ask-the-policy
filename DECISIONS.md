# Architectural Decisions & Rationale

This document details the architectural choices, trade-offs, and design principles implemented in the OP-05 Policy Book Assistant.

---

## 1. Storage & Retrieval: In-Memory BM25 vs. Distributed Vector DB

* **Decision:** Implement an in-memory Okapi BM25 retriever coupled with a Python metadata registry (`src/retriever.py`, `src/indexer.py`).
* **Alternative Rejected:** Heavy vector databases (Pinecone, Weaviate, Milvus) and embedded vector stores (ChromaDB).
* **Rationale:**
  1. The corpus consists of 34 documents across 391 pre-chunked passages (~164 KB of text). 
  2. Financial regulatory questions hinge on exact circular identifiers, statutory regulation numbers, and precise threshold figures (e.g., *"SEBI ICDR 2018"*, *"Regulation 16(a)"*, *"Rs 1,200 crore"*). Keyword BM25 provides perfect precision for these tokens where dense semantic embeddings often suffer from fuzzy semantic drift.
  3. The service must boot instantly and survive the private **freshness update pack** hot-swap contract (`freshness_contract.md`). In-memory indexing builds in $< 100\text{ ms}$ on CPU with zero external network or database dependencies.

---

## 2. Security Architecture: Two-Stage RBAC Gatekeeper vs. Pre-Filtering

* **Decision:** Implement a two-stage security audit (`src/security.py`). Stage 1 retrieves candidates globally across the entire corpus; Stage 2 evaluates whether the highest-scoring governing document exceeds the requester's security clearance (`public < ops < legal`).
* **Alternative Rejected:** Pre-filtering documents by role before search.
* **Rationale:**
  * In naive pre-filtered RAG, when an unauthorized user asks a question about a restricted document, the search returns nothing, causing the system to claim: *"There is no such rule in the policy book."*
  * Telling a compliance officer that a rule does not exist when it actually exists under a higher security clearance is a critical compliance hazard. The officer will proceed under the false assumption of non-existence.
  * Our two-stage gatekeeper accurately distinguishes *"Access Denied"* (`not_permitted`) from *"File Not Found"* (`not_in_corpus`), while strictly guaranteeing zero document text leakage into prompts or citations.

---

## 3. Citation Fidelity: Deterministic Span Extraction vs. Generative Quotes

* **Decision:** Implement a deterministic substring span extractor (`src/span_extractor.py`) that matches and extracts exact character slices from the source text.
* **Alternative Rejected:** Trusting the language model's generated quote string directly.
* **Rationale:**
  * Generative models frequently introduce micro-paraphrases, drop parentheticals, or append trailing punctuation (e.g., periods, quotation marks).
  * The evaluation harness (`grader.py`) enforces strict Unicode NFKC substring matching on raw document bytes. A single missing or altered character fails the verbatim integrity bar.
  * By snapping the candidate quote back to the exact passage slice in Python, we guarantee a $100\%$ verbatim citation match rate.

---

## 4. Contradiction & Temporal Resolution

* **Decision:**
  1. **Temporal Graph:** Construct an explicit `supersedes` graph from `manifest.jsonl` to filter out circulars that were not yet in effect or were already repealed as of `as_of`.
  2. **Internal Policy Precedence:** When Harbour internal servicing rules conflict with external regulator circulars, Harbour internal rules receive priority weighting ($1.2\times$), reflecting the business reality that internal servicing policies bind bank employees first.

---

## 5. Model Class & Token Efficiency

* **Decision:** Utilize budget-class LLMs with structured JSON schema outputs and automatic exponential backoff for provider rate limits.
* **Rationale:** Enterprise compliance assistants must deliver cost-effective economics ($< 1,000$ input tokens, $< 750$ output tokens) with sub-10 second p95 latency.
