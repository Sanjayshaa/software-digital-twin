"""
Phase 5 — Runtime Evidence API Router.
Exposes endpoints for ingesting, querying, and filtering normalized runtime events.
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.models.entities import Repository
from app.services.runtime import (
    RawRuntimeEvent,
    NormalizedRuntimeEvent,
    RuntimeIngestRequest,
    RuntimeIngestResult,
    RuntimeEventPage,
    runtime_evidence_service,
)

router = APIRouter(prefix="/repositories", tags=["Runtime Evidence"])


def _resolve_repo(db: Session, repository_id: str) -> Optional[Repository]:
    return (
        db.query(Repository)
        .filter(
            or_(
                Repository.id == repository_id,
                Repository.name == repository_id,
                Repository.local_path == repository_id,
            )
        )
        .first()
    )


@router.post("/{repository_id}/runtime-events/ingest", response_model=RuntimeIngestResult, status_code=status.HTTP_201_CREATED)
def ingest_runtime_events(
    repository_id: str,
    req: RuntimeIngestRequest,
    db: Session = Depends(get_db),
):
    """
    Ingests, sanitizes, and deterministically correlates a batch of runtime events.
    Applies credential redaction and links events to Structural Digital Twin artifacts.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")

    return runtime_evidence_service.ingest_events(
        db=db,
        repository_id=repo.id,
        events=req.events,
        snapshot_id=req.snapshot_id,
        default_environment=req.environment or "production",
    )


@router.get("/{repository_id}/runtime-events", response_model=RuntimeEventPage)
def list_runtime_events(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None, description="Filter by snapshot ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type (e.g. ERROR, REQUEST)"),
    severity: Optional[str] = Query(None, description="Filter by severity (e.g. ERROR, WARN, INFO)"),
    environment: Optional[str] = Query(None, description="Filter by environment (e.g. production)"),
    service_name: Optional[str] = Query(None, description="Filter by service name"),
    trace_id: Optional[str] = Query(None, description="Filter by trace ID"),
    since: Optional[datetime] = Query(None, description="Start timestamp filter"),
    until: Optional[datetime] = Query(None, description="End timestamp filter"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """Lists normalized runtime events with bounded pagination and filtering."""
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")

    return runtime_evidence_service.list_events(
        db=db,
        repository_id=repo.id,
        snapshot_id=snapshot_id,
        event_type=event_type,
        severity=severity,
        environment=environment,
        service_name=service_name,
        trace_id=trace_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )


@router.get("/{repository_id}/runtime-events/{event_id}", response_model=NormalizedRuntimeEvent)
def get_runtime_event(
    repository_id: str,
    event_id: str,
    db: Session = Depends(get_db),
):
    """Retrieves a single normalized runtime event by ID."""
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")

    event = runtime_evidence_service.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Runtime event '{event_id}' not found")
    return event
