from fastapi import APIRouter, HTTPException, BackgroundTasks
from backend.core.adapter import lxc
from backend.schemas import ContainerInfo, CreateContainerRequest
from typing import List
import sqlite3
import os

router = APIRouter()

# --- HELPER: Get Backup Path from DB ---
def get_backup_path():
    # Use relative path for local dev, absolute for prod
    db_path = "lxc_manager.db" 
    if os.path.exists("/opt/lxc_manager/lxc_manager.db"):
        db_path = "/opt/lxc_manager/lxc_manager.db"
        
    default_path = "/tmp/lxc_backups"
    final_path = default_path
    source = "DEFAULT"

    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='setting'")
            if cursor.fetchone():
                try:
                    cursor.execute("SELECT backup_path FROM setting LIMIT 1")
                    row = cursor.fetchone()
                    if row and row['backup_path'] and row['backup_path'].strip() != "":
                        final_path = row['backup_path']
                        source = "DATABASE"
                except Exception:
                    pass
            conn.close()
    except Exception as e:
        print(f"⚠️ DB Read Error: {e}")

    # Ensure backup directory exists
    if not os.path.exists(final_path):
        try:
            os.makedirs(final_path, exist_ok=True)
        except Exception as e:
            print(f"❌ CRITICAL: Could not create backup dir: {e}")
    
    print(f"💾 Backup Config: {final_path} (Source: {source})")
    return final_path

@router.get("/", response_model=List[ContainerInfo])
def get_containers():
    return lxc.list_containers()

@router.post("/{name}/start")
def start_container(name: str):
    lxc.start_container(name)
    return {"status": "started", "name": name}

@router.post("/{name}/stop")
def stop_container(name: str):
    lxc.stop_container(name)
    return {"status": "stopped", "name": name}

@router.delete("/{name}")
def delete_container(name: str):
    lxc.delete_container(name)
    return {"status": "deleted", "name": name}

@router.post("/")
async def create_container(req: CreateContainerRequest, bg: BackgroundTasks):
    if lxc.get_container(req.name):
        raise HTTPException(status_code=400, detail="Exists")
    bg.add_task(lxc.create_container, req.name, req.distro, req.release, req.arch)
    return {"status": "creation_initiated"}

@router.post("/{name}/backup")
def backup_container_endpoint(name: str, bg: BackgroundTasks):
    path = get_backup_path()
    
    def _run():
        try:
            print(f"⏳ Backing up {name} to {path}...")
            filename = lxc.backup_container(name, path)
            print(f"✅ Backup DONE: {os.path.join(path, filename)}")
        except Exception as e:
            print(f"❌ Backup FAILED: {e}")

    bg.add_task(_run)
    return {"status": "started"}