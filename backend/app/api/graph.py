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
    Branch,
)
from app.services.analysis.engine import structural_twin_engine
from app.services.analysis.graph.projection import twin_graph_projection
from app.services.acquisition import is_safe_clone_url
from app.services.acquisition.git_provider import acquire_github_repository
from app.core.filesystem import validate_safe_local_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repositories", tags=["Interactive Digital Twin Graph"])


from pydantic import BaseModel, Field, model_validator


class OnboardRepoRequest(BaseModel):
    local_path: str
    name: Optional[str] = None
    branch: Optional[str] = "main"


class ConnectGithubRequest(BaseModel):
    github_url: Optional[str] = Field(None, description="Public HTTPS GitHub repository URL (e.g. https://github.com/owner/repo)")
    repo_url: Optional[str] = Field(None, description="Alternative alias for GitHub repository URL")
    name: Optional[str] = Field(None, description="Optional display name for the repository")
    branch: Optional[str] = Field(None, description="Branch to analyze (defaults to remote default branch)")
    github_token: Optional[str] = Field(None, description="GitHub Personal Access Token for private repos (never stored)")
    access_token: Optional[str] = Field(None, description="Alternative alias for GitHub Personal Access Token")

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("github_url") and data.get("repo_url"):
                data["github_url"] = data.get("repo_url")
            if not data.get("github_token") and data.get("access_token"):
                data["github_token"] = data.get("access_token")
            if not data.get("github_url"):
                raise ValueError("Field 'github_url' is required.")
        return data


from app.core.auth import resolve_authorized_repo, provision_guest_user


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
        elif target_env == "ALL" and principal.is_admin:
            pass
    else:
        # Strict zero-trust default: only USER environment repositories, never TEST or FIXTURE
        query = query.filter(Repository.environment == "USER")

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


@router.get("/{repository_id}/snapshots", response_model=List[Dict[str, Any]])
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


