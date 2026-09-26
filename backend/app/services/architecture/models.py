import uuid
from enum import Enum
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DriftCategory(str, Enum):
    FORBIDDEN_DEPENDENCY = "FORBIDDEN_DEPENDENCY"
    LAYER_VIOLATION = "LAYER_VIOLATION"
    CIRCULAR_DEPENDENCY = "CIRCULAR_DEPENDENCY"
    UNEXPECTED_EXTERNAL_DEPENDENCY = "UNEXPECTED_EXTERNAL_DEPENDENCY"
    BOUNDARY_VIOLATION = "BOUNDARY_VIOLATION"
    UNEXPECTED_COUPLING = "UNEXPECTED_COUPLING"
    ARCHITECTURE_BYPASS = "ARCHITECTURE_BYPASS"


class DriftSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class DriftStatus(str, Enum):
    DETECTED = "DETECTED"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"
    ACCEPTED = "ACCEPTED"


class ArchitectureDrift(BaseModel):
    """Represents a single concrete, evidence-based architectural deviation."""
    id: str = Field(default_factory=lambda: f"drift_{uuid.uuid4().hex[:12]}")
    drift_id: Optional[str] = None
    category: str
    severity: str = "HIGH"
    source: str
    target: str
    relationship_type: str = "import"
    relationship: Optional[str] = "import"
    expected_rule: str
    actual_evidence: str
    file_path: str = ""
    file: Optional[str] = ""
    line_number: int = 1
    line: Optional[int] = 1
    snapshot: Optional[str] = None
    confidence: float = Field(default=0.98, ge=0.0, le=1.0)
    status: str = "DETECTED"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def model_post_init(self, __context: Any) -> None:
        if not self.drift_id:
            self.drift_id = self.id
        if not self.file:
            self.file = self.file_path
        elif not self.file_path:
            self.file_path = self.file
        if self.line is not None and self.line != 1:
            self.line_number = self.line
        elif self.line_number is not None:
            self.line = self.line_number
        if self.relationship:
            self.relationship_type = self.relationship


class ArchitectureRule(BaseModel):
    id: str
    name: str
    category: str = "LAYER_VIOLATION"
    severity: str = "HIGH"
    source: Optional[str] = None
    target: Optional[str] = None
    forbidden: bool = True
    forbidden_imports: List[str] = Field(default_factory=list)
    description: str = ""


class LayerDefinition(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = ""
    modules: List[str] = Field(default_factory=list)
    allowed_dependencies: List[str] = Field(default_factory=list)
    forbidden_dependencies: List[str] = Field(default_factory=list)


class ArchitectureBaselineSpec(BaseModel):
    version: str = "1.0.0"
    project: str = ""
    description: str = ""
    layers: Dict[str, LayerDefinition] = Field(default_factory=dict)
    rules: List[ArchitectureRule] = Field(default_factory=list)


class ArchitectureConformanceReport(BaseModel):
    """
    Architecture Conformance Report.
    Note: Conformance percentage is a structural measurement and is explicitly
    separate from project progress / execution percentage.
    """
    id: str = Field(default_factory=lambda: f"rep_{uuid.uuid4().hex[:12]}")
    report_id: Optional[str] = None
    repository_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    expected_boundaries: int = 0
    validated_boundaries: int = 0
    violations_count: int = 0
    violations: Optional[int] = 0
    circular_dependencies: int = 0
    circular_count: Optional[int] = 0
    unexpected_dependencies: int = 0
    unexpected_count: Optional[int] = 0
    conformance_percentage: float = 100.0
    drifts: List[ArchitectureDrift] = Field(default_factory=list)
    baseline_version: str = "1.0.0"
    summary: str = ""
    evaluated_at: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def model_post_init(self, __context: Any) -> None:
        if not self.report_id:
            self.report_id = self.id
        if self.violations:
            self.violations_count = self.violations
        else:
            self.violations = self.violations_count
        if self.circular_dependencies:
            self.circular_count = self.circular_dependencies
        else:
            self.circular_dependencies = self.circular_count or 0
        if self.unexpected_dependencies:
            self.unexpected_count = self.unexpected_dependencies
        else:
            self.unexpected_dependencies = self.unexpected_count or 0


class SnapshotComparisonResult(BaseModel):
    """Represents comparison between two snapshots to detect architecture drift changes."""
    snapshot_a: str
    snapshot_b: str
    new_drifts: List[ArchitectureDrift] = Field(default_factory=list)
    resolved_drifts: List[ArchitectureDrift] = Field(default_factory=list)
    unaltered_drifts: List[ArchitectureDrift] = Field(default_factory=list)
    conformance_a: float = 100.0
    conformance_b: float = 100.0
    conformance_delta: float = 0.0
    summary: str = ""


class SnapshotArchitectureComparison(BaseModel):
    repository_id: str
    from_snapshot_id: str
    to_snapshot_id: str
    conformance_before: float
    conformance_after: float
    conformance_delta: float
    new_drifts: List[ArchitectureDrift] = Field(default_factory=list)
    resolved_drifts: List[ArchitectureDrift] = Field(default_factory=list)
    persistent_drifts: List[ArchitectureDrift] = Field(default_factory=list)
    summary: str = ""


# Aliases for compatibility
ArchitectureDriftItem = ArchitectureDrift
BaselineLayer = LayerDefinition
BaselineRule = ArchitectureRule
ArchitectureBaseline = ArchitectureBaselineSpec
