"""
Phase 4 — Change Impact & Blast Radius Models.
Deterministic data structures for Change Sets, Propagation Rules,
Impact Findings, and Explainable Impact Paths.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
from datetime import datetime


class ChangeType(str, Enum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    RENAMED = "RENAMED"
    MOVED = "MOVED"
    UNKNOWN = "UNKNOWN"


class ChangeKind(str, Enum):
    """Fine-grained change kind taxonomy for deterministic rule dispatch."""
    SYMBOL_MODIFIED = "SYMBOL_MODIFIED"
    SIGNATURE_CHANGED = "SIGNATURE_CHANGED"
    BODY_CHANGED = "BODY_CHANGED"
    SYMBOL_ADDED = "SYMBOL_ADDED"
    SYMBOL_DELETED = "SYMBOL_DELETED"
    API_CONTRACT_CHANGED = "API_CONTRACT_CHANGED"
    HANDLER_CHANGED = "HANDLER_CHANGED"
    DEPENDENCY_CHANGED = "DEPENDENCY_CHANGED"
    FILE_MODIFIED = "FILE_MODIFIED"
    ANY = "ANY"


class PropagationDirection(str, Enum):
    FORWARD = "FORWARD"    # source -> target
    REVERSE = "REVERSE"    # target -> source (e.g., if B calls A, when A changes B is affected)


class ImpactClassification(str, Enum):
    """
    Formal categorization of impact certainty and proximity.
    Separates structural propagation certainty from risk and confidence.
    """
    DIRECT = "DIRECT"                          # Immediate 1-hop incoming dependent
    PROVEN_TRANSITIVE = "PROVEN_TRANSITIVE"    # Multi-hop path (depth >= 2) with proven relationships
    MULTI_HOP = "MULTI_HOP"                    # Canonical alias for transitive propagation
    LIKELY = "LIKELY"                          # Path involving structural alias or heuristic linkage
    POSSIBLE = "POSSIBLE"                      # Dynamic dispatch or unverified reflection boundary
    UNKNOWN = "UNKNOWN"                        # Incomplete coverage or unresolvable relationship


class RelationshipImpactRule(BaseModel):
    """
    Centralized declaration for how typed Digital Twin relationships propagate impact.
    Backward-compatible representation for relationship traversal.
    """
    relationship_type: str
    enabled: bool = True
    direction: PropagationDirection
    impact_semantics: str
    confidence_factor: float = 1.0
    category: str = "COMPONENT"  # COMPONENT, API, TEST, PROCESS, DATABASE, CONFIG


class ImpactPropagationRule(BaseModel):
    """
    Formally specified deterministic propagation rule.
    Maps (change_kind, relationship_type) -> (direction, impact_classification, evidence).
    """
    rule_id: str
    relationship_type: str
    change_kind: str = "ANY"
    direction: PropagationDirection
    impact_classification: ImpactClassification = ImpactClassification.DIRECT
    evidence_requirements: List[str] = Field(default_factory=list)
    confidence_factor: float = Field(ge=0.0, le=1.0, default=1.0)
    max_depth_applicability: int = 5
    rationale: str
    category: str = "COMPONENT"
    enabled: bool = True


class ChangeItem(BaseModel):
    """
    Normalized change item representing a changed file or resolved structural symbol.
    """
    artifact_id: Optional[str] = None
    qualified_name: str
    symbol_name: str
    artifact_type: str  # MODULE, CLASS, METHOD, FUNCTION, API_ENDPOINT, etc.
    source_file: str
    change_type: ChangeType
    base_location: Optional[str] = None
    target_location: Optional[str] = None
    base_hash: Optional[str] = None
    target_hash: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    detection_method: str = "structural_artifact_diff"
    is_symbol_level: bool = True

    @property
    def artifact_name(self) -> str:
        return self.symbol_name


class ChangeSet(BaseModel):
    """
    Normalized change set between baseline Snapshot A and target Snapshot B.
    """
    repository_id: str
    base_snapshot_id: str
    target_snapshot_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "COMPLETED"
    message: Optional[str] = None
    is_verified_zero: bool = False
    diff_mode: str = "SYMBOL_AND_FILE"
    changes: List[ChangeItem] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

    @property
    def total_changes(self) -> int:
        if self.summary and "total_changes" in self.summary:
            return self.summary["total_changes"]
        return len(self.changes)


class ImpactFinding(BaseModel):
    """
    Deterministic finding describing an affected entity and its causal link.
    """
    source_node_id: str
    source_qual_name: str
    impacted_node_id: str
    target_qual_name: str
    target_type: str
    impact_level: int = 1  # 0: CHANGED, 1: DIRECTLY_AFFECTED, 2+: INDIRECTLY_AFFECTED
    relationship_type: str
    path: List[str] = Field(default_factory=list)  # list of qualified names from root to target
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    detection_method: str = "deterministic_graph_traversal"
    rule_id: Optional[str] = None
    impact_classification: Optional[ImpactClassification] = None
    evidence_ids: List[str] = Field(default_factory=list)
    snapshot_id: Optional[str] = None
    provenance: Optional[str] = "DERIVED"
    traversal_depth: int = 1

    @property
    def affected_artifact_name(self) -> str:
        if self.target_qual_name:
            return self.target_qual_name.split(".")[-1]
        return ""


class ImpactPath(BaseModel):
    """
    Explainable causal path from changed root to affected terminal entity.
    """
    root_symbol: str
    target_symbol: str
    nodes: List[str] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)
    depth: int
    confidence: float = 1.0
    terminal_type: str = "COMPONENT"  # COMPONENT, API, TEST, PROCESS


class ImpactSummary(BaseModel):
    """
    Aggregated deterministic metrics for a Change Impact analysis.
    Preserves exact mathematical distinctness: unique_affected vs multi_hop_affected.
    """
    status: Optional[str] = "COMPLETED"
    message: Optional[str] = None
    changed: int = 0
    directly_affected: int = 0
    indirectly_affected: int = 0
    unique_affected: int = 0
    multi_hop_affected: int = 0
    total_evidence_paths: int = 0
    depth_1_paths: int = 0
    depth_2_paths: int = 0
    depth_3_paths: int = 0
    affected_components: int = 0
    affected_services: int = 0
    affected_apis: int = 0
    affected_processes: int = 0
    affected_tests: int = 0
    max_depth_reached: int = 0

    @property
    def root_changes_count(self) -> int:
        return self.changed


class ImpactConfig(BaseModel):
    """
    Configuration options for Change Impact traversal.
    """
    max_depth: int = 5
    include_tests: bool = True
    include_processes: bool = True
    include_apis: bool = True
    custom_rules: Optional[Dict[str, Any]] = None


class ImpactResult(BaseModel):
    """
    Complete, explainable result of a Phase 4 Change Impact analysis.
    """
    analysis_id: str
    repository_id: str
    base_snapshot_id: str
    target_snapshot_id: str
    status: str = "completed"
    message: Optional[str] = None
    summary: ImpactSummary
    changes: List[ChangeItem] = Field(default_factory=list)
    findings: List[ImpactFinding] = Field(default_factory=list)
    paths: List[ImpactPath] = Field(default_factory=list)
    affected_categories: Dict[str, List[str]] = Field(default_factory=dict)
    impact_tree: Optional[Dict[str, Any]] = None
    execution_time_ms: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
