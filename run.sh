#!/bin/bash

# --- CONFIGURATION ---
BACKEND_PORT=8001
FRONTEND_PORT=5500
# ---------------------

if [ "$EUID" -ne 0 ]; then 
  echo "❌ Error: Please run as root: sudo ./run.sh"
  exit 1
fi

REAL_USER=${SUDO_USER:-$USER}
SERVER_IP=$(hostname -I | awk '{print $1}')
# POINT TO THE VENV PYTHON
VENV_PYTHON="./venv/bin/python"

cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    if [ -n "$BACKEND_PID" ]; then kill $BACKEND_PID 2>/dev/null; fi
    if [ -n "$FRONTEND_PID" ]; then kill $FRONTEND_PID 2>/dev/null; fi
    exit
}

trap cleanup SIGINT SIGTERM

echo "🚀 Starting LXC Simple Manager..."

# Start Backend using VENV_PYTHON
echo "   -> Backend on port $BACKEND_PORT..."
$VENV_PYTHON -m uvicorn backend.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT > backend.log 2>&1 &
BACKEND_PID=$!

# Start Frontend
echo "   -> Frontend on port $FRONTEND_PORT..."
sudo -u "$REAL_USER" python3 -m http.server --directory frontend $FRONTEND_PORT --bind 0.0.0.0 > frontend.log 2>&1 &
FRONTEND_PID=$!

sleep 2

echo "✅ Running!"
echo "   -----------------------------------------------------"
echo "   Access from Laptop: http://$SERVER_IP:$FRONTEND_PORT"
echo "   -----------------------------------------------------"
wait