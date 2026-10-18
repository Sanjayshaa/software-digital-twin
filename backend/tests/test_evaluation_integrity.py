"""
Phase 8.9.1 — Evaluation Integrity Audit & Anti-Circularity Test Suite.

Verifies:
1. Twin-derived ground truth rejected (status == INVALID_GROUND_TRUTH).
2. Independent manual ground truth accepted (status == VALID).
3. Patch-only ground truth marked partial (status == PARTIAL_PATCH_ONLY).
4. Unknown / empty ground truth produces no accuracy metric (status == NO_GROUND_TRUTH / GROUND_TRUTH_INSUFFICIENT).
5. Baseline fairness (all algorithms receive identical input and ground truth).
6. Deterministic metrics repeatability.
7. Ground-truth provenance metadata verification.
8. Ground-truth immutability.
9. Prediction / outcome separation.
10. No circular dependency between evaluation and impact engine.
"""

import os
import ast
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.evaluation.models import (
    GroundTruthSource,
    GroundTruthType,
    EvaluationMode,
    MetricStatus,
    BaselineAlgorithm,
    GroundTruthItem,
    GroundTruthSet,
    PredictionRecord,
    OutcomeRecord,
    EvaluationMetrics,
    create_patch_ground_truth,
)
from app.evaluation.metrics import compute_metrics
from app.services.impact.models import ChangeSet, ChangeItem, ChangeType


# -----------------------------------------------------------------------------
# 1. Twin-derived ground truth rejected
# -----------------------------------------------------------------------------
def test_twin_derived_ground_truth_rejected():
    """
    Validates that if ground truth is derived from Twin propagation/predictions,
    it is detected and compute_metrics refuses accuracy calculation.
    Never returns 1.00/1.00/1.00 for circular labels.
    """
    # Case A: Explicit independence flag is False
    circular_item = GroundTruthItem(
        entity="src.components.CodeEditor",
        label="AFFECTED",
        source=GroundTruthSource.UNKNOWN,
        method="Full Twin output replication",
        evidence=["ImpactPropagator path traversal"],
        ground_truth_independent_of_twin=False,
        reason="Copied from Twin prediction",
    )
    circular_set = GroundTruthSet(
        case_id="BENCH_CIRCULAR_TEST",
        evaluation_mode=EvaluationMode.INDEPENDENT_LABELS,
        ground_truth_independent_of_twin=False,
        items=[circular_item],
    )

    assert circular_set.validate_independence() is False

    # Compute metrics with circular ground truth
    metrics = compute_metrics(
        predicted_entities={"src.components.CodeEditor"},
        ground_truth_entities={"src.components.CodeEditor"},
        ground_truth_set=circular_set,
    )

    assert metrics.status == MetricStatus.INVALID_GROUND_TRUTH
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1 == 0.0
    assert "INVALID_FOR_TWIN_ACCURACY" in (metrics.notes or "")
    assert "circular" in (metrics.rejection_reason or "").lower()

    # Case B: Item method carries forbidden Twin keywords even if boolean was set to True
    leaked_item = GroundTruthItem(
        entity="src.components.CodeEditor",
        label="AFFECTED",
        source=GroundTruthSource.MANUAL,
        method="ImpactPropagator traversal verification",
        evidence=["Full Twin output"],
        ground_truth_independent_of_twin=True,
        reason="Inspected ImpactFinding output",
    )
    leaked_set = GroundTruthSet(
        case_id="BENCH_LEAKED_TEST",
        evaluation_mode=EvaluationMode.INDEPENDENT_LABELS,
        ground_truth_independent_of_twin=True,
        items=[leaked_item],
    )

    assert leaked_set.validate_independence() is False
    m2 = compute_metrics(
        predicted_entities={"src.components.CodeEditor"},
        ground_truth_set=leaked_set,
    )
    assert m2.status == MetricStatus.INVALID_GROUND_TRUTH


