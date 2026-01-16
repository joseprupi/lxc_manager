"""
LXC Simple Manager - Network Configuration API

Endpoints for managing:
    - Port forwarding rules (iptables DNAT)
    - Static DHCP assignments
"""

from typing import Dict, List

from fastapi import APIRouter, HTTPException

from backend.core.network import net_manager
from backend.database import PortMapping


router = APIRouter()


# =============================================================================
# DHCP / Static IP Endpoints
# =============================================================================

@router.get("/dhcp")
def get_dhcp_leases() -> Dict[str, str]:
    """
    Get all static DHCP assignments.
    
    Returns:
        Dict mapping container names to IP addresses
    """
    return net_manager.get_static_ips()


@router.post("/dhcp")
def set_dhcp_lease(data: Dict[str, str]):
    """
    Create or update a static DHCP assignment.
    
    Args:
        data: Dict with "name" and "ip" keys
        
    Returns:
        Success status
        
    Raises:
        HTTPException: 400 if required fields missing
        HTTPException: 500 on system error
    """
    if "name" not in data or "ip" not in data:
        raise HTTPException(status_code=400, detail="Missing 'name' or 'ip' field")
    
    try:
        net_manager.set_static_ip(data["name"], data["ip"])
        return {"status": "success", "name": data["name"], "ip": data["ip"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/dhcp/{name}")
def delete_dhcp_lease(name: str):
    """
    Remove a static DHCP assignment.
    
    Args:
        name: Container name to remove
        
    Returns:
        Success status
        
    Raises:
        HTTPException: 404 if not found
    """
    if net_manager.remove_static_ip(name):
        return {"status": "deleted", "name": name}
    raise HTTPException(status_code=404, detail=f"No DHCP entry for '{name}'")


# =============================================================================
# Port Forwarding Endpoints
# =============================================================================

@router.get("/rules", response_model=List[PortMapping])
def get_rules():
    """
    Get all port forwarding rules.
    
    Returns:
        List of PortMapping objects
    """
    return net_manager.get_port_forwards()


@router.post("/rules")
def add_rule(rule: PortMapping):
    """
    Add a new port forwarding rule.
    
    The rule is immediately applied to iptables.
    
    Args:
        rule: Port mapping configuration
        
    Returns:
        Success status with the created rule
        
    Raises:
        HTTPException: 400 if port already in use
        HTTPException: 500 on system error
    """
    try:
        net_manager.add_forwarding_rule(rule)
        return {"status": "added", "rule": rule}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rules/{port}")
def delete_rule(port: int):
    """
    Delete a port forwarding rule.
    
    The rule is immediately removed from iptables.
    
    Args:
        port: External port number of the rule to delete
        
    Returns:
        Success status
        
    Raises:
        HTTPException: 500 on system error
    """
    try:
        net_manager.remove_forwarding_rule(port)
        return {"status": "deleted", "port": port}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply")
def apply_network_changes():
    """
    Force re-application of all network rules.
    
    Syncs all rules from database to kernel. Use this after making
    multiple changes or to recover from inconsistent state.
    
    Returns:
        Success status
        
    Raises:
        HTTPException: 500 on system error
    """
    try:
        net_manager.apply_iptables()
        return {"status": "applied"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
