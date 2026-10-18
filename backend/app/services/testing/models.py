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


class TestCoverageClaim(str, Enum):
    """
    Formal claims the Digital Twin makes regarding test coverage and impact.
    The engine may only make a stronger claim when explicit evidence supports it.
    """
    NO_TEST_RELATIONSHIP_FOUND = "NO_TEST_RELATIONSHIP_FOUND"
    # Claim: Graph traversal explored all AST paths to depth limit; 0 test nodes were reachable.
    
    NO_AUTOMATED_TEST_EXISTS = "NO_AUTOMATED_TEST_EXISTS"
    # Strong Claim: Zero automated tests exist in the entire repository.
    # Prerequisite: Total mapped tests in repository == 0.
    
    TEST_EXISTS_BUT_COVERAGE_IS_UNKNOWN = "TEST_EXISTS_BUT_COVERAGE_IS_UNKNOWN"
    # Claim: Tests exist in repository (e.g. proximity or convention), but static analyzer cannot prove execution path.
    # Prerequisite: Sibling tests or name stem matches exist without verified AST call/import edge.
    
    TEST_EXISTS_AND_IS_UNAFFECTED = "TEST_EXISTS_AND_IS_UNAFFECTED"
    # Strong Claim: Test artifact exists, its dependency closure is mapped, and does not intersect change blast radius.
    # Prerequisite: Applies strictly to TEST ARTIFACTS, never to changed production artifacts.
    
    TEST_IS_AFFECTED = "TEST_IS_AFFECTED"
    # Strong Claim: Proven causal path connects a changed artifact to this test.
    # Prerequisite: Applies strictly to TEST ARTIFACTS with verified propagation path.


class ChangedArtifactEvaluation(BaseModel):
    """
    Semantic evaluation of a changed artifact's test coverage status.
    Guarantees that a changed production artifact is NEVER classified as UNAFFECTED.
    """
    artifact_id: str
    name: str
    qualified_name: str
    artifact_type: str
    location: str
    change_type: str
    coverage_claim: TestCoverageClaim
    claim_rationale: str
    evidence_category: str  # DIRECT_TEST, INDIRECT_TEST, NO_RELATIONSHIP, UNRESOLVED_DEPENDENCY, FRAMEWORK_CONVENTION, NO_TESTS_IN_REPO
    direct_test_count: int = 0
    indirect_test_count: int = 0
    associated_tests: List[str] = Field(default_factory=list)
    traversal_depth_reached: int = 0
    downstream_entities_count: int = 0
    cannot_be_unaffected_proof: str = "A changed source artifact can never be classified as UNAFFECTED; absent test path yields UNKNOWN_COVERAGE."


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
    coverage_claim: TestCoverageClaim = TestCoverageClaim.TEST_IS_AFFECTED
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
    classification: TestImpactClassification = TestImpactClassification.UNKNOWN_COVERAGE
    coverage_claim: TestCoverageClaim = TestCoverageClaim.NO_TEST_RELATIONSHIP_FOUND
    reason_code: str = "NO_TEST_RELATIONSHIP"
    explanation: str = "No TESTS relationship was discovered for this affected artifact."
    reason: str = "No direct or indirect test relationships detected for this changed entity."
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    cannot_be_unaffected_proof: str = "Absence of a test path means coverage is UNKNOWN, NOT that the changed code is safe or UNAFFECTED."


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
    changed_artifact_evaluations: List[ChangedArtifactEvaluation] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
