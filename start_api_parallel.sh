#!/bin/bash
# High-throughput local API for bulk IRS layer pipeline (no hot-reload).
# Use when Horizon dispatches many concurrent layer/1 jobs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "Error: venv not found. Create it first: python3 -m venv venv && pip install -r requirements.txt"
    exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

export APP_RELOAD=false
HOST="${APP_HOST:-0.0.0.0}"
PORT="${APP_PORT:-8000}"
WORKERS="${WORKERS:-20}"
TIMEOUT="${GUNICORN_TIMEOUT:-360}"

mkdir -p logs

free_port() {
    local port=$1
    local attempt
    for attempt in 1 2 3 4 5; do
        local pids
        pids="$(lsof -ti:"$port" 2>/dev/null || true)"
        if [ -z "$pids" ]; then
            return 0
        fi
        echo "Stopping processes on port $port (attempt $attempt): $(echo "$pids" | tr '\n' ' ')"
        # shellcheck disable=SC2086
        kill -9 $pids 2>/dev/null || true
        pkill -9 -f "uvicorn.*main:app" 2>/dev/null || true
        sleep 3
    done
    # Parent uvicorn can linger briefly after worker PIDs die.
    local waited=0
    while lsof -ti:"$port" >/dev/null 2>&1 && [ "$waited" -lt 15 ]; do
        sleep 1
        waited=$((waited + 1))
    done
    if lsof -ti:"$port" >/dev/null 2>&1; then
        echo "ERROR: port $port is still in use:"
        lsof -i:"$port" || true
        exit 1
    fi
}

free_port "$PORT"

echo "Starting Grant Writer API: $WORKERS workers, timeout ${TIMEOUT}s"
echo "  URL: http://127.0.0.1:$PORT/docs"
echo "  Horizon should target: http://127.0.0.1:$PORT"

exec uvicorn main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --timeout-keep-alive "$TIMEOUT" \
    --limit-concurrency 200 \
    --log-level info
