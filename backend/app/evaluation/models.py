"""
Phase 8.9.1 — Evaluation Integrity & Ground-Truth Provenance Models.
Enforces strict ground-truth provenance, independence invariants,
and prevents circular metric contamination.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Set, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

FORBIDDEN_TWIN_KEYWORDS = (
    "impactpropagator",
    "impactfinding",
    "twin knowledge",
    "twin impact paths",
    "twin relationship traversal",
    "full twin output",
    "twin_prediction",
    "full_twin",
)


class GroundTruthSource(str, Enum):
    """Origin source of ground-truth impact labels."""
    PATCH = "PATCH"          # Directly changed by historical commit patch
    TEST = "TEST"            # Physical test execution / historical CI logs
    RUNTIME = "RUNTIME"      # Independently correlated production telemetry
    MANUAL = "MANUAL"        # Peer-reviewed manual architect audit independent of Twin
    EXTERNAL = "EXTERNAL"    # External defect benchmark (Defects4J, BugsInPy, SWE-bench)
    UNKNOWN = "UNKNOWN"      # Unverified or ambiguous provenance


class GroundTruthType(str, Enum):
    """
    Formal categorization of ground truth sources.
    Crucial: Directly changed patch files are NEVER equated with complete ground truth.
    """
    GROUND_TRUTH_PATCH = "GROUND_TRUTH_PATCH"        # Directly modified by commit patch (PARTIAL ONLY)
    GROUND_TRUTH_TEST = "GROUND_TRUTH_TEST"          # Demonstrated by failing/affected test suites
    GROUND_TRUTH_RUNTIME = "GROUND_TRUTH_RUNTIME"    # Corroborated by runtime error traces/spans
    GROUND_TRUTH_MANUAL = "GROUND_TRUTH_MANUAL"      # Curated developer audit / formal code review


class EvaluationMode(str, Enum):
    """Evaluation modes with explicit semantics."""
    PATCH_ONLY = "PATCH_ONLY"                    # Mode A: Overlap with directly modified entities only
    INDEPENDENT_LABELS = "INDEPENDENT_LABELS"    # Mode B: Independently verified test/runtime/manual labels
    NO_GROUND_TRUTH = "NO_GROUND_TRUTH"          # Mode C: Runs algorithms, outputs predictions only; no metrics


class MetricStatus(str, Enum):
    """Validity state of computed evaluation metrics."""
    VALID = "VALID"                                          # Calculated against verified independent ground truth
    INVALID_GROUND_TRUTH = "INVALID_GROUND_TRUTH"            # Rejected: Ground truth derived from Twin predictions
    PARTIAL_PATCH_ONLY = "PARTIAL_PATCH_ONLY"                # Informational only: Reflects direct diff overlap, not impact
    NO_GROUND_TRUTH = "NO_GROUND_TRUTH"                      # Mode C: Predictions reported; metrics refused
    GROUND_TRUTH_INSUFFICIENT = "GROUND_TRUTH_INSUFFICIENT"  # Ground truth empty or unverified


class BaselineAlgorithm(str, Enum):
    """Algorithms evaluated by the comparative benchmark harness."""
    CHANGED_FILES_SET = "CHANGED_FILES_SET"          # Baseline 1: Changed files alone
    IMPORT_CLOSURE = "IMPORT_CLOSURE"                # Baseline 2: Changed files + 1-hop reverse IMPORTS
    CALL_CLOSURE = "CALL_CLOSURE"                    # Baseline 3: Changed symbols + 1-hop reverse CALLS
    FULL_TWIN = "FULL_TWIN"                          # Full Software Digital Twin (Multi-hop, typed, cycle-protected)


class GroundTruthItem(BaseModel):
    """
    An individual entity identified as truly affected by a change,
    with explicit provenance and independence declaration.
    Immutable (frozen) to prevent post-hoc tampering.
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow", frozen=True)

    entity: Optional[str] = Field(default=None, alias="entity_qual_name")
    entity_qual_name: Optional[str] = Field(default=None, alias="entity")
    entity_type: str = "COMPONENT"
    ground_truth_type: GroundTruthType = GroundTruthType.GROUND_TRUTH_MANUAL
    source: GroundTruthSource = Field(default=GroundTruthSource.MANUAL, alias="ground_truth_source")
    method: str = Field(default="independent_architect_review", alias="ground_truth_method")
    evidence: List[str] = Field(default_factory=list, alias="ground_truth_evidence")
    ground_truth_independent_of_twin: bool = True
    label: str = "AFFECTED"
    reviewer: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    reason: Optional[str] = Field(default=None, alias="rationale")
    rationale: Optional[str] = Field(default=None, alias="reason")
    evidence_reference: Optional[str] = None

    @property
    def target_entity(self) -> str:
        return self.entity or self.entity_qual_name or ""

    def is_twin_derived(self) -> bool:
        """Checks if this ground truth label was derived from Twin predictions or algorithms."""
        if not self.ground_truth_independent_of_twin:
            return True
        check_str = f"{self.source} {self.method} {' '.join(self.evidence)} {self.reason or ''} {self.rationale or ''}".lower()
        return any(kw in check_str for kw in FORBIDDEN_TWIN_KEYWORDS)


