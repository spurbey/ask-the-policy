from pathlib import Path
from src.indexer import CorpusRegistry
from src.retriever import BM25Retriever

def test_retriever():
    corpus_dir = Path(__file__).resolve().parent.parent.parent / "Deployment.inc-Hiring-Problems" / "references" / "OP-05" / "corpus"
    registry = CorpusRegistry(corpus_dir)
    retriever = BM25Retriever(registry)

    # Test query 1: Anchor investor portion under SEBI ICDR 2018
    q1 = "Under SEBI ICDR Regulations, 2018, what fraction of the anchor investor portion is reserved for domestic mutual funds?"
    results = retriever.search(q1, top_k=3)
    assert len(results) == 3
    top_p, score = results[0]
    print("Query 1 top hit:", top_p.doc_id, top_p.passage_id, "score:", score)
    assert top_p.passage_id == "SEBI_2018_securities_and_exchange_board_of_india_issue_of_capital_063#s57383"

    # Test query 2: Harbour internal policy identity verification
    q2 = "What does Harbour internal policy require before moving money or waiving a fee?"
    results = retriever.search(q2, top_k=3)
    for p, score in results:
        print("Query 2 hit:", p.doc_id, p.passage_id, "score:", score)
    hit_sections = [p.passage_id for p, _ in results]
    assert "HARBOUR_internal_servicing_policy#s00001" in hit_sections or "HARBOUR_internal_servicing_policy#s00000" in hit_sections

    print("ALL RETRIEVER TESTS PASSED!")

if __name__ == "__main__":
    test_retriever()
