"""
Phase 8.9.1 — Historical Evaluation Harness with Anti-Circularity Enforcement.
Reproducibly executes Change Impact Analysis across baseline algorithms and Full Twin.
Verifies path correctness against PostgreSQL relationships and computes comparative metrics
strictly under proven ground-truth independence.
"""

import time
import uuid
from typing import Dict, List, Set, Any, Optional
from sqlalchemy.orm import Session

from app.models.entities import Repository, RepositorySnapshot, StructuralArtifact, ArtifactRelationship
from app.services.impact.change_detector import change_detector
from app.services.impact.models import ChangeSet, ImpactConfig, ImpactResult
from app.evaluation.models import (
    BenchmarkCase,
    BaselineAlgorithm,
    EvaluationMetrics,
    EvaluationRun,
    PredictionRecord,
    GroundTruthType,
    GroundTruthSet,
    EvaluationMode,
    MetricStatus,
)
from app.evaluation.metrics import compute_metrics
from app.evaluation.baselines import (
    ChangedFilesBaseline,
    ImportClosureBaseline,
    CallClosureBaseline,
    FullTwinEvaluator,
    BaselineOutput,
)


class BenchmarkComparisonReport:
    """Consolidated comparative report for a benchmark case across all algorithms."""
    def __init__(
        self,
        case_id: str,
        repository_name: str,
        base_commit: str,
        target_commit: str,
        change_set_summary: Dict[str, int],
        runs: Dict[str, EvaluationRun],
        path_verification: Dict[str, Any],
        evaluation_mode: EvaluationMode = EvaluationMode.INDEPENDENT_LABELS,
        is_independent: bool = True,
        overall_status: MetricStatus = MetricStatus.VALID,
    ):
        self.case_id = case_id
        self.repository_name = repository_name
        self.base_commit = base_commit
        self.target_commit = target_commit
        self.change_set_summary = change_set_summary
        self.runs = runs
        self.path_verification = path_verification
        self.evaluation_mode = evaluation_mode
        self.is_independent = is_independent
        self.overall_status = overall_status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "repository_name": self.repository_name,
            "base_commit": self.base_commit,
            "target_commit": self.target_commit,
            "evaluation_mode": self.evaluation_mode.value if hasattr(self.evaluation_mode, "value") else str(self.evaluation_mode),
            "is_independent": self.is_independent,
            "overall_status": self.overall_status.value if hasattr(self.overall_status, "value") else str(self.overall_status),
            "changes": self.change_set_summary,
            "comparison": {
                algo: {
                    "status": run.metrics.status.value if hasattr(run.metrics.status, "value") else str(run.metrics.status),
                    "rejection_reason": run.metrics.rejection_reason,
                    "precision": run.metrics.precision,
                    "recall": run.metrics.recall,
                    "f1": run.metrics.f1,
                    "true_positives": run.metrics.true_positives,
                    "false_positives": run.metrics.false_positives,
                    "false_negatives": run.metrics.false_negatives,
                    "total_predicted": run.metrics.total_predicted,
                    "runtime_ms": run.metrics.runtime_ms,
                    "average_path_depth": run.metrics.average_path_depth,
                    "notes": run.metrics.notes,
                }
                for algo, run in self.runs.items()
            },
            "path_verification": self.path_verification,
        }


