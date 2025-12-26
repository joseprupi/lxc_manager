from fastapi import APIRouter, HTTPException, BackgroundTasks
from backend.core.adapter import lxc
from backend.schemas import ContainerInfo, CreateContainerRequest
from typing import List

router = APIRouter()

@router.get("/", response_model=List[ContainerInfo])
def get_containers():
    return lxc.list_containers()

@router.post("/{name}/start")
def start_container(name: str):
    try:
        lxc.start_container(name)
        return {"status": "started", "name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{name}/stop")
def stop_container(name: str):
    try:
        lxc.stop_container(name)
        return {"status": "stopped", "name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# @router.delete("/{name}")
# def delete_container(name: str):
#     try:
#         lxc.delete_container(name)
#         return {"status": "deleted", "name": name}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
async def create_container(req: CreateContainerRequest, background_tasks: BackgroundTasks):
    """
    Starts container creation in the background so the UI doesn't freeze.
    """
    # Check if exists
    if lxc.get_container(req.name):
        raise HTTPException(status_code=400, detail="Container already exists")
    
    # We run this in background because downloading templates takes time
    background_tasks.add_task(lxc.create_container, req.name, req.distro, req.release, req.arch)
    
    return {"status": "creation_initiated", "message": f"Creating {req.name} ({req.distro}/{req.release}). This may take a while."}

@router.post("/{name}/backup")
def backup_container_endpoint(name: str, background_tasks: BackgroundTasks):
    # 1. Get path from DB
    path = get_setting("backup_path", "/tmp/lxc_backups")
    
    # 2. Define the background task wrapper so we can log success/fail
    def _run_backup_task():
        try:
            log_action("BACKUP_START", name, "PENDING", f"Target: {path}")
            filename = lxc.backup_container(name, path)
            log_action("BACKUP_COMPLETE", name, "SUCCESS", f"File: {filename}")
        except Exception as e:
            log_action("BACKUP_ERROR", name, "ERROR", str(e))
            print(f"Backup failed: {e}")

    # 3. Queue it
    background_tasks.add_task(_run_backup_task)
    
    return {"status": "started", "message": f"Backup started. Saving to {path}"}