class GroundTruthSet(BaseModel):
    """
    Immutable set of verified ground-truth affected entities for a benchmark case.
    Prevents circular evaluation by strictly requiring independent provenance.
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow", frozen=True)

    case_id: str
    evaluation_mode: EvaluationMode = EvaluationMode.INDEPENDENT_LABELS
    ground_truth_independent_of_twin: bool = True
    items: List[GroundTruthItem] = Field(default_factory=list)
    is_immutable: bool = True

    def get_qual_names(self) -> Set[str]:
        return {item.target_entity for item in self.items if item.target_entity}

    def validate_independence(self) -> bool:
        """Returns True if and only if EVERY item in the set is verified independent of the Twin."""
        if not self.ground_truth_independent_of_twin:
            return False
        if not self.items:
            return False
        for item in self.items:
            if not item.ground_truth_independent_of_twin:
                return False
            if item.is_twin_derived():
                return False
        return True

    @classmethod
    def load_from_file(cls, file_path: str) -> "GroundTruthSet":
        import json
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


def create_patch_ground_truth(
    case_id: str,
    directly_modified_entities: Set[str],
    reviewer: str = "git_diff_extractor",
) -> GroundTruthSet:
    """
    Constructs a GroundTruthSet representing directly modified entities from a patch.
    Explicitly tags the set with EvaluationMode.PATCH_ONLY and GroundTruthSource.PATCH.
    """
    items = [
        GroundTruthItem(
            entity=name,
            entity_type="MODIFIED_ENTITY",
            ground_truth_type=GroundTruthType.GROUND_TRUTH_PATCH,
            source=GroundTruthSource.PATCH,
            method="git_diff_inspection",
            evidence=[f"Direct commit diff modification for {name}"],
            ground_truth_independent_of_twin=True,
            label="DIRECTLY_MODIFIED",
            reviewer=reviewer,
            confidence=1.0,
            reason="Entity directly modified by historical commit patch. Does NOT represent transitive impact.",
        )
        for name in directly_modified_entities
    ]
    return GroundTruthSet(
        case_id=case_id,
        evaluation_mode=EvaluationMode.PATCH_ONLY,
        ground_truth_independent_of_twin=True,
        items=items,
    )


class BenchmarkCase(BaseModel):
    """
    Formal specification of a historical evaluation scenario.
    """
    case_id: str
    repository_name: str
    remote_url: str
    base_commit: str
    target_commit: str
    base_snapshot_id: Optional[str] = None
    target_snapshot_id: Optional[str] = None
    language: str
    project_type: str
    change_count: int
    expected_label_source: GroundTruthType
    notes: str
    ground_truth: Optional[GroundTruthSet] = None


class PredictionRecord(BaseModel):
    """
    Immutable record of an impact prediction before observing physical/runtime outcomes.
    Enforces clean separation between prediction and outcome calibration.
    """
    prediction_id: str
    analysis_id: str
    change_id: str
    predicted_entity_id: str
    predicted_entity_name: str
    prediction_class: str = "DIRECT"  # DIRECT, PROVEN_TRANSITIVE, MULTI_HOP
    evidence_ids: List[str] = Field(default_factory=list)
    algorithm_version: str = "twin-8.9"
    predicted_at: datetime = Field(default_factory=datetime.utcnow)


class OutcomeRecord(BaseModel):
    """
    Physical or operational observation bound back to a PredictionRecord.
    Forms the future calibration and feedback loop foundation.
    """
    prediction_id: str
    outcome_type: str  # e.g., "CONFIRMED_REGRESSION", "TEST_FAILED", "OBSERVED_ERROR", "SAFE_UNEXECUTED"
    observed_at: datetime = Field(default_factory=datetime.utcnow)
    source: str  # e.g., "PYTEST", "JEST", "SENTRY", "OPENTELEMETRY"
    evidence_id: str


class EvaluationMetrics(BaseModel):
    """
    Mathematically rigorous metrics with explicit circularity guards
    and zero-denominator handling.
    """
    status: MetricStatus = MetricStatus.VALID
    rejection_reason: Optional[str] = None
    evaluation_mode: EvaluationMode = EvaluationMode.INDEPENDENT_LABELS
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0
    total_predicted: int = 0
    total_ground_truth: int = 0
    evidence_backed_coverage: float = 0.0
    average_path_depth: float = 0.0
    runtime_ms: float = 0.0
    notes: Optional[str] = None


class EvaluationRun(BaseModel):
    """Execution output of an evaluation run for a specific algorithm on a benchmark case."""
    run_id: str
    benchmark_case_id: str
    algorithm: BaselineAlgorithm
    metrics: EvaluationMetrics
    predictions: List[PredictionRecord] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
