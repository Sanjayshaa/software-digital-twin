"""
Phase 8.8 — Evidence Provenance and Twin Knowledge Contracts.
Deterministic schemas for canonical evidence provenance and explainability.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class Provenance(str, Enum):
    """
    Formal categorization of knowledge source provenance.
    Separate from probabilistic confidence score.
    """
    OBSERVED = "OBSERVED"     # Directly extracted from source code, AST, Git commit, or runtime batch
    DERIVED = "DERIVED"       # Deterministically computed through graph traversal, AST call chains, diffing
    INFERRED = "INFERRED"     # Heuristic structural/naming convention linkage
    SIMULATED = "SIMULATED"   # Virtual scenario what-if prediction; strictly isolated from production twin
    UNKNOWN = "UNKNOWN"       # Gap in coverage or unresolvable relationship


class CanonicalEvidence(BaseModel):
    """
    Canonical evidence response representation.
    Answers: 'Why did the system produce this result?'
    """
    evidence_id: str
    repository_id: str
    snapshot_id: Optional[str] = None
    evidence_type: str        # e.g., "AST_CALL", "FILE_DIFF", "RUNTIME_CORRELATION", "TEST_ASSERTION"
    source_entity_id: str
    source_location: Optional[str] = None
    relationship_type: Optional[str] = None
    provenance: Provenance
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    justification: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ImpactPathFinding(BaseModel):
    """
    Deterministic impact path finding exposing full provenance chain.
    """
    root_change: Dict[str, Any]
    affected_entity: Dict[str, Any]
    relationship_path: List[str]
    relationship_types: List[str]
    depth: int
    snapshot_id: str
    evidence_ids: List[str]
    provenance: Provenance = Provenance.DERIVED
    confidence: float = 1.0
    explanation: str


class TwinKnowledgeOverview(BaseModel):
    """Authoritative repository knowledge summary with evidence references."""
    repository_id: str
    repository_name: str
    owner_id: Optional[str] = None
    environment: str
    default_branch: str
    total_snapshots: int
    available_snapshots: List[Dict[str, Any]]
    total_artifacts: int
    total_relationships: int
    total_tests: int
    total_apis: int
    total_incidents: int
    total_scenarios: int
    evidence_count: int
    provenance: Provenance = Provenance.OBSERVED


class TwinKnowledgeQueryResult(BaseModel):
    """Deterministic, evidence-grounded response to Ask Twin queries."""
    query: str
    intent: str
    answer: str
    evidence_ids: List[str]
    provenance: Provenance
    confidence: float
    grounded_entities: List[Dict[str, Any]]
    suggested_actions: List[Dict[str, str]]
