from fastapi import APIRouter, HTTPException
from typing import List, Dict
from backend.core.network import net_manager
from backend.database import PortMapping

router = APIRouter()

@router.get("/dhcp")
def get_dhcp_leases():
    # Helper to get current static IP assignments from the manager
    return net_manager.get_static_ips()

@router.post("/dhcp")
def set_dhcp_lease(data: Dict[str, str]):
    if "name" not in data or "ip" not in data:
        raise HTTPException(400, "Missing name or ip")
    try:
        net_manager.set_static_ip(data["name"], data["ip"])
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(500, str(e))

# --- Rules Endpoints ---
@router.get("/rules", response_model=List[PortMapping])
def get_rules():
    # Helper to get current rules from the manager (which gets them from DB)
    return net_manager.get_port_forwards()

@router.post("/rules")
def add_rule(rule: PortMapping):
    try:
        # The manager handles adding to DB and syncing to Kernel
        net_manager.add_forwarding_rule(rule)
        return {"status": "added", "rule": rule}
    except ValueError as e:
        raise HTTPException(400, str(e)) # Duplicate port error
    except Exception as e:
        raise HTTPException(500, str(e))

@router.delete("/rules/{port}")
def delete_rule(port: int):
    try:
        net_manager.remove_forwarding_rule(port)
        return {"status": "removed", "port": port}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/apply")
def apply_changes():
    try:
        net_manager.apply_iptables()
        return {"status": "system_updated"}
    except Exception as e:
        raise HTTPException(500, f"Restore failed: {e}")