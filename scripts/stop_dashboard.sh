#!/usr/bin/env bash

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"


stop_process() {
    PID_FILE="$1"
    NAME="$2"

    if [ ! -f "$PID_FILE" ]; then
        echo "$NAME PID file not found."
        return
    fi

    PID="$(cat "$PID_FILE")"

    if ! kill -0 "$PID" 2>/dev/null; then
        echo "$NAME is not running."
        rm -f "$PID_FILE"
        return
    fi

    echo "Stopping $NAME (PID $PID)..."

    kill "$PID" 2>/dev/null

    for _ in {1..10}; do
        if ! kill -0 "$PID" 2>/dev/null; then
            break
        fi

        sleep 0.2
    done

    if kill -0 "$PID" 2>/dev/null; then
        echo "$NAME did not stop gracefully; forcing shutdown..."
        kill -9 "$PID" 2>/dev/null
    fi

    rm -f "$PID_FILE"

    echo "$NAME stopped."
}


stop_process \
    "$LOG_DIR/backend.pid" \
    "Backend"

stop_process \
    "$LOG_DIR/frontend.pid" \
    "Frontend"
