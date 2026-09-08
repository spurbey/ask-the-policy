# Experiment Log & Engineering Evolution

This log tracks all experimental iterations, baseline failures, architectural interventions, and benchmark measurements in chronological order.

---

## Experiment 01: Baseline Retrieval & Naive Generation

* **Date:** 2026-09-08 12:30 IST
* **Configuration:**
  * In-memory Okapi BM25 index over all 391 passages.
  * Direct prompting of OpenRouter model (`poolside/laguna-xs-2.1:free`) with top-3 retrieved passages.
  * No RBAC gatekeeper; no deterministic quote snapping.
* **Observed Failure Modes:**
  1. **Security / RBAC Failure:** On Question 4 (`indiafinbench_NUM_012`), an unauthorized `public` user asked about an `ops`-restricted SEBI Mutual Fund regulation. The baseline blindly retrieved and quoted the restricted document, causing an immediate **Role Violation** (failing qualification bar 5).
  2. **Hallucination / Fabrication:** On Question 7 (`ooc-009`), an out-of-corpus question regarding NBFC net owned fund requirements, the model output an extensive internal monologue and asserted ₹2 crore from external training data instead of refusing, triggering the **Fabrication** penalty (failing bar 4).
  3. **Verbatim Citation Mismatch:** The model added trailing punctuation (`"domestic mutual funds."`) where the source document read `"domestic mutual funds which reservation..."`, causing failure under the strict Unicode NFKC substring check.
* **Key Learning:** Naive RAG fails outright on compliance retrieval. Explicit two-stage access gating and deterministic span extraction are strictly required.

---

## Experiment 02: Two-Stage RBAC & Deterministic Span Extraction

* **Date:** 2026-09-08 12:40 IST
* **Interventions Applied:**
  1. Implemented `src/security.py` (`SecurityGatekeeper`): Stage 1 performs global retrieval across all 391 passages; Stage 2 checks if the highest-scoring candidate exceeds requester role clearance (`public < ops < legal`). If restricted, immediately returns `status: "not_permitted"`, empty citations, and canned refusal text with zero text leakage.
  2. Implemented `src/span_extractor.py` (`find_best_verbatim_span`): Slices exact character substrings directly from the source passage text matching the candidate quote, ensuring `norm(quote) in norm(passage_text) == True`.
* **Observed Results:**
  * Question 1 (`answered`): Correct answer (`One-third`), exact verbatim citation.
  * Question 4 (`not_permitted`): Successfully intercepted in $0.0\text{s}$, zero document leakage, zero citations.
  * Question 7 (`not_in_corpus`): Successfully refused without external hallucination.

---

## Experiment 03: Temporal DAG, Contradiction Priority & Official Grader Verification

* **Date:** 2026-09-08 12:48 IST
* **Interventions Applied:**
  1. Built `src/temporal.py` (`TemporalEngine`): Enforces `effective_date <= as_of` and tracks document invalidation through the `supersedes` graph.
  2. Added priority weighting ($1.2\times$) for Harbour internal servicing policy to resolve internal vs. regulator contradictions.
  3. Built FastAPI server (`src/server.py`) exposing `POST /ask` and `GET /healthz`.
  4. Ran official test suite and benchmarked against official `grader.py`.
* **Official Grader Measurements (`grader.py --no-judge`):**
  * `schema_valid_rate`: **1.0 (100%)**
  * `citation_verbatim_rate`: **1.0 (100%)** (Target: $\ge 92\%$)
  * `answered_rate_on_answerable`: **1.0 (100%)** (Target: $\ge 87\%$)
  * `ooc_refusal_rate`: **1.0 (100%)** (Target: $\ge 95\%$)
  * `not_permitted_rate`: **1.0 (100%)** (Target: $\ge 87\%$)
  * `role_violations`: **0** (Target: 0)
  * `fabricated_count`: **0** (Target: 0)
* **Outcome:** All qualification deterministic targets met or exceeded.
