"""
LXC Simple Manager - Container Management API

Endpoints for container lifecycle operations including:
    - List, start, stop containers
    - Create and delete containers
    - Backup containers to disk
"""

import os
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.core.adapter import lxc
from backend.database import get_setting, log_action
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
    
    Returns:
        Absolute path to the backup directory
    """
    backup_path = get_setting("backup_path", DEFAULT_BACKUP_PATH)
    
    # Ensure directory exists
    if not os.path.exists(backup_path):
        try:
            os.makedirs(backup_path, exist_ok=True)
        except Exception as e:
            print(f"ERROR: Could not create backup directory: {e}")
            backup_path = DEFAULT_BACKUP_PATH
            os.makedirs(backup_path, exist_ok=True)
    
    return backup_path


# =============================================================================
# List and Get Operations
# =============================================================================

@router.get("/", response_model=List[ContainerInfo])
def list_containers():
    """
    List all LXC containers.
    
    Returns:
        List of containers with their state and IP addresses
    """
    return lxc.list_containers()


@router.get("/{name}", response_model=ContainerInfo)
def get_container(name: str):
    """
    Get details for a specific container.
    
    Args:
        name: Container name
        
    Returns:
        Container information
        
    Raises:
        HTTPException: 404 if container not found
    """
    container = lxc.get_container(name)
    if not container:
        raise HTTPException(status_code=404, detail=f"Container '{name}' not found")
    return container


# =============================================================================
# Lifecycle Operations
# =============================================================================

@router.post("/{name}/start")
def start_container(name: str):
    """
    Start a stopped container.
    
    Args:
        name: Container name
        
    Returns:
        Success status
    """
    try:
        lxc.start_container(name)
        log_action("START", name, "SUCCESS")
        return {"status": "started", "name": name}
    except Exception as e:
        log_action("START", name, "ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/stop")
def stop_container(name: str):
    """
    Stop a running container.
    
    Args:
        name: Container name
        
    Returns:
        Success status
    """
    try:
        lxc.stop_container(name)
        log_action("STOP", name, "SUCCESS")
        return {"status": "stopped", "name": name}
    except Exception as e:
        log_action("STOP", name, "ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Create and Delete Operations
# =============================================================================

@router.post("/")
async def create_container(req: CreateContainerRequest, bg: BackgroundTasks):
    """
    Create a new container (asynchronous).
    
    Container creation runs in the background as it may take several minutes
    to download and configure the container image.
    
    Args:
        req: Container creation parameters
        bg: FastAPI background tasks
        
    Returns:
        Status indicating creation has been initiated
        
    Raises:
        HTTPException: 400 if container already exists
    """
    if lxc.get_container(req.name):
        raise HTTPException(status_code=400, detail=f"Container '{req.name}' already exists")
    
    def _create():
        try:
            lxc.create_container(req.name, req.distro, req.release, req.arch)
            log_action("CREATE", req.name, "SUCCESS", f"{req.distro}/{req.release}/{req.arch}")
        except Exception as e:
            log_action("CREATE", req.name, "ERROR", str(e))
    
    bg.add_task(_create)
    return {"status": "creation_initiated", "name": req.name}


@router.delete("/{name}")
def delete_container(name: str):
    """
    Delete a container.
    
    WARNING: This permanently destroys the container and all its data.
    The container is stopped first if running.
    
    Args:
        name: Container name
        
    Returns:
        Success status
    """
    try:
        lxc.delete_container(name)
        log_action("DELETE", name, "SUCCESS")
        return {"status": "deleted", "name": name}
    except Exception as e:
        log_action("DELETE", name, "ERROR", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Backup Operations
# =============================================================================

@router.post("/{name}/backup")
def backup_container(name: str, bg: BackgroundTasks):
    """
    Create a backup of a container (asynchronous).
    
    Creates a compressed tarball of the container in the configured backup
    directory. The container is temporarily stopped during backup to ensure
    consistency, then restarted.
    
    Args:
        name: Container name
        bg: FastAPI background tasks
        
    Returns:
        Status indicating backup has started
    """
    backup_path = get_backup_path()
    
    def _backup():
        try:
            print(f"INFO: Starting backup of '{name}' to {backup_path}...")
            filename = lxc.backup_container(name, backup_path)
            full_path = os.path.join(backup_path, filename)
            print(f"INFO: Backup complete: {full_path}")
            log_action("BACKUP", name, "SUCCESS", full_path)
        except Exception as e:
            print(f"ERROR: Backup failed for '{name}': {e}")
            log_action("BACKUP", name, "ERROR", str(e))
    
    bg.add_task(_backup)
    return {"status": "backup_started", "name": name, "destination": backup_path}
