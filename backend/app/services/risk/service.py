"""
Phase 7 — Risk Intelligence Service.
Coordinates risk analysis runs, persistence into PostgreSQL entities (AnalysisRun & RiskAssessment),
and historical retrieval.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder

from app.models.entities import Repository, RepositorySnapshot, AnalysisRun, RiskAssessment
from app.services.risk.models import (
    RiskConfig,
    RiskAssessmentResult,
    RiskCategory,
    ConfidenceLevel,
    GuardrailResult,
    RiskFactorItem,
)
from app.services.risk.engine import risk_intelligence_engine, RiskIntelligenceEngine


class RiskIntelligenceService:
    """
    High-level orchestrator for Risk Intelligence & Architecture Guardrail evaluation.
    """

    def __init__(self, engine: Optional[RiskIntelligenceEngine] = None):
        self.engine = engine or risk_intelligence_engine

    def run_risk_analysis(
        self,
        db: Session,
        repository_id: str,
        base_snapshot_id: str,
        target_snapshot_id: str,
        config: Optional[RiskConfig] = None,
    ) -> RiskAssessmentResult:
        """
        Validates repository and snapshots, runs deterministic risk analysis, and persists findings.
        """
        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise ValueError(f"Repository '{repository_id}' not found.")

        base_snap = db.query(RepositorySnapshot).filter_by(id=base_snapshot_id).first()
        if not base_snap:
            raise ValueError(f"Base snapshot '{base_snapshot_id}' not found.")
        if base_snap.repository_id != repository_id:
            raise ValueError(f"Base snapshot '{base_snapshot_id}' does not belong to repository '{repository_id}'.")

        target_snap = db.query(RepositorySnapshot).filter_by(id=target_snapshot_id).first()
        if not target_snap:
            raise ValueError(f"Target snapshot '{target_snapshot_id}' not found.")
        if target_snap.repository_id != repository_id:
            raise ValueError(f"Target snapshot '{target_snapshot_id}' does not belong to repository '{repository_id}'.")

        result = self.engine.assess_risk(
            db=db,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
            config=config,
        )

        # Persist AnalysisRun record
        analysis_run = AnalysisRun(
            id=result.analysis_id,
            project_id=repo.project_id,
            repository_id=repo.id,
            snapshot_id=target_snapshot_id,
            run_type="risk_analysis",
            status="COMPLETED",
            files_scanned=len(result.affected_components),
            artifacts_created=len(result.risk_factors),
            relationships_created=len(result.guardrail_results),
            summary=jsonable_encoder(result),
            created_at=result.created_at,
            completed_at=datetime.utcnow(),
        )
        db.add(analysis_run)

        # Persist RiskAssessment entity
        factor_summary = {
            f.factor_id.value if hasattr(f.factor_id, "value") else str(f.factor_id): {
                "score": f.score,
                "severity": f.severity,
                "status": f.status,
            }
            for f in result.risk_factors
        }
        risk_entity = RiskAssessment(
            id=f"ra_{result.analysis_id[5:]}" if len(result.analysis_id) > 5 else result.analysis_id,
            project_id=repo.project_id,
            change_id=None,
            analysis_run_id=analysis_run.id,
            overall_score=result.overall_score,
            factor_breakdown=factor_summary,
            severity_level=result.overall_category.value,
            confidence=result.confidence_score,
            created_at=result.created_at,
        )
        db.add(risk_entity)
        db.commit()

        return result

    def get_risk_analysis(
        self,
        db: Session,
        repository_id: str,
        analysis_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves stored Risk Assessment result by analysis ID.
        """
        run = (
            db.query(AnalysisRun)
            .filter_by(id=analysis_id, repository_id=repository_id, run_type="risk_analysis")
            .first()
        )
        if not run:
            return None
        return run.summary


risk_intelligence_service = RiskIntelligenceService()
