"""
Phase 4 — Change Impact & Blast Radius API Router.
Exposes deterministic endpoints for running, retrieving, and projecting change impact analyses.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.models.entities import Repository, RepositorySnapshot
from app.services.impact import (
    change_impact_service,
    ImpactConfig,
    ImpactResult,
)

router = APIRouter(prefix="/repositories", tags=["Change Impact & Blast Radius"])


class ImpactAnalysisRequest(BaseModel):
    base_snapshot_id: str = Field(..., description="Baseline Snapshot ID (before change)")
    target_snapshot_id: str = Field(..., description="Target Snapshot ID (after change)")
    max_depth: Optional[int] = Field(5, ge=1, le=20, description="Maximum traversal depth (default 5)")
    include_tests: Optional[bool] = Field(True, description="Propagate impact to affected test suites")
    include_processes: Optional[bool] = Field(True, description="Propagate impact to affected business processes")
    include_apis: Optional[bool] = Field(True, description="Propagate impact to exposed API endpoints")


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


@router.post("/{repository_id}/impact-analysis", response_model=Dict[str, Any])
def run_impact_analysis(
    repository_id: str,
    req: ImpactAnalysisRequest,
    db: Session = Depends(get_db),
):
    """
    Executes a deterministic Change Impact & Blast Radius analysis between two snapshots.
    Traverses typed relationships with cycle protection, attaches evidence, and generates explainable paths.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    base_snap = db.query(RepositorySnapshot).filter_by(id=req.base_snapshot_id).first()
    if not base_snap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Base snapshot '{req.base_snapshot_id}' not found.",
        )
    if base_snap.repository_id != repo.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Base snapshot '{req.base_snapshot_id}' does not belong to repository '{repo.id}'.",
        )

    target_snap = db.query(RepositorySnapshot).filter_by(id=req.target_snapshot_id).first()
    if not target_snap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target snapshot '{req.target_snapshot_id}' not found.",
        )
    if target_snap.repository_id != repo.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target snapshot '{req.target_snapshot_id}' does not belong to repository '{repo.id}'.",
        )

    config = ImpactConfig(
        max_depth=req.max_depth or 5,
        include_tests=req.include_tests if req.include_tests is not None else True,
        include_processes=req.include_processes if req.include_processes is not None else True,
        include_apis=req.include_apis if req.include_apis is not None else True,
    )

    try:
        result = change_impact_service.run_impact_analysis(
            db=db,
            repository_id=repo.id,
            base_snapshot_id=req.base_snapshot_id,
            target_snapshot_id=req.target_snapshot_id,
            config=config,
        )
        return result.model_dump()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Change impact analysis failed: {str(e)}",
        )


@router.get("/{repository_id}/impact-analysis/{analysis_id}", response_model=Dict[str, Any])
def get_impact_analysis(
    repository_id: str,
    analysis_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieves the full deterministic findings and paths for a previously completed impact analysis.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    result = change_impact_service.get_impact_analysis(
        db=db,
        repository_id=repo.id,
        analysis_id=analysis_id,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Impact analysis '{analysis_id}' not found for repository '{repo.id}'.",
        )

    return result.model_dump()


@router.get("/{repository_id}/impact-analysis/{analysis_id}/graph", response_model=Dict[str, Any])
def get_impact_graph(
    repository_id: str,
    analysis_id: str,
    db: Session = Depends(get_db),
):
    """
    Projects the impact subgraph: changed nodes, directly/indirectly affected entities,
    and causal connecting relationships.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    graph_projection = change_impact_service.get_impact_graph(
        db=db,
        repository_id=repo.id,
        analysis_id=analysis_id,
    )
    if not graph_projection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Impact graph for analysis '{analysis_id}' not found.",
        )

    return graph_projection


@router.get("/{repository_id}/snapshot-diff", response_model=Dict[str, Any])
def get_snapshot_diff(
    repository_id: str,
    base_snapshot_id: str,
    target_snapshot_id: str,
    db: Session = Depends(get_db),
):
    """
    Computes a fast, normalized ChangeSet between two snapshots.
    Surfaces ADDED, REMOVED, and MODIFIED symbols/files before running full blast-radius.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    from app.services.impact.change_detector import change_detector
    change_set = change_detector.detect_changes(
        db=db,
        repository_id=repo.id,
        base_snapshot_id=base_snapshot_id,
        target_snapshot_id=target_snapshot_id,
    )
    return change_set.model_dump()
