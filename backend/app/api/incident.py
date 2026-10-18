"""
Phase 5 — Incident Intelligence & Investigation API Router.
Exposes endpoints for creating incidents, tracking correlations, and running deterministic causal investigations.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.models.entities import Repository
from app.services.incident import (
    IncidentCreate,
    IncidentResponse,
    InvestigationResult,
    incident_service,
)

from app.core.auth import resolve_authorized_repo, get_current_user_optional, AuthenticatedPrincipal

router = APIRouter(prefix="/repositories", tags=["Incident Intelligence"])


def _resolve_repo(
    db: Session,
    repository_id: str,
    principal: Optional[AuthenticatedPrincipal] = None,
) -> Optional[Repository]:
    return resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)


@router.post("/{repository_id}/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def create_incident(
    repository_id: str,
    req: IncidentCreate,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Creates a new incident record and binds linked runtime events and affected components."""
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")

    return incident_service.create_incident(
        db=db,
        repository_id=repo.id,
        req=req,
    )


@router.get("/{repository_id}/incidents", response_model=List[IncidentResponse])
def list_incidents(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None, description="Filter by snapshot ID"),
    status: Optional[str] = Query(None, description="Filter by status (open, investigated, resolved)"),
    severity: Optional[str] = Query(None, description="Filter by severity (low, medium, high, critical)"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Lists incidents for a repository."""
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")

    return incident_service.list_incidents(
        db=db,
        repository_id=repo.id,
        snapshot_id=snapshot_id,
        status=status,
        severity=severity,
    )


@router.get("/{repository_id}/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(
    repository_id: str,
    incident_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Retrieves single incident details."""
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")

    incident = incident_service.get_incident(db, incident_id, repository_id=repo.id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")
    return incident


@router.post("/{repository_id}/incidents/{incident_id}/investigate", response_model=InvestigationResult)
def investigate_incident(
    repository_id: str,
    incident_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Executes a deterministic causal investigation for an incident.
    Correlates runtime events with recent changes, structural artifacts, affected processes, and tests,
    yielding evidence-backed candidate causal paths.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")

    return incident_service.investigate_incident(db, incident_id, repository_id=repo.id)
