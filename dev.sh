#!/usr/bin/env bash
# Start backend (uvicorn :8000) and frontend (next dev :3000) together.
# Ctrl+C stops both. Logs are interleaved with [backend]/[frontend] prefixes.

set -euo pipefail

cd "$(dirname "$0")"

# Recursively kill a PID and all its descendants. Needed because `npm run dev`
# spawns `next dev`, and `uv run uvicorn --reload` spawns a reloader + worker —
# `kill $PID` on the parent leaves grandchildren orphaned.
kill_tree() {
  local pid=$1 sig=${2:-TERM} child
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    kill_tree "$child" "$sig"
  done
  kill "-$sig" "$pid" 2>/dev/null || true
}

cleanup() {
  trap - INT TERM EXIT
  echo "" >&2
  echo "[dev] stopping…" >&2
  # Walk descendants of dev.sh itself — most reliable: anything we spawned
  # (uv → uvicorn → reloader, npm → next dev → workers, sed pipes) is a
  # descendant of $$.
  for child in $(pgrep -P $$ 2>/dev/null); do
    kill_tree "$child" TERM
  done
  sleep 1
  # Belt-and-braces: anything still holding our ports gets a hard kill.
  for port_pid in $(lsof -ti:8000 -ti:3000 2>/dev/null); do
    kill -KILL "$port_pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "[dev] stopped."
}
trap cleanup INT TERM EXIT

(cd backend && exec uv run --active uvicorn app.main:app --reload --port 8000) \
  > >(sed -u 's/^/[backend] /') 2>&1 &
BACK_PID=$!

(cd frontend && exec npm run dev) \
  > >(sed -u 's/^/[frontend] /') 2>&1 &
FRONT_PID=$!

echo "[dev] backend pid=$BACK_PID  frontend pid=$FRONT_PID"
echo "[dev] backend → http://localhost:8000  |  frontend → http://localhost:3000"
echo "[dev] Ctrl+C to stop both."

# Wait until either child exits (bash 3.2-compatible — macOS lacks `wait -n`).
while kill -0 "$BACK_PID" 2>/dev/null && kill -0 "$FRONT_PID" 2>/dev/null; do
  sleep 1
done
