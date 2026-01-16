# LXC Simple Manager

A lightweight web interface for managing Linux Containers (LXC) on Debian/Ubuntu servers. Provides a modern UI for container lifecycle management, network configuration, and backups without requiring complex orchestration tools.

**Intended for development environments, not production workloads.**

## Features

### Container Management
- **Lifecycle Control**: Start, stop, and delete containers
- **One-Click Creation**: Deploy containers from distribution templates (Debian, Ubuntu, Alpine)
- **Backup**: Create compressed tarballs of containers to a configurable directory

### Network Configuration
- **Port Forwarding (DNAT)**: Visual manager for iptables NAT rules
- **Safe Architecture**: Uses a dedicated iptables chain (`LXC_MANAGER`) to avoid interfering with system rules
- **Static IPs**: Manage DHCP leases for containers directly from the UI

### Persistence
- **SQLite Database**: All settings and network rules stored locally
- **Automatic Sync**: Network rules are automatically applied to the kernel on startup

## Installation

### Prerequisites

```bash
sudo apt install python3-lxc lxc lxc-net bridge-utils
```

### Automatic Install (Recommended)

```bash
git clone https://github.com/joseprupi/lxc-simple-manager
cd lxc-simple-manager
sudo ./install.sh
```

This installs to `/opt/lxc_manager` and configures a systemd service.

### Manual Setup (Development)

```bash
# Create virtual environment with system packages (required for python3-lxc)
python3 -m venv venv --system-site-packages
./venv/bin/pip install -r backend/requirements.txt

# Run in development mode
sudo ./run.sh
```

## Usage

### Access

- **Web Interface**: `http://<SERVER_IP>:8001`
- **API Documentation**: `http://<SERVER_IP>:8001/docs`

### Service Management

```bash
# Status
systemctl status lxc-manager

# Logs
journalctl -u lxc-manager -f

# Restart
systemctl restart lxc-manager
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/containers` | List all containers |
| POST | `/api/containers` | Create a new container |
| POST | `/api/containers/{name}/start` | Start a container |
| POST | `/api/containers/{name}/stop` | Stop a container |
| DELETE | `/api/containers/{name}` | Delete a container |
| POST | `/api/containers/{name}/backup` | Backup a container |
| GET | `/api/network/rules` | List port forwarding rules |
| POST | `/api/network/rules` | Add a port forwarding rule |
| DELETE | `/api/network/rules/{port}` | Delete a rule |
| GET | `/api/network/dhcp` | List DHCP assignments |
| POST | `/api/network/dhcp` | Add/update DHCP assignment |
| GET | `/api/settings` | Get application settings |
| POST | `/api/settings` | Update settings |

## Security Considerations

⚠️ **This tool runs as root and exposes system-level controls.**

- Do **not** expose to the public internet
- Run only on trusted networks
- Consider placing behind a reverse proxy with authentication
- The delete container functionality permanently destroys data

## Project Structure

```
lxc-simple-manager/
├── backend/
│   ├── api/
│   │   └── routers/
│   │       ├── containers.py    # Container lifecycle API
│   │       ├── network.py       # Network configuration API
│   │       └── settings.py      # Settings API
│   ├── core/
│   │   ├── adapter.py           # LXC operations (native/shell)
│   │   └── network.py           # iptables/DHCP management
│   ├── database.py              # SQLModel definitions
│   ├── schemas.py               # Pydantic schemas
│   ├── main.py                  # FastAPI application
│   └── requirements.txt
├── frontend/
│   └── index.html               # Single-page Vue.js application
├── install.sh                   # Production installer
├── run.sh                       # Development runner
├── lxc-manager.service          # systemd unit file
└── README.md
```

## License

MIT
