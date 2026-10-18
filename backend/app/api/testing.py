"""
Phase 6 — Test Impact Intelligence API Router.
Exposes deterministic endpoints for computing and retrieving test impact analyses.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.auth import resolve_authorized_repo, get_current_user_optional, AuthenticatedPrincipal
from app.models.entities import Repository, RepositorySnapshot, StructuralArtifact, ArtifactRelationship
from app.services.testing import (
    test_impact_service,
    TestImpactConfig,
    TestImpactResult,
)

router = APIRouter(prefix="/repositories", tags=["Test Impact Intelligence"])


class TestImpactRequest(BaseModel):
    target_snapshot_id: str = Field(..., description="Target Snapshot ID (after change)")
    base_snapshot_id: Optional[str] = Field(None, description="Baseline Snapshot ID (before change). If omitted, previous snapshot is used.")
    max_depth: Optional[int] = Field(6, ge=1, le=20, description="Maximum traversal depth (default 6)")
    include_indirect: Optional[bool] = Field(True, description="Include transitively impacted tests")
    include_unaffected: Optional[bool] = Field(True, description="Include unaffected test catalog in output")


def _resolve_repo(
    db: Session,
    repository_id: str,
    principal: Optional[AuthenticatedPrincipal] = None,
) -> Optional[Repository]:
    return resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)


@router.post("/{repository_id}/test-impact", response_model=Dict[str, Any])
def run_test_impact_analysis(
    repository_id: str,
    req: TestImpactRequest,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Executes deterministic Test Impact Intelligence between two snapshots.
    Answers: 'If I change this code, which tests should I run and why?'
    Returns directly affected tests, indirectly affected tests, unaffected tests, and unknown coverage.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
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
        # Find preceding snapshot within this repository
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
            # If no earlier snapshot, fall back to target snapshot itself (diff will be empty)
            prev_snap = target_snap
        base_snapshot_id = prev_snap.id

    base_snap = db.query(RepositorySnapshot).filter_by(id=base_snapshot_id).first()
    if not base_snap or base_snap.repository_id != repo.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Base snapshot '{base_snapshot_id}' not found for repository '{repo.id}'.",
        )

    config = TestImpactConfig(
        max_depth=req.max_depth or 6,
        include_indirect=req.include_indirect if req.include_indirect is not None else True,
        include_unaffected=req.include_unaffected if req.include_unaffected is not None else True,
    )

    try:
        result = test_impact_service.run_test_impact_analysis(
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
            detail=f"Test impact analysis failed: {str(e)}",
        )


@router.get("/{repository_id}/test-impact/{analysis_id}", response_model=Dict[str, Any])
def get_test_impact_analysis(
    repository_id: str,
    analysis_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Retrieves stored Test Impact Analysis results by analysis ID.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    res = test_impact_service.get_test_impact_result(db, repo.id, analysis_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test impact analysis '{analysis_id}' not found.",
        )
    return res


@router.get("/{repository_id}/tests-catalog", response_model=Dict[str, Any])
def get_tests_catalog(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the comprehensive catalog of tests discovered for this repository snapshot,
    including test types, locations, and mapped target components.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
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
        return {"tests": [], "total": 0}

    artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=snap.id).all()
    rels = db.query(ArtifactRelationship).filter_by(snapshot_id=snap.id).all()

    art_map = {a.id: a for a in artifacts}

    # Identify tests
    test_artifacts = []
    for a in artifacts:
        is_test_type = a.artifact_type in ("TEST_CASE", "TEST_SUITE")
        is_test_loc = bool(a.location and ("/test" in a.location.lower() or a.location.lower().startswith("test")))
        is_test_name = a.name.startswith("test_") or a.name.endswith("Test") or a.name.endswith("Tests")
        if is_test_type or (is_test_loc and is_test_name):
            test_artifacts.append(a)

    test_targets_map = {}
    for r in rels:
        if r.relationship_type.upper() in ("TESTS", "CALLS", "IMPORTS"):
            source_art = art_map.get(r.source_artifact_id)
            target_art = art_map.get(r.target_artifact_id)
            if source_art and source_art in test_artifacts and target_art:
                test_targets_map.setdefault(source_art.id, []).append({
                    "id": target_art.id,
                    "name": target_art.name,
                    "type": target_art.artifact_type,
                    "relationship": r.relationship_type,
                })

    catalog = []
    for t in test_artifacts:
        catalog.append({
            "id": t.id,
            "name": t.name,
            "qualified_name": t.qualified_name,
            "artifact_type": t.artifact_type,
            "location": t.location or "unknown",
            "targets": test_targets_map.get(t.id, []),
            "metadata": t.metadata_payload or {},
        })

    return {
        "repository_id": repo.id,
        "snapshot_id": snap.id,
        "total": len(catalog),
        "tests": catalog,
    }
