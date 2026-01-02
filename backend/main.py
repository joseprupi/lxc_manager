"""
LXC Simple Manager - Main Application Entry Point

A lightweight web interface for managing Linux Containers (LXC) on Debian/Ubuntu servers.
Provides container lifecycle management, network configuration, and backup functionality.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.api.routers import containers, settings, network
from backend.database import create_db_and_tables
from backend.core.network import net_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    
    Startup:
        - Creates database tables if they don't exist
        - Initializes network rules from database to kernel
    """
    # Startup
    create_db_and_tables()
    
    try:
        net_manager.initialize_network()
    except Exception as e:
        print(f"CRITICAL: Failed to initialize network: {e}")
    
    yield
    
    # Shutdown (cleanup if needed)


app = FastAPI(
    title="LXC Simple Manager",
    description="A lightweight web interface for managing Linux Containers",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(containers.router, prefix="/api/containers", tags=["containers"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(network.router, prefix="/api/network", tags=["network"])

# Serve static frontend files
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the main frontend application."""
    return FileResponse("frontend/index.html")


@app.get("/api/health", tags=["health"])
def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns:
        dict: Status information including database type
    """
    return {"status": "healthy", "database": "SQLite"}
