"""
Phase 7 — Risk Intelligence & Architecture Guardrails Data Models.
Deterministic data structures for:
- Risk Categories (LOW, MODERATE, HIGH, CRITICAL)
- Confidence Levels (LOW, MEDIUM, HIGH)
- Architecture Guardrail Results (PASS, WARN, VIOLATION, UNKNOWN)
- Risk Factor Items with Provenance Evidence
- Complete Explainable Risk Assessment
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class RiskCategory(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class GuardrailStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    VIOLATION = "VIOLATION"
    UNKNOWN = "UNKNOWN"


class GuardrailSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class GuardrailType(str, Enum):
    FORBIDDEN_DEPENDENCY = "FORBIDDEN_DEPENDENCY"
    LAYER_VIOLATION = "LAYER_VIOLATION"
    BOUNDARY_VIOLATION = "BOUNDARY_VIOLATION"
    CIRCULAR_DEPENDENCY = "CIRCULAR_DEPENDENCY"
    UNEXPECTED_EXTERNAL_DEPENDENCY = "UNEXPECTED_EXTERNAL_DEPENDENCY"
    UNEXPECTED_COUPLING = "UNEXPECTED_COUPLING"
    ARCHITECTURE_BYPASS = "ARCHITECTURE_BYPASS"
    TEST_COVERAGE_DROP = "TEST_COVERAGE_DROP"


class GuardrailResult(BaseModel):
    """
    Deterministic result of evaluating an architectural rule/guardrail.
    """
    rule_id: str
    rule_name: str
    guardrail_type: GuardrailType
    status: GuardrailStatus
    severity: GuardrailSeverity = GuardrailSeverity.HIGH
    affected_entities: List[str] = Field(default_factory=list)
    source: str
    target: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    explanation: str


class RiskFactorType(str, Enum):
    IMPACT_BREADTH = "IMPACT_BREADTH"
    IMPACT_DEPTH = "IMPACT_DEPTH"
    TEST_IMPACT = "TEST_IMPACT"
    ARCHITECTURE_DRIFT = "ARCHITECTURE_DRIFT"
    DEPENDENCY_COUPLING = "DEPENDENCY_COUPLING"
    RUNTIME_ACTIVITY = "RUNTIME_ACTIVITY"
    INCIDENT_HISTORY = "INCIDENT_HISTORY"
    API_SURFACE = "API_SURFACE"
    UNKNOWN_EVIDENCE = "UNKNOWN_EVIDENCE"


class RiskFactorItem(BaseModel):
    """
    Structured fact representing a single risk contributor with provenance evidence.
    """
    factor_id: RiskFactorType
    name: str
    score: float = Field(0.0, ge=0.0, le=100.0, description="Normalized factor score (0-100)")
    weight: float = Field(1.0, ge=0.0, description="Relative weighting factor")
    severity: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    status: str = "OBSERVED"  # OBSERVED, DERIVED, UNKNOWN, NOT_APPLICABLE
    evidence: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)
    description: str


class RiskConfig(BaseModel):
    """
    Configuration options for Risk Assessment and Guardrail analysis.
    """
    max_impact_depth: int = 6
    baseline_path: Optional[str] = None
    environment: Optional[str] = "production"
    include_runtime: bool = True
    include_incidents: bool = True


class RiskAssessmentResult(BaseModel):
    """
    Complete explainable result of a Phase 7 Risk Intelligence analysis.
    Answers: 'How significant is this change, what evidence contributes, and which guardrails are relevant?'
    """
    analysis_id: str
    repository_id: str
    base_snapshot_id: str
    target_snapshot_id: str
    status: str = "completed"
    overall_category: RiskCategory
    overall_score: float = Field(0.0, ge=0.0, le=100.0)
    confidence: ConfidenceLevel
    confidence_score: float = Field(1.0, ge=0.0, le=1.0)
    explanation: str
    risk_factors: List[RiskFactorItem] = Field(default_factory=list)
    guardrail_results: List[GuardrailResult] = Field(default_factory=list)
    affected_components: List[str] = Field(default_factory=list)
    affected_apis: List[str] = Field(default_factory=list)
    affected_tests: List[str] = Field(default_factory=list)
    runtime_evidence: List[str] = Field(default_factory=list)
    incident_evidence: List[str] = Field(default_factory=list)
    unknown_evidence: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
