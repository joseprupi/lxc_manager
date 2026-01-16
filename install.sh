#!/bin/bash
#
# LXC Simple Manager - Installation Script
#
# Installs the application to /opt/lxc_manager and configures it as a systemd service.
#

set -e

INSTALL_DIR="/opt/lxc_manager"
SERVICE_NAME="lxc-manager"

echo "================================================"
echo "  LXC Simple Manager - Installation"
echo "================================================"
echo ""

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root."
    echo "Usage: sudo ./install.sh"
    exit 1
fi

# Check for required system packages
echo "Checking dependencies..."
MISSING_DEPS=""

if ! command -v lxc-ls &> /dev/null; then
    MISSING_DEPS="$MISSING_DEPS lxc"
fi

if ! python3 -c "import lxc" 2>/dev/null; then
    MISSING_DEPS="$MISSING_DEPS python3-lxc"
fi

if [ -n "$MISSING_DEPS" ]; then
    echo "Missing required packages:$MISSING_DEPS"
    echo ""
    echo "Install with: apt install$MISSING_DEPS"
    exit 1
fi

echo "Dependencies OK."
echo ""

# Install rsync if not present
if ! command -v rsync &> /dev/null; then
    echo "Installing rsync..."
    apt install -y rsync > /dev/null
fi

# Create installation directory
echo "Creating installation directory..."
mkdir -p "$INSTALL_DIR"

# Sync files (preserve database if it exists)
echo "Copying files..."
rsync -av \
    --exclude='lxc_manager.db' \
    --exclude='venv' \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.log' \
    --exclude='*.pyc' \
    . "$INSTALL_DIR/"

# Setup Python virtual environment
echo "Setting up Python environment..."
cd "$INSTALL_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv --system-site-packages
fi

./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet -r backend/requirements.txt

# Install systemd service
echo "Configuring systemd service..."
cp lxc-manager.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

# Wait for service to start
sleep 2

# Check service status
if systemctl is-active --quiet "$SERVICE_NAME"; then
    SERVER_IP=$(hostname -I | awk '{print $1}')
    echo ""
    echo "================================================"
    echo "  Installation Complete!"
    echo "================================================"
    echo ""
    echo "  Web Interface:  http://${SERVER_IP}:8001"
    echo "  API Docs:       http://${SERVER_IP}:8001/docs"
    echo ""
    echo "  Service Status: systemctl status $SERVICE_NAME"
    echo "  View Logs:      journalctl -u $SERVICE_NAME -f"
    echo ""
else
    echo ""
    echo "Warning: Service may not have started correctly."
    echo "Check status with: systemctl status $SERVICE_NAME"
    exit 1
fi
