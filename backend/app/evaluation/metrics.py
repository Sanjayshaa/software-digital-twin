"""
Phase 8.9.1 — Evaluation Metrics Calculator with Anti-Circularity Guards.
Refuses to compute accuracy metrics if ground truth is derived from the Twin.
Explicitly distinguishes between PATCH_ONLY, INDEPENDENT_LABELS, and NO_GROUND_TRUTH modes.
"""

from typing import Set, List, Dict, Any, Optional
from app.evaluation.models import (
    EvaluationMetrics,
    MetricStatus,
    EvaluationMode,
    GroundTruthSet,
)


def compute_metrics(
    predicted_entities: Set[str],
    ground_truth_entities: Optional[Set[str]] = None,
    universe_entities: Optional[Set[str]] = None,
    evidence_backed_count: int = 0,
    path_depths: Optional[List[int]] = None,
    runtime_ms: float = 0.0,
    is_independent: bool = True,
    evaluation_mode: EvaluationMode = EvaluationMode.INDEPENDENT_LABELS,
    ground_truth_set: Optional[GroundTruthSet] = None,
) -> EvaluationMetrics:
    """
    Computes deterministic confusion matrix and metrics against ground truth.
    Strictly enforces the Non-Circularity Invariant:
    If ground truth is not independent of Twin predictions, accuracy calculation is refused.
    """
    if ground_truth_entities is None:
        ground_truth_entities = set()

    # 1. Inspect GroundTruthSet if provided
    if ground_truth_set is not None:
        evaluation_mode = ground_truth_set.evaluation_mode
        is_independent = ground_truth_set.validate_independence()
        ground_truth_entities = ground_truth_set.get_qual_names()

    pred_count = len(predicted_entities)
    gt_count = len(ground_truth_entities)

    # Calculate evidence coverage & average path depth
    ev_coverage = 0.0
    if pred_count > 0:
        ev_coverage = round(evidence_backed_count / pred_count, 4)

    avg_depth = 0.0
    if path_depths and len(path_depths) > 0:
        avg_depth = round(sum(path_depths) / len(path_depths), 2)

    # 2. Guard: Mode C (NO_GROUND_TRUTH)
    if evaluation_mode == EvaluationMode.NO_GROUND_TRUTH:
        return EvaluationMetrics(
            status=MetricStatus.NO_GROUND_TRUTH,
            rejection_reason="Evaluation executed in NO_GROUND_TRUTH mode. Predictions reported without accuracy calculation.",
            evaluation_mode=evaluation_mode,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            total_predicted=pred_count,
            total_ground_truth=0,
            evidence_backed_coverage=ev_coverage,
            average_path_depth=avg_depth,
            runtime_ms=runtime_ms,
            notes="Predictions only. Precision/Recall/F1 omitted by protocol.",
        )

    # 3. Guard: Anti-Circularity Check
    if not is_independent:
        return EvaluationMetrics(
            status=MetricStatus.INVALID_GROUND_TRUTH,
            rejection_reason="Ground truth is derived from Digital Twin predictions. Accuracy calculation refused to prevent circular metric contamination.",
            evaluation_mode=evaluation_mode,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            total_predicted=pred_count,
            total_ground_truth=gt_count,
            evidence_backed_coverage=ev_coverage,
            average_path_depth=avg_depth,
            runtime_ms=runtime_ms,
            notes="INVALID_FOR_TWIN_ACCURACY: Circular dependency detected between Twin predictions and ground truth labels.",
        )

    # 4. Guard: Insufficient Ground Truth
    if gt_count == 0:
        return EvaluationMetrics(
            status=MetricStatus.GROUND_TRUTH_INSUFFICIENT,
            rejection_reason="Ground truth set is empty. Accuracy metrics cannot be established.",
            evaluation_mode=evaluation_mode,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            true_positives=0,
            false_positives=pred_count,
            false_negatives=0,
            total_predicted=pred_count,
            total_ground_truth=0,
            evidence_backed_coverage=ev_coverage,
            average_path_depth=avg_depth,
            runtime_ms=runtime_ms,
            notes="GROUND TRUTH INSUFFICIENT: No independently verified ground-truth labels available for this commit pair. Precision, recall, and F1 are undefined (0.0).",
        )

    # 5. Compute Confusion Matrix
    tp_set = predicted_entities.intersection(ground_truth_entities)
    fp_set = predicted_entities.difference(ground_truth_entities)
    fn_set = ground_truth_entities.difference(predicted_entities)

    tp = len(tp_set)
    fp = len(fp_set)
    fn = len(fn_set)

    tn = 0
    if universe_entities is not None:
        tn = len(universe_entities.difference(predicted_entities).difference(ground_truth_entities))

    precision = round(tp / pred_count, 4) if pred_count > 0 else 0.0
    recall = round(tp / gt_count, 4) if gt_count > 0 else 0.0
    f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0.0 else 0.0

    # 6. Set Status based on EvaluationMode
    if evaluation_mode == EvaluationMode.PATCH_ONLY:
        status = MetricStatus.PARTIAL_PATCH_ONLY
        notes = "Evaluated against directly modified entities only. Does NOT represent true change impact accuracy."
    else:
        status = MetricStatus.VALID
        notes = "Evaluated against independently verified ground truth labels."

    return EvaluationMetrics(
        status=status,
        evaluation_mode=evaluation_mode,
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        total_predicted=pred_count,
        total_ground_truth=gt_count,
        evidence_backed_coverage=ev_coverage,
        average_path_depth=avg_depth,
        runtime_ms=runtime_ms,
        notes=notes,
    )
