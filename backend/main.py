import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.health import router as health_router
from app.api.discovery import router as discovery_router
from app.api.analysis import router as analysis_router
from app.api.status import router as status_router
from app.api.architecture import router as architecture_router
from app.api.graph import router as graph_router
from app.api.impact import router as impact_router
from app.api.runtime import router as runtime_router
from app.api.process import router as process_router
from app.api.incident import router as incident_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Deterministic Digital Twin engine for pre-deployment risk and test impact analysis.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "app", "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Web UI route
@app.get("/app", response_class=FileResponse, tags=["Web UI"])
def serve_ui():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Digital Twin Visual UI is being initialized."}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

# Root route
@app.get("/", tags=["System"])
def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "ui": "/app",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
    }

# Register API routers
app.include_router(health_router)
app.include_router(discovery_router)
app.include_router(analysis_router)
app.include_router(status_router)
app.include_router(architecture_router)
app.include_router(graph_router)
app.include_router(impact_router)
app.include_router(runtime_router)
app.include_router(process_router)
app.include_router(incident_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
