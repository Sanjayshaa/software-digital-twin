"""
Phase 7 — Risk Intelligence & Architecture Guardrails API Router.
Exposes deterministic endpoints for computing and retrieving explainable risk assessments
and evaluating architectural boundary guardrails.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.models.entities import Repository, RepositorySnapshot
from app.services.risk import (
    risk_intelligence_service,
    guardrail_evaluator,
    RiskConfig,
    RiskAssessmentResult,
)

router = APIRouter(prefix="/repositories", tags=["Risk Intelligence & Architecture Guardrails"])


class RiskAnalysisRequest(BaseModel):
    target_snapshot_id: str = Field(..., description="Target Snapshot ID (after change)")
    base_snapshot_id: Optional[str] = Field(None, description="Baseline Snapshot ID (before change). If omitted, previous snapshot is used.")
    max_depth: Optional[int] = Field(6, ge=1, le=20, description="Maximum traversal depth (default 6)")
    environment: Optional[str] = Field("production", description="Environment for runtime event correlation")
    baseline_path: Optional[str] = Field(None, description="Optional custom baseline path")


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


@router.post("/{repository_id}/risk-analysis", response_model=Dict[str, Any])
def run_risk_analysis(
    repository_id: str,
    req: RiskAnalysisRequest,
    db: Session = Depends(get_db),
):
    """
    Executes deterministic Risk Intelligence & Guardrail evaluation between two snapshots.
    Answers: 'How significant is this change, what evidence contributes, and which guardrails are relevant?'
    Returns explainable risk category, confidence level, risk factors, guardrail results, and recommendations.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    target_snap = db.query(RepositorySnapshot).filter_by(id=req.target_snapshot_id).first()
    if not target_snap or target_snap.repository_id != repo.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target snapshot '{req.target_snapshot_id}' not found for repository '{repo.id}'.",
        )

    base_snapshot_id = req.base_snapshot_id
    if not base_snapshot_id:
        # Find preceding snapshot
        prev_snap = (
            db.query(RepositorySnapshot)
            .filter(
                RepositorySnapshot.repository_id == repo.id,
                RepositorySnapshot.created_at < target_snap.created_at,
            )
            .order_by(RepositorySnapshot.created_at.desc())
            .first()
        )
        if not prev_snap:
            # Fall back to target snapshot itself
            prev_snap = target_snap
        base_snapshot_id = prev_snap.id

    base_snap = db.query(RepositorySnapshot).filter_by(id=base_snapshot_id).first()
    if not base_snap or base_snap.repository_id != repo.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Base snapshot '{base_snapshot_id}' not found for repository '{repo.id}'.",
        )

    config = RiskConfig(
        max_impact_depth=req.max_depth or 6,
        environment=req.environment or "production",
        baseline_path=req.baseline_path,
    )

    try:
        result = risk_intelligence_service.run_risk_analysis(
            db=db,
            repository_id=repo.id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=req.target_snapshot_id,
            config=config,
        )
        from fastapi.encoders import jsonable_encoder
        return jsonable_encoder(result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk analysis failed: {str(e)}",
        )


@router.get("/{repository_id}/risk-analysis/{analysis_id}", response_model=Dict[str, Any])
def get_risk_analysis(
    repository_id: str,
    analysis_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieves stored Risk Assessment results by analysis ID.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    res = risk_intelligence_service.get_risk_analysis(db, repo.id, analysis_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Risk analysis '{analysis_id}' not found.",
        )
    return res


@router.get("/{repository_id}/architecture/guardrails", response_model=Dict[str, Any])
def get_architecture_guardrails(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    baseline_path: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Evaluates and returns architecture boundary guardrails for the given snapshot.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    snap = None
    if snapshot_id:
        snap = db.query(RepositorySnapshot).filter_by(id=snapshot_id, repository_id=repo.id).first()
    if not snap:
        snap = (
            db.query(RepositorySnapshot)
            .filter_by(repository_id=repo.id)
            .order_by(RepositorySnapshot.created_at.desc())
            .first()
        )
    if not snap:
        return {"repository_id": repo.id, "guardrails": [], "total": 0}

    results = guardrail_evaluator.evaluate_guardrails(
        db=db,
        repository_id=repo.id,
        snapshot_id=snap.id,
        baseline_path=baseline_path,
    )

    from fastapi.encoders import jsonable_encoder
    encoded_results = jsonable_encoder(results)
    violations = [g for g in results if g.status.value == "VIOLATION"]
    warnings = [g for g in results if g.status.value == "WARN"]

    return {
        "repository_id": repo.id,
        "snapshot_id": snap.id,
        "total": len(results),
        "violations_count": len(violations),
        "warnings_count": len(warnings),
        "guardrails": encoded_results,
    }
