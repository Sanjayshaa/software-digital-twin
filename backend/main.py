import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
# Auto-reload trigger for 3D verification audit

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
from app.api.testing import router as testing_router
from app.api.risk import router as risk_router
from app.api.simulation import router as simulation_router
from app.api.auth import router as auth_router
from app.api.twin_knowledge import router as twin_knowledge_router
from app.api.evaluation import router as evaluation_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi import Request

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Deterministic Digital Twin engine for pre-deployment risk and test impact analysis.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# SEC-06 Remediation: Enforce explicit origins and disallow wildcard with credentials
settings.validate_cors()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOWED_METHODS,
    allow_headers=settings.CORS_ALLOWED_HEADERS,
)


@app.middleware("http")
async def security_and_governance_middleware(request: Request, call_next):
    """
    Enforces:
    1. Request payload size limits (rejects oversized bodies with 413).
    2. Standard HTTP security headers on all responses.
    """
    path = request.url.path
    is_auth_endpoint = path.startswith("/auth") or path.startswith("/api/v1/auth")
    max_allowed_bytes = settings.MAX_AUTH_BODY_BYTES if is_auth_endpoint else settings.MAX_REQUEST_BODY_BYTES

    content_length_header = request.headers.get("content-length")
    if content_length_header:
        try:
            content_length = int(content_length_header)
            if content_length > max_allowed_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request payload size ({content_length} bytes) exceeds maximum permitted limit ({max_allowed_bytes} bytes).",
                        "code": "PAYLOAD_TOO_LARGE",
                    },
                )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length header.", "code": "INVALID_HEADER"},
            )

    response = await call_next(request)

    # Standard security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://fonts.googleapis.com https://fonts.gstatic.com data: blob:; font-src 'self' https://fonts.gstatic.com data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; frame-ancestors 'none';"

    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Global uncaught exception during %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
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

@app.get("/login", response_class=FileResponse, tags=["Web UI"])
@app.get("/signin", response_class=FileResponse, tags=["Web UI"])
def serve_login():
    login_file = os.path.join(static_dir, "login.html")
    if os.path.exists(login_file):
        return FileResponse(login_file)
    return RedirectResponse(url="/app")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

# Root route
@app.get("/", tags=["System"])
def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and "application/json" not in accept and not accept.startswith("*/*"):
        return RedirectResponse(url="/app")
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
app.include_router(testing_router)
app.include_router(risk_router)
app.include_router(simulation_router, prefix="/api/v1")
app.include_router(simulation_router)
app.include_router(twin_knowledge_router, prefix="/api/v1")
app.include_router(twin_knowledge_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(auth_router)
app.include_router(evaluation_router, prefix="/api/v1")
app.include_router(evaluation_router)


@app.on_event("startup")
def ensure_vendor_assets():
    """
    Downloads and caches Three.js and OrbitControls locally in static/vendor
    so that 3D Spatial Architecture visualization functions 100% reliably
    even when CDN connections are throttled, offline, or restricted.
    """
    import urllib.request
    import logging
    log = logging.getLogger(__name__)
    vendor_dir = os.path.join(static_dir, "vendor")
    os.makedirs(vendor_dir, exist_ok=True)
    
    three_path = os.path.join(vendor_dir, "three.min.js")
    orbit_path = os.path.join(vendor_dir, "OrbitControls.js")

    if not os.path.exists(three_path) or os.path.getsize(three_path) < 1000:
        try:
            url = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
            req = urllib.request.Request(url, headers={"User-Agent": "TwinCore/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read()
                with open(three_path, "wb") as f:
                    f.write(content)
            log.info("Successfully cached three.min.js locally (%d bytes)", len(content))
        except Exception as e:
            log.warning("Could not download three.min.js: %s", e)

    if not os.path.exists(orbit_path) or os.path.getsize(orbit_path) < 1000:
        try:
            url = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"
            req = urllib.request.Request(url, headers={"User-Agent": "TwinCore/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read()
                with open(orbit_path, "wb") as f:
                    f.write(content)
            log.info("Successfully cached OrbitControls.js locally (%d bytes)", len(content))
        except Exception as e:
            log.warning("Could not download OrbitControls.js: %s", e)


@app.on_event("startup")
def migrate_legacy_unowned_repositories():
    """
    Phase 8.7.7 Zero-Trust Isolation Migration:
    Ensures that any legacy repository lacking an explicit owner_id is classified as 'FIXTURE'
    so it can never leak into production user repository listings.
    """
    try:
        from app.core.database import SessionLocal
        from app.models.entities import Repository
        db = SessionLocal()
        try:
            unowned = db.query(Repository).filter(Repository.owner_id.is_(None), Repository.environment == "USER").all()
            if unowned:
                for repo in unowned:
                    repo.environment = "FIXTURE"
                db.commit()
        finally:
            db.close()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Legacy repository migration check skipped: %s", exc)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
