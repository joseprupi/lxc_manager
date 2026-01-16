"""
LXC Simple Manager - Pydantic Schemas

Request and response models for the API endpoints.
"""

from typing import List

from pydantic import BaseModel, Field


class ContainerInfo(BaseModel):
    """
    Container information returned by list and get operations.
    
    Attributes:
        name: Container name
        state: Current state (RUNNING, STOPPED, FROZEN, etc.)
        ipv4: List of IPv4 addresses assigned to the container
        ipv6: List of IPv6 addresses assigned to the container
    """
    name: str
    state: str
    ipv4: List[str] = Field(default_factory=list)
    ipv6: List[str] = Field(default_factory=list)


class CreateContainerRequest(BaseModel):
    """
    Request payload for creating a new container.
    
    Attributes:
        name: Desired container name (must be unique)
        distro: Linux distribution (e.g., "alpine", "debian", "ubuntu")
        release: Distribution release version (e.g., "3.18", "bookworm")
        arch: Target architecture (default: "amd64")
    """
    name: str = Field(..., min_length=1, max_length=64)
    distro: str = Field(..., min_length=1)
    release: str = Field(..., min_length=1)
    arch: str = Field(default="amd64")


class ConfigUpdate(BaseModel):
    """
    Request payload for updating application settings.
    
    Attributes:
        backup_path: Directory path for container backups
    """
    backup_path: str = Field(..., min_length=1)
