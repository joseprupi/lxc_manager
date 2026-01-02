"""
LXC Simple Manager - Database Models and Operations

This module defines the SQLModel-based database schema and provides
helper functions for common database operations.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, Session, create_engine, select


# =============================================================================
# Database Models
# =============================================================================

class Setting(SQLModel, table=True):
    """
    Key-value store for application settings.
    
    Attributes:
        key: Setting identifier (primary key)
        value: Setting value as string
    """
    key: str = Field(primary_key=True)
    value: str


class AuditLog(SQLModel, table=True):
    """
    Audit log for tracking container operations.
    
    Attributes:
        id: Auto-generated primary key
        timestamp: When the action occurred
        action: Type of action (BACKUP, DELETE, START, STOP, etc.)
        container_name: Name of the affected container
        details: Additional context about the action
        status: Outcome (SUCCESS, ERROR)
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now)
    action: str
    container_name: str
    details: Optional[str] = None
    status: str


class PortMapping(SQLModel, table=True):
    """
    Port forwarding rule for DNAT configuration.
    
    Attributes:
        id: Auto-generated primary key
        interface: Network interface (e.g., "enp6s0f1") or "all"
        protocol: Transport protocol ("tcp" or "udp")
        external_port: Public-facing port number
        internal_ip: Container's internal IP address
        internal_port: Container's internal port number
        comment: Optional description of the rule
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    interface: str
    protocol: str
    external_port: int
    internal_ip: str
    internal_port: int
    comment: Optional[str] = None


# =============================================================================
# Database Engine Configuration
# =============================================================================

SQLITE_FILE_NAME = "lxc_manager.db"
SQLITE_URL = f"sqlite:///{SQLITE_FILE_NAME}"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False}  # Required for FastAPI + SQLite
)


def create_db_and_tables():
    """Initialize database schema, creating tables if they don't exist."""
    SQLModel.metadata.create_all(engine)


# =============================================================================
# Settings Operations
# =============================================================================

def get_setting(key: str, default: str = "") -> str:
    """
    Retrieve a setting value from the database.
    
    Args:
        key: The setting identifier
        default: Value to return if setting doesn't exist
        
    Returns:
        The setting value or default
    """
    with Session(engine) as session:
        setting = session.get(Setting, key)
        return setting.value if setting else default


def set_setting(key: str, value: str) -> None:
    """
    Store or update a setting in the database.
    
    Args:
        key: The setting identifier
        value: The value to store
    """
    with Session(engine) as session:
        setting = session.get(Setting, key)
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value)
        session.add(setting)
        session.commit()


# =============================================================================
# Audit Log Operations
# =============================================================================

def log_action(action: str, container: str, status: str, details: str = "") -> None:
    """
    Record an action in the audit log.
    
    Args:
        action: Type of action performed
        container: Name of the affected container
        status: Outcome of the action
        details: Additional context
    """
    with Session(engine) as session:
        log = AuditLog(
            action=action,
            container_name=container,
            status=status,
            details=details
        )
        session.add(log)
        session.commit()


# =============================================================================
# Port Mapping Operations
# =============================================================================

def get_all_rules() -> list[PortMapping]:
    """
    Retrieve all port forwarding rules from the database.
    
    Returns:
        List of all PortMapping records
    """
    with Session(engine) as session:
        return list(session.exec(select(PortMapping)).all())


def add_rule_to_db(rule: PortMapping) -> PortMapping:
    """
    Add a new port forwarding rule to the database.
    
    Args:
        rule: The port mapping configuration to add
        
    Returns:
        The created PortMapping with assigned ID
        
    Raises:
        ValueError: If the external port is already in use
    """
    with Session(engine) as session:
        existing = session.exec(
            select(PortMapping).where(PortMapping.external_port == rule.external_port)
        ).first()
        
        if existing:
            raise ValueError(f"Port {rule.external_port} is already mapped")
        
        session.add(rule)
        session.commit()
        session.refresh(rule)
        return rule


def delete_rule_from_db(external_port: int) -> bool:
    """
    Remove a port forwarding rule from the database.
    
    Args:
        external_port: The external port of the rule to delete
        
    Returns:
        True if a rule was deleted, False otherwise
    """
    with Session(engine) as session:
        rule = session.exec(
            select(PortMapping).where(PortMapping.external_port == external_port)
        ).first()
        
        if rule:
            session.delete(rule)
            session.commit()
            return True
        return False