# -----------------------------------------------------------------------------
# 2. Independent manual ground truth accepted
# -----------------------------------------------------------------------------
def test_independent_manual_ground_truth_accepted():
    """
    Validates that independently audited manual annotations with provenance
    are accepted and produce valid accuracy metrics.
    """
    labels_file = Path("benchmark_cases/lab_record_system/manual_labels.json")
    assert labels_file.exists(), f"Missing manual benchmark labels at {labels_file}"

    gt_set = GroundTruthSet.load_from_file(str(labels_file))
    assert gt_set.validate_independence() is True
    assert len(gt_set.items) == 3

    qual_names = gt_set.get_qual_names()
    assert "src.components.CodeEditor" in qual_names
    assert "POST /api/run" in qual_names
    assert "tests.languageDetector" in qual_names

    # Test evaluation with a partial prediction
    pred = {"src.components.CodeEditor", "POST /api/run"}
    metrics = compute_metrics(
        predicted_entities=pred,
        ground_truth_set=gt_set,
    )

    assert metrics.status == MetricStatus.VALID
    assert metrics.true_positives == 2
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 1
    assert metrics.precision == 1.0  # 2 / 2
    assert metrics.recall == 0.6667  # 2 / 3
    assert metrics.f1 == 0.8         # 2 * 1.0 * 0.6667 / 1.6667
    assert metrics.evaluation_mode == EvaluationMode.INDEPENDENT_LABELS


# -----------------------------------------------------------------------------
# 3. Patch-only ground truth marked partial
# -----------------------------------------------------------------------------
def test_patch_only_ground_truth_marked_partial():
    """
    Validates that PATCH_ONLY ground truth (directly modified entities)
    is explicitly marked PARTIAL_PATCH_ONLY and disclaims complete impact accuracy.
    """
    patch_entities = {
        "src/services/languageDetector.ts",
        "src/components/CodeEditor.tsx",
    }
    patch_gt = create_patch_ground_truth(
        case_id="BENCH_PATCH_ONLY",
        directly_modified_entities=patch_entities,
        reviewer="git_diff_parser",
    )

    assert patch_gt.evaluation_mode == EvaluationMode.PATCH_ONLY
    assert patch_gt.validate_independence() is True

    # Baseline predicted modified file
    metrics = compute_metrics(
        predicted_entities={"src/services/languageDetector.ts", "other_file.ts"},
        ground_truth_set=patch_gt,
    )

    assert metrics.status == MetricStatus.PARTIAL_PATCH_ONLY
    assert metrics.evaluation_mode == EvaluationMode.PATCH_ONLY
    assert "directly modified entities only" in (metrics.notes or "").lower()
    assert "not" in (metrics.notes or "").lower()


# -----------------------------------------------------------------------------
# 4. Unknown ground truth produces no accuracy metric
# -----------------------------------------------------------------------------
def test_unknown_ground_truth_produces_no_accuracy_metric():
    """
    Validates that when ground truth is unknown (Mode C) or insufficient,
    the metric engine reports predictions without precision/recall/F1 claims.
    """
    # Mode C: NO_GROUND_TRUTH
    m_mode_c = compute_metrics(
        predicted_entities={"ComponentA", "ComponentB"},
        ground_truth_entities=set(),
        evaluation_mode=EvaluationMode.NO_GROUND_TRUTH,
    )
    assert m_mode_c.status == MetricStatus.NO_GROUND_TRUTH
    assert m_mode_c.precision == 0.0
    assert m_mode_c.recall == 0.0
    assert m_mode_c.f1 == 0.0
    assert m_mode_c.total_predicted == 2
    assert m_mode_c.total_ground_truth == 0
    assert "NO_GROUND_TRUTH" in m_mode_c.rejection_reason

    # Mode B but with empty/insufficient ground truth
    m_insufficient = compute_metrics(
        predicted_entities={"ComponentA"},
        ground_truth_entities=set(),
        evaluation_mode=EvaluationMode.INDEPENDENT_LABELS,
    )
    assert m_insufficient.status == MetricStatus.GROUND_TRUTH_INSUFFICIENT
    assert m_insufficient.precision == 0.0
    assert m_insufficient.recall == 0.0
    assert m_insufficient.f1 == 0.0
    assert "INSUFFICIENT" in (m_insufficient.notes or "")


