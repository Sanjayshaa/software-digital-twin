import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.entities import Repository, RepositorySnapshot
from app.core.auth import resolve_authorized_repo, get_current_user_optional, AuthenticatedPrincipal
from app.services.architecture.service import architecture_service
from app.services.architecture.models import (
    ArchitectureConformanceReport,
    SnapshotComparisonResult,
)

router = APIRouter(tags=["Architecture Conformance & Drift"])


class CompareSnapshotsRequest(BaseModel):
    snapshot_a_id: str
    snapshot_b_id: str


@router.post("/repositories/{repository_id}/architecture/check", response_model=ArchitectureConformanceReport)
def check_architecture_drift(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None, description="Optional snapshot ID to associate report with"),
    baseline_path: Optional[str] = Query(None, description="Optional custom baseline path"),
    persist: bool = Query(True, description="Whether to persist results in PostgreSQL"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Evaluates architecture drift from repository evidence (AST / import relationships)
    against the architecture baseline. Does NOT guess or use LLM estimation.
    """
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    try:
        report = architecture_service.evaluate_repository(
            repository_path=repo.local_path,
            baseline_path=baseline_path,
            snapshot_id=snapshot_id,
            repository_id=repo.id,
        )

        if persist:
            architecture_service.persist_report(
                db=db,
                report=report,
                repository_id=repo.id,
                snapshot_id=snapshot_id,
            )

        return report
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Architecture drift detection failed: {str(exc)}")


@router.get("/repositories/{repository_id}/architecture/conformance", response_model=ArchitectureConformanceReport)
def get_conformance_report(
    repository_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Retrieves the latest verified architecture conformance report for a repository."""
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    report = architecture_service.get_latest_report(db=db, repository_id=repo.id)
    if not report:
        raise HTTPException(status_code=404, detail=f"No architecture conformance report found for repository '{repository_id}'")
    return report


@router.post("/architecture/compare", response_model=SnapshotComparisonResult)
def compare_snapshots(
    req: CompareSnapshotsRequest,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Compares architecture drift reports between Snapshot A and Snapshot B."""
    snap_a = db.query(RepositorySnapshot).filter_by(id=req.snapshot_a_id).first()
    snap_b = db.query(RepositorySnapshot).filter_by(id=req.snapshot_b_id).first()
    if not snap_a or not snap_b:
        raise HTTPException(status_code=404, detail="One or both snapshots not found.")

    repo_a = resolve_authorized_repo(db=db, repository_id=snap_a.repository_id, principal=principal)
    repo_b = resolve_authorized_repo(db=db, repository_id=snap_b.repository_id, principal=principal)
    if not repo_a or not repo_b:
        raise HTTPException(status_code=404, detail="Snapshots not found or unauthorized.")

    try:
        return architecture_service.compare_snapshots(
            db=db,
            snapshot_a_id=req.snapshot_a_id,
            snapshot_b_id=req.snapshot_b_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
