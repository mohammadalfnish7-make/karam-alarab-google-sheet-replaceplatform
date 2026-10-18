#!/usr/bin/env bash
# Run the FastAPI app on the Mac (useful when debugging outside Docker).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

export LLM_PROVIDER="${LLM_PROVIDER:-anthropic}"
export LLM_MODEL="${LLM_MODEL:-claude-haiku-5-5}"
export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}"
export UPLOAD_DIR="${UPLOAD_DIR_HOST:-$ROOT/uploads}"
export EXCEL_IMPORT_PATH="${EXCEL_IMPORT_PATH:-$ROOT/excel sheet/WM _NEW  Load Plan.xlsx}"
mkdir -p "$UPLOAD_DIR"

echo "Starting API on :8000 (provider=${LLM_PROVIDER} model=${LLM_MODEL})"
echo "Point the web container at it with:"
echo "  API_UPSTREAM=host.docker.internal:8000 docker compose up -d --build web"
echo "  docker compose stop api"

cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  python3.12 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
.venv/bin/pip install -q -r requirements.txt
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
