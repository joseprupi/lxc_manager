#!/bin/bash

# 1. Create directory
echo "Installing to /opt/lxc_manager..."
sudo mkdir -p /opt/lxc_manager
if ! command -v rsync &> /dev/null; then
    sudo apt install rsync -y
fi

echo "Syncing files (preserving database)..."
sudo rsync -av --exclude='lxc_manager.db' --exclude='venv' . /opt/lxc_manager/

# 2. Setup Python environment
cd /opt/lxc_manager
python3 -m venv venv --system-site-packages
./venv/bin/pip install -r backend/requirements.txt

# 3. Install Systemd Service
sudo cp lxc-manager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lxc-manager
sudo systemctl start lxc-manager

echo "Installation complete. Service is running on port 8001."