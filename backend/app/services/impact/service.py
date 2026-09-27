"""
Phase 4 — Change Impact Service.
High-level service orchestrating change impact execution, persistence in AnalysisRun,
result retrieval, and visual graph projection.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder

from app.models.entities import Repository, RepositorySnapshot, AnalysisRun
from app.services.impact.models import (
    ImpactConfig,
    ImpactResult,
    ImpactFinding,
    ImpactSummary,
    ChangeItem,
    ImpactPath,
)
from app.services.impact.analyzer import change_impact_analyzer, ChangeImpactAnalyzer


class ChangeImpactService:
    """
    Service layer for Change Impact / Blast Radius queries, persistence, and projections.
    """

    def __init__(self, analyzer: Optional[ChangeImpactAnalyzer] = None):
        self.analyzer = analyzer or change_impact_analyzer

    def run_impact_analysis(
        self,
        db: Session,
        repository_id: str,
        base_snapshot_id: str,
        target_snapshot_id: str,
        config: Optional[ImpactConfig] = None,
    ) -> ImpactResult:
        """
        Validates snapshots, runs deterministic impact analysis, and persists AnalysisRun trace.
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

        # Execute deterministic impact analysis
        result = self.analyzer.analyze(
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
            run_type="change_impact",
            status="COMPLETED",
            files_scanned=len(result.changes),
            artifacts_created=len(result.findings),
            relationships_created=len(result.paths),
            summary=jsonable_encoder(result),
            created_at=result.created_at,
            completed_at=datetime.utcnow(),
        )
        db.add(analysis_run)
        db.commit()

        return result

    def get_impact_analysis(
        self,
        db: Session,
        repository_id: str,
        analysis_id: str,
    ) -> Optional[ImpactResult]:
        """
        Retrieves a previously computed impact analysis from AnalysisRun.
        """
        run = (
            db.query(AnalysisRun)
            .filter_by(id=analysis_id, repository_id=repository_id, run_type="change_impact")
            .first()
        )
        if not run or not run.summary:
            return None

        return ImpactResult(**run.summary)

    def get_impact_graph(
        self,
        db: Session,
        repository_id: str,
        analysis_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Projects an impact graph containing only changed nodes, directly/indirectly
        affected nodes, and the causal connecting edges.
        """
        result = self.get_impact_analysis(db, repository_id, analysis_id)
        if not result:
            return None

        nodes_dict: Dict[str, Dict[str, Any]] = {}
        edges_list: List[Dict[str, Any]] = []

        # 1. Add Changed Root Nodes
        for change in result.changes:
            nodes_dict[change.qualified_name] = {
                "id": change.qualified_name,
                "name": change.symbol_name or change.qualified_name,
                "type": change.artifact_type,
                "role": "CHANGED",
                "impact_level": 0,
                "confidence": change.confidence,
                "change_type": change.change_type.value,
                "location": change.target_location or change.base_location,
            }

        # 2. Add Impacted Nodes & Connecting Edges from Findings
        for finding in result.findings:
            if finding.target_qual_name not in nodes_dict:
                role = "DIRECTLY_AFFECTED" if finding.impact_level == 1 else "INDIRECTLY_AFFECTED"
                nodes_dict[finding.target_qual_name] = {
                    "id": finding.target_qual_name,
                    "name": finding.target_qual_name.split(".")[-1],
                    "type": finding.target_type,
                    "role": role,
                    "impact_level": finding.impact_level,
                    "confidence": finding.confidence,
                    "location": None,
                }

            edges_list.append({
                "source": finding.source_qual_name,
                "target": finding.target_qual_name,
                "type": finding.relationship_type,
                "confidence": finding.confidence,
                "impact_level": finding.impact_level,
            })

        # Deterministic sorting
        nodes = sorted(list(nodes_dict.values()), key=lambda n: (n["impact_level"], n["id"]))
        edges = sorted(edges_list, key=lambda e: (e["impact_level"], e["source"], e["target"], e["type"]))

        return {
            "analysis_id": analysis_id,
            "repository_id": repository_id,
            "base_snapshot_id": result.base_snapshot_id,
            "target_snapshot_id": result.target_snapshot_id,
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }


change_impact_service = ChangeImpactService()
