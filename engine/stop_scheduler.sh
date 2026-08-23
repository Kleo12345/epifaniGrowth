#!/usr/bin/env bash
# Stop the Epifani Growth Engine scheduler.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/scheduler.pid"

if [[ ! -f "$PID_FILE" ]]; then
    echo "Scheduler is not running (no PID file found)."
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    rm -f "$PID_FILE"
    echo "Scheduler stopped (PID $PID)."
else
    echo "Scheduler process $PID not found — cleaning up stale PID file."
    rm -f "$PID_FILE"
fi
