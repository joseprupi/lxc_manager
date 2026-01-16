#!/bin/bash
#
# LXC Simple Manager - Development Runner
#
# Starts the FastAPI backend in development mode with auto-reload.
# Must be run as root since LXC operations require elevated privileges.
#

set -e

BACKEND_PORT=8001

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root."
    echo "Usage: sudo ./run.sh"
    exit 1
fi

# Get the original user for display purposes
REAL_USER="${SUDO_USER:-$USER}"
SERVER_IP=$(hostname -I | awk '{print $1}')

# Path to virtual environment Python
VENV_PYTHON="./venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found."
    echo "Please run: python3 -m venv venv --system-site-packages"
    echo "Then: ./venv/bin/pip install -r backend/requirements.txt"
    exit 1
fi

# Cleanup function for graceful shutdown
cleanup() {
    echo ""
    echo "Shutting down..."
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "================================================"
echo "  LXC Simple Manager - Development Mode"
echo "================================================"
echo ""
echo "Starting backend server..."

# Start FastAPI with uvicorn
$VENV_PYTHON -m uvicorn backend.main:app \
    --reload \
    --host 0.0.0.0 \
    --port $BACKEND_PORT \
    > backend.log 2>&1 &
BACKEND_PID=$!

sleep 2

# Check if backend started successfully
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Error: Backend failed to start. Check backend.log for details."
    exit 1
fi

echo ""
echo "Server running!"
echo ""
echo "  Web Interface:  http://${SERVER_IP}:${BACKEND_PORT}"
echo "  API Docs:       http://${SERVER_IP}:${BACKEND_PORT}/docs"
echo "  Logs:           ./backend.log"
echo ""
echo "Press Ctrl+C to stop."
echo ""

wait
