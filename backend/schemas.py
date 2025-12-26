from pydantic import BaseModel
from typing import List, Optional

class ContainerInfo(BaseModel):
    name: str
    state: str
    ipv4: List[str] = []
    ipv6: List[str] = []

class CreateContainerRequest(BaseModel):
    name: str
    distro: str  # e.g., "alpine", "debian"
    release: str # e.g., "3.18", "bookworm"
    arch: str = "amd64"
