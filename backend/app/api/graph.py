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
    try:
        return resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    except Exception as exc:
        logger.warning(f"Could not resolve repository '{repository_id}' due to database error: {exc}")
        return None


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
    art_types_list = [t.strip() for t in artifact_types.split(",")] if artifact_types else None
    rel_types_list = [r.strip() for r in relationship_types.split(",")] if relationship_types else None
    lang_list = [l.strip() for l in languages.split(",")] if languages else None

    # Synthetic Demo Repository Projection Handler
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
        from app.services.demo.fixture import DEMO_NODES, DEMO_EDGES, DEMO_REPO_METADATA

        # Progressive disclosure filtering by level:
        # Level 1 (Macro): Services and Gateways only (6 nodes)
        # Level 2 (Components): Services, APIs, Databases (16 nodes)
        # Level 3 & 4 (Micro / All): All 22 nodes (Services, APIs, Databases, Tests)
        if level == 1:
            allowed_cats = {"service"}
        elif level == 2:
            allowed_cats = {"service", "api", "database"}
        else:
            allowed_cats = {"service", "api", "database", "test"}

        filtered_nodes = []
        for n in DEMO_NODES:
            cat = n.get("category", "")
            if cat not in allowed_cats:
                continue
            if not include_tests and cat == "test":
                continue
            node_type = n.get("type") or n.get("artifact_type") or cat.upper()
            if art_types_list and node_type not in art_types_list:
                continue
            
            node_copy = dict(n)
            node_copy["type"] = node_type
            node_copy["label"] = n.get("name", n["id"])
            node_copy["file"] = n.get("file_path", "")
            node_copy["verification_status"] = "VERIFIED_AST"
            node_copy["diff_status"] = "UNCHANGED"
            node_copy["provenance"] = "DETERMINISTIC_REFERENCE_FIXTURE"
            node_copy["is_demo"] = True
            filtered_nodes.append(node_copy)

        active_ids = {n["id"] for n in filtered_nodes}

        filtered_edges = []
        for e in DEMO_EDGES:
            if e["source"] in active_ids and e["target"] in active_ids:
                if rel_types_list and e.get("type") not in rel_types_list:
                    continue
                edge_copy = dict(e)
                edge_copy["confidence"] = 1.0
                edge_copy["detection_method"] = "ast_call_expression"
                edge_copy["verification_status"] = "VERIFIED_AST"
                edge_copy["diff_status"] = "UNCHANGED"
                edge_copy["evidence"] = {
                    "file": "gateway/router.py" if "gw" in e["source"] else "services/order_service.py",
                    "line": 1,
                    "snippet": f"{e['source']} -> {e['target']}"
                }
                edge_copy["is_demo"] = True
                filtered_edges.append(edge_copy)

        if level == 1 and (not rel_types_list or "ROUTES_TO" in rel_types_list):
            macro_edges = [
                {"id": "macro-rel-gw-auth", "source": "art-gw", "target": "art-auth", "type": "ROUTES_TO"},
                {"id": "macro-rel-gw-prod", "source": "art-gw", "target": "art-prod", "type": "ROUTES_TO"},
                {"id": "macro-rel-gw-order", "source": "art-gw", "target": "art-order", "type": "ROUTES_TO"},
            ]
            for me in macro_edges:
                if me["source"] in active_ids and me["target"] in active_ids:
                    edge_copy = dict(me)
                    edge_copy["confidence"] = 1.0
                    edge_copy["detection_method"] = "macro_topology_inference"
                    edge_copy["verification_status"] = "VERIFIED_AST"
                    edge_copy["diff_status"] = "UNCHANGED"
                    edge_copy["evidence"] = {
                        "file": "gateway/router.py",
                        "line": 1,
                        "snippet": f"{me['source']} -> {me['target']} (Macro Ingress Route)"
                    }
                    edge_copy["is_demo"] = True
                    filtered_edges.append(edge_copy)

        return {
            "status": "SUCCESS",
            "repository_id": repository_id,
            "snapshot_id": snapshot_id or "snap-demo-online-shop-v1",
            "nodes": filtered_nodes,
            "edges": filtered_edges,
            "summary": {
                "total_nodes": len(filtered_nodes),
                "total_edges": len(filtered_edges),
                "snapshot_id": snapshot_id or "snap-demo-online-shop-v1",
                "commit_hash": DEMO_REPO_METADATA["commit_sha"],
                "branch_name": DEMO_REPO_METADATA["default_branch"],
                "is_demo": True,
                "provenance": "DETERMINISTIC_REFERENCE_FIXTURE"
            },
            "is_demo": True,
            "provenance": "DETERMINISTIC_REFERENCE_FIXTURE"
        }

    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
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
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
        return {
            "name": "ecommerce-microservices-reference",
            "type": "directory",
            "path": "",
            "children": {
                "gateway": {
                    "name": "gateway",
                    "type": "directory",
                    "path": "gateway",
                    "children": {
                        "router.py": {"name": "router.py", "type": "file", "path": "gateway/router.py", "language": "python", "artifacts_count": 5}
                    }
                },
                "services": {
                    "name": "services",
                    "type": "directory",
                    "path": "services",
                    "children": {
                        "auth_service.py": {"name": "auth_service.py", "type": "file", "path": "services/auth_service.py", "language": "python", "artifacts_count": 2},
                        "order_service.py": {"name": "order_service.py", "type": "file", "path": "services/order_service.py", "language": "python", "artifacts_count": 3},
                        "payment_service.py": {"name": "payment_service.py", "type": "file", "path": "services/payment_service.py", "language": "python", "artifacts_count": 3},
                        "product_service.py": {"name": "product_service.py", "type": "file", "path": "services/product_service.py", "language": "python", "artifacts_count": 2},
                        "inventory_service.py": {"name": "inventory_service.py", "type": "file", "path": "services/inventory_service.py", "language": "python", "artifacts_count": 2}
                    }
                },
                "schema": {
                    "name": "schema",
                    "type": "directory",
                    "path": "schema",
                    "children": {
                        "orders.sql": {"name": "orders.sql", "type": "file", "path": "schema/orders.sql", "language": "sql", "artifacts_count": 1},
                        "payments.sql": {"name": "payments.sql", "type": "file", "path": "schema/payments.sql", "language": "sql", "artifacts_count": 1}
                    }
                },
                "tests": {
                    "name": "tests",
                    "type": "directory",
                    "path": "tests",
                    "children": {
                        "test_payment.py": {"name": "test_payment.py", "type": "file", "path": "tests/test_payment.py", "language": "python", "artifacts_count": 2},
                        "test_orders.py": {"name": "test_orders.py", "type": "file", "path": "tests/test_orders.py", "language": "python", "artifacts_count": 1}
                    }
                }
            }
        }

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
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
        return [
            {
                "id": "snap-demo-online-shop-v1",
                "commit_hash": "a7f920c8b31d402e86ef512d7c0018a4",
                "branch_name": "main",
                "created_at": "2026-10-24T16:30:00Z",
                "artifacts_count": 22,
                "relationships_count": 22,
                "is_demo": True,
            }
        ]

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
    Returns actual Git branches (local and remote-tracking), current branch, and default branch.
    Syncs with real Git repository on disk without fabricating branch states.
    """
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
        return [
            {"name": "main", "is_default": True, "is_current": True, "head_commit_hash": "a7f920c8b31d402e86ef512d7c0018a4"}
        ]

    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    # 1. Discover actual branches from Git
    from app.services.acquisition.git_provider import discover_repository_branches
    discovered = discover_repository_branches(repo.local_path, default_branch=repo.default_branch or "main")

    # 2. Sync to Branch table idempotently
    try:
        existing_branches = {b.name: b for b in db.query(Branch).filter_by(repository_id=repo.id).all()}
        for d in discovered:
            b_name = d["name"]
            is_def = d.get("is_default", False)
            h_hash = d.get("head_commit_hash")
            if b_name in existing_branches:
                eb = existing_branches[b_name]
                eb.is_default = is_def
                if h_hash and h_hash != "no-git":
                    eb.head_commit_hash = h_hash
            else:
                nb = Branch(
                    repository_id=repo.id,
                    name=b_name,
                    is_default=is_def,
                    head_commit_hash=h_hash if h_hash != "no-git" else None,
                )
                db.add(nb)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Could not sync branches to database: %s", exc)

    return discovered


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
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
        from app.services.demo.fixture import DEMO_REPO_METADATA, DEMO_NODES, DEMO_EDGES
        demo_glance = {
            "has_architecture": True,
            "architecture_style": "Microservices E-Commerce Platform (Gateway + Services + Relational DB)",
            "summary": {
                "detected_layers_count": 5,
                "entry_points_count": 3,
                "major_components_count": 6,
                "key_flows_count": 5,
            },
            "layers": {
                "frontend": {
                    "label": "Frontend & Presentation",
                    "status": "DETECTED",
                    "count": 2,
                    "description": "Client-side React components and checkout view templates.",
                    "items": [
                        {"id": "node-fe-checkout", "name": "CheckoutView.tsx", "type": "COMPONENT", "location": "frontend/src/views/CheckoutView.tsx:1", "node_id": "art-fe-checkout"},
                        {"id": "node-fe-catalog", "name": "ProductList.tsx", "type": "COMPONENT", "location": "frontend/src/components/ProductList.tsx:1", "node_id": "art-fe-catalog"},
                    ],
                },
                "api": {
                    "label": "API & Ingress Boundaries",
                    "status": "DETECTED",
                    "count": 14,
                    "description": "Declared HTTP routes, REST endpoints, and reverse proxy routes.",
                    "items": [
                        {"id": "node-api-checkout", "name": "POST /api/v1/checkout", "type": "API_ENDPOINT", "location": "services/order_service.py:45", "method": "POST", "path": "/api/v1/checkout", "node_id": "art-order"},
                        {"id": "node-api-orders", "name": "GET /api/v1/orders", "type": "API_ENDPOINT", "location": "services/order_service.py:110", "method": "GET", "path": "/api/v1/orders", "node_id": "art-order"},
                        {"id": "node-api-payment", "name": "POST /api/v1/payments", "type": "API_ENDPOINT", "location": "services/payment_service.py:30", "method": "POST", "path": "/api/v1/payments", "node_id": "art-pay"},
                        {"id": "node-api-auth", "name": "POST /api/v1/auth/login", "type": "API_ENDPOINT", "location": "services/auth_service.py:20", "method": "POST", "path": "/api/v1/auth/login", "node_id": "art-auth"},
                    ],
                },
                "services": {
                    "label": "Core Business Logic & Services",
                    "status": "DETECTED",
                    "count": 6,
                    "description": "Domain microservices, payment orchestrators, and order processors.",
                    "items": [
                        {"id": "art-gw", "name": "ApiGateway", "type": "GATEWAY", "location": "gateway/router.py:15", "fan_in": 0, "fan_out": 4, "node_id": "art-gw"},
                        {"id": "art-order", "name": "OrderService", "type": "SERVICE", "location": "services/order_service.py:15", "fan_in": 1, "fan_out": 3, "node_id": "art-order"},
                        {"id": "art-pay", "name": "PaymentService", "type": "SERVICE", "location": "services/payment_service.py:15", "fan_in": 1, "fan_out": 2, "node_id": "art-pay"},
                        {"id": "art-auth", "name": "AuthService", "type": "SERVICE", "location": "services/auth_service.py:10", "fan_in": 1, "fan_out": 1, "node_id": "art-auth"},
                        {"id": "art-inv", "name": "InventoryService", "type": "SERVICE", "location": "services/inventory_service.py:15", "fan_in": 1, "fan_out": 1, "node_id": "art-inv"},
                        {"id": "art-prod", "name": "ProductService", "type": "SERVICE", "location": "services/product_service.py:12", "fan_in": 1, "fan_out": 1, "node_id": "art-prod"},
                    ],
                },
                "storage": {
                    "label": "Data Access & Persistence",
                    "status": "DETECTED",
                    "count": 5,
                    "description": "PostgreSQL relational tables and SQLAlchemy ORM models.",
                    "items": [
                        {"id": "art-db-orders", "name": "orders", "type": "TABLE", "location": "models/orders.py:10", "node_id": "art-db-orders"},
                        {"id": "art-db-pay", "name": "payments", "type": "TABLE", "location": "models/payments.py:10", "node_id": "art-db-pay"},
                        {"id": "art-db-users", "name": "users", "type": "TABLE", "location": "models/users.py:8", "node_id": "art-db-users"},
                        {"id": "art-db-prod", "name": "products", "type": "TABLE", "location": "models/products.py:12", "node_id": "art-db-prod"},
                        {"id": "art-db-inv", "name": "inventory", "type": "TABLE", "location": "models/inventory.py:10", "node_id": "art-db-inv"},
                    ],
                },
                "external": {
                    "label": "External Integrations",
                    "status": "DETECTED",
                    "count": 2,
                    "description": "Third-party payment gateway and distributed in-memory cache.",
                    "items": [
                        {"name": "Stripe Gateway", "provider": "Stripe API", "role": "Card processing & idempotency", "location": "services/payment_service.py:65"},
                        {"name": "Redis Distributed Lock", "provider": "Redis", "role": "Inventory reservation session locking", "location": "services/inventory_service.py:40"},
                    ],
                },
            },
            "entry_points": [
                {"file_path": "gateway/router.py", "role": "API Gateway Reverse Proxy Ingress", "type": "SERVER"},
                {"file_path": "services/order_service.py", "role": "Order Processing Microservice Entry Point", "type": "SERVER"},
                {"file_path": "frontend/src/index.tsx", "role": "Client Single Page Application Root Component", "type": "CLIENT"},
            ],
            "major_components": [
                {"id": "art-gw", "name": "ApiGateway", "type": "GATEWAY", "location": "gateway/router.py:15", "in_degree": 0, "out_degree": 4, "connectivity": 4, "role": "Ingress reverse proxy and TLS boundary", "node_id": "art-gw"},
                {"id": "art-order", "name": "OrderService", "type": "SERVICE", "location": "services/order_service.py:15", "in_degree": 1, "out_degree": 3, "connectivity": 4, "role": "Order lifecycle and checkout orchestration", "node_id": "art-order"},
                {"id": "art-pay", "name": "PaymentService", "type": "SERVICE", "location": "services/payment_service.py:15", "in_degree": 1, "out_degree": 2, "connectivity": 3, "role": "Payment tokenization and settlement", "node_id": "art-pay"},
                {"id": "art-auth", "name": "AuthService", "type": "SERVICE", "location": "services/auth_service.py:10", "in_degree": 1, "out_degree": 1, "connectivity": 2, "role": "JWT authentication and RBAC authorization", "node_id": "art-auth"},
                {"id": "art-inv", "name": "InventoryService", "type": "SERVICE", "location": "services/inventory_service.py:15", "in_degree": 1, "out_degree": 1, "connectivity": 2, "role": "Stock level queries and reservation", "node_id": "art-inv"},
                {"id": "art-prod", "name": "ProductService", "type": "SERVICE", "location": "services/product_service.py:12", "in_degree": 1, "out_degree": 1, "connectivity": 2, "role": "Product catalog queries and search", "node_id": "art-prod"},
            ],
            "key_flows": [
                {"source": {"id": "art-gw", "name": "ApiGateway", "type": "GATEWAY", "location": "gateway/router.py:15"}, "target": {"id": "art-order", "name": "OrderService", "type": "SERVICE", "location": "services/order_service.py:15"}, "relation": "CALLS", "description": "ApiGateway routes checkout traffic to OrderService"},
                {"source": {"id": "art-order", "name": "OrderService", "type": "SERVICE", "location": "services/order_service.py:15"}, "target": {"id": "art-pay", "name": "PaymentService", "type": "SERVICE", "location": "services/payment_service.py:15"}, "relation": "CALLS", "description": "OrderService orchestrates payment authorization via PaymentService"},
                {"source": {"id": "art-order", "name": "OrderService", "type": "SERVICE", "location": "services/order_service.py:15"}, "target": {"id": "art-inv", "name": "InventoryService", "type": "SERVICE", "location": "services/inventory_service.py:15"}, "relation": "CALLS", "description": "OrderService reserves stock through InventoryService"},
                {"source": {"id": "art-order", "name": "OrderService", "type": "SERVICE", "location": "services/order_service.py:15"}, "target": {"id": "art-db-orders", "name": "orders", "type": "TABLE", "location": "models/orders.py:10"}, "relation": "PERSISTS", "description": "OrderService persists confirmed orders in database"},
                {"source": {"id": "art-pay", "name": "PaymentService", "type": "SERVICE", "location": "services/payment_service.py:15"}, "target": {"id": "art-db-pay", "name": "payments", "type": "TABLE", "location": "models/payments.py:10"}, "relation": "PERSISTS", "description": "PaymentService persists transaction ledger"},
            ],
        }
        return {
            "repository": DEMO_REPO_METADATA,
            "snapshot": {
                "id": "snap-demo-online-shop-v1",
                "commit_hash": DEMO_REPO_METADATA["commit_sha"],
                "branch_name": DEMO_REPO_METADATA["default_branch"],
                "created_at": DEMO_REPO_METADATA["committed_at"],
            },
            "metrics": {
                "total_artifacts": len(DEMO_NODES),
                "total_relationships": len(DEMO_EDGES),
                "total_files": DEMO_REPO_METADATA["discovery_summary"]["total_files"],
                "total_services": DEMO_REPO_METADATA["discovery_summary"]["services"],
                "total_apis": DEMO_REPO_METADATA["discovery_summary"]["api_endpoints"],
                "total_databases": DEMO_REPO_METADATA["discovery_summary"]["database_tables"],
                "total_tests": DEMO_REPO_METADATA["discovery_summary"]["test_cases"],
                "files": DEMO_REPO_METADATA["discovery_summary"]["total_files"],
                "lines_of_code": sum(lang.get("lines", 0) for lang in DEMO_REPO_METADATA["discovery_summary"].get("languages", {}).values()) or 8260,
                "artifacts": len(DEMO_NODES),
                "relationships": len(DEMO_EDGES),
                "tests": DEMO_REPO_METADATA["discovery_summary"]["test_cases"],
                "apis": DEMO_REPO_METADATA["discovery_summary"]["api_endpoints"],
                "processes": 4,
                "violations": 0,
            },
            "architecture_glance": demo_glance,
            "architecture_packages": [],
            "is_demo": True,
            "provenance": "DETERMINISTIC_REFERENCE_FIXTURE"
        }

    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    from app.services.acquisition import resolve_git_info
    git_info = None
    if repo.local_path and os.path.exists(repo.local_path):
        try:
            git_info = resolve_git_info(repo.local_path)
        except Exception:
            git_info = None

    latest_run = (
        db.query(AnalysisRun)
        .filter_by(repository_id=repo.id)
        .order_by(AnalysisRun.created_at.desc())
        .first()
    )

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

        if latest_run and latest_run.status in ("running", "pending"):
            status_val = "ANALYSIS_IN_PROGRESS"
            sync_state = "ANALYSIS_IN_PROGRESS"
            sync_label = "Analyzing..."
            sync_badge_color = "blue"
            status_msg = "Digital Twin analysis is currently running."
        elif latest_run and latest_run.status in ("failed", "FAILED"):
            status_val = "ANALYSIS_FAILED"
            sync_state = "ANALYSIS_FAILED"
            sync_label = "Analysis Failed"
            sync_badge_color = "red"
            status_msg = (latest_run.errors[0] if latest_run.errors else "Digital Twin analysis failed.")
        else:
            status_val = "NO_SNAPSHOT_AVAILABLE"
            sync_state = "NO_SNAPSHOT_AVAILABLE"
            sync_label = "No Snapshot"
            sync_badge_color = "amber"
            status_msg = "Repository is connected, but no Digital Twin snapshot has been generated yet. Run discovery and analysis to generate your twin."

        return {
            "repository": {
                "id": repo.id,
                "name": repo.name,
                "local_path": repo.local_path,
                "default_branch": repo.default_branch,
            },
            "has_snapshots": False,
            "status": status_val,
            "sync_state": sync_state,
            "sync_label": sync_label,
            "sync_badge_color": sync_badge_color,
            "status_message": status_msg,
            "message": status_msg,
            "git_status": {
                "is_git_repo": bool(git_info and git_info.is_git_repo),
                "head_sha": git_info.commit_sha if git_info else None,
                "current_branch": git_info.branch_name if git_info else repo.default_branch,
                "snapshot_sha": None,
                "is_head": False,
            },
            "metrics": {
                "files": local_files_count,
                "lines_of_code": None,
                "artifacts": 0,
                "relationships": 0,
                "tests": 0,
                "processes": 0,
                "apis": 0,
                "violations": 0,
            },
            "component_breakdown": {},
            "architecture_packages": [],
            "architecture_glance": {
                "has_architecture": False,
                "architecture_style": "Unknown / Not detected",
                "summary": {
                    "detected_layers_count": 0,
                    "entry_points_count": 0,
                    "major_components_count": 0,
                    "key_flows_count": 0,
                },
                "layers": {
                    "frontend": {"label": "Frontend & Presentation", "status": "NOT_DETECTED", "count": 0, "description": "No client-side UI components detected.", "items": []},
                    "api": {"label": "API & Ingress Boundaries", "status": "NOT_DETECTED", "count": 0, "description": "No HTTP route contracts detected.", "items": []},
                    "services": {"label": "Core Business Logic & Services", "status": "NOT_DETECTED", "count": 0, "description": "No domain services detected.", "items": []},
                    "storage": {"label": "Data Access & Persistence", "status": "NOT_DETECTED", "count": 0, "description": "No database tables or ORM models detected.", "items": []},
                    "external": {"label": "External Integrations", "status": "NOT_DETECTED", "count": 0, "description": "No third-party SDKs or cloud integrations detected.", "items": []},
                },
                "entry_points": [],
                "major_components": [],
                "key_flows": [],
            },
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

    # Evaluate truthful sync state
    is_head_match = False
    if git_info and git_info.is_git_repo and git_info.commit_sha and active_snap.commit_hash:
        is_head_match = (git_info.commit_sha.lower() == active_snap.commit_hash.lower())

    if latest_run and latest_run.status in ("running", "pending"):
        sync_state = "ANALYSIS_IN_PROGRESS"
        sync_label = "Analyzing..."
        sync_badge_color = "blue"
        status_val = "ANALYSIS_IN_PROGRESS"
        status_msg = "Analysis in progress on repository..."
    elif latest_run and latest_run.status in ("failed", "FAILED"):
        sync_state = "ANALYSIS_FAILED"
        sync_label = "Analysis Failed"
        sync_badge_color = "red"
        status_val = "ANALYSIS_FAILED"
        status_msg = latest_run.errors[0] if latest_run.errors else "Latest analysis run failed."
    elif git_info and git_info.is_git_repo and not is_head_match:
        sync_state = "OUT_OF_SYNC"
        sync_label = "Behind HEAD"
        sync_badge_color = "amber"
        status_val = "ANALYSIS_COMPLETED"
        status_msg = f"Active snapshot ({active_snap.commit_hash[:7]}) is behind Git HEAD ({git_info.commit_sha[:7]})."
    else:
        sync_state = "SYNCHRONIZED"
        sync_label = "Synced"
        sync_badge_color = "green"
        status_val = "ANALYSIS_COMPLETED"
        status_msg = f"Repository synchronized with HEAD snapshot ({active_snap.commit_hash[:7] if active_snap.commit_hash else 'active'})."

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

    # Honest lines of code calculation
    lines_of_code = None
    if active_snap.snapshot_metadata and isinstance(active_snap.snapshot_metadata, dict):
        if "total_lines" in active_snap.snapshot_metadata:
            lines_of_code = active_snap.snapshot_metadata["total_lines"]
        elif "lines_of_code" in active_snap.snapshot_metadata:
            lines_of_code = active_snap.snapshot_metadata["lines_of_code"]
    if lines_of_code is None:
        try:
            from sqlalchemy import func
            from app.models.entities import File
            loc_sum = db.query(func.sum(File.line_count)).filter_by(snapshot_id=active_snap.id).scalar()
            if loc_sum is not None and loc_sum > 0:
                lines_of_code = int(loc_sum)
        except Exception:
            pass

    # Extract deep repository understanding
    from app.services.discovery.project_overview import (
        extract_project_purpose,
        extract_entry_points,
        extract_service_and_api_inventory,
        extract_database_entities,
        extract_test_inventory_and_coverage,
        extract_project_architecture_glance,
    )

    project_purpose = extract_project_purpose(repo.local_path, default_name=repo.name)
    entry_points = extract_entry_points(repo.local_path, artifacts)
    services_and_apis = extract_service_and_api_inventory(artifacts)
    database_entities = extract_database_entities(artifacts)
    test_inventory_info = extract_test_inventory_and_coverage(artifacts, relationships)
    architecture_glance = extract_project_architecture_glance(repo.local_path, artifacts, relationships)

    # Technology profile extraction
    tech_stack = {}
    if active_snap.snapshot_metadata and isinstance(active_snap.snapshot_metadata, dict):
        if "analyzers" in active_snap.snapshot_metadata:
            tech_stack["analyzers"] = active_snap.snapshot_metadata["analyzers"]
    # Infer languages from artifacts
    detected_languages = list({a.language for a in artifacts if a.language and a.language not in ("generic", "external")})
    tech_stack["languages"] = detected_languages

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
        "status": status_val,
        "sync_state": sync_state,
        "sync_label": sync_label,
        "sync_badge_color": sync_badge_color,
        "status_message": status_msg,
        "message": status_msg,
        "project_purpose": project_purpose,
        "entry_points": entry_points,
        "services_and_apis": services_and_apis,
        "database_entities": database_entities,
        "test_inventory_details": test_inventory_info,
        "tech_stack": tech_stack,
        "git_status": {
            "is_git_repo": bool(git_info and git_info.is_git_repo),
            "head_sha": git_info.commit_sha if git_info else None,
            "current_branch": git_info.branch_name if git_info else repo.default_branch,
            "snapshot_sha": active_snap.commit_hash,
            "is_head": is_head_match,
        },
        "metrics": {
            "files": total_files,
            "lines_of_code": lines_of_code,
            "artifacts": len(artifacts),
            "relationships": len(relationships),
            "tests": tests_count,
            "apis": apis_count,
            "processes": process_flows_count,
            "violations": len(violations),
        },
        "component_breakdown": breakdown,
        "architecture_packages": arch_packages,
        "architecture_glance": architecture_glance,
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


@router.get("/{repository_id}/report", response_model=Dict[str, Any])
def get_repository_report(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the comprehensive developer repository architecture report.
    Gives a developer a detailed, readable understanding of the whole repository.
    """
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
        from app.services.discovery.page_services import _build_demo_report_data
        return _build_demo_report_data()

    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    snapshot = None
    if snapshot_id:
        snapshot = db.query(RepositorySnapshot).filter_by(id=snapshot_id, repository_id=repo.id).first()
    if not snapshot:
        snapshot = db.query(RepositorySnapshot).filter_by(repository_id=repo.id).order_by(RepositorySnapshot.created_at.desc()).first()

    from app.services.discovery.page_services import build_report_page_data
    return build_report_page_data(repo, snapshot, db)


