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
    ) -> Tuple[str, AnalysisRunResult]:
        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise ValueError(f"Repository with ID '{repository_id}' does not exist.")

        # 1. Execute Phase 2 Discovery Brain
        profile, plan = discovery_engine.discover(repo.local_path)

        # 2. Derive Snapshot ID deterministically from commit/repo
        clean_commit = commit_hash.strip() if commit_hash else "head"
        snap_raw = f"{repo.id}::{clean_commit}::{branch_name}"
        snapshot_id = f"snap_{hashlib.sha256(snap_raw.encode('utf-8')).hexdigest()[:16]}"

        # 3. Build Analysis Context
        context = AnalysisContext(
            repository_id=repo.id,
            repository_path=repo.local_path,
            snapshot_id=snapshot_id,
            commit_hash=commit_hash,
            branch_name=branch_name,
            project_id=repo.project_id,
        )

        # 4. Scan Repository Inventory
        inventory = self._scanner.scan(repo.local_path)

        # 5. Execute Analyzer Runtime
        result = analyzer_runner.run(context, plan, inventory)

        # 6. Idempotently persist Twin into PostgreSQL
        twin_writer.write_twin(
            db=db,
            repository_id=repo.id,
            snapshot_id=snapshot_id,
            inventory=inventory,
            result=result,
            commit_hash=commit_hash,
            branch_name=branch_name,
        )

        # 7. Continuous Architecture Drift Detection
        try:
            from app.services.architecture.drift_detector import architecture_drift_detector
            arch_report = architecture_drift_detector.detect_drift_for_snapshot(
                db=db,
                repository_id=repo.id,
                snapshot_id=snapshot_id,
                persist=True,
            )
            result.summary["architecture_conformance"] = arch_report.conformance_percentage
            result.summary["architecture_drifts_count"] = arch_report.violations_count
        except Exception as exc:
            result.warnings.append(f"Architecture drift detection note: {str(exc)}")

        return snapshot_id, result


structural_twin_engine = StructuralTwinEngine()
