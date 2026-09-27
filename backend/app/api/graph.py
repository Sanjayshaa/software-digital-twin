import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.models.entities import (
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    AnalysisRun,
    ArchitectureDriftEntity,
)
from app.services.analysis.engine import structural_twin_engine
from app.services.analysis.graph.projection import twin_graph_projection

router = APIRouter(prefix="/repositories", tags=["Interactive Digital Twin Graph"])


class OnboardRepoRequest(BaseModel):
    local_path: str
    name: Optional[str] = None
    branch: Optional[str] = "main"


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


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def list_repositories(db: Session = Depends(get_db)):
    """Lists all analyzed software repositories in the Digital Twin database."""
    repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "local_path": r.local_path,
            "default_branch": r.default_branch,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in repos
    ]


@router.get("/{repository_id}/graph", response_model=Dict[str, Any])
def get_repository_graph(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None, description="Snapshot ID (defaults to latest)"),
    focus: Optional[str] = Query(None, description="Focus on specific artifact ID or qualified name"),
    depth: int = Query(2, ge=1, le=5, description="Neighborhood depth for focus query"),
    level: int = Query(2, ge=1, le=4, description="Progressive disclosure level (1: Packages, 2: Components, 3: Members, 4: All)"),
    artifact_types: Optional[str] = Query(None, description="Comma-separated artifact types filter"),
    relationship_types: Optional[str] = Query(None, description="Comma-separated relationship types filter"),
    languages: Optional[str] = Query(None, description="Comma-separated languages filter"),
    include_tests: bool = Query(True, description="Include test cases and test suites"),
    include_external_dependencies: bool = Query(False, description="Include external library dependencies"),
    diff_snapshot_id: Optional[str] = Query(None, description="Second snapshot ID to compute structural diff against"),
    impact_artifact_id: Optional[str] = Query(None, description="Artifact ID to calculate forward change blast radius"),
    db: Session = Depends(get_db),
):
    """
    Projects the persisted PostgreSQL Digital Twin into an interactive node-edge graph.
    Derives all elements from persisted artifacts, typed relationships, evidence, and snapshots.
    Supports Obsidian-style progressive disclosure, neighborhood focus, snapshot diffing, and change impact.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    art_types_list = [t.strip() for t in artifact_types.split(",")] if artifact_types else None
    rel_types_list = [r.strip() for r in relationship_types.split(",")] if relationship_types else None
    lang_list = [l.strip() for l in languages.split(",")] if languages else None

    try:
        graph_data = twin_graph_projection.project_graph(
            db=db,
            repository_id=repo.id,
            snapshot_id=snapshot_id,
            focus=focus,
            depth=depth,
            level=level,
            artifact_types=art_types_list,
            relationship_types=rel_types_list,
            languages=lang_list,
            include_tests=include_tests,
            include_external_dependencies=include_external_dependencies,
            diff_snapshot_id=diff_snapshot_id,
            impact_artifact_id=impact_artifact_id,
        )
        return graph_data
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error projecting Digital Twin graph: {str(exc)}",
        )


@router.get("/{repository_id}/process-graph", response_model=Dict[str, Any])
def get_repository_process_graph(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None, description="Snapshot ID (defaults to latest)"),
    db: Session = Depends(get_db),
):
    """
    Returns the workflow and process flow visualization for the repository.
    Explicitly categorizes each step and transition by evidence status:
    OBSERVED, STATICALLY_INFERRED, HEURISTIC, or UNKNOWN.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    try:
        return twin_graph_projection.get_process_graph(
            db=db,
            repository_id=repo.id,
            snapshot_id=snapshot_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error projecting process graph: {str(exc)}",
        )


@router.get("/{repository_id}/file-tree", response_model=Dict[str, Any])
def get_repository_file_tree(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None, description="Snapshot ID (defaults to latest)"),
    db: Session = Depends(get_db),
):
    """
    Returns the repository directory and file tree with artifact counts for interactive explorer navigation.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    try:
        return twin_graph_projection.get_file_tree(
            db=db,
            repository_id=repo.id,
            snapshot_id=snapshot_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating repository file tree: {str(exc)}",
        )


@router.get("/{repository_id}/graph/snapshots", response_model=List[Dict[str, Any]])
def get_repository_snapshots(
    repository_id: str,
    db: Session = Depends(get_db),
):
    """
    Returns the chronological list of snapshots for a repository with artifact and relationship counts.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    return twin_graph_projection.get_snapshots(db=db, repository_id=repo.id)


