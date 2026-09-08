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
            # Low confidence lexical match -> out of corpus
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

        # 5. Build focused context prompt (top 1 passage, or top 2 if short)
        context_parts = [f"Passage ({best_passage.passage_id}):\n{best_passage.text}"]
        if len(allowed_hits) > 1 and len(best_passage.text) < 400:
            context_parts.append(f"Passage ({allowed_hits[1].passage_id}):\n{allowed_hits[1].text}")
        context_str = "\n\n---\n\n".join(context_parts)

        # 6. Prompt LLM
        prompt = f"""You are an enterprise compliance assistant.
Read the passage below and answer the question as of {as_of}.
If the passage does NOT contain the answer, respond with status "not_in_corpus".
Be direct, factual, and concise.

{context_str}

Question: {question_text}

Respond ONLY with a JSON object in this exact schema:
{{
  "status": "answered",
  "answer": "concise factual answer",
  "quote": "exact phrase from the passage supporting your answer"
}}
If not found in the passage:
{{
  "status": "not_in_corpus",
  "answer": "This information is not present in the policy book.",
  "quote": ""
}}
"""
        raw_output = self.llm.chat_completion([
            {"role": "system", "content": "You are a concise compliance helper. Always respond in JSON."},
            {"role": "user", "content": prompt}
        ], max_tokens=1000)

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

        # Deterministic verbatim span extraction
        verbatim_quote = find_best_verbatim_span(best_passage.text, candidate_quote)

        citations = []
        if verbatim_quote:
            citations.append({
                "doc_id": best_passage.doc_id,
                "section": best_passage.passage_id,
                "quote": verbatim_quote
            })

        return {
            "id": qid,
            "status": "answered",
            "answer": answer,
            "citations": citations
        }
