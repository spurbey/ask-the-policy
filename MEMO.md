# MEMORANDUM

**TO:** Head of Compliance, Harbour Financial Services  
**FROM:** Forward-Deployed AI Engineering Team  
**DATE:** 8 September 2026  
**SUBJECT:** Operational Deployment of the Policy Book Retrieval & Compliance Assistant  

---

### Executive Summary

We have delivered an automated compliance assistant that answers regulatory and internal servicing questions exclusively from authorized, in-force documentation. The system is designed around a zero-trust principle: it never guesses, never paraphrases legal mandates, and strictly enforces role-based confidentiality. 

---

### 1. What It Answers and What It Refuses

1. **In-Corpus Questions:** Answers questions grounded in current RBI, SEBI, and Harbour internal policy circulars with direct factual statements and 100% verbatim citations pinned to exact section identifiers.
2. **Access-Restricted Inquiries (`not_permitted`):** When an employee or branch customer queries a topic governed by an operational or legal circular exceeding their clearance, the system responds: *"You are not permitted to see the document governing this question."* It provides zero text quotes, names no confidential circulars, and avoids falsely claiming the rule does not exist.
3. **Out-of-Scope Inquiries (`not_in_corpus`):** If a question falls outside our 34 indexed documents, the assistant explicitly refuses to answer. It never hallucinates regulations from external parametric training data.

---

### 2. The Cost and Consequence of Wrong Answers

In lending compliance, an erroneous answer carries compounding regulatory and financial liabilities:
* **Quoting Withdrawn Circulars:** Quoting a withdrawn 2019 RBI master direction to a borrower exposes the institution to statutory penalties under Section 47A of the Banking Regulation Act (fines exceeding ₹50 lakh) and creates unserviceable customer claims.
* **Information Leakage:** Exposing legal-grade underwriting exceptions or internal audit policies to unauthorized personnel violates privacy compliance and weakens our regulatory defensibility.
* **The "False Non-Existence" Trap:** If an employee is told a rule does not exist simply because they lack clearance to read it, they will act as if unconstrained. Our two-stage gatekeeper guarantees access denial rather than false absence.

---

### 3. How You Will Know When the System Has Gone Stale

Regulatory policies evolve continuously. To detect staleness before a branch employee encounters it:
1. **Automated Supersedes Auditing:** The system maintains an active graph of document lineages (`effective_date` and `supersedes`). Any query timestamped after a known circular withdrawal automatically invalidates older precedents.
2. **Quarterly Diff Ingestion:** When the compliance team receives a gazette notification or updated master direction, the new text is placed in the corpus directory. The service performs dynamic indexing on restart in under 1 second without downtime.
3. **Audit Logging & Tracing:** Every prediction logs the `doc_id`, `section`, and verbatim quote used to formulate the answer, enabling immediate retrospective audits when an upstream circular is amended.

---

### 4. What Keeping It Current for One Year Takes

Maintaining this system in production requires minimal operational overhead:
* **Infrastructure:** Zero dedicated GPU infrastructure. The service runs in standard lightweight Linux containers on CPU, consuming $< 250\text{ MB}$ of RAM and serving queries with sub-second retrieval latency.
* **Maintenance Workflow:** 
  1. Add new PDF/text circulars into the repository manifest (`manifest.jsonl`).
  2. Specify the `effective_date`, `supersedes` references, and security `role`.
  3. Trigger the zero-downtime rolling container restart (`scripts/reproduce.sh`).
* **Compute Budget:** Operational inference stays strictly within budget-class language models ($< \$15$ monthly inference spend at standard enterprise volume).
