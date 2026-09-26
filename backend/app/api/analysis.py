from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.entities import (
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    Evidence,
    AnalysisRun,
)
from app.services.analysis.engine import structural_twin_engine
from app.services.analysis.query.twin_query_service import twin_query_service

router = APIRouter(prefix="/repositories", tags=["Structural Digital Twin"])


@router.post("/{repository_id}/analyze", response_model=Dict[str, Any])
def analyze_repository(
    repository_id: str,
    commit_hash: str = "HEAD",
    branch_name: str = "main",
    db: Session = Depends(get_db),
):
    """
    Executes the Phase 3 Analyzer Runtime to parse source code, extract structural artifacts,
    derive typed relationships, record evidence, and build a persistent Digital Twin snapshot.
    """
    repo = db.query(Repository).filter_by(id=repository_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    try:
        snapshot_id, result = structural_twin_engine.build_structural_twin(
            db=db,
            repository_id=repo.id,
            commit_hash=commit_hash,
            branch_name=branch_name,
        )
        return {
            "status": result.status,
            "run_id": result.run_id,
            "repository_id": repo.id,
            "snapshot_id": snapshot_id,
            "files_scanned": result.files_scanned,
            "artifacts_created": len(result.artifacts),
            "relationships_created": len(result.relationships),
            "evidence_count": len(result.evidence_items),
            "warnings_count": len(result.warnings),
            "errors_count": len(result.errors),
            "analyzers_executed": result.analyzer_names,
            "summary": result.summary,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Structural analysis failed: {str(exc)}",
        )


@router.get("/{repository_id}/twin", response_model=Dict[str, Any])
def get_repository_twin(
    repository_id: str,
    db: Session = Depends(get_db),
):
    """Returns overview of the Digital Twin state for a repository."""
    repo = db.query(Repository).filter_by(id=repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    snapshots = twin_query_service.get_snapshots_by_repo(db, repository_id)
    latest_snapshot = snapshots[0] if snapshots else None

    structure = {}
    if latest_snapshot:
        structure = twin_query_service.get_component_structure(db, latest_snapshot.id)

    return {
        "repository_id": repo.id,
        "repository_name": repo.name,
        "total_snapshots": len(snapshots),
        "latest_snapshot_id": latest_snapshot.id if latest_snapshot else None,
        "component_structure": structure,
    }


@router.get("/{repository_id}/snapshots", response_model=List[Dict[str, Any]])
def get_repository_snapshots(
    repository_id: str,
    db: Session = Depends(get_db),
):
    """Returns all snapshots recorded for the repository over time."""
    snapshots = twin_query_service.get_snapshots_by_repo(db, repository_id)
    return [
        {
            "id": s.id,
            "commit_hash": s.commit_hash,
            "branch_name": s.branch_name,
            "total_files": s.total_files,
            "total_symbols": s.total_symbols,
            "created_at": s.created_at,
        }
        for s in snapshots
    ]


@router.get("/{repository_id}/snapshots/{snapshot_id}", response_model=Dict[str, Any])
def get_snapshot_details(
    repository_id: str,
    snapshot_id: str,
    db: Session = Depends(get_db),
):
    """Returns detailed component and structural metrics for a specific snapshot."""
    snapshot = twin_query_service.get_snapshot(db, snapshot_id)
    if not snapshot or snapshot.repository_id != repository_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")

    structure = twin_query_service.get_component_structure(db, snapshot_id)
    return {
        "snapshot": {
            "id": snapshot.id,
            "commit_hash": snapshot.commit_hash,
            "branch_name": snapshot.branch_name,
            "total_files": snapshot.total_files,
            "total_symbols": snapshot.total_symbols,
            "created_at": snapshot.created_at,
        },
        "structure": structure,
    }


@router.get("/{repository_id}/artifacts", response_model=List[Dict[str, Any]])
def get_repository_artifacts(
    repository_id: str,
    snapshot_id: Optional[str] = None,
    artifact_type: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
):
    """Returns normalized structural artifacts for a snapshot."""
    if not snapshot_id:
        snapshots = twin_query_service.get_snapshots_by_repo(db, repository_id)
        if not snapshots:
            return []
        snapshot_id = snapshots[0].id

    artifacts = twin_query_service.get_artifacts(
        db=db,
        snapshot_id=snapshot_id,
        artifact_type=artifact_type,
        language=language,
        limit=limit,
    )

    return [
        {
            "id": a.id,
            "artifact_type": a.artifact_type,
            "language": a.language,
            "name": a.name,
            "qualified_name": a.qualified_name,
            "location": a.location,
            "line_start": a.line_start,
            "line_end": a.line_end,
            "signature": a.signature,
            "confidence": a.confidence,
            "metadata": a.metadata_payload,
        }
        for a in artifacts
    ]


@router.get("/{repository_id}/relationships", response_model=List[Dict[str, Any]])
def get_repository_relationships(
    repository_id: str,
    snapshot_id: Optional[str] = None,
    relationship_type: Optional[str] = None,
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
):
    """Returns typed relationships between structural artifacts."""
    if not snapshot_id:
        snapshots = twin_query_service.get_snapshots_by_repo(db, repository_id)
        if not snapshots:
            return []
        snapshot_id = snapshots[0].id

    relationships = twin_query_service.get_relationships(
        db=db,
        snapshot_id=snapshot_id,
        rel_type=relationship_type,
        limit=limit,
    )

    return [
        {
            "id": r.id,
            "source_artifact_id": r.source_artifact_id,
            "target_artifact_id": r.target_artifact_id,
            "relationship_type": r.relationship_type,
            "confidence": r.confidence,
            "detection_method": r.detection_method,
            "source_location": r.source_location,
        }
        for r in relationships
    ]


@router.get("/{repository_id}/evidence", response_model=List[Dict[str, Any]])
def get_repository_evidence(
    repository_id: str,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
):
    """Returns all recorded evidence items."""
    repo = db.query(Repository).filter_by(id=repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    items = twin_query_service.get_evidence(db, repo.project_id, limit=limit)
    return [
        {
            "id": e.id,
            "source_type": e.source_type,
            "source_reference": e.source_reference,
            "description": e.description,
            "confidence": e.confidence,
            "payload": e.payload,
            "created_at": e.created_at,
        }
        for e in items
    ]


@router.get("/{repository_id}/analysis-runs/{run_id}", response_model=Dict[str, Any])
def get_analysis_run(
    repository_id: str,
    run_id: str,
    db: Session = Depends(get_db),
):
    """Returns details for a specific analysis run."""
    run = db.query(AnalysisRun).filter_by(id=run_id, repository_id=repository_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")

    return {
        "id": run.id,
        "status": run.status,
        "run_type": run.run_type,
        "snapshot_id": run.snapshot_id,
        "analyzer_names": run.analyzer_names,
        "files_scanned": run.files_scanned,
        "artifacts_created": run.artifacts_created,
        "relationships_created": run.relationships_created,
        "warnings": run.warnings,
        "errors": run.errors,
        "summary": run.summary,
        "started_at": run.created_at,
        "completed_at": run.completed_at,
    }