# -----------------------------------------------------------------------------
# 5. Baseline fairness
# -----------------------------------------------------------------------------
def test_baseline_fairness():
    """
    Validates baseline fairness invariant:
    All algorithms receive identical input, identical ground truth, and
    no algorithm can modify ground truth during execution.
    """
    from app.evaluation.baselines import (
        ChangedFilesBaseline,
        ImportClosureBaseline,
        CallClosureBaseline,
    )

    change_item = ChangeItem(
        change_type=ChangeType.MODIFIED,
        artifact_id="art_1",
        qualified_name="src.services.languageDetector",
        symbol_name="languageDetector",
        artifact_type="MODULE",
        source_file="src/services/languageDetector.ts",
    )
    change_set = ChangeSet(
        repository_id="repo_1",
        base_snapshot_id="snap_1",
        target_snapshot_id="snap_2",
        changes=[change_item],
    )

    gt_set = GroundTruthSet(
        case_id="BENCH_FAIRNESS",
        evaluation_mode=EvaluationMode.INDEPENDENT_LABELS,
        items=[
            GroundTruthItem(
                entity="src.services.languageDetector",
                label="AFFECTED",
                source=GroundTruthSource.MANUAL,
                method="architect_review",
                evidence=["diff analysis"],
                ground_truth_independent_of_twin=True,
                reason="Independent review",
            )
        ],
    )

    gt_names_before = set(gt_set.get_qual_names())

    # Run Baseline 1
    out1 = ChangedFilesBaseline.evaluate(change_set=change_set)
    m1 = compute_metrics(predicted_entities=out1.predicted_entities, ground_truth_set=gt_set)

    # Run Baseline 2
    out2 = ImportClosureBaseline.evaluate(change_set=change_set, artifacts=[], relationships=[])
    m2 = compute_metrics(predicted_entities=out2.predicted_entities, ground_truth_set=gt_set)

    # Run Baseline 3
    out3 = CallClosureBaseline.evaluate(change_set=change_set, artifacts=[], relationships=[])
    m3 = compute_metrics(predicted_entities=out3.predicted_entities, ground_truth_set=gt_set)

    # Verify ground truth was completely unaffected by executions
    assert gt_set.get_qual_names() == gt_names_before
    assert m1.evaluation_mode == m2.evaluation_mode == m3.evaluation_mode == EvaluationMode.INDEPENDENT_LABELS
    assert m1.total_ground_truth == m2.total_ground_truth == m3.total_ground_truth == 1


# -----------------------------------------------------------------------------
# 6. Deterministic metrics
# -----------------------------------------------------------------------------
def test_deterministic_metrics():
    """
    Validates that running evaluation twice with identical inputs produces
    bitwise identical metric results.
    """
    pred = {"EntityA", "EntityB", "EntityC"}
    gt = {"EntityB", "EntityC", "EntityD"}

    m1 = compute_metrics(predicted_entities=pred, ground_truth_entities=gt)
    m2 = compute_metrics(predicted_entities=pred, ground_truth_entities=gt)

    assert m1.precision == m2.precision == 0.6667
    assert m1.recall == m2.recall == 0.6667
    assert m1.f1 == m2.f1 == 0.6667
    assert m1.true_positives == m2.true_positives == 2
    assert m1.false_positives == m2.false_positives == 1
    assert m1.false_negatives == m2.false_negatives == 1
    assert m1.status == m2.status == MetricStatus.VALID


