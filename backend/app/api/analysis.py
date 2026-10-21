from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import resolve_authorized_repo, get_current_user_optional, AuthenticatedPrincipal
from app.models.entities import (
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    Evidence,
    AnalysisRun,
)
from app.services.acquisition.git_provider import (
    discover_repository_commits,
    extract_commit_source_tree,
)
from app.services.analysis.engine import structural_twin_engine
from app.services.analysis.query.twin_query_service import twin_query_service

router = APIRouter(prefix="/repositories", tags=["Structural Digital Twin"])


@router.get("/{repository_id}/commits", response_model=Dict[str, Any])
@router.get("/{repository_id}/history/commits", response_model=Dict[str, Any])
def get_repository_commits(
    repository_id: str,
    max_count: int = Query(default=30, le=100),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Discovers actual accessible Git commits for the repository.
    Cross-references each commit with existing analyzed Twin snapshots.
    Preserves exact commit SHA, author, timestamp, and message.
    Distinguishes commit availability from snapshot availability.
    Never fabricates historical snapshots or commits.
    """
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

    # 1. Query existing analyzed snapshots in DB
    existing_snaps = db.query(RepositorySnapshot).filter_by(repository_id=repo.id).all()
    snap_by_commit = {s.commit_hash: s for s in existing_snaps if s.commit_hash}

    # 2. Discover Git commits
    discovery = discover_repository_commits(
        workspace_path=repo.local_path,
        max_count=max_count,
        allow_deepen=True,
        default_branch=repo.default_branch or "main",
    )

    commits_data = []
    seen_shas = set()

    for c in discovery.get("commits", []):
        sha = c["commit_sha"]
        seen_shas.add(sha)
        matched_snap = snap_by_commit.get(sha)
        commits_data.append({
            "commit_sha": sha,
            "short_sha": c["short_sha"],
            "branch_name": repo.default_branch or "main",
            "message": c["message"],
            "author": c["author"],
            "authored_date": c["authored_date"],
            "is_head": c["is_head"],
            "has_snapshot": (matched_snap is not None),
            "snapshot_id": matched_snap.id if matched_snap else None,
            "status": "ANALYZED" if matched_snap else "AVAILABLE_FOR_ANALYSIS",
            "total_files": matched_snap.total_files if matched_snap else None,
            "total_symbols": matched_snap.total_symbols if matched_snap else None,
            "created_at": matched_snap.created_at.isoformat() if (matched_snap and matched_snap.created_at) else None,
        })

    # Include any snapshots in DB that might not have appeared in git log (e.g. non-git or different ref)
    for s in existing_snaps:
        if s.commit_hash and s.commit_hash not in seen_shas:
            commits_data.append({
                "commit_sha": s.commit_hash,
                "short_sha": s.commit_hash[:7] if len(s.commit_hash) >= 7 else s.commit_hash,
                "branch_name": s.branch_name or repo.default_branch or "main",
                "message": f"Snapshot {s.id[:10]}",
                "author": "Observed Snapshot",
                "authored_date": s.created_at.isoformat() if s.created_at else None,
                "is_head": False,
                "has_snapshot": True,
                "snapshot_id": s.id,
                "status": "ANALYZED",
                "total_files": s.total_files,
                "total_symbols": s.total_symbols,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })

    total_accessible = len(commits_data)
    total_analyzed = sum(1 for c in commits_data if c["has_snapshot"])
    is_shallow = discovery.get("is_shallow", False)

    limitation_reason = None
    if total_accessible < 2:
        if is_shallow:
            limitation_reason = (
                f"Repository clone is shallow (history depth 1). Only 1 commit ({commits_data[0]['short_sha'] if commits_data else 'HEAD'}) "
                "is accessible locally. Pairwise Change Impact requires at least two distinct commits. "
                "Use What-If Simulation to evaluate hypothetical changes on this snapshot."
            )
        else:
            limitation_reason = (
                "Repository has only 1 accessible commit in Git history. Pairwise Change Impact "
                "requires at least two distinct states to compute AST deltas and propagate blast radius. "
                "Use What-If Simulation to evaluate hypothetical changes on this snapshot."
            )

    return {
        "repository_id": repo.id,
        "repository_name": repo.name,
        "default_branch": repo.default_branch or "main",
        "total_commits": total_accessible,
        "total_analyzed_snapshots": total_analyzed,
        "is_shallow": is_shallow,
        "can_perform_pairwise_impact": (total_accessible >= 2),
        "limitation_reason": limitation_reason,
        "commits": commits_data,
    }


@router.get("/{repository_id}/commits/{commit_sha}/analyze", response_model=Dict[str, Any])
@router.post("/{repository_id}/snapshots/reconstruct", response_model=Dict[str, Any])
@router.post("/{repository_id}/commits/{commit_sha}/analyze", response_model=Dict[str, Any])
def reconstruct_snapshot(
    repository_id: str,
    commit_sha: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    branch_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Reconstructs the actual historical source tree at commit_sha using git archive,
    extracts structural artifacts, computes typed relationships, and persists a real Digital Twin snapshot.
    Does NOT modify the workspace working directory or branch.
    Zero fabrication: derives all twin entities directly from the historical commit AST.
    """
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

    target_sha = commit_sha or (payload.get("commit_sha") if payload else None)
    if not target_sha:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required commit_sha.")

    target_branch = branch_name or (payload.get("branch_name") if payload else None) or repo.default_branch or "main"

    # Check if snapshot already exists
    existing = db.query(RepositorySnapshot).filter_by(repository_id=repo.id, commit_hash=target_sha).first()
    if existing:
        return {
            "status": "ALREADY_EXISTS",
            "snapshot_id": existing.id,
            "commit_hash": existing.commit_hash,
            "branch_name": existing.branch_name,
            "total_files": existing.total_files,
            "total_symbols": existing.total_symbols,
            "message": f"Snapshot for commit {target_sha[:7]} already exists in Digital Twin database.",
        }

    # Extract historical source tree into isolated temp directory
    import tempfile
    import shutil
    temp_dir = tempfile.mkdtemp(prefix=f"recon_{repo.id[:8]}_{target_sha[:7]}_")

    try:
        ok, err = extract_commit_source_tree(
            workspace_path=repo.local_path,
            commit_sha=target_sha,
            dest_dir=temp_dir,
            default_branch=target_branch,
        )
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to extract historical commit '{target_sha[:7]}': {err}",
            )

        # Build Digital Twin on historical tree
        snapshot_id, result = structural_twin_engine.build_structural_twin(
            db=db,
            repository_id=repo.id,
            commit_hash=target_sha,
            branch_name=target_branch,
            source_path=temp_dir,
        )

        return {
            "status": "COMPLETED",
            "snapshot_id": snapshot_id,
            "commit_hash": target_sha,
            "branch_name": target_branch,
            "files_scanned": result.files_scanned,
            "artifacts_created": len(result.artifacts),
            "relationships_created": len(result.relationships),
            "evidence_count": len(result.evidence_items),
            "message": f"Historical snapshot successfully reconstructed and indexed for commit {target_sha[:7]}.",
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/{repository_id}/snapshots", response_model=List[Dict[str, Any]])
def get_repository_snapshots(
    repository_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns all snapshots recorded for the repository over time."""
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns detailed component and structural metrics for a specific snapshot."""
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns normalized structural artifacts for a snapshot."""
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns typed relationships between structural artifacts."""
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns all recorded evidence items."""
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns details for a specific analysis run."""
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

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


# ====================================================================
# ARCHITECTURE BASELINE & DRIFT ENDPOINTS
# ====================================================================

@router.get("/{repository_id}/architecture/conformance")
def get_architecture_conformance(
    repository_id: str,
    snapshot_id: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns deterministic architecture conformance report for a snapshot."""
    from app.services.architecture.drift_detector import architecture_drift_detector

    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

    if not snapshot_id:
        snapshots = twin_query_service.get_snapshots_by_repo(db, repository_id)
        if not snapshots:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No snapshots found for repository")
        snapshot_id = snapshots[0].id

    report = architecture_drift_detector.detect_drift_for_snapshot(
        db=db,
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        persist=True,
    )
    return report.model_dump()


@router.get("/{repository_id}/architecture/drifts")
def get_architecture_drifts(
    repository_id: str,
    snapshot_id: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns detected architectural drifts and boundary violations."""
    from app.services.architecture.drift_detector import architecture_drift_detector

    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

    if not snapshot_id:
        snapshots = twin_query_service.get_snapshots_by_repo(db, repository_id)
        if not snapshots:
            return []
        snapshot_id = snapshots[0].id

    report = architecture_drift_detector.detect_drift_for_snapshot(
        db=db,
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        persist=False,
    )

    drifts = report.drifts
    if category:
        drifts = [d for d in drifts if d.category.upper() == category.upper()]
    if severity:
        drifts = [d for d in drifts if d.severity.upper() == severity.upper()]

    return [d.model_dump() for d in drifts]


@router.get("/{repository_id}/architecture/compare")
def compare_architecture_snapshots(
    repository_id: str,
    from_snapshot: str = Query(..., description="Source baseline snapshot ID"),
    to_snapshot: str = Query(..., description="Target candidate snapshot ID"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Compares architectural state between two snapshots, identifying new and resolved drifts."""
    from app.services.architecture.drift_detector import architecture_drift_detector

    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository '{repository_id}' not found.")

    comparison = architecture_drift_detector.compare_snapshots(
        db=db,
        repository_id=repository_id,
        from_snapshot_id=from_snapshot,
        to_snapshot_id=to_snapshot,
    )
    return comparison.model_dump()