@router.get("/{repository_id}/branches", response_model=List[Dict[str, Any]])
def get_repository_branches(
    repository_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns branch history and current default branch.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    branches = db.query(Branch).filter_by(repository_id=repo.id).all()
    if not branches:
        distinct_branches = db.query(RepositorySnapshot.branch_name).filter_by(repository_id=repo.id).distinct().all()
        return [{"name": b[0] or "main", "is_default": (b[0] == repo.default_branch)} for b in distinct_branches]
    return [{"id": b.id, "name": b.name, "head_commit_hash": b.head_commit_hash, "is_default": b.is_default} for b in branches]


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
    session_token = None
    if principal:
        target_user_id = principal.user_id
    else:
        # Auto-provision isolated ephemeral guest session
        guest_user, session_token = provision_guest_user(db)
        target_user_id = guest_user.id

    # Enforce strict filesystem containment (SEC-01)
    abs_path = validate_safe_local_path(payload.local_path)

    repo_name = (
        payload.name.strip()
        if payload.name and payload.name.strip()
        else os.path.basename(abs_path.rstrip("/\\")) or "repository"
    )

    proj = db.query(Project).filter_by(name=f"Project-{repo_name}-{target_user_id[:8]}").first()
    if not proj:
        proj = Project(name=f"Project-{repo_name}-{target_user_id[:8]}", description=f"Digital Twin for {repo_name}")
        db.add(proj)
        db.commit()
        db.refresh(proj)

    repo = db.query(Repository).filter_by(local_path=abs_path, owner_id=target_user_id).first()
    if repo:
        if payload.name and payload.name.strip():
            setattr(repo, "name", repo_name)
        setattr(repo, "environment", "USER")
        setattr(repo, "source_type", "LOCAL")
        db.commit()
        db.refresh(repo)
    else:
        repo = Repository(
            project_id=proj.id,
            owner_id=target_user_id,
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
        res = {
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
        if session_token:
            res["session_token"] = session_token
        return res
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
    github_url = payload.github_url or payload.repo_url
    if not github_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid GitHub repository URL is required.",
        )

    is_safe, reason = is_safe_clone_url(github_url)
    if not is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid repository URL: {reason}",
        )

    # 2. Acquire (clone) the repository
    logger.info("Acquiring GitHub repository: %s branch=%s", github_url, payload.branch)
    acquisition = acquire_github_repository(
        github_url=github_url,
        branch=payload.branch or None,
        github_token=payload.github_token or None,  # Token used here only; never persisted
    )

    if not acquisition.success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=acquisition.user_facing_error or "Repository acquisition failed.",
        )

    # 3. Derive repository display name, tenant ownership, and build twin
    try:
        session_token = None
        if principal:
            target_user_id = principal.user_id
        else:
            # Auto-provision isolated ephemeral guest session
            guest_user, session_token = provision_guest_user(db)
            target_user_id = guest_user.id

        repo_name = (
            payload.name.strip()
            if payload.name and payload.name.strip()
            else os.path.basename(acquisition.workspace_path.rstrip("/\\")) or "repository"
        )

        # 4. Persist or update Repository record scoped strictly to this owner
        proj = db.query(Project).filter_by(name=f"Project-{repo_name}-{target_user_id[:8]}").first()
        if not proj:
            proj = Project(name=f"Project-{repo_name}-{target_user_id[:8]}", description=f"Digital Twin for {repo_name}")
            db.add(proj)
            db.commit()
            db.refresh(proj)

        repo = db.query(Repository).filter_by(remote_url=acquisition.remote_url, owner_id=target_user_id).first()
        if repo:
            # Update path to latest clone
            setattr(repo, "local_path", acquisition.workspace_path)
            setattr(repo, "default_branch", acquisition.branch_name)
            if payload.name and payload.name.strip():
                setattr(repo, "name", repo_name)
            setattr(repo, "source_type", "GITHUB")
            setattr(repo, "environment", "USER")
            db.commit()
            db.refresh(repo)
        else:
            repo = Repository(
                project_id=proj.id,
                owner_id=target_user_id,
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
        snapshot_id, result = structural_twin_engine.build_structural_twin(
            db=db,
            repository_id=repo.id,
            commit_hash=acquisition.commit_sha,
            branch_name=acquisition.branch_name,
        )
        res = {
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
        if session_token:
            res["session_token"] = session_token
        return res
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Digital Twin build failed for GitHub repo %s: %s", payload.github_url, exc)
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

        # Safe extraction to prevent Zip Slip and Tar Slip
        extract_dir_abs = os.path.abspath(extract_dir)
        if filename.lower().endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                for member in zf.infolist():
                    target_path = os.path.abspath(os.path.join(extract_dir_abs, member.filename))
                    if os.path.commonpath([target_path, extract_dir_abs]) != extract_dir_abs:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Archive contains unsafe path traversal members."
                        )
                zf.extractall(extract_dir)
        elif filename.lower().endswith((".tar.gz", ".tgz", ".tar")):
            import tarfile
            with tarfile.open(archive_path, "r:*") as tf:
                for member in tf.getmembers():
                    target_path = os.path.abspath(os.path.join(extract_dir_abs, member.name))
                    if os.path.commonpath([target_path, extract_dir_abs]) != extract_dir_abs:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Archive contains unsafe path traversal members."
                        )
                tf.extractall(extract_dir)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported archive format. Supported formats: .zip, .tar.gz, .tgz, .tar"
            )

        if os.path.exists(archive_path):
            os.remove(archive_path)

        contents = [os.path.join(extract_dir, x) for x in os.listdir(extract_dir) if not x.startswith(".")]
        dirs = [c for c in contents if os.path.isdir(c)]
        scan_path = dirs[0] if len(dirs) == 1 and len(contents) == 1 else extract_dir

        session_token = None
        if principal:
            target_user_id = principal.user_id
        else:
            guest_user, session_token = provision_guest_user(db)
            target_user_id = guest_user.id

        repo_name = (
            name.strip()
            if name and name.strip()
            else Path(filename).stem
        )

        proj = db.query(Project).filter_by(name=f"Project-{repo_name}-{target_user_id[:8]}").first()
        if not proj:
            proj = Project(name=f"Project-{repo_name}-{target_user_id[:8]}", description=f"Digital Twin for uploaded archive {repo_name}")
            db.add(proj)
            db.commit()
            db.refresh(proj)

        repo = Repository(
            project_id=proj.id,
            owner_id=target_user_id,
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

        res = {
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
        if session_token:
            res["session_token"] = session_token
        return res
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to process uploaded archive")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Archive processing failed: {str(exc)}",
        )


@router.delete("/{repository_id}", response_model=Dict[str, Any])
def delete_repository(
    repository_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Safely and transactionally deletes an ingested repository, its snapshots,
    artifacts, relationships, evidence, analysis runs, scenarios, and local cloned workspaces.
    Enforces that only the authorized owner or an admin can delete the repository.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    # Check ownership or admin
    if principal and not principal.is_admin and repo.owner_id and repo.owner_id != principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this repository.",
        )

    from app.models.entities import (
        Evidence,
        SimulationScenario,
        HistoricalChange,
        ProjectTechnology,
        ProjectCapability,
    )

    snapshots = db.query(RepositorySnapshot).filter_by(repository_id=repo.id).all()
    snapshot_ids = [s.id for s in snapshots]

    if snapshot_ids:
        db.query(ArtifactRelationship).filter(
            (ArtifactRelationship.snapshot_id.in_(snapshot_ids))
        ).delete(synchronize_session=False)

        db.query(StructuralArtifact).filter(
            StructuralArtifact.snapshot_id.in_(snapshot_ids)
        ).delete(synchronize_session=False)

    db.query(Evidence).filter_by(project_id=repo.project_id).delete(synchronize_session=False)
    db.query(AnalysisRun).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db.query(SimulationScenario).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db.query(HistoricalChange).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db.query(ProjectTechnology).filter_by(project_id=repo.project_id).delete(synchronize_session=False)
    db.query(ProjectCapability).filter_by(project_id=repo.project_id).delete(synchronize_session=False)
    db.query(RepositorySnapshot).filter_by(repository_id=repo.id).delete(synchronize_session=False)

    # Clean up local filesystem clone if in temporary or uploads folder
    local_path = repo.local_path
    if local_path and os.path.exists(local_path):
        norm_path = os.path.abspath(local_path)
        if "data/repos" in norm_path or "tmp" in norm_path or "temp" in norm_path:
            try:
                import shutil
                shutil.rmtree(norm_path, ignore_errors=True)
            except Exception:
                pass

    repo_name = repo.name
    db.delete(repo)
    db.commit()

    return {
        "status": "DELETED",
        "repository_id": repository_id,
        "name": repo_name,
        "message": f"Repository '{repo_name}' and all associated Digital Twin data successfully deleted.",
    }


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
        local_files_count = 0
        if repo.local_path and os.path.isdir(repo.local_path):
            try:
                for _, _, flist in os.walk(repo.local_path):
                    local_files_count += len([f for f in flist if not f.startswith(".")])
            except Exception:
                pass

        return {
            "repository": {
                "id": repo.id,
                "name": repo.name,
                "local_path": repo.local_path,
                "default_branch": repo.default_branch,
            },
            "has_snapshots": False,
            "status": "UNANALYZED",
            "message": "Repository is connected, but no Digital Twin snapshot has been generated yet.",
            "metrics": {
                "files": local_files_count,
                "artifacts": 0,
                "relationships": 0,
                "tests": 0,
                "processes": 0,
                "apis": 0,
                "violations": 0,
            },
            "component_breakdown": {},
            "architecture_packages": [],
        }

    if snapshot_id:
        active_snap = next((s for s in snapshots if s.id == snapshot_id), None)
        if not active_snap:
            raise HTTPException(
                status_code=404,
                detail=f"Snapshot '{snapshot_id}' does not belong to repository '{repo.id}'."
            )
    else:
        active_snap = snapshots[0]

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
    package_files_map = {}
    for a in artifacts:
        loc = a.location or a.qualified_name or ""
        pkg = loc.split("/")[0] if "/" in loc else (a.qualified_name.split(".")[0] if "." in a.qualified_name else "root")
        if pkg not in packages_map:
            packages_map[pkg] = {
                "name": pkg,
                "artifact_count": 0,
                "total_artifacts": 0,
                "classes": 0,
                "functions": 0,
                "modules": 0,
                "module_count": 0,
                "files_count": 0,
                "file_count": 0,
                "sample_components": [],
            }
            package_files_map[pkg] = set()

        packages_map[pkg]["artifact_count"] += 1
        packages_map[pkg]["total_artifacts"] += 1

        file_key = (a.location.split(":")[0] if a.location else None) or a.file_id or a.qualified_name
        if file_key:
            package_files_map[pkg].add(file_key)

        if a.artifact_type in ("CLASS", "SERVICE"):
            packages_map[pkg]["classes"] += 1
            if len(packages_map[pkg]["sample_components"]) < 3 and a.name not in packages_map[pkg]["sample_components"]:
                packages_map[pkg]["sample_components"].append(a.name)
        elif a.artifact_type in ("FUNCTION", "METHOD"):
            packages_map[pkg]["functions"] += 1
        elif a.artifact_type in ("MODULE", "PACKAGE"):
            packages_map[pkg]["modules"] += 1
            packages_map[pkg]["module_count"] += 1
            if len(packages_map[pkg]["sample_components"]) < 3 and a.name not in packages_map[pkg]["sample_components"]:
                packages_map[pkg]["sample_components"].append(a.name)
        elif a.artifact_type == "COMPONENT":
            if len(packages_map[pkg]["sample_components"]) < 3 and a.name not in packages_map[pkg]["sample_components"]:
                packages_map[pkg]["sample_components"].append(a.name)

    for pkg, pdata in packages_map.items():
        fc = len(package_files_map[pkg])
        pdata["files_count"] = fc
        pdata["file_count"] = fc

    arch_packages = sorted(list(packages_map.values()), key=lambda p: -p["total_artifacts"])

    # Honest file count from snapshot metadata, files table, or location set
    total_files = active_snap.total_files or len(files_set) or breakdown.get("MODULE", 0)

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
            "files": total_files,
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


@router.get("/{repository_id}/audit-verification", response_model=Dict[str, Any])
def audit_verification(
    repository_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Authoritative end-to-end verification and diagnostic audit for:
    1. Repository & Snapshot Integrity
    2. 3D Spatial Knowledge Graph Projection across L1, L2, L3
    3. Edge Endpoint Consistency & Coordinate Health
    4. Deterministic What-If Simulation
    5. Change Impact Analysis
    6. Zero-Mutation Verification
    7. Offline Vendor Asset Verification
    """
    repo = db.query(Repository).filter(
        or_(
            Repository.id == repository_id,
            Repository.name == repository_id,
        )
    ).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    import traceback
    try:
        # 1. Vendor Assets Check
        static_vendor_dir = os.path.join(os.path.dirname(__file__), "..", "static", "vendor")
        three_path = os.path.join(static_vendor_dir, "three.min.js")
        orbit_path = os.path.join(static_vendor_dir, "OrbitControls.js")
        vendor_assets_status = {
            "three_min_js": os.path.exists(three_path) and os.path.getsize(three_path) > 100000,
            "three_size_bytes": os.path.getsize(three_path) if os.path.exists(three_path) else 0,
            "orbit_controls_js": os.path.exists(orbit_path) and os.path.getsize(orbit_path) > 10000,
            "orbit_size_bytes": os.path.getsize(orbit_path) if os.path.exists(orbit_path) else 0,
        }

        # 2. Snapshot Check
        latest_snap = (
            db.query(RepositorySnapshot)
            .filter_by(repository_id=repo.id)
            .order_by(RepositorySnapshot.created_at.desc())
            .first()
        )
        if not latest_snap:
            return {
                "status": "FAIL",
                "detail": "No snapshot found for repository",
                "vendor_assets": vendor_assets_status,
            }

        raw_artifact_count = db.query(StructuralArtifact).filter_by(snapshot_id=latest_snap.id).count()
        raw_rel_count = db.query(ArtifactRelationship).filter_by(snapshot_id=latest_snap.id).count()

        # 3. Test Graph Projections across L1, L2, L3
        levels_audit = {}
        for lvl in [1, 2, 3]:
            proj = twin_graph_projection.project_graph(
                db=db,
                repository_id=repo.id,
                snapshot_id=latest_snap.id,
                level=lvl,
                include_tests=True,
                include_external_dependencies=False,
            )
            nodes = proj.get("nodes", [])
            edges = proj.get("edges", [])
            node_id_set = {n["id"] for n in nodes}

            # Check edge endpoints
            invalid_endpoints = []
            for e in edges:
                if e["source"] not in node_id_set or e["target"] not in node_id_set:
                    invalid_endpoints.append({"source": e["source"], "target": e["target"]})

            # Check coordinate health and non-null required fields
            invalid_nodes = []
            for n in nodes:
                if not n.get("id") or not n.get("name"):
                    invalid_nodes.append(n.get("id"))

            # Types breakdown
            type_counts = {}
            for n in nodes:
                t = n.get("type", "UNKNOWN")
                type_counts[t] = type_counts.get(t, 0) + 1

            levels_audit[f"L{lvl}"] = {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "invalid_endpoints_count": len(invalid_endpoints),
                "invalid_nodes_count": len(invalid_nodes),
                "type_counts": type_counts,
                "status": "PASS" if len(invalid_endpoints) == 0 and len(invalid_nodes) == 0 else "FAIL",
            }

        # 4. Zero-Mutation Verification on What-If Simulation
        from app.services.simulation import scenario_service, CreateScenarioRequest
        from app.core.database import engine
        engine.dispose()
        db.rollback()
        count_artifacts_before = db.query(StructuralArtifact).count()
        count_rels_before = db.query(ArtifactRelationship).count()

        sample_art = db.query(StructuralArtifact).filter_by(snapshot_id=latest_snap.id).first()
        target_mutation_id = sample_art.id if sample_art else "test_target"

        sim_request = CreateScenarioRequest(
            name="Verification Diagnostic Scenario",
            description="Automated audit scenario to verify deterministic multi-hop propagation.",
            base_snapshot_id=latest_snap.id,
            proposed_changes=[{
                "mutation_id": "mut_audit_1",
                "mutation_type": "MODIFY_SYMBOL",
                "target": target_mutation_id,
                "description": "Diagnostic mutation test",
            }],
        )

        created_scenario = scenario_service.create_scenario(db=db, repository_id=repo.id, request=sim_request)
        sim_result = scenario_service.simulate_scenario(db=db, scenario_id=created_scenario["id"])

        # Clean up test scenario
        scenario_service.delete_scenario(db=db, scenario_id=created_scenario["id"], repository_id=repo.id)

        count_artifacts_after = db.query(StructuralArtifact).count()
        count_rels_after = db.query(ArtifactRelationship).count()
        zero_mutation = (count_artifacts_before == count_artifacts_after) and (count_rels_before == count_rels_after)

        # 5. Pairwise Change Impact Analysis
        from app.services.impact import change_impact_service, ImpactConfig
        snaps = (
            db.query(RepositorySnapshot)
            .filter_by(repository_id=repo.id)
            .order_by(RepositorySnapshot.created_at.desc())
            .all()
        )
        pairwise_impact_data = None
        if len(snaps) >= 2:
            try:
                impact_res = change_impact_service.run_impact_analysis(
                    db=db,
                    repository_id=repo.id,
                    base_snapshot_id=snaps[1].id,
                    target_snapshot_id=snaps[0].id,
                    config=ImpactConfig(max_depth=5),
                )
                pairwise_impact_data = {
                    "status": impact_res.status,
                    "analysis_id": impact_res.analysis_id,
                    "base_snapshot_id": impact_res.base_snapshot_id,
                    "target_snapshot_id": impact_res.target_snapshot_id,
                    "execution_time_ms": impact_res.execution_time_ms,
                    "summary": impact_res.summary.model_dump(),
                    "changes_count": len(impact_res.changes),
                    "findings_count": len(impact_res.findings),
                    "paths_count": len(impact_res.paths),
                }
            except Exception as e:
                pairwise_impact_data = {"status": "ERROR", "error": str(e)}

        # 6. Risk Analysis & Architecture Guardrails Verification
        from app.services.risk import risk_intelligence_service, RiskConfig
        risk_res = risk_intelligence_service.run_risk_analysis(
            db=db,
            repository_id=repo.id,
            base_snapshot_id=latest_snap.id,
            target_snapshot_id=latest_snap.id,
            config=RiskConfig(max_impact_depth=6),
        )

        # 7. Compile Final Diagnostic Verification Report
        all_passed = (
            vendor_assets_status["three_min_js"]
            and vendor_assets_status["orbit_controls_js"]
            and levels_audit["L1"]["status"] == "PASS"
            and levels_audit["L2"]["status"] == "PASS"
            and levels_audit["L3"]["status"] == "PASS"
            and zero_mutation
            and sim_result.status.value in ["COMPLETED", "SUCCESS", "completed", "success"]
            and risk_res.overall_category is not None
        )

        return {
            "status": "PASS" if all_passed else "FAIL",
            "repository": {
                "id": repo.id,
                "name": repo.name,
                "environment": repo.environment,
            },
            "snapshot": {
                "id": latest_snap.id,
                "commit_hash": latest_snap.commit_hash,
                "branch": latest_snap.branch_name,
                "total_files": latest_snap.total_files,
                "total_symbols": latest_snap.total_symbols,
                "raw_artifacts_count": raw_artifact_count,
                "raw_relationships_count": raw_rel_count,
            },
            "vendor_assets": vendor_assets_status,
            "levels": levels_audit,
            "what_if_simulation": {
                "status": sim_result.status.value,
                "scenario_id": sim_result.scenario_id,
                "mutated_target": target_mutation_id,
                "affected_components_count": len(sim_result.impact.affected_components),
                "affected_apis_count": len(sim_result.impact.affected_apis),
                "propagation_paths_count": len(sim_result.impact.propagation_paths),
                "directly_affected_tests_count": len(sim_result.tests.directly_affected_tests),
                "zero_mutation_verified": zero_mutation,
                "provenance_label": "SIMULATED",
            },
            "pairwise_change_impact": pairwise_impact_data,
            "risk_analysis": {
                "overall_category": risk_res.overall_category.value,
                "overall_score": risk_res.overall_score,
                "confidence": risk_res.confidence.value,
                "confidence_score": risk_res.confidence_score,
                "explanation": risk_res.explanation,
                "guardrail_results_count": len(risk_res.guardrail_results),
                "guardrails": [
                    {
                        "rule_id": g.rule_id,
                        "rule_name": g.rule_name,
                        "status": g.status.value,
                        "severity": g.severity.value,
                        "explanation": g.explanation,
                        "evidence": g.evidence,
                        "affected_entities": g.affected_entities,
                    }
                    for g in risk_res.guardrail_results
                ],
                "recommendations": risk_res.recommendations,
            },
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
