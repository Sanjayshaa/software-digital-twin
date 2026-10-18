"""
Phase 8.9 — Baseline Comparison Algorithms.
Provides deterministic baseline implementations for rigorous empirical evaluation:
- Baseline 1: Changed-Files Set (predicts only directly modified entities/files)
- Baseline 2: Import Closure (predicts changed entities + 1-hop reverse IMPORTS/DEPENDS_ON)
- Baseline 3: Call Closure (predicts changed symbols + 1-hop reverse CALLS)
- Full Twin: Multi-hop typed causal propagation with cycle protection and alias resolution
"""

import time
from typing import Set, List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.entities import StructuralArtifact, ArtifactRelationship
from app.services.impact.models import ChangeSet, ImpactConfig, ImpactResult
from app.services.impact.analyzer import change_impact_analyzer
from app.evaluation.models import BaselineAlgorithm, PredictionRecord


class BaselineOutput:
    """Standardized output structure for baseline comparison."""
    def __init__(
        self,
        algorithm: BaselineAlgorithm,
        predicted_entities: Set[str],
        predictions: List[PredictionRecord],
        runtime_ms: float,
        evidence_backed_count: int,
        path_depths: List[int],
    ):
        self.algorithm = algorithm
        self.predicted_entities = predicted_entities
        self.predictions = predictions
        self.runtime_ms = runtime_ms
        self.evidence_backed_count = evidence_backed_count
        self.path_depths = path_depths


class ChangedFilesBaseline:
    """
    Baseline 1: Changed-file set.
    Predicts strictly the entities/files directly modified by the patch.
    No propagation along any relationship.
    """
    algorithm = BaselineAlgorithm.CHANGED_FILES_SET

    @classmethod
    def evaluate(cls, change_set: ChangeSet, **kwargs) -> BaselineOutput:
        start_time = time.time()
        predicted: Set[str] = set()
        records: List[PredictionRecord] = []

        for i, change in enumerate(change_set.changes):
            name = change.qualified_name or change.symbol_name or change.source_file
            predicted.add(name)
            records.append(
                PredictionRecord(
                    prediction_id=f"pred_base1_{i}_{change.artifact_id or 'anon'}",
                    analysis_id="base1_run",
                    change_id=change.artifact_id or f"ch_{i}",
                    predicted_entity_id=change.artifact_id or name,
                    predicted_entity_name=name,
                    prediction_class="DIRECT_CHANGE",
                    evidence_ids=[f"ev_diff_{change.artifact_id or i}"],
                    algorithm_version="baseline-1-diff",
                )
            )

        elapsed = round((time.time() - start_time) * 1000, 2)
        return BaselineOutput(
            algorithm=cls.algorithm,
            predicted_entities=predicted,
            predictions=records,
            runtime_ms=elapsed,
            evidence_backed_count=len(records),
            path_depths=[0] * len(predicted),
        )


class ImportClosureBaseline:
    """
    Baseline 2: Import/dependency closure.
    Predicts changed entities plus immediate 1-hop reverse IMPORTS and DEPENDS_ON neighbors.
    Does not traverse CALLS, TESTS, or multi-hop transitive paths.
    """
    algorithm = BaselineAlgorithm.IMPORT_CLOSURE

    @classmethod
    def evaluate(
        cls,
        change_set: ChangeSet,
        artifacts: List[StructuralArtifact],
        relationships: List[ArtifactRelationship],
        **kwargs,
    ) -> BaselineOutput:
        start_time = time.time()
        predicted: Set[str] = set()
        records: List[PredictionRecord] = []

        art_map = {a.id: a for a in artifacts}
        art_qual_map = {a.qualified_name: a for a in artifacts}

        # 1. Add direct changes
        changed_ids: Set[str] = set()
        for change in change_set.changes:
            art = art_map.get(change.artifact_id) or art_qual_map.get(change.qualified_name)
            name = change.qualified_name or change.symbol_name or change.source_file
            predicted.add(name)
            if art:
                changed_ids.add(art.id)

        # 2. Add 1-hop reverse IMPORTS and DEPENDS_ON (who imports or depends on the changed entity)
        import_rels = [
            r for r in relationships
            if r.relationship_type in ("IMPORTS", "DEPENDS_ON")
            and r.target_artifact_id in changed_ids
        ]

        path_depths = [0] * len(change_set.changes)

        for i, r in enumerate(import_rels):
            importer = art_map.get(r.source_artifact_id)
            if importer:
                predicted.add(importer.qualified_name)
                path_depths.append(1)
                records.append(
                    PredictionRecord(
                        prediction_id=f"pred_base2_{i}_{importer.id}",
                        analysis_id="base2_run",
                        change_id=r.target_artifact_id,
                        predicted_entity_id=importer.id,
                        predicted_entity_name=importer.qualified_name,
                        prediction_class="IMPORT_NEIGHBOR",
                        evidence_ids=[f"ev_import_{r.id[:8]}"],
                        algorithm_version="baseline-2-imports",
                    )
                )

        elapsed = round((time.time() - start_time) * 1000, 2)
        return BaselineOutput(
            algorithm=cls.algorithm,
            predicted_entities=predicted,
            predictions=records,
            runtime_ms=elapsed,
            evidence_backed_count=len(predicted),
            path_depths=path_depths,
        )


