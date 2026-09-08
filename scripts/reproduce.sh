#!/usr/bin/env bash
# OP-05 Reproduction and Service Runner
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$DIR"
export PORT="${PORT:-8000}"
export CORPUS_DIR="${CORPUS_DIR:-$DIR/../Deployment.inc-Hiring-Problems/references/OP-05/corpus}"

MODE="${1:-serve}"

echo "========================================================="
echo "OP-05 Policy Book Assistant Runner"
echo "Mode:       $MODE"
echo "Corpus:     $CORPUS_DIR"
echo "Port:       $PORT"
echo "========================================================="

case "$MODE" in
    serve)
        echo "Starting HTTP server on 0.0.0.0:$PORT..."
        exec uvicorn src.server:app --host 0.0.0.0 --port "$PORT"
        ;;
    eval)
        echo "Running evaluation on dev set..."
        exec python "$DIR/scripts/run_eval.py" "$@"
        ;;
    test)
        echo "Running test suite..."
        python "$DIR/tests/test_indexer.py"
        python "$DIR/tests/test_retriever.py"
        python "$DIR/tests/test_temporal.py"
        python "$DIR/tests/test_span_extractor.py"
        python "$DIR/tests/test_server.py"
        echo "All reproduction tests passed!"
        ;;
    *)
        echo "Usage: $0 {serve|eval|test}"
        exit 1
        ;;
esac
