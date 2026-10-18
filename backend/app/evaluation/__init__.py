"""
Phase 8.9 — Benchmark & Evaluation Package.
Formal evaluation, baseline comparison, and metrics calculation for Change Impact Analysis.
"""

from app.evaluation.models import (
    GroundTruthType,
    BaselineAlgorithm,
    GroundTruthItem,
    GroundTruthSet,
    BenchmarkCase,
    PredictionRecord,
    OutcomeRecord,
    EvaluationMetrics,
    EvaluationRun,
)
from app.evaluation.metrics import compute_metrics
from app.evaluation.baselines import (
    ChangedFilesBaseline,
    ImportClosureBaseline,
    CallClosureBaseline,
    FullTwinEvaluator,
    BaselineOutput,
)
from app.evaluation.harness import EvaluationHarness, BenchmarkComparisonReport
from app.evaluation.test_evaluator import (
    TestImpactEvaluator,
    TestImpactEvaluationReport,
    TestSelectionDecision,
    TestSelectionClaim,
)

__all__ = [
    "GroundTruthType",
    "BaselineAlgorithm",
    "GroundTruthItem",
    "GroundTruthSet",
    "BenchmarkCase",
    "PredictionRecord",
    "OutcomeRecord",
    "EvaluationMetrics",
    "EvaluationRun",
    "compute_metrics",
    "ChangedFilesBaseline",
    "ImportClosureBaseline",
    "CallClosureBaseline",
    "FullTwinEvaluator",
    "BaselineOutput",
    "EvaluationHarness",
    "BenchmarkComparisonReport",
    "TestImpactEvaluator",
    "TestImpactEvaluationReport",
    "TestSelectionDecision",
    "TestSelectionClaim",
]
