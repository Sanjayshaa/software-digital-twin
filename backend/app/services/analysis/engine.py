import hashlib
from typing import Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.entities import Repository
from app.services.discovery.scanner import RepositoryScanner, FileInventory
from app.services.discovery.engine import discovery_engine
from app.services.analysis.runtime.context import AnalysisContext
from app.services.analysis.runtime.runner import analyzer_runner
from app.services.analysis.runtime.result import AnalysisRunResult
from app.services.analysis.persistence.twin_writer import twin_writer
from app.services.acquisition import resolve_git_info


class StructuralTwinEngine:
    """Orchestrates Phase 3 Structural Intelligence & Digital Twin Builder."""

    def __init__(self):
        self._scanner = RepositoryScanner()

    def build_structural_twin(
        self,
        db: Session,
        repository_id: str,
        commit_hash: str = "HEAD",
        branch_name: str = "main",
        source_path: Optional[str] = None,
    ) -> Tuple[str, AnalysisRunResult]:
        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise ValueError(f"Repository with ID '{repository_id}' does not exist.")

        scan_path = source_path or repo.local_path
        git_info = resolve_git_info(repo.local_path)

        # 1. Resolve real Git metadata.
        # If an explicit commit SHA was specified, respect it.
        # Otherwise, if local_path is a git repo, resolve to its HEAD.
        if commit_hash and commit_hash != "HEAD" and len(commit_hash) >= 7:
            resolved_commit = commit_hash
            resolved_branch = branch_name or (git_info.branch_name if git_info.is_git_repo else "main")
        elif git_info.is_git_repo:
            resolved_commit = git_info.commit_sha
            resolved_branch = git_info.branch_name
        else:
            resolved_commit = commit_hash if commit_hash and commit_hash != "HEAD" else "no-git"
            resolved_branch = branch_name if branch_name else "no-git"

        # Update the repository record with resolved Git metadata if available
        if git_info.is_git_repo:
            repo.vcs_type = "git"
            if git_info.remote_url and not repo.remote_url:
                repo.remote_url = git_info.remote_url
            if git_info.branch_name != "no-git" and (not repo.default_branch or repo.default_branch == "main"):
                repo.default_branch = git_info.branch_name
            db.commit()

        # 2. Execute Phase 2 Discovery Brain on scan_path
        profile, plan = discovery_engine.discover(scan_path)

        # 3. Derive Snapshot ID deterministically from real commit SHA + repo
        snap_raw = f"{repo.id}::{resolved_commit}::{resolved_branch}"
        snapshot_id = f"snap_{hashlib.sha256(snap_raw.encode('utf-8')).hexdigest()[:16]}"

        # 4. Build Analysis Context
        context = AnalysisContext(
            repository_id=repo.id,
            repository_path=scan_path,
            snapshot_id=snapshot_id,
            commit_hash=resolved_commit,
            branch_name=resolved_branch,
            project_id=repo.project_id,
        )

        # 5. Scan Repository Inventory from scan_path
        inventory = self._scanner.scan(scan_path)

        # 6. Execute Analyzer Runtime
        result = analyzer_runner.run(context, plan, inventory)

        # 7. Idempotently persist Twin into PostgreSQL
        twin_writer.write_twin(
            db=db,
            repository_id=repo.id,
            snapshot_id=snapshot_id,
            inventory=inventory,
            result=result,
            commit_hash=resolved_commit,
            branch_name=resolved_branch,
        )

        return snapshot_id, result


structural_twin_engine = StructuralTwinEngine()
