from typing import Optional
from sqlmodel import Field, SQLModel, create_engine, Session, select
from datetime import datetime

# 1. The Models (Tables)

class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now)
    action: str  # e.g., "BACKUP", "DELETE", "START"
    container_name: str
    details: Optional[str] = None
    status: str # "SUCCESS", "ERROR"

class PortMapping(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    interface: str      # e.g., "enp6s0f1" or "all"
    protocol: str       # "tcp" or "udp"
    external_port: int  # e.g., 8080
    internal_ip: str    # "10.0.3.15"
    internal_port: int  # 80
    comment: Optional[str] = None

# 2. The Engine (SQLite file)
sqlite_file_name = "lxc_manager.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

# check_same_thread=False is needed for FastAPI+SQLite
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# Helper to get the backup path (with default)
def get_setting(key: str, default: str = "") -> str:
    with Session(engine) as session:
        setting = session.get(Setting, key)
        return setting.value if setting else default

def set_setting(key: str, value: str):
    with Session(engine) as session:
        setting = session.get(Setting, key)
        if not setting:
            setting = Setting(key=key, value=value)
        else:
            setting.value = value
        session.add(setting)
        session.commit()

def log_action(action: str, container: str, status: str, details: str = ""):
    with Session(engine) as session:
        log = AuditLog(action=action, container_name=container, status=status, details=details)
        session.add(log)
        session.commit()

def get_all_rules():
    with Session(engine) as session:
        return session.exec(select(PortMapping)).all()

def add_rule_to_db(rule: PortMapping):
    with Session(engine) as session:
        # Check for duplicates to avoid errors
        existing = session.exec(
            select(PortMapping).where(PortMapping.external_port == rule.external_port)
        ).first()
        if existing:
            raise ValueError(f"Port {rule.external_port} is already mapped.")
        session.add(rule)
        session.commit()
        session.refresh(rule)
        return rule

def delete_rule_from_db(external_port: int):
    with Session(engine) as session:
        rule = session.exec(
            select(PortMapping).where(PortMapping.external_port == external_port)
        ).first()
        if rule:
            session.delete(rule)
            session.commit()