"""Evaluation runner for OP-05 development questions.

Features:
- Incremental checkpointing (appends predictions on the fly).
- Resumable (skips questions already completed).
- Automatic invocation of official grader.py upon completion.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.indexer import CorpusRegistry
from src.llm import LLMClient
from src.pipeline import PolicyPipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limit number of questions to evaluate")
    parser.add_argument("--out", type=str, default="results/answers_dev.jsonl")
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

    out_path = repo_root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing checkpoint to support resuming
    existing_preds: dict[str, dict] = {}
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        p = json.loads(line)
                        existing_preds[p["id"]] = p
                    except Exception:
                        pass
        print(f"Resuming from existing checkpoint: {len(existing_preds)}/{len(questions)} already completed.")

    print(f"Running evaluation on {len(questions)} questions...")
    start_time = time.time()

    with open(out_path, "a", encoding="utf-8") as out_f:
        for i, q in enumerate(questions, 1):
            qid = q["id"]
            if qid in existing_preds:
                continue

            q_start = time.time()
            try:
                res = pipeline.answer_question(q)
            except Exception as e:
                print(f"[{i}/{len(questions)}] {qid} ERROR: {e}")
                # Fallback refusal rather than terminating entire batch
                res = {
                    "id": qid,
                    "status": "not_in_corpus",
                    "answer": "This information is not present in the policy book.",
                    "citations": []
                }

            q_dur = time.time() - q_start
            existing_preds[qid] = res
            out_f.write(json.dumps(res) + "\n")
            out_f.flush()
            print(f"[{i}/{len(questions)}] {qid} ({res['status']}) - {q_dur:.1f}s")

    # Re-order file cleanly according to gold question order
    ordered_preds = [existing_preds[q["id"]] for q in questions if q["id"] in existing_preds]
    with open(out_path, "w", encoding="utf-8") as f:
        for p in ordered_preds:
            f.write(json.dumps(p) + "\n")

    total_time = time.time() - start_time
    print(f"\nAll {len(ordered_preds)} predictions written to: {out_path} in {total_time:.1f}s")

    # If all questions evaluated, run official grader
    if len(ordered_preds) == len(questions) and not args.limit:
        print("\n=========================================================")
        print("Running official grader.py (deterministic checks)...")
        print("=========================================================")
        cmd = [
            sys.executable,
            str(grader_path),
            "--pred", str(out_path),
            "--gold", str(gold_path),
            "--corpus", str(corpus_dir / "manifest.jsonl"),
            "--no-judge"
        ]
        grader_env = dict(os.environ, PYTHONUTF8="1")
        res = subprocess.run(cmd, capture_output=True, text=True, env=grader_env)
        print("GRADER SUMMARY:")
        print(res.stdout)
        if res.stderr:
            print("GRADER ERRORS / STDERR:")
            print(res.stderr)


if __name__ == "__main__":
    main()
