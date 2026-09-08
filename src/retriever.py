"""BM25 Lexical Retriever for OP-05 corpus.

Indexes all 391 passages in-memory and returns ranked candidates.
"""
from __future__ import annotations

import re
from typing import List, Tuple
from rank_bm25 import BM25Okapi
from src.indexer import CorpusRegistry, Passage


def tokenize(text: str) -> List[str]:
    """Lowercase word tokenizer with legal hyphen/dot preservation."""
    return re.findall(r"\b\w+(?:[-_]\w+)*\b", text.lower())


class BM25Retriever:
    def __init__(self, registry: CorpusRegistry):
        self.registry = registry
        self.passages: List[Passage] = registry.passages
        self.corpus_tokens = [tokenize(p.text + " " + p.title) for p in self.passages]
        self.bm25 = BM25Okapi(self.corpus_tokens)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Passage, float]]:
        """Search passages by BM25 relevance score."""
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        scored_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = [(self.passages[i], float(scores[i])) for i in scored_indices[:top_k]]
        return results
