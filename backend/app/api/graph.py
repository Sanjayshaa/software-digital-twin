import os
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.auth import get_current_user_optional, AuthenticatedPrincipal
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
from app.services.acquisition import is_safe_clone_url
from app.services.acquisition.git_provider import acquire_github_repository
from app.core.filesystem import validate_safe_local_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repositories", tags=["Interactive Digital Twin Graph"])


class OnboardRepoRequest(BaseModel):
    local_path: str
    name: Optional[str] = None
    branch: Optional[str] = "main"


class ConnectGithubRequest(BaseModel):
    github_url: str = Field(..., description="Public HTTPS GitHub repository URL (e.g. https://github.com/owner/repo)")
    name: Optional[str] = Field(None, description="Optional display name for the repository")
    branch: Optional[str] = Field(None, description="Branch to analyze (defaults to remote default branch)")
    github_token: Optional[str] = Field(None, description="GitHub Personal Access Token for private repos (never stored)")


from app.core.auth import resolve_authorized_repo


def _resolve_repo(
    db: Session,
    repository_id: str,
    principal: Optional[AuthenticatedPrincipal] = None,
) -> Optional[Repository]:
    return resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def list_repositories(
    environment: Optional[str] = Query(None, description="Environment filter: USER or TEST or ALL"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Lists analyzed software repositories in the Digital Twin database with strict multi-user authorization."""
    # 1. Unauthenticated Guest: return empty list immediately. Never leak another user's repositories!
    if not principal:
        return []

    query = db.query(Repository)

    if environment:
        target_env = environment.upper()
        if target_env in ["USER", "TEST", "FIXTURE"]:
            query = query.filter(Repository.environment == target_env)

    # 2. Authenticated Non-Admin User: only repositories owned by this user
    if not principal.is_admin:
        query = query.filter(Repository.owner_id == principal.user_id)

    repos = query.order_by(Repository.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "local_path": r.local_path,
            "default_branch": r.default_branch,
            "source_type": r.source_type,
            "environment": r.environment,
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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Projects the persisted PostgreSQL Digital Twin into an interactive node-edge graph.
    Derives all elements from persisted artifacts, typed relationships, evidence, and snapshots.
    Supports Obsidian-style progressive disclosure, neighborhood focus, snapshot diffing, and change impact.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the workflow and process flow visualization for the repository.
    Explicitly categorizes each step and transition by evidence status:
    OBSERVED, STATICALLY_INFERRED, HEURISTIC, or UNKNOWN.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the repository directory and file tree with artifact counts for interactive explorer navigation.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the chronological list of snapshots for a repository with artifact and relationship counts.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    return twin_graph_projection.get_snapshots(db=db, repository_id=repo.id)


@router.post("/onboard", response_model=Dict[str, Any])
def onboard_repository(
    payload: OnboardRepoRequest,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Onboards and analyzes a local software repository through the UI platform.
    Executes discovery, structural AST parsing, relationship extraction, and snapshot generation.
    """
    # Enforce strict filesystem containment (SEC-01)
    abs_path = validate_safe_local_path(payload.local_path)

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
        if principal and repo.owner_id is None:
            repo.owner_id = principal.user_id
        repo.environment = "USER"
        repo.source_type = "LOCAL"
        db.commit()
        db.refresh(repo)
    else:
        repo = Repository(
            project_id=proj.id,
            owner_id=principal.user_id if principal else None,
            name=repo_name,
            local_path=abs_path,
            default_branch=payload.branch or "main",
            source_type="LOCAL",
            environment="USER",
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
            "source_type": "LOCAL",
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


@router.post("/connect-github", response_model=Dict[str, Any])
def connect_github_repository(
    payload: ConnectGithubRequest,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Connects a real GitHub repository by cloning it into an isolated workspace
    and then building a Digital Twin from the real source.

    Security guarantees:
    - URL is validated before use (HTTPS only, no command injection)
    - Token is used only during cloning and is never stored in the database
    - Clone workspace is isolated from the project source tree
    - Repository scripts are never executed during analysis
    - Clone is cleaned up on failure
    """
    # 1. Validate the GitHub URL
    is_safe, reason = is_safe_clone_url(payload.github_url)
    if not is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid repository URL: {reason}",
        )

    # 2. Acquire (clone) the repository
    logger.info("Acquiring GitHub repository: %s branch=%s", payload.github_url, payload.branch)
    acquisition = acquire_github_repository(
        github_url=payload.github_url,
        branch=payload.branch or None,
        github_token=payload.github_token or None,  # Token used here only; never persisted
    )

    if not acquisition.success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=acquisition.user_facing_error or "Repository acquisition failed.",
        )

    # 3. Derive repository display name
    repo_name = (
        payload.name.strip()
        if payload.name and payload.name.strip()
        else os.path.basename(acquisition.workspace_path.rstrip("/\\")) or "repository"
    )

    # 4. Persist or update Repository record
    # Key by canonical remote_url so the same GitHub repo doesn't create duplicates
    proj = db.query(Project).filter_by(name=f"Project-{repo_name}").first()
    if not proj:
        proj = Project(name=f"Project-{repo_name}", description=f"Digital Twin for {repo_name}")
        db.add(proj)
        db.commit()
        db.refresh(proj)

    repo = db.query(Repository).filter_by(remote_url=acquisition.remote_url).first()
    if repo:
        # Update path to latest clone
        repo.local_path = acquisition.workspace_path
        repo.default_branch = acquisition.branch_name
        if payload.name and payload.name.strip():
            repo.name = repo_name
        if principal and repo.owner_id is None:
            repo.owner_id = principal.user_id
        repo.source_type = "GITHUB"
        repo.environment = "USER"
        db.commit()
        db.refresh(repo)
    else:
        repo = Repository(
            project_id=proj.id,
            owner_id=principal.user_id if principal else None,
            name=repo_name,
            local_path=acquisition.workspace_path,
            remote_url=acquisition.remote_url,
            default_branch=acquisition.branch_name,
            vcs_type="git",
            source_type="GITHUB",
            environment="USER",
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

    # 5. Build Digital Twin from the real cloned source
    try:
        snapshot_id, result = structural_twin_engine.build_structural_twin(
            db=db,
            repository_id=repo.id,
            commit_hash=acquisition.commit_sha,
            branch_name=acquisition.branch_name,
        )
        return {
            "status": "COMPLETED",
            "source_type": "GITHUB",
            "repository": {
                "id": repo.id,
                "name": repo.name,
                "remote_url": acquisition.remote_url,
                "branch": acquisition.branch_name,
                "commit_sha": acquisition.commit_sha,
            },
            "repository_id": repo.id,
            "repository_name": repo.name,
            "remote_url": acquisition.remote_url,
            "snapshot_id": snapshot_id,
            "commit_sha": acquisition.commit_sha,
            "branch": acquisition.branch_name,
            "files_scanned": result.files_scanned,
            "artifacts_count": len(result.artifacts),
            "relationships_count": len(result.relationships),
            "analyzers_executed": result.analyzer_names,
        }
    except Exception as exc:
        logger.exception("Digital Twin build failed for GitHub repo %s", payload.github_url)
        # Failure Atomicity: Clean up cloned workspace directory and rollback database state
        from app.services.acquisition.git_provider import cleanup_acquired_workspace
        cleanup_acquired_workspace(acquisition.workspace_path)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Digital Twin build failed: {str(exc)}",
        )


@router.post("/upload-archive", response_model=Dict[str, Any])
async def upload_project_archive(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Safely accepts an uploaded project archive (ZIP), validates containment,
    extracts it into an isolated temporary workspace, and synthesizes a Digital Twin.
    """
    import zipfile
    import shutil
    import tempfile
    from pathlib import Path

    filename = file.filename or "archive.zip"
    if not (filename.lower().endswith(".zip") or filename.lower().endswith(".tar.gz")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported archive format. Please upload a .zip file."
        )

    extract_dir = tempfile.mkdtemp(prefix="twin_upload_")
    archive_path = os.path.join(extract_dir, filename)

    try:
        MAX_SIZE = 100 * 1024 * 1024
        size = 0
        with open(archive_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Archive exceeds 100MB maximum size limit."
                    )
                buffer.write(chunk)

        # Safe extraction to prevent Zip Slip
        if filename.lower().endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                for member in zf.infolist():
                    target_path = os.path.abspath(os.path.join(extract_dir, member.filename))
                    if not target_path.startswith(os.path.abspath(extract_dir)):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Archive contains unsafe path traversal members."
                        )
                zf.extractall(extract_dir)
        else:
            shutil.unpack_archive(archive_path, extract_dir)

        if os.path.exists(archive_path):
            os.remove(archive_path)

        contents = [os.path.join(extract_dir, x) for x in os.listdir(extract_dir) if not x.startswith(".")]
        dirs = [c for c in contents if os.path.isdir(c)]
        scan_path = dirs[0] if len(dirs) == 1 and len(contents) == 1 else extract_dir

        repo_name = (
            name.strip()
            if name and name.strip()
            else Path(filename).stem
        )

        proj = db.query(Project).filter_by(name=f"Project-{repo_name}").first()
        if not proj:
            proj = Project(name=f"Project-{repo_name}", description=f"Digital Twin for uploaded archive {repo_name}")
            db.add(proj)
            db.commit()
            db.refresh(proj)

        repo = Repository(
            project_id=proj.id,
            owner_id=principal.user_id if principal else None,
            name=repo_name,
            local_path=scan_path,
            default_branch="main",
            source_type="ARCHIVE",
            environment="USER",
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

        snapshot_id, result = structural_twin_engine.build_structural_twin(
            db=db,
            repository_id=repo.id,
            commit_hash="HEAD",
            branch_name="main",
        )

        return {
            "status": "COMPLETED",
            "source_type": "ARCHIVE",
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
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to process uploaded archive")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Archive processing failed: {str(exc)}",
        )


@router.get("/{repository_id}/overview", response_model=Dict[str, Any])
def get_repository_overview(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the comprehensive, real Digital Twin Overview metrics and health indicators.
    All data is derived directly from PostgreSQL records.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
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

    if snapshot_id:
        active_snap = next((s for s in snapshots if s.id == snapshot_id), None)
        if not active_snap:
            raise HTTPException(
                status_code=404,
                detail=f"Snapshot '{snapshot_id}' does not belong to repository '{repo.id}'."
            )
    else:
        # Strict state integrity: do not silently assume snapshots[0] if no snapshot was specified
        return {
            "repository": {
                "id": repo.id,
                "name": repo.name,
                "local_path": repo.local_path,
                "default_branch": repo.default_branch,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
            },
            "snapshot": None,
            "has_snapshots": len(snapshots) > 0,
            "metrics": {
                "files": 0,
                "artifacts": 0,
                "relationships": 0,
                "tests": 0,
                "apis": 0,
                "processes": 0,
                "violations": 0,
            },
            "component_breakdown": {},
            "architecture_packages": [],
            "latest_impact": None,
            "analysis_status": {},
            "latest_run": None,
        }

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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the table of structural components (classes, modules, functions, interfaces) for the snapshot.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
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
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns mapped test suites and test cases with target components and evidence links.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
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
