"""
LXC Simple Manager - Container Management API

Endpoints for container lifecycle operations including:
    - List, start, stop containers
    - Create and delete containers
    - Backup containers to disk
"""

import os
import traceback
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.core.adapter import lxc
from backend.database import get_setting
from backend.schemas import ContainerInfo, CreateContainerRequest


router = APIRouter()


# =============================================================================
# Configuration Helpers
# =============================================================================

DEFAULT_BACKUP_PATH = "/tmp/lxc_backups"


def get_backup_path() -> str:
    """
    Get the configured backup directory path.
    
    Reads from database settings, falls back to default if not configured.
    Ensures the directory exists before returning.
    """
    backup_path = get_setting("backup_path", DEFAULT_BACKUP_PATH)
    
    if not os.path.exists(backup_path):
        try:
            os.makedirs(backup_path, exist_ok=True)
        except Exception as e:
            print(f"ERROR: Could not create backup directory: {e}")
            backup_path = DEFAULT_BACKUP_PATH
            os.makedirs(backup_path, exist_ok=True)
    
    return backup_path


def safe_log_action(action: str, container: str, status: str, details: str = ""):
    """Safely log an action, ignoring errors if audit table doesn't exist."""
    try:
        from backend.database import log_action
        log_action(action, container, status, details)
    except Exception as e:
        print(f"WARNING: Could not log action: {e}")


# =============================================================================
# List and Get Operations
# =============================================================================

@router.get("/", response_model=List[ContainerInfo])
def list_containers():
    """List all LXC containers."""
    return lxc.list_containers()


@router.get("/{name}", response_model=ContainerInfo)
def get_container(name: str):
    """Get details for a specific container."""
    container = lxc.get_container(name)
    if not container:
        raise HTTPException(status_code=404, detail=f"Container '{name}' not found")
    return container


# =============================================================================
# Lifecycle Operations
# =============================================================================

@router.post("/{name}/start")
def start_container(name: str):
    """Start a stopped container."""
    try:
        lxc.start_container(name)
        safe_log_action("START", name, "SUCCESS")
        return {"status": "started", "name": name}
    except Exception as e:
        # Print full traceback to logs for debugging
        print(f"ERROR starting container '{name}':")
        traceback.print_exc()
        safe_log_action("START", name, "ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/stop")
def stop_container(name: str):
    """Stop a running container."""
    try:
        lxc.stop_container(name)
        safe_log_action("STOP", name, "SUCCESS")
        return {"status": "stopped", "name": name}
    except Exception as e:
        print(f"ERROR stopping container '{name}':")
        traceback.print_exc()
        safe_log_action("STOP", name, "ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Create and Delete Operations
# =============================================================================

@router.post("/")
async def create_container(req: CreateContainerRequest, bg: BackgroundTasks):
    """Create a new container (asynchronous)."""
    if lxc.get_container(req.name):
        raise HTTPException(status_code=400, detail=f"Container '{req.name}' already exists")
    
    def _create():
        try:
            lxc.create_container(req.name, req.distro, req.release, req.arch)
            safe_log_action("CREATE", req.name, "SUCCESS", f"{req.distro}/{req.release}/{req.arch}")
        except Exception as e:
            print(f"ERROR creating container '{req.name}':")
            traceback.print_exc()
            safe_log_action("CREATE", req.name, "ERROR", str(e))
    
    bg.add_task(_create)
    return {"status": "creation_initiated", "name": req.name}


@router.delete("/{name}")
def delete_container(name: str):
    """Delete a container (permanently destroys all data)."""
    try:
        lxc.delete_container(name)
        safe_log_action("DELETE", name, "SUCCESS")
        return {"status": "deleted", "name": name}
    except Exception as e:
        print(f"ERROR deleting container '{name}':")
        traceback.print_exc()
        safe_log_action("DELETE", name, "ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Backup Operations
# =============================================================================

@router.post("/{name}/backup")
def backup_container(name: str, bg: BackgroundTasks):
    """Create a backup of a container (asynchronous)."""
    backup_path = get_backup_path()
    
    def _backup():
        try:
            print(f"INFO: Starting backup of '{name}' to {backup_path}...")
            filename = lxc.backup_container(name, backup_path)
            full_path = os.path.join(backup_path, filename)
            print(f"INFO: Backup complete: {full_path}")
            safe_log_action("BACKUP", name, "SUCCESS", full_path)
        except Exception as e:
            print(f"ERROR: Backup failed for '{name}':")
            traceback.print_exc()
            safe_log_action("BACKUP", name, "ERROR", str(e))
    
    bg.add_task(_backup)
    return {"status": "backup_started", "name": name, "destination": backup_path}


# =============================================================================
# Monitoring Operations
# =============================================================================

@router.get("/{name}/logs")
def get_container_logs(name: str, lines: int = 100):
    """
    Get recent logs from a container.
    
    Args:
        name: Container name
        lines: Number of lines to return (default 100, max 1000)
        
    Returns:
        Log content
    """
    # Limit lines to prevent abuse
    lines = min(max(1, lines), 1000)
    
    try:
        logs = lxc.get_container_logs(name, lines)
        return {"name": name, "lines": lines, "content": logs}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}/stats")
def get_container_stats(name: str):
    """
    Get resource usage statistics for a container.
    
    Returns CPU, memory, and disk usage information.
    
    Args:
        name: Container name
        
    Returns:
        Resource statistics
    """
    try:
        stats = lxc.get_container_stats(name)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))