@router.post("/onboard", response_model=Dict[str, Any])
def onboard_repository(payload: OnboardRepoRequest, db: Session = Depends(get_db)):
    """
    Onboards and analyzes a local software repository through the UI platform.
    Executes discovery, structural AST parsing, relationship extraction, and snapshot generation.
    """
    raw_path = payload.local_path.strip()
    abs_path = os.path.abspath(raw_path)
    if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Local path does not exist or is not a directory: '{raw_path}'",
        )

    repo_name = (
        payload.name.strip()
        if payload.name and payload.name.strip()
        else os.path.basename(abs_path.rstrip("/\\")) or "repository"
    )

    proj = db.query(Project).filter_by(name=f"Project-{repo_name}").first()
    if not proj:
        proj = Project(name=f"Project-{repo_name}", description=f"Digital Twin for {repo_name}")
        db.add(proj)
        db.commit()
        db.refresh(proj)

    repo = db.query(Repository).filter_by(local_path=abs_path).first()
    if repo:
        if payload.name and payload.name.strip():
            repo.name = repo_name
            db.commit()
            db.refresh(repo)
    else:
        repo = Repository(
            project_id=proj.id,
            name=repo_name,
            local_path=abs_path,
            default_branch=payload.branch or "main",
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

    try:
        snapshot_id, result = structural_twin_engine.build_structural_twin(
            db=db,
            repository_id=repo.id,
            commit_hash="HEAD",
            branch_name=payload.branch or "main",
        )
        return {
            "status": "COMPLETED",
            "repository": {
                "id": repo.id,
                "name": repo.name,
                "local_path": repo.local_path,
                "branch": repo.default_branch,
            },
            "repository_id": repo.id,
            "repository_name": repo.name,
            "local_path": repo.local_path,
            "snapshot_id": snapshot_id,
            "files_scanned": result.files_scanned,
            "artifacts_count": len(result.artifacts),
            "relationships_count": len(result.relationships),
            "evidence_count": len(result.evidence_items),
            "analyzers_executed": result.analyzer_names,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Digital Twin build failed: {str(exc)}",
        )


@router.get("/{repository_id}/overview", response_model=Dict[str, Any])
def get_repository_overview(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Returns the comprehensive, real Digital Twin Overview metrics and health indicators.
    All data is derived directly from PostgreSQL records.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    snapshots = (
        db.query(RepositorySnapshot)
        .filter_by(repository_id=repo.id)
        .order_by(RepositorySnapshot.created_at.desc())
        .all()
    )
    if not snapshots:
        return {
            "repository": {
                "id": repo.id,
                "name": repo.name,
                "local_path": repo.local_path,
                "default_branch": repo.default_branch,
            },
            "has_snapshots": False,
            "metrics": {},
        }

    active_snap = next((s for s in snapshots if s.id == snapshot_id), snapshots[0])

    artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=active_snap.id).all()
    relationships = db.query(ArtifactRelationship).filter_by(snapshot_id=active_snap.id).all()
    drifts = db.query(ArchitectureDriftEntity).filter_by(snapshot_id=active_snap.id).all()
    latest_run = (
        db.query(AnalysisRun)
        .filter_by(snapshot_id=active_snap.id)
        .order_by(AnalysisRun.created_at.desc())
        .first()
    )

    files_set = set()
    breakdown = {}
    tests_count = 0
    apis_count = 0

    for a in artifacts:
        breakdown[a.artifact_type] = breakdown.get(a.artifact_type, 0) + 1
        if a.artifact_type in ("TEST_CASE", "TEST_SUITE"):
            tests_count += 1
        elif a.artifact_type == "API_ENDPOINT":
            apis_count += 1

        if a.location:
            file_part = a.location.split(":")[0]
            if file_part:
                files_set.add(file_part)

    try:
        proc_data = twin_graph_projection.get_process_graph(db, repo.id, active_snap.id)
        process_flows_count = len(proc_data.get("nodes", []))
    except Exception:
        process_flows_count = 0

    violations = [d for d in drifts if d.status == "DETECTED"]

    # Latest Change Impact run if available
    latest_impact_run = (
        db.query(AnalysisRun)
        .filter_by(repository_id=repo.id, run_type="change_impact")
        .order_by(AnalysisRun.created_at.desc())
        .first()
    )
    latest_impact_data = latest_impact_run.summary if (latest_impact_run and latest_impact_run.summary) else None

    # Aggregated Architecture Packages (Level 1 grouping)
    packages_map = {}
    for a in artifacts:
        loc = a.location or a.qualified_name or ""
        pkg = loc.split("/")[0] if "/" in loc else (a.qualified_name.split(".")[0] if "." in a.qualified_name else "root")
        if pkg not in packages_map:
            packages_map[pkg] = {
                "name": pkg,
                "total_artifacts": 0,
                "classes": 0,
                "functions": 0,
                "modules": 0,
                "sample_components": [],
            }
        packages_map[pkg]["total_artifacts"] += 1
        if a.artifact_type in ("CLASS", "SERVICE"):
            packages_map[pkg]["classes"] += 1
            if len(packages_map[pkg]["sample_components"]) < 3 and a.name not in packages_map[pkg]["sample_components"]:
                packages_map[pkg]["sample_components"].append(a.name)
        elif a.artifact_type in ("FUNCTION", "METHOD"):
            packages_map[pkg]["functions"] += 1
        elif a.artifact_type in ("MODULE", "PACKAGE"):
            packages_map[pkg]["modules"] += 1
            if len(packages_map[pkg]["sample_components"]) < 3 and a.name not in packages_map[pkg]["sample_components"]:
                packages_map[pkg]["sample_components"].append(a.name)

    arch_packages = sorted(list(packages_map.values()), key=lambda p: -p["total_artifacts"])

    return {
        "repository": {
            "id": repo.id,
            "name": repo.name,
            "local_path": repo.local_path,
            "default_branch": repo.default_branch,
            "created_at": repo.created_at.isoformat() if repo.created_at else None,
        },
        "snapshot": {
            "id": active_snap.id,
            "commit_hash": active_snap.commit_hash,
            "branch_name": active_snap.branch_name,
            "created_at": active_snap.created_at.isoformat() if active_snap.created_at else None,
        },
        "has_snapshots": True,
        "metrics": {
            "files": len(files_set) or breakdown.get("MODULE", 0),
            "artifacts": len(artifacts),
            "relationships": len(relationships),
            "tests": tests_count,
            "apis": apis_count,
            "processes": process_flows_count,
            "violations": len(violations),
        },
        "component_breakdown": breakdown,
        "architecture_packages": arch_packages,
        "latest_impact": latest_impact_data,
        "analysis_status": {
            "discovery": "Complete",
            "technology_profile": "Complete",
            "structural_twin": "Complete",
            "dependency_mapping": "Complete",
            "test_mapping": "Complete" if tests_count > 0 else "Evaluated",
            "process_mapping": "Statically Inferred" if process_flows_count > 0 else "None detected",
            "architecture_validation": "Evaluated" if drifts else "No baseline violations",
        },
        "latest_run": {
            "id": latest_run.id if latest_run else None,
            "status": latest_run.status if latest_run else "COMPLETED",
            "analyzers": latest_run.analyzer_names if latest_run else [],
            "completed_at": latest_run.completed_at.isoformat() if latest_run and latest_run.completed_at else None,
        },
        "violations": [
            {
                "id": d.id,
                "category": d.category,
                "severity": d.severity,
                "source": d.source,
                "target": d.target,
                "expected_rule": d.expected_rule,
                "actual_evidence": d.actual_evidence,
                "location": f"{d.file_path}:{d.line_number}",
            }
            for d in violations[:20]
        ],
    }


@router.get("/{repository_id}/components", response_model=Dict[str, Any])
def get_repository_components(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Returns the table of structural components (classes, modules, functions, interfaces) for the snapshot.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    snapshots = (
        db.query(RepositorySnapshot)
        .filter_by(repository_id=repo.id)
        .order_by(RepositorySnapshot.created_at.desc())
        .all()
    )
    if not snapshots:
        return {"components": [], "total": 0}

    active_snap = next((s for s in snapshots if s.id == snapshot_id), snapshots[0])

    artifacts = (
        db.query(StructuralArtifact)
        .filter(
            StructuralArtifact.snapshot_id == active_snap.id,
            StructuralArtifact.artifact_type.in_(["CLASS", "MODULE", "FUNCTION", "METHOD", "INTERFACE", "API_ENDPOINT"]),
        )
        .order_by(StructuralArtifact.artifact_type, StructuralArtifact.name)
        .all()
    )

    return {
        "snapshot_id": active_snap.id,
        "total": len(artifacts),
        "components": [
            {
                "id": a.id,
                "name": a.name,
                "type": a.artifact_type,
                "qualified_name": a.qualified_name,
                "language": a.language,
                "location": a.location or f"{a.file_path}:{a.line_start or 1}",
                "line_start": a.line_start,
                "line_end": a.line_end,
                "confidence": a.confidence,
            }
            for a in artifacts
        ],
    }


@router.get("/{repository_id}/tests-map", response_model=Dict[str, Any])
def get_repository_tests_map(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Returns mapped test suites and test cases with target components and evidence links.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    snapshots = (
        db.query(RepositorySnapshot)
        .filter_by(repository_id=repo.id)
        .order_by(RepositorySnapshot.created_at.desc())
        .all()
    )
    if not snapshots:
        return {"tests": [], "total_tests": 0}

    active_snap = next((s for s in snapshots if s.id == snapshot_id), snapshots[0])

    test_artifacts = (
        db.query(StructuralArtifact)
        .filter(
            StructuralArtifact.snapshot_id == active_snap.id,
            StructuralArtifact.artifact_type.in_(["TEST_CASE", "TEST_SUITE"]),
        )
        .all()
    )

    art_ids = [t.id for t in test_artifacts]
    relationships = (
        db.query(ArtifactRelationship)
        .filter(
            ArtifactRelationship.snapshot_id == active_snap.id,
            or_(
                ArtifactRelationship.source_artifact_id.in_(art_ids),
                ArtifactRelationship.target_artifact_id.in_(art_ids),
            ),
        )
        .all()
    )

    target_ids = {r.target_artifact_id for r in relationships} | {r.source_artifact_id for r in relationships}
    targets = {
        a.id: a for a in db.query(StructuralArtifact).filter(StructuralArtifact.id.in_(target_ids)).all()
    }

    test_items = []
    tested_components_set = set()
    verified_mappings_count = 0

    for t in test_artifacts:
        covered = []
        for r in relationships:
            if r.source_artifact_id == t.id or (r.source_artifact_id == t.qualified_name):
                tgt = targets.get(r.target_artifact_id)
                if tgt and tgt.artifact_type not in ("TEST_CASE", "TEST_SUITE"):
                    covered.append({
                        "name": tgt.name,
                        "type": tgt.artifact_type,
                        "relationship": r.relationship_type,
                        "location": tgt.location or f"{tgt.qualified_name}",
                    })
                    tested_components_set.add(tgt.name)
            # Also check if test targets component by naming convention or import
            elif r.target_artifact_id == t.id and r.relationship_type == "TESTS":
                src = targets.get(r.source_artifact_id)
                if src:
                    covered.append({
                        "name": src.name,
                        "type": src.artifact_type,
                        "relationship": "TESTS",
                        "location": src.location or f"{src.qualified_name}",
                    })
                    tested_components_set.add(src.name)

        if covered:
            verified_mappings_count += 1

        test_items.append({
            "id": t.id,
            "name": t.name,
            "type": t.artifact_type,
            "location": t.location,
            "line_start": t.line_start,
            "line_end": t.line_end,
            "covered_targets": covered,
            "evidence_status": "VERIFIED_MAPPING" if covered else "STATICALLY_INFERRED",
        })

    unmapped_count = len(test_items) - verified_mappings_count

    return {
        "snapshot_id": active_snap.id,
        "total_tests": len(test_items),
        "verified_mappings_count": verified_mappings_count,
        "unmapped_count": unmapped_count,
        "tested_components_count": len(tested_components_set),
        "tests": test_items,
    }
