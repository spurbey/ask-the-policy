"""Temporal validity and version resolution engine for OP-05.

Tracks effective dates, supersedes relationships, and determines which documents
were in force on a given as_of date.
"""
from __future__ import annotations

from typing import Dict, List, Set
from src.indexer import CorpusRegistry, DocumentMeta


class TemporalEngine:
    def __init__(self, registry: CorpusRegistry):
        self.registry = registry
        # Map: superseded_doc_id -> (superseding_doc_id, effective_date)
        self.superseded_by: Dict[str, List[tuple[str, str]]] = {}
        self._build_graph()

    def _build_graph(self) -> None:
        for doc_id, meta in self.registry.documents.items():
            for old_id in meta.supersedes:
                if old_id not in self.superseded_by:
                    self.superseded_by[old_id] = []
                self.superseded_by[old_id].append((doc_id, meta.effective_date))

    def is_document_active(self, doc_id: str, as_of: str) -> bool:
        """Check if a document was active (in force and not superseded) as of date."""
        meta = self.registry.get_document(doc_id)
        if not meta:
            return False

        # 1. Not yet in force
        if meta.effective_date > as_of:
            return False

        # 2. Check if superseded on or before as_of
        if doc_id in self.superseded_by:
            for superseding_id, eff_date in self.superseded_by[doc_id]:
                if eff_date <= as_of:
                    return False

        return True

    def get_superseded_documents(self, as_of: str) -> Set[str]:
        """Return set of doc_ids that are superseded as of date."""
        superseded = set()
        for old_id, replacements in self.superseded_by.items():
            for _, eff_date in replacements:
                if eff_date <= as_of:
                    superseded.add(old_id)
                    break
        return superseded
