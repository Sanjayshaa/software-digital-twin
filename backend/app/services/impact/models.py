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


class PropagationDirection(str, Enum):
    FORWARD = "FORWARD"    # source -> target
    REVERSE = "REVERSE"    # target -> source (e.g., if B calls A, when A changes B is affected)


class RelationshipImpactRule(BaseModel):
    """
    Centralized declaration for how typed Digital Twin relationships propagate impact.
    """
    relationship_type: str
    enabled: bool = True
    direction: PropagationDirection
    impact_semantics: str
    confidence_factor: float = 1.0
    category: str = "COMPONENT"  # COMPONENT, API, TEST, PROCESS, DATABASE, CONFIG


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


class ChangeSet(BaseModel):
    """
    Normalized change set between baseline Snapshot A and target Snapshot B.
    """
    repository_id: str
    base_snapshot_id: str
    target_snapshot_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    changes: List[ChangeItem] = Field(default_factory=list)
    summary: Dict[str, int] = Field(default_factory=dict)


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
    """
    changed: int = 0
    directly_affected: int = 0
    indirectly_affected: int = 0
    affected_components: int = 0
    affected_services: int = 0
    affected_apis: int = 0
    affected_processes: int = 0
    affected_tests: int = 0
    max_depth_reached: int = 0


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
    execution_time_ms: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
