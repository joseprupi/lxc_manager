from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routers import containers

app = FastAPI(title="LXC Simple Manager")

# CORS (Allow frontend to talk to backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(containers.router, prefix="/api/containers", tags=["containers"])

@app.get("/")
def health_check():
    return {"status": "LXC Manager Running"}
