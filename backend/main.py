from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # <-- NEW IMPORT
from fastapi.responses import FileResponse   # <-- NEW IMPORT
import os

from backend.api.routers import containers, settings, network
from backend.database import create_db_and_tables
from backend.core.network import net_manager

app = FastAPI(title="LXC Simple Manager")

# Unified Startup Event (Cleaned up duplicates)
@app.on_event("startup")
def on_startup():
    # 1. Create DB Tables
    create_db_and_tables()
    
    # 2. Load Network Rules from DB to Kernel
    try:
        net_manager.initialize_network()
    except Exception as e:
        print(f"CRITICAL: Failed to initialize network: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(containers.router, prefix="/api/containers", tags=["containers"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(network.router, prefix="/api/network", tags=["network"])

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def read_root():
    # This assumes your working directory is /opt/lxc_manager (set in systemd)
    return FileResponse('frontend/index.html')

@app.get("/api/health")
def health_check():
    return {"status": "LXC Manager Running", "db": "SQLite"}