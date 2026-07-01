#!/usr/bin/env bash
set -euo pipefail

# Quick dev runner. Use uvicorn directly for production.

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
    echo ">> creating .venv"
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if ! python -c "import fastapi" 2>/dev/null; then
    echo ">> installing dependencies"
    pip install -e ".[dev]"
fi

if [ ! -f ".env" ]; then
    echo ">> no .env found, copying from .env.example"
    cp .env.example .env
fi

if [ ! -f "$RAG_INDEX_PATH" ] && [ ! -f "./data/faiss.index" ]; then
    echo ">> no FAISS index found, running seed_kb + build_index"
    python scripts/seed_kb.py
    python -m app.rag.build_index
fi

export PYTHONUNBUFFERED=1
exec uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}" --reload