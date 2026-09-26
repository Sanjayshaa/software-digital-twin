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

# Root route
@app.get("/", tags=["System"])
def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
    }

# Register health, discovery, and analysis routers
app.include_router(health_router)
app.include_router(discovery_router)
app.include_router(analysis_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
