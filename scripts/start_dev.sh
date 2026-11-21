#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Starting Aegis 2AM Backend (http://localhost:8000) & War Room UI (http://localhost:3000)..."
.venv/bin/uvicorn backend.api.app:app --reload --port 8000 &
BACK_PID=$!

(cd frontend && npm run dev) &
FRONT_PID=$!

trap 'kill $BACK_PID $FRONT_PID 2>/dev/null || true' EXIT INT TERM
wait