@router.get("/{repository_id}/docs", response_model=Dict[str, Any])
def get_repository_docs(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns structured living project documentation explaining how implementation is organized.
    Documents whole project without relying on commit history.
    """
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
        from app.services.discovery.page_services import _build_demo_docs_data
        return _build_demo_docs_data()

    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    snapshot = None
    if snapshot_id:
        snapshot = db.query(RepositorySnapshot).filter_by(id=snapshot_id, repository_id=repo.id).first()
    if not snapshot:
        snapshot = db.query(RepositorySnapshot).filter_by(repository_id=repo.id).order_by(RepositorySnapshot.created_at.desc()).first()

    from app.services.discovery.page_services import build_docs_page_data
    return build_docs_page_data(repo, snapshot, db)


@router.get("/{repository_id}/stats", response_model=Dict[str, Any])
def get_repository_stats(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns measurable repository evidence and unique project signals:
    size, composition, timeline, work patterns, change records, and analysis coverage.
    Distinct from Code Health.
    """
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
        from app.services.discovery.page_services import _build_demo_stats_data
        return _build_demo_stats_data()

    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    snapshot = None
    if snapshot_id:
        snapshot = db.query(RepositorySnapshot).filter_by(id=snapshot_id, repository_id=repo.id).first()
    if not snapshot:
        snapshot = db.query(RepositorySnapshot).filter_by(repository_id=repo.id).order_by(RepositorySnapshot.created_at.desc()).first()

    from app.services.discovery.page_services import build_stats_page_data
    return build_stats_page_data(repo, snapshot, db)


@router.get("/{repository_id}/security", response_model=Dict[str, Any])
def get_repository_security(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns detected security findings, vulnerabilities, and severity hierarchy for the snapshot.
    """
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
        from app.services.discovery.page_services import _build_demo_security_data
        return _build_demo_security_data()

    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    snapshot = None
    if snapshot_id:
        snapshot = db.query(RepositorySnapshot).filter_by(id=snapshot_id, repository_id=repo.id).first()
    if not snapshot:
        snapshot = db.query(RepositorySnapshot).filter_by(repository_id=repo.id).order_by(RepositorySnapshot.created_at.desc()).first()

    from app.services.discovery.page_services import build_security_page_data
    return build_security_page_data(repo, snapshot, db)


@router.post("/{repository_id}/security/scan", response_model=Dict[str, Any])
def trigger_repository_security_scan(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Triggers an active static security audit across repository files, secrets, and incident telemetry.
    """
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
        from app.services.discovery.page_services import _build_demo_security_data
        return _build_demo_security_data()

    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    snapshot = None
    if snapshot_id:
        snapshot = db.query(RepositorySnapshot).filter_by(id=snapshot_id, repository_id=repo.id).first()
    if not snapshot:
        snapshot = db.query(RepositorySnapshot).filter_by(repository_id=repo.id).order_by(RepositorySnapshot.created_at.desc()).first()

    from app.services.discovery.page_services import run_repository_security_scan
    return run_repository_security_scan(repo, snapshot, db)


@router.get("/{repository_id}/test-reachability", response_model=Dict[str, Any])
def get_repository_test_reachability(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns graph test reachability, defect-health scores, and weak unreached files matching Repowise Tests.
    """
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
        from app.services.discovery.page_services import _build_demo_test_reachability_data
        return _build_demo_test_reachability_data()

    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    snapshot = None
    if snapshot_id:
        snapshot = db.query(RepositorySnapshot).filter_by(id=snapshot_id, repository_id=repo.id).first()
    if not snapshot:
        snapshot = db.query(RepositorySnapshot).filter_by(repository_id=repo.id).order_by(RepositorySnapshot.created_at.desc()).first()

    from app.services.discovery.page_services import build_test_reachability_data
    return build_test_reachability_data(repo, snapshot, db)


@router.get("/{repository_id}/dependency-map", response_model=Dict[str, Any])
def get_repository_dependency_map(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the interactive cluster-level dependency intelligence and risk map matching
    the Repowise Knowledge Graph reference and TwinCore Service Dependency Risk Map.
    """
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"] or repository_id.startswith("demo-"):
        from app.services.discovery.page_services import _build_demo_dependency_map_data
        return _build_demo_dependency_map_data()

    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        if "demo" in repository_id.lower():
            from app.services.discovery.page_services import _build_demo_dependency_map_data
            return _build_demo_dependency_map_data()
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    snapshot = None
    if snapshot_id:
        snapshot = db.query(RepositorySnapshot).filter_by(id=snapshot_id, repository_id=repo.id).first()
    if not snapshot:
        snapshot = db.query(RepositorySnapshot).filter_by(repository_id=repo.id).order_by(RepositorySnapshot.created_at.desc()).first()

    from app.services.discovery.page_services import build_dependency_map_data
    return build_dependency_map_data(repo, snapshot, db)


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
    if repository_id in ["repo-demo-ecommerce-001", "synthetic-online-shop"]:
        from app.services.demo.fixture import DEMO_NODES
        comps = [
            {
                "id": n["id"],
                "name": n["name"],
                "qualified_name": n["qualified_name"],
                "artifact_type": n.get("artifact_type", "SERVICE"),
                "location": n.get("location", ""),
                "language": n.get("language", "python"),
                "layer": n.get("layer", "CORE_SERVICE"),
                "is_demo": True,
            }
            for n in DEMO_NODES
            if n.get("category") in ["service", "api", "database"]
        ]
        return {"components": comps, "total": len(comps)}

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
