#!/usr/bin/env bash
# Start a throwaway API and worker for the browser tests: fresh demo data in a temporary folder,
# so the tests never touch data/ (your local database and files).
set -euo pipefail
cd "$(dirname "$0")/../../backend"
PY="${PYTHON:-../.venv/bin/python}"
[ -x "$PY" ] || PY=python3
DIR="$(mktemp -d)"
export CODETWIN_DATA_DIR="$DIR" CODETWIN_DATABASE_URL="sqlite:///$DIR/e2e.db" CODETWIN_EMBEDDER=hashing
"$PY" -m codetwin.cli seed-demo >/dev/null
"$PY" -m codetwin.worker &
WORKER=$!
trap 'kill $WORKER 2>/dev/null; rm -rf "$DIR"' EXIT
"$PY" -m uvicorn codetwin.api.main:app --port "${PORT:-8100}"
