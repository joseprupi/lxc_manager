from fastapi import APIRouter
from pydantic import BaseModel
from backend.database import get_setting, set_setting

router = APIRouter()

class ConfigUpdate(BaseModel):
    backup_path: str

@router.get("/")
def get_config():
    return {
        # Default to /tmp if not set
        "backup_path": get_setting("backup_path", "/tmp/lxc_backups") 
    }

@router.post("/")
def update_config(config: ConfigUpdate):
    set_setting("backup_path", config.backup_path)
    return {"status": "updated", "config": config}