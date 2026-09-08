"""Baseline retrieval and answer generation pipeline for OP-05.

Uses BM25 retrieval over all passages and calls the LLM to extract answers and citations.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List
from src.indexer import CorpusRegistry, Passage
from src.retriever import BM25Retriever
from src.llm import LLMClient


def parse_json_from_llm(raw_text: str) -> Dict[str, Any]:
    """Robustly parse JSON object from LLM output (including markdown-fenced code blocks)."""
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


class BaselinePipeline:
    def __init__(self, registry: CorpusRegistry, llm_client: LLMClient):
        self.registry = registry
        self.retriever = BM25Retriever(registry)
        self.llm = llm_client

    def answer_question(self, q: Dict[str, Any]) -> Dict[str, Any]:
        qid = q["id"]
        question_text = q["question"]
        role = q.get("role", "public")
        as_of = q.get("as_of", "2026-01-01")

        # 1. Retrieve top 3 candidate passages
        hits = self.retriever.search(question_text, top_k=3)
        if not hits:
            return {
                "id": qid,
                "status": "not_in_corpus",
                "answer": "This information is not present in the policy book.",
                "citations": []
            }

        top_passage, top_score = hits[0]

        # 2. Build context prompt
        context_parts = []
        for p, score in hits:
            context_parts.append(f"Passage ID: {p.passage_id} (Document: {p.doc_id})\nText:\n{p.text}")
        context_str = "\n\n---\n\n".join(context_parts)

        prompt = f"""You are an enterprise compliance assistant.
Read the passages below and answer the question.
You MUST provide:
1. "answer": The direct, concise factual answer.
2. "section": The exact Passage ID where the evidence was found (e.g. {top_passage.passage_id}).
3. "quote": The EXACT verbatim sentence or phrase from that passage supporting your answer.

Passages:
{context_str}

Question: {question_text}
Requester Role: {role}
As-Of Date: {as_of}

Respond ONLY with a JSON object in this exact schema:
{{
  "answer": "...",
  "section": "...",
  "quote": "..."
}}
"""
        raw_output = self.llm.chat_completion([
            {"role": "system", "content": "You are an expert compliance assistant. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ])

        parsed = parse_json_from_llm(raw_output)
        answer = str(parsed.get("answer", "")).strip()
        quote = str(parsed.get("quote", "")).strip()
        section = str(parsed.get("section", top_passage.passage_id)).strip()

        # Find matching passage for doc_id
        matched_p = None
        for p, _ in hits:
            if p.passage_id == section:
                matched_p = p
                break
        if not matched_p:
            matched_p = top_passage

        citations = []
        if quote:
            citations.append({
                "doc_id": matched_p.doc_id,
                "section": matched_p.passage_id,
                "quote": quote
            })

        return {
            "id": qid,
            "status": "answered",
            "answer": answer,
            "citations": citations
        }
