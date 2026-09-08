"""Corpus loader and metadata indexer for OP-05.

Reads manifest.jsonl and passages.jsonl from CORPUS_DIR, joins metadata,
and builds an in-memory registry of documents and passages.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


ROLE_RANK = {
    "public": 0,
    "ops": 1,
    "legal": 2,
}


@dataclass
class DocumentMeta:
    doc_id: str
    title: str
    effective_date: str
    supersedes: list[str]
    role: str
    text_path: str
    sha256: str
    source_url: Optional[str] = None


@dataclass
class Passage:
    passage_id: str
    doc_id: str
    text: str
    role: str
    effective_date: str
    supersedes: list[str] = field(default_factory=list)
    title: str = ""


class CorpusRegistry:
    def __init__(self, corpus_dir: Path | str):
        self.corpus_dir = Path(corpus_dir)
        self.documents: dict[str, DocumentMeta] = {}
        self.passages: list[Passage] = []
        self.passage_by_id: dict[tuple[str, str], Passage] = {}
        self._load()

    def _load(self) -> None:
        manifest_path = self.corpus_dir / "manifest.jsonl"
        passages_path = self.corpus_dir / "passages.jsonl"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")
        if not passages_path.exists():
            raise FileNotFoundError(f"Passages not found: {passages_path}")

        # 1. Load document manifest
        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                meta = DocumentMeta(
                    doc_id=d["doc_id"],
                    title=d.get("title", ""),
                    effective_date=d.get("effective_date", "1970-01-01"),
                    supersedes=d.get("supersedes", []),
                    role=d.get("role", "public"),
                    text_path=d.get("text_path", ""),
                    sha256=d.get("sha256", ""),
                    source_url=d.get("source_url"),
                )
                self.documents[meta.doc_id] = meta

        # 2. Load passages and enrich with document metadata
        with open(passages_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                p = json.loads(line)
                doc_id = p["doc_id"]
                doc_meta = self.documents.get(doc_id)
                role = doc_meta.role if doc_meta else "public"
                eff_date = doc_meta.effective_date if doc_meta else "1970-01-01"
                supersedes = doc_meta.supersedes if doc_meta else []
                title = doc_meta.title if doc_meta else ""

                passage = Passage(
                    passage_id=p["passage_id"],
                    doc_id=doc_id,
                    text=p["text"],
                    role=role,
                    effective_date=eff_date,
                    supersedes=supersedes,
                    title=title,
                )
                self.passages.append(passage)
                self.passage_by_id[(doc_id, p["passage_id"])] = passage

    def get_document(self, doc_id: str) -> Optional[DocumentMeta]:
        return self.documents.get(doc_id)

    def get_passage(self, doc_id: str, passage_id: str) -> Optional[Passage]:
        return self.passage_by_id.get((doc_id, passage_id))

    def is_permitted(self, doc_role: str, user_role: str) -> bool:
        """True if user_role clearance is >= doc_role."""
        return ROLE_RANK.get(user_role, 0) >= ROLE_RANK.get(doc_role, 0)
