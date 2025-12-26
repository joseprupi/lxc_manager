# LXC Simple Manager

A lightweight, stateless web interface for managing pure LXC containers. 
It uses standard system tools (`lxc-ls`, `lxc-create`) via Python's `subprocess`, avoiding complex C-bindings or databases.

## Prerequisites
- Linux host with LXC installed (`sudo apt install lxc`)
- Python 3.8+
- Root/Sudo privileges (required for LXC management)

## Quick Start

1. **Install Dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

2. **Run the Server:**
   ```bash
   sudo ./run.sh
   ```

3. **Open the Dashboard:**
   Open `frontend/index.html` in your browser.

## Architecture
- **Backend:** FastAPI (Python). No database. Source of truth is the OS.
- **Frontend:** Vue 3 (CDN). No build steps required.
- **Networking:** Relies on standard LXC networking.

## Project Structure
- `backend/core/adapter.py`: The wrapper around `subprocess` calls.
- `backend/api/routers`: API endpoints.
- `frontend/`: Static HTML/JS files.
