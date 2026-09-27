"""
Phase 4 — Change Impact Analyzer.
Deterministic coordinator of change detection, graph propagation,
path canonicalization, and entity categorization.
"""

import time
import uuid
from typing import Dict, List, Set, Optional
from sqlalchemy.orm import Session

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
    ) -> ImpactResult:
        """
        Runs deterministic change impact analysis between base_snapshot_id and target_snapshot_id.
        """
        start_time = time.time()
        cfg = config or ImpactConfig()
        analysis_id = f"impact_{uuid.uuid4().hex[:12]}"

        # 1. Detect Changes (symbol-level where supported, file-level fallback)
        change_set: ChangeSet = self.detector.detect_changes(
            db=db,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
        )

        # Handle No-Change scenario
        if not change_set.changes:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return ImpactResult(
                analysis_id=analysis_id,
                repository_id=repository_id,
                base_snapshot_id=base_snapshot_id,
                target_snapshot_id=target_snapshot_id,
                status="completed",
                message="No changes detected between selected snapshots.",
                summary=ImpactSummary(),
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
                execution_time_ms=elapsed_ms,
            )

        # 2. Propagate Impact along typed Digital Twin relationships
        findings: List[ImpactFinding] = self.propagator.propagate_impact(
            db=db,
            change_set=change_set,
            config=cfg,
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

        # Indirectly affected nodes that were also directly affected should count as directly affected
        indirectly_only = indirectly_affected_nodes - directly_affected_nodes

        summary = ImpactSummary(
            changed=len(changed_artifacts),
            directly_affected=len(directly_affected_nodes),
            indirectly_affected=len(indirectly_only),
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
            execution_time_ms=elapsed_ms,
        )


change_impact_analyzer = ChangeImpactAnalyzer()
