"""
Phase 4 — Change Impact & Blast Radius API Router.
Exposes deterministic endpoints for running, retrieving, and projecting change impact analyses.
"""

import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
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


from app.core.auth import resolve_authorized_repo, get_current_user_optional, AuthenticatedPrincipal


def _resolve_repo(
    db: Session,
    repository_id: str,
    principal: Optional[AuthenticatedPrincipal] = None,
) -> Optional[Repository]:
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if repo:
        return repo
    if not principal:
        return db.query(Repository).filter(
            or_(
                Repository.id == repository_id,
                Repository.name == repository_id,
            )
        ).first()
    return None


@router.get("/{repository_id}/impact-analysis", response_model=Dict[str, Any])
def run_impact_analysis_get(
    repository_id: str,
    base_snapshot_id: str = Query(...),
    target_snapshot_id: str = Query(...),
    max_depth: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """GET route for deterministic Change Impact analysis between two snapshots."""
    req = ImpactAnalysisRequest(
        base_snapshot_id=base_snapshot_id,
        target_snapshot_id=target_snapshot_id,
        max_depth=max_depth,
    )
    return run_impact_analysis(
        repository_id=repository_id,
        req=req,
        db=db,
        principal=principal,
    )


def _ensure_snapshot(
    db: Session,
    repo: Repository,
    snapshot_or_commit: str,
) -> Optional[RepositorySnapshot]:
    """Resolves existing snapshot or auto-reconstructs from local Git source tree if unindexed."""
    snap = db.query(RepositorySnapshot).filter(
        RepositorySnapshot.repository_id == repo.id,
        or_(
            RepositorySnapshot.id == snapshot_or_commit,
            RepositorySnapshot.commit_hash == snapshot_or_commit,
            RepositorySnapshot.commit_hash.startswith(snapshot_or_commit),
        )
    ).first()
    if snap:
        return snap

    if repo.local_path and os.path.isdir(repo.local_path):
        import tempfile
        import shutil
        from app.services.acquisition.git_provider import extract_commit_source_tree
        from app.services.analysis.engine import structural_twin_engine

        target_sha = snapshot_or_commit
        target_branch = repo.default_branch or "main"
        temp_dir = tempfile.mkdtemp(prefix=f"recon_{repo.id[:8]}_{target_sha[:7]}_")
        try:
            ok, err = extract_commit_source_tree(
                workspace_path=repo.local_path,
                commit_sha=target_sha,
                dest_dir=temp_dir,
                default_branch=target_branch,
            )
            if ok:
                snap_id, _ = structural_twin_engine.build_structural_twin(
                    db=db,
                    repository_id=repo.id,
                    commit_hash=target_sha,
                    branch_name=target_branch,
                    source_path=temp_dir,
                )
                return db.query(RepositorySnapshot).filter_by(id=snap_id).first()
        except Exception:
            pass
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return None


@router.post("/{repository_id}/impact-analysis", response_model=Dict[str, Any])
def run_impact_analysis(
    repository_id: str,
    req: ImpactAnalysisRequest,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Executes a deterministic Change Impact & Blast Radius analysis between two snapshots.
    Traverses typed relationships with cycle protection, attaches evidence, and generates explainable paths.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    base_snap = _ensure_snapshot(db, repo, req.base_snapshot_id)
    if not base_snap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Base snapshot or commit '{req.base_snapshot_id}' not found and could not be reconstructed.",
        )

    target_snap = _ensure_snapshot(db, repo, req.target_snapshot_id)
    if not target_snap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target snapshot or commit '{req.target_snapshot_id}' not found and could not be reconstructed.",
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
            base_snapshot_id=base_snap.id,
            target_snapshot_id=target_snap.id,
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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Retrieves the full deterministic findings and paths for a previously completed impact analysis.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Projects the impact subgraph: changed nodes, directly/indirectly affected entities,
    and causal connecting relationships.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
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
@router.get("/{repository_id}/diff", response_model=Dict[str, Any])
def get_snapshot_diff(
    repository_id: str,
    base_snapshot_id: str,
    target_snapshot_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Computes a fast, normalized ChangeSet between two snapshots.
    Surfaces ADDED, REMOVED, and MODIFIED symbols/files before running full blast-radius.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
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


class EntityBlastRadiusRequest(BaseModel):
    artifact_id: Optional[str] = Field(None, description="Artifact ID, qualified name, or symbol name")
    entity_name: Optional[str] = Field(None, description="Alias for artifact_id")
    snapshot_id: Optional[str] = Field(None, description="Optional snapshot ID (defaults to latest)")
    max_depth: Optional[int] = Field(5, ge=1, le=10)


@router.post("/{repository_id}/blast-radius", response_model=Dict[str, Any])
@router.get("/{repository_id}/blast-radius", response_model=Dict[str, Any])
def compute_entity_blast_radius(
    repository_id: str,
    artifact_id: Optional[str] = Query(None),
    snapshot_id: Optional[str] = Query(None),
    max_depth: int = Query(5, ge=1, le=10),
    body: Optional[EntityBlastRadiusRequest] = None,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Directly computes forward and backward blast radius for any individual entity,
    component, API, or symbol in the Digital Twin without requiring two distinct git commits.
    Enables instant blast radius tracing for shallow-cloned and single-snapshot repositories.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    from app.models.entities import StructuralArtifact, ArtifactRelationship
    from app.services.analysis.graph.projection import twin_graph_projection

    target = None
    if body and (body.artifact_id or body.entity_name):
        target = (body.artifact_id or body.entity_name).strip()
    elif artifact_id and artifact_id.strip():
        target = artifact_id.strip()

    snap_id = (body.snapshot_id if body and body.snapshot_id else None) or snapshot_id
    if not snap_id:
        latest = (
            db.query(RepositorySnapshot)
            .filter_by(repository_id=repo.id)
            .order_by(RepositorySnapshot.created_at.desc())
            .first()
        )
        if not latest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No snapshots found for repository '{repo.name}'. Please ingest or analyze the repository first.",
            )
        snap_id = latest.id

    artifacts = (
        db.query(StructuralArtifact)
        .filter_by(snapshot_id=snap_id)
        .all()
    )
    relationships = (
        db.query(ArtifactRelationship)
        .filter_by(snapshot_id=snap_id)
        .all()
    )

    if not artifacts:
        return {
            "status": "EMPTY",
            "message": f"Snapshot '{snap_id}' contains 0 structural artifacts.",
            "candidates": [],
        }

    # If no target specified, return top architectural hubs as candidates
    if not target:
        # Sort artifacts by in-degree / hubness
        candidates = []
        for a in artifacts[:25]:
            candidates.append({
                "id": a.id,
                "name": a.name,
                "qualified_name": a.qualified_name,
                "artifact_type": str(a.artifact_type),
                "location": a.location,
            })
        return {
            "status": "AWAITING_TARGET",
            "message": "Specify an 'artifact_id' or choose from candidate entities.",
            "snapshot_id": snap_id,
            "total_artifacts": len(artifacts),
            "candidates": candidates,
        }

    impact_data = twin_graph_projection._compute_impact_blast_radius(
        artifacts=artifacts,
        relationships=relationships,
        root_artifact_id=target,
    )

    if not impact_data or not impact_data.get("affected_node_ids"):
        # Suggest candidates that closely match
        t_low = target.lower()
        close_matches = [
            {"id": a.id, "name": a.name, "qualified_name": a.qualified_name, "location": a.location}
            for a in artifacts
            if t_low in (a.name or "").lower() or t_low in (a.qualified_name or "").lower()
        ][:8]
        return {
            "status": "NOT_FOUND",
            "message": f"Entity '{target}' could not be resolved in snapshot.",
            "candidates": close_matches,
        }

    art_map = {str(a.id): a for a in artifacts}
    affected_nodes = []
    details = impact_data.get("details", {})

    for nid in impact_data.get("affected_node_ids", set()):
        art = art_map.get(str(nid))
        if not art:
            continue
        node_details = details.get(str(nid), {})
        affected_nodes.append({
            "id": art.id,
            "name": art.name,
            "qualified_name": art.qualified_name,
            "artifact_type": str(art.artifact_type),
            "location": art.location,
            "depth": node_details.get("depth", 0),
            "reasons": node_details.get("reasons", []),
            "is_root": (str(art.id) == str(impact_data.get("root_artifact_id"))),
        })

    # Sort root first, then by depth ascending
    affected_nodes.sort(key=lambda x: (not x["is_root"], x["depth"], x["name"]))

    summary = impact_data.get("summary", {})
    root_art = art_map.get(str(impact_data.get("root_artifact_id")))

    return {
        "status": "SUCCESS",
        "repository_id": repo.id,
        "repository_name": repo.name,
        "snapshot_id": snap_id,
        "root_artifact_id": impact_data.get("root_artifact_id"),
        "root_name": root_art.name if root_art else target,
        "root_qualified_name": root_art.qualified_name if root_art else target,
        "root_type": str(root_art.artifact_type) if root_art else "UNKNOWN",
        "root_location": root_art.location if root_art else "",
        "root_artifact": {
            "id": impact_data.get("root_artifact_id"),
            "name": root_art.name if root_art else target,
            "qualified_name": root_art.qualified_name if root_art else target,
            "artifact_type": str(root_art.artifact_type) if root_art else "UNKNOWN",
            "location": root_art.location if root_art else "",
        },
        "blast_radius_score": summary.get("blast_radius_score", 0.0),
        "risk_level": summary.get("risk_level", "LOW"),
        "total_affected": summary.get("total_affected", len(affected_nodes)),
        "affected_components_count": summary.get("affected_components_count", 0),
        "affected_apis": summary.get("affected_apis", []),
        "affected_tests": summary.get("affected_tests", []),
        "affected_components": [n["qualified_name"] for n in affected_nodes if not n.get("is_root") and n.get("artifact_type") not in ("API_ENDPOINT", "TEST_CASE", "TEST_SUITE")],
        "affected_nodes": affected_nodes,
        "summary": summary,
    }

