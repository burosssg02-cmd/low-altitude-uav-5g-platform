#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"

mkdir -p "$LOG_DIR"

echo "========================================"
echo " Low-Altitude UAV Platform V0.9"
echo "========================================"

# Load NVM / Node.js environment
if [ -f "$HOME/.nvm/nvm.sh" ]; then
    export NVM_DIR="$HOME/.nvm"
    . "$NVM_DIR/nvm.sh"
fi

# Check required executables
if [ ! -x "$PROJECT_ROOT/.venv/bin/uvicorn" ]; then
    echo "[ERROR] uvicorn not found:"
    echo "  $PROJECT_ROOT/.venv/bin/uvicorn"
    exit 1
fi

if [ ! -x "$PROJECT_ROOT/frontend/node_modules/.bin/vite" ]; then
    echo "[ERROR] Vite not found."
    echo "Run:"
    echo "  cd $PROJECT_ROOT/frontend"
    echo "  npm install"
    exit 1
fi

echo "[1/2] Starting FastAPI backend..."

cd "$PROJECT_ROOT"

nohup "$PROJECT_ROOT/.venv/bin/uvicorn" \
    backend.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    > "$LOG_DIR/backend.log" \
    2>&1 &

BACKEND_PID=$!
echo "$BACKEND_PID" > "$LOG_DIR/backend.pid"

sleep 2

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "[ERROR] Backend failed to start."
    echo "Check:"
    echo "  $LOG_DIR/backend.log"
    exit 1
fi

echo "[2/2] Starting React Dashboard..."

cd "$PROJECT_ROOT/frontend"

nohup "$PROJECT_ROOT/frontend/node_modules/.bin/vite" \
    --host 0.0.0.0 \
    --port 5173 \
    > "$LOG_DIR/frontend.log" \
    2>&1 &

FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$LOG_DIR/frontend.pid"

sleep 2

if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "[ERROR] Frontend failed to start."
    echo "Check:"
    echo "  $LOG_DIR/frontend.log"
    exit 1
fi

echo
echo "Backend PID:  $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo
echo "Backend:"
echo "  http://localhost:8000"
echo
echo "Dashboard:"
echo "  http://localhost:5173"
echo
echo "Swagger:"
echo "  http://localhost:8000/docs"
echo
echo "Logs:"
echo "  logs/backend.log"
echo "  logs/frontend.log"
echo
echo "V0.9 platform started."
