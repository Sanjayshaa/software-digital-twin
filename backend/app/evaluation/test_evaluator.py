"""
Phase 8.9 — Test Selection & Impact Evaluator.
Evaluates test impact selection separately from physical test execution.
Enforces the 5-state test taxonomy and the safe selection policy:
RUN: AFFECTED + UNKNOWN
SKIP: only proven UNAFFECTED
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
from datetime import datetime


class TestSelectionDecision(str, Enum):
    RUN = "RUN"
    SKIP = "SKIP"


class TestSelectionClaim(str, Enum):
    AFFECTED = "AFFECTED"
    UNAFFECTED = "UNAFFECTED"
    UNKNOWN = "UNKNOWN"


class TestEvaluationItem(BaseModel):
    """Evaluation item for a single test suite or test case under change."""
    test_id: str
    test_name: str
    test_location: Optional[str] = None
    claim: TestSelectionClaim
    decision: TestSelectionDecision
    evidence_path: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    rationale: str
    physical_execution_result: Optional[str] = None  # PASSED, FAILED, SKIPPED, NOT_RUN


class TestImpactEvaluationReport(BaseModel):
    """
    Comprehensive test selection evaluation report.
    Never alters predictions after physical execution.
    """
    repository_id: str
    base_snapshot_id: str
    target_snapshot_id: str
    total_tests_in_repo: int
    affected_tests_count: int
    unaffected_tests_count: int
    unknown_coverage_count: int
    safe_to_run_count: int     # AFFECTED + UNKNOWN
    safe_to_skip_count: int    # only proven UNAFFECTED
    test_reduction_percentage: float
    items: List[TestEvaluationItem] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class TestImpactEvaluator:
    """
    Evaluates test selection safety and test suite reduction without executing tests.
    """

    @classmethod
    def evaluate_test_selection(
        cls,
        affected_tests: List[Dict[str, Any]],
        unaffected_tests: List[Dict[str, Any]],
        unknown_coverage_count: int,
        repository_id: str,
        base_snapshot_id: str,
        target_snapshot_id: str,
    ) -> TestImpactEvaluationReport:
        items: List[TestEvaluationItem] = []

        # 1. Affected tests
        for t in affected_tests:
            t_id = t.get("test_id") or t.get("id") or t.get("test_name")
            items.append(
                TestEvaluationItem(
                    test_id=t_id,
                    test_name=t.get("test_name", "Unknown Test"),
                    test_location=t.get("location"),
                    claim=TestSelectionClaim.AFFECTED,
                    decision=TestSelectionDecision.RUN,
                    evidence_path=t.get("impact_path") or [],
                    evidence_ids=[f"ev_test_{t_id[:8]}" if t_id else "ev_test_aff"],
                    confidence=1.0,
                    rationale="Test assertion surface or imported module connects directly to modified AST symbol.",
                )
            )

        # 2. Unaffected tests
        for t in unaffected_tests:
            t_id = t.get("test_id") or t.get("id") or t.get("test_name")
            items.append(
                TestEvaluationItem(
                    test_id=t_id,
                    test_name=t.get("test_name", "Unknown Test"),
                    test_location=t.get("location"),
                    claim=TestSelectionClaim.UNAFFECTED,
                    decision=TestSelectionDecision.SKIP,
                    evidence_path=[],
                    evidence_ids=[f"ev_unaff_{t_id[:8]}" if t_id else "ev_test_unaff"],
                    confidence=1.0,
                    rationale="Reverse dependency traversal confirms test AST footprint is completely disjoint from change set.",
                )
            )

        total_catalog = len(affected_tests) + len(unaffected_tests)
        safe_to_run = len(affected_tests) + unknown_coverage_count
        safe_to_skip = len(unaffected_tests)

        # Reduction % based on tests that can safely be skipped vs total catalog
        reduction_pct = 0.0
        if total_catalog > 0:
            reduction_pct = round((safe_to_skip / total_catalog) * 100, 2)

        return TestImpactEvaluationReport(
            repository_id=repository_id,
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
            total_tests_in_repo=total_catalog,
            affected_tests_count=len(affected_tests),
            unaffected_tests_count=len(unaffected_tests),
            unknown_coverage_count=unknown_coverage_count,
            safe_to_run_count=safe_to_run,
            safe_to_skip_count=safe_to_skip,
            test_reduction_percentage=reduction_pct,
            items=items,
        )
