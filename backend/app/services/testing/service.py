"""
Phase 6 — Test Impact Service.
Orchestrates test impact analysis execution, persistence in AnalysisRun,
and retrieval of historical results.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder

from app.models.entities import Repository, RepositorySnapshot, AnalysisRun
from app.services.testing.models import (
    TestImpactConfig,
    TestImpactResult,
    TestImpactSummary,
    TestImpactItem,
    UnknownCoverageItem,
)
from app.services.testing.engine import test_impact_engine, TestImpactEngine


class TestImpactService:
    """
    High-level service orchestrating Test Impact Intelligence.
    """

    def __init__(self, engine: Optional[TestImpactEngine] = None):
        self.engine = engine or test_impact_engine

    def run_test_impact_analysis(
        self,
        db: Session,
        repository_id: str,
        base_snapshot_id: str,
        target_snapshot_id: str,
        config: Optional[TestImpactConfig] = None,
    ) -> TestImpactResult:
        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise ValueError(f"Repository '{repository_id}' not found.")
        from sqlalchemy import or_

        base_snap = db.query(RepositorySnapshot).filter(
            RepositorySnapshot.repository_id == repository_id,
            or_(
                RepositorySnapshot.id == base_snapshot_id,
                RepositorySnapshot.commit_hash == base_snapshot_id,
                RepositorySnapshot.commit_hash.startswith(base_snapshot_id),
            ),
        ).first()
        if not base_snap:
            raise ValueError(f"Base snapshot or commit '{base_snapshot_id}' not found.")

        target_snap = db.query(RepositorySnapshot).filter(
            RepositorySnapshot.repository_id == repository_id,
            or_(
                RepositorySnapshot.id == target_snapshot_id,
                RepositorySnapshot.commit_hash == target_snapshot_id,
                RepositorySnapshot.commit_hash.startswith(target_snapshot_id),
            ),
        ).first()
        if not target_snap:
            raise ValueError(f"Target snapshot or commit '{target_snapshot_id}' not found.")

        canonical_base_id = base_snap.id
        canonical_target_id = target_snap.id

        # Execute deterministic test impact engine
        result = self.engine.compute_test_impact(
            db=db,
            repository_id=repository_id,
            base_snapshot_id=canonical_base_id,
            target_snapshot_id=canonical_target_id,
            config=config,
        )

        # Persist AnalysisRun record
        analysis_run = AnalysisRun(
            id=result.analysis_id,
            project_id=repo.project_id,
            repository_id=repo.id,
            snapshot_id=target_snapshot_id,
            run_type="test_impact",
            status="COMPLETED",
            analyzer_names=["test_impact_engine"],
            summary={
                "base_snapshot_id": base_snapshot_id,
                "target_snapshot_id": target_snapshot_id,
                "summary": jsonable_encoder(result.summary),
                "affected_tests_count": len(result.affected_tests),
                "directly_affected_count": result.summary.directly_affected_count,
                "indirectly_affected_count": result.summary.indirectly_affected_count,
                "unaffected_count": result.summary.unaffected_count,
                "unknown_coverage_count": result.summary.unknown_coverage_count,
                "execution_time_ms": result.execution_time_ms,
            },
            artifacts_created=len(result.affected_tests),
            errors=[],
            completed_at=datetime.utcnow(),
        )
        db.add(analysis_run)
        db.commit()

        return result

    def get_test_impact_result(
        self,
        db: Session,
        repository_id: str,
        analysis_id: str,
    ) -> Optional[Dict[str, Any]]:
        run = (
            db.query(AnalysisRun)
            .filter_by(id=analysis_id, repository_id=repository_id, run_type="test_impact")
            .first()
        )
        if not run:
            return None

        # If summary contains full payload
        base_id = run.summary.get("base_snapshot_id") if run.summary else None
        target_id = run.snapshot_id

        if base_id and target_id:
            # Recompute or retrieve
            res = self.engine.compute_test_impact(
                db=db,
                repository_id=repository_id,
                base_snapshot_id=base_id,
                target_snapshot_id=target_id,
            )
            res.analysis_id = run.id
            res.created_at = run.completed_at or run.created_at
            return jsonable_encoder(res)

        return run.summary


test_impact_service = TestImpactService()
