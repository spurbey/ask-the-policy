from pathlib import Path
from src.indexer import CorpusRegistry, ROLE_RANK

def test_corpus_loading():
    corpus_dir = Path(__file__).resolve().parent.parent.parent / "Deployment.inc-Hiring-Problems" / "references" / "OP-05" / "corpus"
    assert corpus_dir.exists(), f"Corpus directory not found: {corpus_dir}"

    registry = CorpusRegistry(corpus_dir)
    assert len(registry.documents) == 34, f"Expected 34 documents, found {len(registry.documents)}"
    assert len(registry.passages) == 391, f"Expected 391 passages, found {len(registry.passages)}"

    # Verify role counts
    roles = {doc.role for doc in registry.documents.values()}
    assert roles == {"public", "ops", "legal"}

    # Verify permission hierarchy
    assert registry.is_permitted("public", "public") is True
    assert registry.is_permitted("ops", "public") is False
    assert registry.is_permitted("legal", "ops") is False
    assert registry.is_permitted("public", "legal") is True

    # Check a specific known passage
    known_doc = "HARBOUR_internal_servicing_policy"
    known_section = "HARBOUR_internal_servicing_policy#s00001"
    p = registry.get_passage(known_doc, known_section)
    assert p is not None
    assert p.doc_id == known_doc
    assert p.role == "ops"
    assert "Identity before money" in p.text

    print("ALL INDEXER TESTS PASSED!")

if __name__ == "__main__":
    test_corpus_loading()
