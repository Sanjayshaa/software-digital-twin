"""
Phase 6 — Test Impact Intelligence Data Models.
Deterministic data structures for Test Impact Analysis:
- TestImpactClassification: DIRECTLY_AFFECTED, INDIRECTLY_AFFECTED, UNAFFECTED, UNKNOWN_COVERAGE
- TestEvidenceStatus: OBSERVED, DERIVED, INFERRED, UNKNOWN
- TestImpactItem: individual test finding with explainable causal path and relationships
- UnknownCoverageItem: changed entity without detected test coverage
- TestImpactSummary: aggregated metrics
- TestImpactResult: complete analysis result
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TestImpactClassification(str, Enum):
    DIRECTLY_AFFECTED = "DIRECTLY_AFFECTED"      # Test directly targets or asserts on the changed entity
    INDIRECTLY_AFFECTED = "INDIRECTLY_AFFECTED"  # Test targets a component reachable from the changed entity
    UNAFFECTED = "UNAFFECTED"                    # Test mapped in repository, but outside change blast radius
    UNKNOWN_COVERAGE = "UNKNOWN_COVERAGE"        # Changed entity has no mapped tests covering it


class TestEvidenceStatus(str, Enum):
    OBSERVED = "OBSERVED"   # Explicit test-to-target relationship directly declared in codebase
    DERIVED = "DERIVED"     # Deterministically derived via multi-hop graph traversal (CALLS, IMPORTS, etc.)
    INFERRED = "INFERRED"   # Heuristic naming or structural proximity linkage
    UNKNOWN = "UNKNOWN"     # No coverage or linkage recorded


class TestImpactItem(BaseModel):
    """
    Structured fact representing a test and why it is affected by the code change.
    """
    test_id: Optional[str] = None
    test_name: str
    qualified_name: str
    location: str
    classification: TestImpactClassification
    evidence_status: TestEvidenceStatus = TestEvidenceStatus.DERIVED
    reason: str
    impact_path: List[str] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)
    depth: int = 1
    confidence: float = 1.0


class UnknownCoverageItem(BaseModel):
    """
    Changed entity that lacks test coverage in the digital twin.
    """
    artifact_id: Optional[str] = None
    name: str
    qualified_name: str
    artifact_type: str
    location: str
    change_type: str
    reason: str = "No direct or indirect test relationships detected for this changed entity."


class TestImpactSummary(BaseModel):
    """
    Aggregated deterministic counts for test impact analysis.
    """
    total_tests_mapped: int = 0
    potentially_affected_count: int = 0
    directly_affected_count: int = 0
    indirectly_affected_count: int = 0
    unaffected_count: int = 0
    unknown_coverage_count: int = 0


class TestImpactConfig(BaseModel):
    """
    Configuration options for test impact calculation.
    """
    max_depth: int = 6
    include_indirect: bool = True
    include_unaffected: bool = True


class TestImpactResult(BaseModel):
    """
    Complete explainable result of a Phase 6 Test Impact analysis run.
    """
    analysis_id: str
    repository_id: str
    base_snapshot_id: str
    target_snapshot_id: str
    status: str = "completed"
    message: Optional[str] = None
    summary: TestImpactSummary
    affected_tests: List[TestImpactItem] = Field(default_factory=list)
    unaffected_tests: List[TestImpactItem] = Field(default_factory=list)
    unknown_coverage: List[UnknownCoverageItem] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
