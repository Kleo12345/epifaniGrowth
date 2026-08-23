#!/usr/bin/env bash
# Start the Epifani Growth Engine scheduler as a background daemon.
# Logs go to scheduler.log; PID is saved to scheduler.pid for stopping.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/scheduler.pid"
LOG_FILE="$SCRIPT_DIR/scheduler.log"

if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Scheduler is already running (PID $PID). Use stop_scheduler.sh to stop it."
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

# Resolve the conda Python for the epifani-growth environment
CONDA_PYTHON=$(conda run -n epifani-growth which python 2>/dev/null || true)
if [[ -z "$CONDA_PYTHON" ]]; then
    echo "Error: conda environment 'epifani-growth' not found. Run: conda activate epifani-growth"
    exit 1
fi

echo "Starting Epifani scheduler..."
echo "  Log: $LOG_FILE"
echo "  PID: $PID_FILE"

nohup "$CONDA_PYTHON" "$SCRIPT_DIR/core/scheduler.py" \
    >> "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
echo "Started (PID $!)."
echo "Tail the log: tail -f $LOG_FILE"
