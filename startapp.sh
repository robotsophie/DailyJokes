#!/usr/bin/env bash
# Builds the React frontend and starts Laugh Loop locally on :8000.
# Safe to run again: an already-running backend is left alone.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"

port_in_use() {
  (echo >/dev/tcp/127.0.0.1/"$1") >/dev/null 2>&1
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Please install Python 3 and run this again." >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js and npm are required. Please install them and run this again." >&2
  exit 1
fi

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Creating the Python environment…"
  python3 -m venv "$BACKEND_DIR/.venv"
fi
echo "Preparing backend packages…"
"$VENV_PYTHON" -m pip install --quiet --upgrade pip
"$VENV_PYTHON" -m pip install --quiet -r "$BACKEND_DIR/requirements.txt"

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Preparing frontend packages…"
  (cd "$FRONTEND_DIR" && npm install)
fi
echo "Building the frontend…"
(cd "$FRONTEND_DIR" && npm run build --silent)

mkdir -p "$ROOT_DIR/logs"
if port_in_use 8000; then
  echo "Backend already listening on :8000"
else
  (cd "$BACKEND_DIR" && nohup "$VENV_PYTHON" -m uvicorn app.main:app --reload --port 8000 >"$ROOT_DIR/logs/backend.log" 2>&1 &)
  echo "Backend is starting…"
fi
for _ in {1..30}; do
  if port_in_use 8000; then break; fi
  sleep 1
done

echo
echo "Open Laugh Loop: http://localhost:8000"
