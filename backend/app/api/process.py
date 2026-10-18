"""
Phase 5 — Process Twin API Router.
Exposes endpoints for discovering, listing, and retrieving deterministic software execution workflows.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.auth import resolve_authorized_repo, get_current_user_optional, AuthenticatedPrincipal
from app.models.entities import Repository
from app.services.process import (
    ProcessModel,
    ProcessDiscoveryResult,
    process_service,
)

router = APIRouter(prefix="/repositories", tags=["Process Twin"])


def _resolve_repo(
    db: Session,
    repository_id: str,
    principal: Optional[AuthenticatedPrincipal] = None,
) -> Optional[Repository]:
    return resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)


class ProcessDiscoverRequest(BaseModel):
    snapshot_id: Optional[str] = Field(None, description="Target snapshot ID (defaults to latest)")


@router.post("/{repository_id}/processes/discover", response_model=ProcessDiscoveryResult, status_code=status.HTTP_200_OK)
def discover_processes(
    repository_id: str,
    req: ProcessDiscoverRequest = ProcessDiscoverRequest(),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Triggers deterministic process discovery from AST entrypoints and call chains.
    Persists discovered workflows, steps, and transitions into the Digital Twin database.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")

    return process_service.discover_processes(
        db=db,
        repository_id=repo.id,
        snapshot_id=req.snapshot_id,
    )


@router.get("/{repository_id}/processes", response_model=List[ProcessModel])
def list_processes(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None, description="Filter by snapshot ID"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Lists discovered and persisted process workflows for a repository snapshot."""
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")

    return process_service.list_processes(
        db=db,
        repository_id=repo.id,
        snapshot_id=snapshot_id,
    )


@router.get("/{repository_id}/processes/{process_id}", response_model=ProcessModel)
def get_process(
    repository_id: str,
    process_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Retrieves full process workflow details including steps, transitions, and evidence."""
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found")

    process = process_service.get_process(db, process_id)
    if not process or process.repository_id != repo.id:
        raise HTTPException(status_code=404, detail=f"Process '{process_id}' not found")
    return process
