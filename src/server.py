"""FastAPI HTTP service for OP-05.

Exposes:
- GET /healthz: Health probe indicating index readiness.
- POST /ask: Compliance query endpoint accepting {id, question, role, as_of}.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.indexer import CorpusRegistry
from src.llm import LLMClient
from src.pipeline import PolicyPipeline


class AskRequest(BaseModel):
    id: str
    question: str
    role: str = "public"
    as_of: Optional[str] = "2026-01-01"


class CitationItem(BaseModel):
    doc_id: str
    section: str
    quote: str


class AskResponse(BaseModel):
    id: str
    status: str
    answer: str
    citations: List[CitationItem] = Field(default_factory=list)


# Initialize application
app = FastAPI(title="Ask the Policy Book", version="1.0.0")

# Global pipeline instance
pipeline: Optional[PolicyPipeline] = None


@app.on_event("startup")
def startup_event():
    global pipeline
    default_corpus = Path(__file__).resolve().parent.parent.parent / "Deployment.inc-Hiring-Problems" / "references" / "OP-05" / "corpus"
    corpus_dir = Path(os.environ.get("CORPUS_DIR", str(default_corpus)))

    if not corpus_dir.exists():
        raise RuntimeError(f"CORPUS_DIR does not exist: {corpus_dir}")

    registry = CorpusRegistry(corpus_dir)
    llm = LLMClient()
    pipeline = PolicyPipeline(registry, llm)
    print(f"Service initialized successfully with {len(registry.passages)} passages from: {corpus_dir}")


@app.get("/healthz")
def health_check():
    """Healthcheck endpoint for container orchestration and freshness restarts."""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Index initializing")
    return {"status": "ok", "passages_indexed": len(pipeline.registry.passages)}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """Authoritative compliance QA endpoint."""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Service not ready")

    q_dict = {
        "id": req.id,
        "question": req.question,
        "role": req.role,
        "as_of": req.as_of or "2026-01-01"
    }

    try:
        res = pipeline.answer_question(q_dict)
        return AskResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
