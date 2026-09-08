"""Evaluation runner for OP-05 development questions.

Runs pipeline on questions_dev.jsonl, saves predictions, and invokes grader.py.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from src.indexer import CorpusRegistry
from src.llm import LLMClient
from src.pipeline import PolicyPipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limit number of questions to evaluate")
    parser.add_argument("--out", type=str, default="results/raw/baseline_preds.jsonl")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    ref_dir = repo_root.parent / "Deployment.inc-Hiring-Problems" / "references" / "OP-05"
    corpus_dir = ref_dir / "corpus"
    gold_path = ref_dir / "questions_dev.jsonl"
    grader_path = ref_dir / "grader.py"

    print(f"Loading corpus from: {corpus_dir}")
    registry = CorpusRegistry(corpus_dir)
    llm = LLMClient()
    pipeline = PolicyPipeline(registry, llm)

    # Load questions
    questions = []
    with open(gold_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))

    if args.limit:
        questions = questions[:args.limit]

    print(f"Running evaluation on {len(questions)} questions...")
    out_path = repo_root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    preds = []
    start_time = time.time()
    for i, q in enumerate(questions, 1):
        q_start = time.time()
        res = pipeline.answer_question(q)
        q_dur = time.time() - q_start
        preds.append(res)
        print(f"[{i}/{len(questions)}] {q['id']} ({res['status']}) - {q_dur:.1f}s")

    with open(out_path, "w", encoding="utf-8") as f:
        for p in preds:
            f.write(json.dumps(p) + "\n")

    total_time = time.time() - start_time
    print(f"\nPredictions written to: {out_path} in {total_time:.1f}s")

    # If we evaluated the full set, run the official grader
    if not args.limit:
        print("\nRunning official grader.py (deterministic checks)...")
        cmd = [
            sys.executable,
            str(grader_path),
            "--pred", str(out_path),
            "--gold", str(gold_path),
            "--corpus", str(corpus_dir / "manifest.jsonl"),
            "--no-judge"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        print("GRADER SUMMARY:")
        print(res.stdout)
        if res.stderr:
            print("GRADER ERRORS / STDERR:")
            print(res.stderr)


if __name__ == "__main__":
    main()