class EvaluationHarness:
    """
    Orchestrates historical replay and baseline comparisons against ground truth.
    Strictly enforces the Non-Circularity Invariant.
    """

    @classmethod
    def run_benchmark(
        cls,
        db: Session,
        repository_id: str,
        base_snapshot_id: str,
        target_snapshot_id: str,
        ground_truth_entities: Optional[Set[str]] = None,
        ground_truth_set: Optional[GroundTruthSet] = None,
        case_id: str = "BENCH_RUN",
        config: Optional[ImpactConfig] = None,
        evaluation_mode: EvaluationMode = EvaluationMode.INDEPENDENT_LABELS,
        is_independent: bool = True,
    ) -> BenchmarkComparisonReport:
        """
        Runs all 3 baselines plus Full Twin on the exact same change set and snapshot data.
        Refuses accuracy calculation if ground_truth is derived from the Twin.
        """
        repo = db.query(Repository).filter_by(id=repository_id).first()
        repo_name = repo.name if repo else "unknown"

        snap_base = db.query(RepositorySnapshot).filter_by(id=base_snapshot_id).first()
        snap_target = db.query(RepositorySnapshot).filter_by(id=target_snapshot_id).first()

        base_commit = snap_base.commit_hash if snap_base else "base"
        target_commit = snap_target.commit_hash if snap_target else "target"

        # Resolve ground truth parameters
        if ground_truth_set is not None:
            evaluation_mode = ground_truth_set.evaluation_mode
            is_independent = ground_truth_set.validate_independence()
            ground_truth_entities = ground_truth_set.get_qual_names()
        elif ground_truth_entities is None:
            ground_truth_entities = set()
            evaluation_mode = EvaluationMode.NO_GROUND_TRUTH

        # 1. Detect Changes
        change_set: ChangeSet = change_detector.detect_changes(
            db=db,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
        )

        # 2. Pre-fetch snapshot artifacts and relationships for fast in-memory execution
        target_artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=target_snapshot_id).all()
        target_rels = db.query(ArtifactRelationship).filter_by(snapshot_id=target_snapshot_id).all()
        base_artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=base_snapshot_id).all()
        base_rels = db.query(ArtifactRelationship).filter_by(snapshot_id=base_snapshot_id).all()

        universe_entities = {a.qualified_name for a in target_artifacts}

        runs: Dict[str, EvaluationRun] = {}

        # -------------------------------------------------------------
        # BASELINE 1: Changed-file set
        # -------------------------------------------------------------
        b1_out = ChangedFilesBaseline.evaluate(change_set=change_set)
        b1_metrics = compute_metrics(
            predicted_entities=b1_out.predicted_entities,
            ground_truth_entities=ground_truth_entities,
            universe_entities=universe_entities,
            evidence_backed_count=b1_out.evidence_backed_count,
            path_depths=b1_out.path_depths,
            runtime_ms=b1_out.runtime_ms,
            is_independent=is_independent,
            evaluation_mode=evaluation_mode,
            ground_truth_set=ground_truth_set,
        )
        runs[BaselineAlgorithm.CHANGED_FILES_SET.value] = EvaluationRun(
            run_id=f"run_b1_{uuid.uuid4().hex[:8]}",
            benchmark_case_id=case_id,
            algorithm=BaselineAlgorithm.CHANGED_FILES_SET,
            metrics=b1_metrics,
            predictions=b1_out.predictions,
        )

        # -------------------------------------------------------------
        # BASELINE 2: Import closure
        # -------------------------------------------------------------
        b2_out = ImportClosureBaseline.evaluate(
            change_set=change_set,
            artifacts=target_artifacts,
            relationships=target_rels,
        )
        b2_metrics = compute_metrics(
            predicted_entities=b2_out.predicted_entities,
            ground_truth_entities=ground_truth_entities,
            universe_entities=universe_entities,
            evidence_backed_count=b2_out.evidence_backed_count,
            path_depths=b2_out.path_depths,
            runtime_ms=b2_out.runtime_ms,
            is_independent=is_independent,
            evaluation_mode=evaluation_mode,
            ground_truth_set=ground_truth_set,
        )
        runs[BaselineAlgorithm.IMPORT_CLOSURE.value] = EvaluationRun(
            run_id=f"run_b2_{uuid.uuid4().hex[:8]}",
            benchmark_case_id=case_id,
            algorithm=BaselineAlgorithm.IMPORT_CLOSURE,
            metrics=b2_metrics,
            predictions=b2_out.predictions,
        )

        # -------------------------------------------------------------
        # BASELINE 3: Call closure
        # -------------------------------------------------------------
        b3_out = CallClosureBaseline.evaluate(
            change_set=change_set,
            artifacts=target_artifacts,
            relationships=target_rels,
        )
        b3_metrics = compute_metrics(
            predicted_entities=b3_out.predicted_entities,
            ground_truth_entities=ground_truth_entities,
            universe_entities=universe_entities,
            evidence_backed_count=b3_out.evidence_backed_count,
            path_depths=b3_out.path_depths,
            runtime_ms=b3_out.runtime_ms,
            is_independent=is_independent,
            evaluation_mode=evaluation_mode,
            ground_truth_set=ground_truth_set,
        )
        runs[BaselineAlgorithm.CALL_CLOSURE.value] = EvaluationRun(
            run_id=f"run_b3_{uuid.uuid4().hex[:8]}",
            benchmark_case_id=case_id,
            algorithm=BaselineAlgorithm.CALL_CLOSURE,
            metrics=b3_metrics,
            predictions=b3_out.predictions,
        )

        # -------------------------------------------------------------
        # FULL TWIN: Multi-hop causal propagation
        # -------------------------------------------------------------
        twin_res, twin_out = FullTwinEvaluator.evaluate(
            db=db,
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
            change_set=change_set,
            config=config,
            target_artifacts=target_artifacts,
            target_rels=target_rels,
            base_artifacts=base_artifacts,
            base_rels=base_rels,
        )
        # Note: Twin predicted set for blast radius comparison includes unique affected entities
        twin_predicted = set(twin_res.affected_categories.get("affected_components", []))
        twin_predicted.update(twin_res.affected_categories.get("affected_services", []))
        twin_predicted.update(twin_res.affected_categories.get("affected_apis", []))
        twin_predicted.update(twin_res.affected_categories.get("affected_tests", []))

        twin_metrics = compute_metrics(
            predicted_entities=twin_predicted,
            ground_truth_entities=ground_truth_entities,
            universe_entities=universe_entities,
            evidence_backed_count=len(twin_res.paths),
            path_depths=[p.depth for p in twin_res.paths],
            runtime_ms=twin_out.runtime_ms,
            is_independent=is_independent,
            evaluation_mode=evaluation_mode,
            ground_truth_set=ground_truth_set,
        )
        runs[BaselineAlgorithm.FULL_TWIN.value] = EvaluationRun(
            run_id=f"run_twin_{uuid.uuid4().hex[:8]}",
            benchmark_case_id=case_id,
            algorithm=BaselineAlgorithm.FULL_TWIN,
            metrics=twin_metrics,
            predictions=twin_out.predictions,
        )

        # -------------------------------------------------------------
        # Path Verification: Verify every step of every path against DB
        # -------------------------------------------------------------
        target_art_map = {a.id: a for a in target_artifacts}
        target_qual_pairs = set()
        for r in target_rels:
            s_art = target_art_map.get(r.source_artifact_id)
            t_art = target_art_map.get(r.target_artifact_id)
            if s_art and t_art:
                target_qual_pairs.add((s_art.qualified_name, t_art.qualified_name, r.relationship_type))

        valid_paths = 0
        total_paths = len(twin_res.paths)

        for p in twin_res.paths:
            path_ok = True
            for i in range(len(p.nodes) - 1):
                u = p.nodes[i]
                v = p.nodes[i + 1]
                step_exists = any(
                    (u == s and v == t) or (v == s and u == t)
                    for (s, t, _) in target_qual_pairs
                )
                if not step_exists:
                    path_ok = False
                    break
            if path_ok or len(p.nodes) == 1:
                valid_paths += 1

        path_verification = {
            "total_paths": total_paths,
            "valid_paths": valid_paths,
            "validity_percentage": round((valid_paths / total_paths * 100), 2) if total_paths > 0 else 100.0,
            "unique_affected_count": twin_res.summary.unique_affected,
            "multi_hop_count": twin_res.summary.multi_hop_affected,
            "depth_1_paths": twin_res.summary.depth_1_paths,
            "depth_2_paths": twin_res.summary.depth_2_paths,
            "depth_3_paths": twin_res.summary.depth_3_paths,
        }

        overall_status = twin_metrics.status

        return BenchmarkComparisonReport(
            case_id=case_id,
            repository_name=repo_name,
            base_commit=base_commit,
            target_commit=target_commit,
            change_set_summary={
                "total": len(change_set.changes),
                "added": sum(1 for c in change_set.changes if c.change_type.value == "ADDED"),
                "removed": sum(1 for c in change_set.changes if c.change_type.value == "REMOVED"),
                "modified": sum(1 for c in change_set.changes if c.change_type.value == "MODIFIED"),
            },
            runs=runs,
            path_verification=path_verification,
            evaluation_mode=evaluation_mode,
            is_independent=is_independent,
            overall_status=overall_status,
        )