# -----------------------------------------------------------------------------
# 7. Ground-truth provenance metadata
# -----------------------------------------------------------------------------
def test_ground_truth_provenance_metadata():
    """
    Validates that every ground-truth item enforces explicit provenance metadata:
    source, method, evidence, independence declaration, reason, reviewer, confidence.
    """
    item = GroundTruthItem(
        entity="app.services.AuthService",
        label="AFFECTED",
        source=GroundTruthSource.TEST,
        method="failing_test_reproduction",
        evidence=["tests/test_auth.py:45 - TestTokenValidation failed"],
        ground_truth_independent_of_twin=True,
        reviewer="CI Automated Runner",
        confidence=1.0,
        reason="Failing unit test proves downstream behavioral mutation",
    )

    assert item.source == GroundTruthSource.TEST
    assert item.method == "failing_test_reproduction"
    assert len(item.evidence) == 1
    assert item.ground_truth_independent_of_twin is True
    assert item.confidence == 1.0

    # Ensure invalid source type is rejected by Pydantic validation
    with pytest.raises(ValidationError):
        GroundTruthItem(
            entity="app.services.AuthService",
            source="INVALID_FABRICATED_SOURCE",  # Must be one of GroundTruthSource enum
            method="speculation",
            reason="Unsubstantiated",
        )


# -----------------------------------------------------------------------------
# 8. Ground-truth immutability
# -----------------------------------------------------------------------------
def test_ground_truth_immutability():
    """
    Validates that GroundTruthItem and GroundTruthSet cannot be mutated
    after creation, protecting them against post-hoc tampering by algorithms.
    """
    item = GroundTruthItem(
        entity="src.components.Button",
        label="AFFECTED",
        source=GroundTruthSource.MANUAL,
        method="code_review",
        reason="Direct import",
        ground_truth_independent_of_twin=True,
    )

    with pytest.raises(ValidationError):
        item.label = "UNAFFECTED"  # Pydantic frozen model blocks modification

    gt_set = GroundTruthSet(
        case_id="BENCH_IMMUTABLE",
        items=[item],
    )

    with pytest.raises(ValidationError):
        gt_set.items = []  # Pydantic frozen model blocks attribute reassignment


# -----------------------------------------------------------------------------
# 9. Prediction / outcome separation
# -----------------------------------------------------------------------------
def test_prediction_outcome_separation():
    """
    Validates that PredictionRecord remains cleanly separated from OutcomeRecord.
    Observing a physical test run does not modify the original prediction record.
    """
    pred = PredictionRecord(
        prediction_id="pred_99001",
        analysis_id="an_77001",
        change_id="ch_55001",
        predicted_entity_id="art_101",
        predicted_entity_name="src.controllers.OrderController",
        prediction_class="MULTI_HOP",
        evidence_ids=["ev_path_1", "ev_path_2"],
        algorithm_version="twin-8.9.1",
    )

    outcome = OutcomeRecord(
        prediction_id=pred.prediction_id,
        outcome_type="CONFIRMED_REGRESSION",
        source="SELENIUM_E2E",
        evidence_id="e2e_run_log_332",
    )

    assert outcome.prediction_id == pred.prediction_id
    assert pred.algorithm_version == "twin-8.9.1"
    assert pred.predicted_entity_name == "src.controllers.OrderController"
    assert outcome.outcome_type == "CONFIRMED_REGRESSION"


# -----------------------------------------------------------------------------
# 10. No circular dependency between evaluation and impact engine
# -----------------------------------------------------------------------------
def test_no_circular_dependency_between_evaluation_and_impact_engine():
    """
    Validates that the core impact engine (backend/app/services/impact/)
    has zero imports from the evaluation module (app.evaluation).
    This strictly decouples prediction generation from evaluation assessment.
    """
    impact_dir = Path("backend/app/services/impact")
    assert impact_dir.exists(), f"Impact directory not found at {impact_dir}"

    for py_file in impact_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "app.evaluation" not in alias.name, (
                        f"Circular dependency detected: {py_file} imports {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "app.evaluation" not in module, (
                    f"Circular dependency detected: {py_file} imports from {module}"
                )
