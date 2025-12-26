# LXC Simple Manager

A lightweight, stateful web interface for managing Linux Containers (LXC) on Debian/Ubuntu servers. 
It provides a safe, modern UI to manage container lifecycles, network rules, and backups without needing complex orchestration tools like Kubernetes or Proxmox.

![Dashboard Screenshot](./screenshots/dashboard_placeholder.png)

## 🚀 Features

### 📦 Container Management
* **Lifecycle Control:** Start, Stop, Freeze, and Delete containers.
* **One-Click Creation:** Download and deploy generic Linux distro images (Debian, Ubuntu, Alpine).
* **Safety First:** "Nuclear Code" confirmation required for deletion.

### 🛡️ Network Orchestrator
* **Port Forwarding (DNAT):** Visual manager for `iptables`. 
* **Safe Architecture:** Uses a custom sidecar chain (`LXC_MANAGER`) to avoid messing up system-level rules (SSH, Docker).
* **Static IPs:** Manage DHCP leases for containers directly from the UI.
* **Multi-Interface Support:** Bind rules to specific interfaces or listen on `all`.

### 💾 Backup & Persistence
* **Container Snapshots:** One-click backup of entire containers to a secondary disk (HDD/SSD).
* **Stateful Config:** All settings and rules are stored in a local SQLite database (`lxc_manager.db`).
* **Config Safety:** Automatically backs up `/etc/iptables.up.rules` and DHCP configs before applying changes.

![Settings Screenshot](./screenshots/settings_placeholder.png)

## 🛠️ Architecture

* **Backend:** Python (FastAPI) + SQLite (SQLModel)
* **Frontend:** Vue.js 3 + Tailwind CSS (Single HTML file)
* **System Integration:**
    * Direct `lxc-*` command execution / Python bindings.
    * Direct `iptables` chain management.
    * Systemd integration for network persistence.

## ⚡ Installation

1.  **Clone the repo:**
    ```bash
    git clone https://github.com/your-username/lxc-simple-manager.git
    cd lxc-simple-manager
    ```

2.  **Install System Dependencies:**
    ```bash
    sudo apt install python3-lxc lxc lxc-net bridge-utils
    ```

3.  **Setup Environment:**
    ```bash
    # Create venv with access to system packages (crucial for python3-lxc)
    python3 -m venv venv --system-site-packages
    
    # Install Python deps
    ./venv/bin/pip install -r backend/requirements.txt
    ```

4.  **Migrate Existing Rules (Optional):**
    If you have existing iptables rules you want to import into the database:
    ```bash
    sudo ./venv/bin/python3 import_rules.py
    ```

## 🚀 Usage

The manager needs `root` privileges to control LXC and IPTables.

```bash
sudo ./run.sh
```

* **Web Interface:** `http://<SERVER_IP>:8001`
* **API Docs:** `http://<SERVER_IP>:8001/docs`

## ⚠️ Security Note

This tool runs as **root** and exposes system-level controls. 
* **Do not expose this port to the public internet.**
