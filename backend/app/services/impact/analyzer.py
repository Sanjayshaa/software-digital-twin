"""
Phase 4 — Change Impact Analyzer.
Deterministic coordinator of change detection, graph propagation,
path canonicalization, and entity categorization.
"""

import time
import uuid
from typing import Dict, List, Set, Optional
from sqlalchemy.orm import Session

from app.models.entities import StructuralArtifact, ArtifactRelationship
from app.services.impact.models import (
    ChangeSet,
    ImpactConfig,
    ImpactFinding,
    ImpactPath,
    ImpactSummary,
    ImpactResult,
)
from app.services.impact.change_detector import change_detector, ChangeDetector
from app.services.impact.propagator import impact_propagator, ImpactPropagator
from app.services.impact.path_finder import impact_path_finder, ImpactPathFinder


class ChangeImpactAnalyzer:
    """
    Coordinates end-to-end Change Impact and Blast Radius analysis.
    Produces deterministic, reproducible, and explainable findings.
    """

    def __init__(
        self,
        detector: Optional[ChangeDetector] = None,
        propagator: Optional[ImpactPropagator] = None,
        path_finder: Optional[ImpactPathFinder] = None,
    ):
        self.detector = detector or change_detector
        self.propagator = propagator or impact_propagator
        self.path_finder = path_finder or impact_path_finder

    def analyze(
        self,
        db: Session,
        repository_id: str,
        base_snapshot_id: str,
        target_snapshot_id: str,
        config: Optional[ImpactConfig] = None,
        change_set: Optional[ChangeSet] = None,
        target_artifacts: Optional[List[StructuralArtifact]] = None,
        target_rels: Optional[List[ArtifactRelationship]] = None,
        base_artifacts: Optional[List[StructuralArtifact]] = None,
        base_rels: Optional[List[ArtifactRelationship]] = None,
    ) -> ImpactResult:
        """
        Runs deterministic change impact analysis between base_snapshot_id and target_snapshot_id.
        """
        start_time = time.time()
        cfg = config or ImpactConfig()
        analysis_id = f"impact_{uuid.uuid4().hex[:12]}"

        # Pre-load artifacts once for both change detection and propagation
        if base_artifacts is None:
            base_artifacts = (
                db.query(StructuralArtifact)
                .filter_by(snapshot_id=base_snapshot_id)
                .all()
            )
        if target_artifacts is None:
            target_artifacts = (
                db.query(StructuralArtifact)
                .filter_by(snapshot_id=target_snapshot_id)
                .all()
            )

        # 1. Detect Changes (symbol-level where supported, file-level fallback) or use provided change_set
        if change_set is None:
            change_set = self.detector.detect_changes(
                db=db,
                repository_id=repository_id,
                base_snapshot_id=base_snapshot_id,
                target_snapshot_id=target_snapshot_id,
                base_artifacts=base_artifacts,
                target_artifacts=target_artifacts,
            )

        # Handle Identical / No-Change scenario
        is_identical = (base_snapshot_id == target_snapshot_id) or (change_set.status == "IDENTICAL_COMMITS")
        if not change_set.changes or is_identical:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            if is_identical:
                status_str = "IDENTICAL_COMMITS"
                msg = change_set.message or "Baseline and Target refer to the identical commit or snapshot."
            elif change_set.status == "VERIFIED_ZERO_CHANGES":
                status_str = "VERIFIED_ZERO_CHANGES"
                msg = change_set.message or "Zero structural or file differences detected between selected revisions."
            elif change_set.status == "REVISION_RESOLUTION_FAILED":
                status_str = "FAILED"
                msg = change_set.message or "Could not resolve revision or snapshot."
            else:
                status_str = "COMPLETED"
                msg = change_set.message or "No changes detected between selected snapshots."

            return ImpactResult(
                analysis_id=analysis_id,
                repository_id=repository_id,
                base_snapshot_id=base_snapshot_id,
                target_snapshot_id=target_snapshot_id,
                status=status_str,
                message=msg,
                summary=ImpactSummary(status=status_str, message=msg, changed=0),
                changes=[],
                findings=[],
                paths=[],
                affected_categories={
                    "changed_artifacts": [],
                    "affected_components": [],
                    "affected_services": [],
                    "affected_apis": [],
                    "affected_processes": [],
                    "affected_tests": [],
                    "affected_database_entities": [],
                },
                impact_tree={"direct": [], "indirect": [], "tests": []},
                execution_time_ms=elapsed_ms,
            )

        # 2. Propagate Impact along typed Digital Twin relationships
        findings: List[ImpactFinding] = self.propagator.propagate_impact(
            db=db,
            change_set=change_set,
            config=cfg,
            target_artifacts=target_artifacts,
            target_rels=target_rels,
            base_artifacts=base_artifacts,
            base_rels=base_rels,
        )

        # 3. Canonicalize explainable Impact Paths
        paths: List[ImpactPath] = self.path_finder.build_paths(findings)

        # 4. Classify affected entities into categories
        changed_artifacts: List[str] = sorted(list({c.qualified_name for c in change_set.changes}))

        directly_affected_nodes: Set[str] = set()
        indirectly_affected_nodes: Set[str] = set()
        affected_components: Set[str] = set()
        affected_services: Set[str] = set()
        affected_apis: Set[str] = set()
        affected_processes: Set[str] = set()
        affected_tests: Set[str] = set()
        affected_dbs: Set[str] = set()

        max_depth = 0

        for f in findings:
            if f.impact_level > max_depth:
                max_depth = f.impact_level

            if f.impact_level == 1:
                directly_affected_nodes.add(f.target_qual_name)
            elif f.impact_level >= 2:
                indirectly_affected_nodes.add(f.target_qual_name)

            t_type = (f.target_type or "").upper()
            t_name = f.target_qual_name.lower()

            if "TEST" in t_type or "test" in t_name:
                affected_tests.add(f.target_qual_name)
            elif "API" in t_type or "ENDPOINT" in t_type or "route" in t_name or "/api/" in t_name:
                affected_apis.add(f.target_qual_name)
            elif "PROCESS" in t_type or "workflow" in t_name:
                affected_processes.add(f.target_qual_name)
            elif "SERVICE" in t_type or "service" in t_name:
                affected_services.add(f.target_qual_name)
                affected_components.add(f.target_qual_name)
            elif "DATABASE" in t_type or "table" in t_name or "model" in t_type:
                affected_dbs.add(f.target_qual_name)
            else:
                affected_components.add(f.target_qual_name)

        unique_affected_nodes = directly_affected_nodes.union(indirectly_affected_nodes)
        multi_hop_affected_nodes = {f.target_qual_name for f in findings if f.impact_level >= 2}

        depth_1_paths = sum(1 for p in paths if p.depth == 1)
        depth_2_paths = sum(1 for p in paths if p.depth == 2)
        depth_3_paths = sum(1 for p in paths if p.depth == 3)

        summary = ImpactSummary(
            changed=len(changed_artifacts),
            directly_affected=len(directly_affected_nodes),
            indirectly_affected=len(indirectly_affected_nodes),
            unique_affected=len(unique_affected_nodes),
            multi_hop_affected=len(multi_hop_affected_nodes),
            total_evidence_paths=len(paths),
            depth_1_paths=depth_1_paths,
            depth_2_paths=depth_2_paths,
            depth_3_paths=depth_3_paths,
            affected_components=len(affected_components),
            affected_services=len(affected_services),
            affected_apis=len(affected_apis),
            affected_processes=len(affected_processes),
            affected_tests=len(affected_tests),
            max_depth_reached=max_depth,
        )

        categories: Dict[str, List[str]] = {
            "changed_artifacts": changed_artifacts,
            "affected_components": sorted(list(affected_components)),
            "affected_services": sorted(list(affected_services)),
            "affected_apis": sorted(list(affected_apis)),
            "affected_processes": sorted(list(affected_processes)),
            "affected_tests": sorted(list(affected_tests)),
            "affected_database_entities": sorted(list(affected_dbs)),
        }

        impact_tree = {
            "direct": [
                {"id": f.impacted_node_id, "name": f.target_qual_name, "type": f.target_type}
                for f in findings if f.impact_level == 1
            ],
            "indirect": [
                {"id": f.impacted_node_id, "name": f.target_qual_name, "type": f.target_type}
                for f in findings if f.impact_level >= 2
            ],
            "tests": [
                {"id": f.impacted_node_id, "name": f.target_qual_name, "type": f.target_type}
                for f in findings if "TEST" in (f.target_type or "").upper()
            ],
        }

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return ImpactResult(
            analysis_id=analysis_id,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
            status="completed",
            message=f"Change impact analysis completed across {len(change_set.changes)} changes.",
            summary=summary,
            changes=change_set.changes,
            findings=findings,
            paths=paths,
            affected_categories=categories,
            impact_tree=impact_tree,
            execution_time_ms=elapsed_ms,
        )


change_impact_analyzer = ChangeImpactAnalyzer()
ImpactAnalyzer = ChangeImpactAnalyzer
