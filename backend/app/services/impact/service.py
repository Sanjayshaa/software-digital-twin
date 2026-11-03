"""
Phase 4 — Change Impact Service.
High-level service orchestrating change impact execution, persistence in AnalysisRun,
result retrieval, and visual graph projection.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder

from app.models.entities import (
    Repository,
    RepositorySnapshot,
    AnalysisRun,
    StructuralArtifact,
    ArtifactRelationship,
    SnapshotStatus,
)
from app.services.impact.models import (
    ImpactConfig,
    ImpactResult,
    ImpactFinding,
    ImpactSummary,
    ChangeItem,
    ImpactPath,
    ImpactPreconditionError,
)
from app.services.acquisition.git_provider import check_git_ancestry
from app.services.impact.analyzer import change_impact_analyzer, ChangeImpactAnalyzer
from app.services.impact.change_detector import change_detector, map_changes_to_proposed_mutations


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
        # Precondition P0-1: Repository scope enforcement (HTTP 400 Bad Request)
        if base_snap.repository_id != repository_id:
            raise ImpactPreconditionError(
                f"Base snapshot '{base_snapshot_id}' does not belong to repository '{repository_id}'.",
                status_code=400,
                error_code="CROSS_REPO_MISMATCH",
            )

        target_snap = db.query(RepositorySnapshot).filter_by(id=target_snapshot_id).first()
        if not target_snap:
            raise ValueError(f"Target snapshot '{target_snapshot_id}' not found.")
        if target_snap.repository_id != repository_id:
            raise ImpactPreconditionError(
                f"Target snapshot '{target_snapshot_id}' does not belong to repository '{repository_id}'.",
                status_code=400,
                error_code="CROSS_REPO_MISMATCH",
            )

        # Precondition P0-1/P0-2: Baseline snapshot must be READY
        if base_snap.status != SnapshotStatus.READY:
            raise ImpactPreconditionError(
                f"Baseline snapshot '{base_snapshot_id}' is not in READY state (current status: {base_snap.status}). Analysis requires both snapshots to be READY.",
                status_code=409,
                error_code="SNAPSHOT_NOT_READY",
            )

        # Precondition P0-1/P0-2: Target snapshot must be READY
        if target_snap.status != SnapshotStatus.READY:
            raise ImpactPreconditionError(
                f"Target snapshot '{target_snapshot_id}' is not in READY state (current status: {target_snap.status}). Analysis requires both snapshots to be READY.",
                status_code=409,
                error_code="SNAPSHOT_NOT_READY",
            )

        # Precondition P0-2: Same-commit contract
        if (base_snap.commit_hash or "").strip().lower() == (target_snap.commit_hash or "").strip().lower():
            raise ImpactPreconditionError(
                "Baseline and target refer to the same commit; no change can be computed.",
                status_code=409,
                error_code="SAME_COMMIT",
            )

        # Precondition P0-2: Git Ancestry Check
        is_ancestor, ancestry_err = check_git_ancestry(
            workspace_path=repo.local_path,
            base_sha=base_snap.commit_hash,
            target_sha=target_snap.commit_hash,
        )
        if not is_ancestor:
            raise ImpactPreconditionError(
                ancestry_err or f"Baseline commit '{base_snap.commit_hash}' is not an ancestor of target commit '{target_snap.commit_hash}'.",
                status_code=409,
                error_code="ANCESTRY_VIOLATION",
            )

        # Execute deterministic impact analysis
        result = self.analyzer.analyze(
            db=db,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
            config=config,
        )

        # Phase 1 P0: Ensure provenance is attached to result
        result.base_commit_sha = base_snap.commit_hash
        result.target_commit_sha = target_snap.commit_hash

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

    def run_live_incremental_analysis(
        self,
        db: Session,
        repository_id: str,
        base_snapshot_id: Optional[str] = None,
        config: Optional[ImpactConfig] = None,
    ) -> Dict[str, Any]:
        """
        Detects live uncommitted modifications in the local working tree,
        maps them to knowledge graph AST symbols, propagates blast radius through the Digital Twin,
        and translates changed nodes into What-If simulation mutations.
        """
        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise ValueError(f"Repository '{repository_id}' not found.")

        # 1. Resolve base snapshot
        base_snap = None
        if base_snapshot_id:
            base_snap = db.query(RepositorySnapshot).filter_by(id=base_snapshot_id, repository_id=repo.id).first()
        if not base_snap:
            base_snap = (
                db.query(RepositorySnapshot)
                .filter_by(repository_id=repo.id)
                .order_by(RepositorySnapshot.created_at.desc())
                .first()
            )

        if not base_snap:
            raise ValueError(f"No existing snapshot found for repository '{repo.name}'. Please ingest/analyze repository first.")

        # 2. Detect live changes in working tree
        change_set = change_detector.detect_live_changes(
            db=db,
            repository_id=repo.id,
            base_snapshot_id=base_snap.id,
        )

        # 3. If zero uncommitted changes:
        if change_set.is_verified_zero or not change_set.changes:
            return {
                "status": "VERIFIED_CLEAN",
                "working_tree_status": "CLEAN",
                "repository_id": repo.id,
                "repository_name": repo.name,
                "base_snapshot_id": base_snap.id,
                "base_commit": base_snap.commit_hash,
                "base_branch": base_snap.branch_name,
                "message": change_set.message or "Working tree is clean. Zero uncommitted changes detected.",
                "change_set": jsonable_encoder(change_set),
                "impact_result": {
                    "analysis_id": f"live_clean_{base_snap.id[:8]}",
                    "status": "VERIFIED_CLEAN",
                    "message": "Zero uncommitted changes to propagate.",
                    "summary": {"total_affected": 0, "blast_radius_score": 0.0, "risk_level": "LOW"},
                    "changes": [],
                    "findings": [],
                    "paths": [],
                    "affected_categories": {
                        "changed_artifacts": [],
                        "affected_components": [],
                        "affected_services": [],
                        "affected_apis": [],
                        "affected_processes": [],
                        "affected_tests": [],
                        "affected_database_entities": [],
                    },
                    "impact_tree": {"direct": [], "indirect": [], "tests": []},
                },
                "proposed_mutations": [],
                "targeted_tests": [],
                "affected_apis": [],
                "affected_services": [],
                "blast_radius_score": 0.0,
                "risk_level": "LOW",
                "total_affected_entities": 0,
                "summary": {
                    "working_tree_status": "CLEAN",
                    "total_changed_items": 0,
                    "symbol_level_changes": 0,
                    "file_level_changes": 0,
                    "blast_radius_score": 0.0,
                    "risk_level": "LOW",
                    "affected_tests_count": 0,
                    "what_if_mutations_count": 0,
                },
            }

        # 4. Load baseline graph nodes & edges
        base_artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=base_snap.id).all()
        base_rels = db.query(ArtifactRelationship).filter_by(snapshot_id=base_snap.id).all()

        # 5. Execute propagation across the Knowledge Graph
        cfg = config or ImpactConfig(max_depth=5, include_tests=True, include_apis=True)
        impact_result = self.analyzer.analyze(
            db=db,
            repository_id=repo.id,
            base_snapshot_id=base_snap.id,
            target_snapshot_id=f"{base_snap.id}:working-tree",
            config=cfg,
            change_set=change_set,
            target_artifacts=base_artifacts,
            target_rels=base_rels,
            base_artifacts=base_artifacts,
            base_rels=base_rels,
        )

        # 6. Convert to What-If proposed mutations
        proposed_mutations = map_changes_to_proposed_mutations(change_set.changes)

        affected_tests = impact_result.affected_categories.get("affected_tests", [])
        affected_apis = impact_result.affected_categories.get("affected_apis", [])
        affected_services = impact_result.affected_categories.get("affected_services", [])

        # Persist AnalysisRun trace for reproducibility
        try:
            analysis_run = AnalysisRun(
                id=impact_result.analysis_id,
                project_id=repo.project_id,
                repository_id=repo.id,
                snapshot_id=base_snap.id,
                run_type="live_incremental_impact",
                status="COMPLETED",
                files_scanned=len(change_set.changes),
                artifacts_created=len(impact_result.findings),
                relationships_created=len(impact_result.paths),
                summary={
                    "working_tree_status": "DIRTY",
                    "total_changes": len(change_set.changes),
                    "blast_radius_score": impact_result.summary.blast_radius_score,
                    "risk_level": impact_result.summary.risk_level,
                    "affected_tests_count": len(affected_tests),
                    "what_if_mutations_count": len(proposed_mutations),
                },
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
            db.add(analysis_run)
            db.commit()
        except Exception:
            db.rollback()

        return {
            "status": "SUCCESS",
            "working_tree_status": "DIRTY",
            "repository_id": repo.id,
            "repository_name": repo.name,
            "base_snapshot_id": base_snap.id,
            "base_commit": base_snap.commit_hash,
            "base_branch": base_snap.branch_name,
            "message": change_set.message,
            "change_set": jsonable_encoder(change_set),
            "impact_result": jsonable_encoder(impact_result),
            "proposed_mutations": proposed_mutations,
            "targeted_tests": affected_tests,
            "affected_apis": affected_apis,
            "affected_services": affected_services,
            "blast_radius_score": getattr(impact_result.summary, "blast_radius_score", 0.0) if hasattr(impact_result.summary, "blast_radius_score") else round(min(1.0, (impact_result.summary.unique_affected + impact_result.summary.multi_hop_affected) / 20.0), 2),
            "risk_level": getattr(impact_result.summary, "risk_level", "LOW") if hasattr(impact_result.summary, "risk_level") else ("HIGH" if (impact_result.summary.unique_affected + impact_result.summary.multi_hop_affected) > 3 else "LOW"),
            "total_affected_entities": impact_result.summary.unique_affected + impact_result.summary.multi_hop_affected,
            "summary": {
                "working_tree_status": "DIRTY",
                "total_changed_items": len(change_set.changes),
                "symbol_level_changes": change_set.summary.get("symbol_level_count", 0),
                "file_level_changes": change_set.summary.get("file_level_count", 0),
                "blast_radius_score": getattr(impact_result.summary, "blast_radius_score", 0.0) if hasattr(impact_result.summary, "blast_radius_score") else round(min(1.0, (impact_result.summary.unique_affected + impact_result.summary.multi_hop_affected) / 20.0), 2),
                "risk_level": getattr(impact_result.summary, "risk_level", "LOW") if hasattr(impact_result.summary, "risk_level") else ("HIGH" if (impact_result.summary.unique_affected + impact_result.summary.multi_hop_affected) > 3 else "LOW"),
                "affected_tests_count": len(affected_tests),
                "what_if_mutations_count": len(proposed_mutations),
            },
        }


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
