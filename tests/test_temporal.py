from pathlib import Path
from src.indexer import CorpusRegistry
from src.temporal import TemporalEngine

def test_temporal():
    corpus_dir = Path(__file__).resolve().parent.parent.parent / "Deployment.inc-Hiring-Problems" / "references" / "OP-05" / "corpus"
    registry = CorpusRegistry(corpus_dir)
    engine = TemporalEngine(registry)

    # Check a 2018 regulation as of 2020-01-01 -> active
    assert engine.is_document_active("SEBI_2018_securities_and_exchange_board_of_india_issue_of_capital_063", "2020-01-01") is True

    # Document with effective_date 2020-01-01 is NOT active in 2019
    assert engine.is_document_active("RBI_Reserve_Ba_reserve_bank_of_india_small_finance_banks_prudential_no_099", "2019-01-01") is False

    # But IS active in 2021
    assert engine.is_document_active("RBI_Reserve_Ba_reserve_bank_of_india_small_finance_banks_prudential_no_099", "2021-01-01") is True

    print("ALL TEMPORAL TESTS PASSED!")

if __name__ == "__main__":
    test_temporal()