class CallClosureBaseline:
    """
    Baseline 3: Simple call/dependency closure.
    Predicts changed symbols plus immediate 1-hop reverse CALLS (callers).
    Does not perform multi-hop expansion, alias resolution, or cross-tier API/process propagation.
    """
    algorithm = BaselineAlgorithm.CALL_CLOSURE

    @classmethod
    def evaluate(
        cls,
        change_set: ChangeSet,
        artifacts: List[StructuralArtifact],
        relationships: List[ArtifactRelationship],
        **kwargs,
    ) -> BaselineOutput:
        start_time = time.time()
        predicted: Set[str] = set()
        records: List[PredictionRecord] = []

        art_map = {a.id: a for a in artifacts}
        art_qual_map = {a.qualified_name: a for a in artifacts}

        changed_ids: Set[str] = set()
        for change in change_set.changes:
            art = art_map.get(change.artifact_id) or art_qual_map.get(change.qualified_name)
            name = change.qualified_name or change.symbol_name or change.source_file
            predicted.add(name)
            if art:
                changed_ids.add(art.id)

        # 1-hop reverse CALLS (who calls the changed entity)
        call_rels = [
            r for r in relationships
            if r.relationship_type == "CALLS"
            and r.target_artifact_id in changed_ids
        ]

        path_depths = [0] * len(change_set.changes)

        for i, r in enumerate(call_rels):
            caller = art_map.get(r.source_artifact_id)
            if caller:
                predicted.add(caller.qualified_name)
                path_depths.append(1)
                records.append(
                    PredictionRecord(
                        prediction_id=f"pred_base3_{i}_{caller.id}",
                        analysis_id="base3_run",
                        change_id=r.target_artifact_id,
                        predicted_entity_id=caller.id,
                        predicted_entity_name=caller.qualified_name,
                        prediction_class="CALLER_NEIGHBOR",
                        evidence_ids=[f"ev_call_{r.id[:8]}"],
                        algorithm_version="baseline-3-calls",
                    )
                )

        elapsed = round((time.time() - start_time) * 1000, 2)
        return BaselineOutput(
            algorithm=cls.algorithm,
            predicted_entities=predicted,
            predictions=records,
            runtime_ms=elapsed,
            evidence_backed_count=len(predicted),
            path_depths=path_depths,
        )


class FullTwinEvaluator:
    """
    Full Digital Twin Change Impact Engine.
    Executes multi-hop reverse reachability, typed relationship rules, cycle protection,
    alias resolution, and multi-tier API/process/test propagation.
    """
    algorithm = BaselineAlgorithm.FULL_TWIN

    @classmethod
    def evaluate(
        cls,
        db: Session,
        repository_id: str,
        base_snapshot_id: str,
        target_snapshot_id: str,
        change_set: Optional[ChangeSet] = None,
        config: Optional[ImpactConfig] = None,
        target_artifacts: Optional[List[StructuralArtifact]] = None,
        target_rels: Optional[List[ArtifactRelationship]] = None,
        base_artifacts: Optional[List[StructuralArtifact]] = None,
        base_rels: Optional[List[ArtifactRelationship]] = None,
    ) -> Tuple[ImpactResult, BaselineOutput]:
        start_time = time.time()
        cfg = config or ImpactConfig(max_depth=5, include_tests=True, include_processes=True, include_apis=True)

        res = change_impact_analyzer.analyze(
            db=db,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
            config=cfg,
            change_set=change_set,
            target_artifacts=target_artifacts,
            target_rels=target_rels,
            base_artifacts=base_artifacts,
            base_rels=base_rels,
        )

        predicted: Set[str] = set()
        records: List[PredictionRecord] = []
        path_depths: List[int] = []

        # 1. Changed entities
        for c in res.changes:
            predicted.add(c.qualified_name)
            path_depths.append(0)

        # 2. Findings (affected entities)
        for i, f in enumerate(res.findings):
            predicted.add(f.target_qual_name)
            path_depths.append(f.impact_level)
            records.append(
                PredictionRecord(
                    prediction_id=f"pred_twin_{i}_{f.impacted_node_id}",
                    analysis_id=res.analysis_id,
                    change_id=f.source_node_id,
                    predicted_entity_id=f.impacted_node_id,
                    predicted_entity_name=f.target_qual_name,
                    prediction_class="DIRECT" if f.impact_level == 1 else "PROVEN_TRANSITIVE",
                    evidence_ids=f.evidence_ids or [f"ev_{f.impacted_node_id[:8]}"],
                    algorithm_version="twin-8.9-full",
                )
            )

        elapsed = round((time.time() - start_time) * 1000, 2)
        baseline_out = BaselineOutput(
            algorithm=cls.algorithm,
            predicted_entities=predicted,
            predictions=records,
            runtime_ms=elapsed,
            evidence_backed_count=len(predicted),
            path_depths=path_depths,
        )
        return res, baseline_out
