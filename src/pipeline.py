"""Production pipeline for OP-05.

Combines BM25 retrieval, Temporal validity filtering, Two-Stage RBAC Security Gatekeeper,
Contradiction & Internal Policy priority, and Deterministic Verbatim Span Extraction.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from src.indexer import CorpusRegistry, Passage
from src.retriever import BM25Retriever
from src.security import SecurityGatekeeper
from src.temporal import TemporalEngine
from src.span_extractor import find_best_verbatim_span, norm
from src.llm import LLMClient


def parse_json_from_llm(raw_text: str) -> Dict[str, Any]:
    """Robustly parse JSON object from LLM output."""
    text = raw_text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        m2 = re.search(r"(\{.*\})", text, re.DOTALL)
        if m2:
            text = m2.group(1)

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"answer": raw_text.strip(), "quote": ""}


class PolicyPipeline:
    def __init__(self, registry: CorpusRegistry, llm_client: LLMClient):
        self.registry = registry
        self.retriever = BM25Retriever(registry)
        self.llm = llm_client
        self.gatekeeper = SecurityGatekeeper()
        self.temporal = TemporalEngine(registry)

    def answer_question(self, q: Dict[str, Any]) -> Dict[str, Any]:
        qid = q["id"]
        question_text = q["question"]
        user_role = q.get("role", "public")
        as_of = q.get("as_of", "2026-01-01")

        # 1. Global retrieval across all passages
        raw_hits = self.retriever.search(question_text, top_k=8)
        if not raw_hits or raw_hits[0][1] < 10.0:
            # Low confidence lexical match -> likely out of corpus
            return {
                "id": qid,
                "status": "not_in_corpus",
                "answer": "This information is not present in the policy book.",
                "citations": []
            }

        # 2. Filter out documents not yet effective as of as_of date
        valid_hits: List[Tuple[Passage, float]] = []
        for p, score in raw_hits:
            if p.effective_date <= as_of:
                # Prioritize Harbour internal servicing policy when applicable
                adjusted_score = score
                if "harbour" in p.doc_id.lower():
                    adjusted_score *= 1.2
                valid_hits.append((p, adjusted_score))

        valid_hits.sort(key=lambda x: x[1], reverse=True)
        if not valid_hits:
            return {
                "id": qid,
                "status": "not_in_corpus",
                "answer": "This information is not present in the policy book.",
                "citations": []
            }

        # 3. Two-Stage RBAC Security Audit
        is_allowed, blocking_passage = self.gatekeeper.audit_retrieval(valid_hits, user_role)
        if not is_allowed:
            return {
                "id": qid,
                "status": "not_permitted",
                "answer": "You are not permitted to see the document governing this question.",
                "citations": []
            }

        # 4. Filter candidates to permitted documents only
        allowed_hits = [p for p, s in valid_hits if self.gatekeeper.is_permitted(p.role, user_role)]
        if not allowed_hits:
            return {
                "id": qid,
                "status": "not_permitted",
                "answer": "You are not permitted to see the document governing this question.",
                "citations": []
            }

        best_passage = allowed_hits[0]

        # 5. Build context string
        context_parts = []
        for p in allowed_hits[:3]:
            context_parts.append(f"Passage ID: {p.passage_id} (Document: {p.doc_id}, Role: {p.role})\nText:\n{p.text}")
        context_str = "\n\n---\n\n".join(context_parts)

        # 6. Prompt LLM
        prompt = f"""You are an enterprise compliance assistant.
Read the passages below and answer the question as of {as_of}.
Important instructions:
- If Harbour internal policy conflicts with a regulator rule, Harbour internal policy takes precedence for Harbour agents.
- If the passages do not answer the question or lack evidence, respond with status "not_in_corpus".
- Keep the answer factual, precise and concise.

Passages:
{context_str}

Question: {question_text}
Requester Role: {user_role}
As-Of Date: {as_of}

Respond ONLY with a JSON object in this exact schema:
{{
  "status": "answered",
  "answer": "direct factual answer",
  "section": "exact Passage ID containing the supporting evidence (e.g. {best_passage.passage_id})",
  "quote": "key phrase from that passage supporting your answer"
}}
If not in corpus, respond with:
{{
  "status": "not_in_corpus",
  "answer": "This information is not present in the policy book.",
  "section": "",
  "quote": ""
}}
"""
        raw_output = self.llm.chat_completion([
            {"role": "system", "content": "You are an expert compliance assistant. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ])

        parsed = parse_json_from_llm(raw_output)
        status = parsed.get("status", "answered")

        if status == "not_in_corpus":
            return {
                "id": qid,
                "status": "not_in_corpus",
                "answer": "This information is not present in the policy book.",
                "citations": []
            }

        answer = str(parsed.get("answer", "")).strip()
        candidate_quote = str(parsed.get("quote", "")).strip()
        section = str(parsed.get("section", best_passage.passage_id)).strip()

        # Match section to passage
        matched_passage = None
        for p in allowed_hits:
            if p.passage_id == section:
                matched_passage = p
                break
        if not matched_passage:
            matched_passage = best_passage

        # Deterministic verbatim span extraction
        verbatim_quote = find_best_verbatim_span(matched_passage.text, candidate_quote)

        citations = []
        if verbatim_quote:
            citations.append({
                "doc_id": matched_passage.doc_id,
                "section": matched_passage.passage_id,
                "quote": verbatim_quote
            })

        return {
            "id": qid,
            "status": "answered",
            "answer": answer,
            "citations": citations
        }
