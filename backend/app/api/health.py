from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.config import settings
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["Health & Readiness"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """
    Liveness probe: verifies that the FastAPI server is running.
    """
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        environment=settings.APP_ENV,
    )


@router.get("/ready", response_model=ReadinessResponse)
def get_readiness(db: Session = Depends(get_db)) -> ReadinessResponse:
    """
    Readiness probe: verifies that the PostgreSQL database connection is operational.
    """
    try:
        # Execute simple query to test DB connectivity
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            return ReadinessResponse(
                status="ready",
                database="connected",
                details={
                    "postgres_server": settings.POSTGRES_SERVER,
                    "postgres_port": settings.POSTGRES_PORT,
                    "database": settings.POSTGRES_DB,
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connectivity probe returned unexpected result"
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(exc)}"
        )
