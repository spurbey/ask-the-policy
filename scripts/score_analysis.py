from src.indexer import CorpusRegistry
from src.retriever import BM25Retriever
import json

corpus_dir = "../Deployment.inc-Hiring-Problems/references/OP-05/corpus"
reg = CorpusRegistry(corpus_dir)
ret = BM25Retriever(reg)

with open("../Deployment.inc-Hiring-Problems/references/OP-05/questions_dev.jsonl", "r", encoding="utf-8") as f:
    questions = [json.loads(line) for line in f]

for i, q in enumerate(questions[:15], 1):
    hits = ret.search(q["question"], top_k=1)
    top_p, score = hits[0] if hits else (None, 0.0)
    print(f"Q{i} [{q['expected_status']:15s}]: top score = {score:.2f} (doc: {top_p.doc_id[:40] if top_p else 'None'})")
