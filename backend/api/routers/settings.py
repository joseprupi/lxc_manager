"""
LXC Simple Manager - Settings API

Endpoints for managing application configuration.
"""

from fastapi import APIRouter

from backend.database import get_setting, set_setting
from backend.schemas import ConfigUpdate


router = APIRouter()


DEFAULT_BACKUP_PATH = "/tmp/lxc_backups"


@router.get("/")
def get_config():
    """
    Get current application configuration.
    
    Returns:
        dict: Current settings including backup_path
    """
    return {
        "backup_path": get_setting("backup_path", DEFAULT_BACKUP_PATH)
    }


@router.post("/")
def update_config(config: ConfigUpdate):
    """
    Update application configuration.
    
    Args:
        config: New configuration values
        
    Returns:
        Confirmation with updated values
    """
    set_setting("backup_path", config.backup_path)
    return {
        "status": "updated",
        "config": {
            "backup_path": config.backup_path
        }
    }
