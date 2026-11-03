"""
Phase 2 — Provider-Neutral Pull Request & CI Integration Models.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class PREventPayload(BaseModel):
    provider: str = Field("github", description="VCS provider: 'github', 'gitlab', or 'generic'")
    repository_id: Optional[str] = Field(None, description="TwinCore internal repository UUID")
    external_repository: Optional[str] = Field(None, description="External repo identifier e.g. 'owner/repo'")
    pull_request_number: int = Field(..., ge=1, description="Pull request number")
    title: Optional[str] = Field(None, description="PR title")
    base_branch: str = Field(..., description="Target branch (e.g. 'main')")
    base_commit_sha: str = Field(..., description="Base Git commit SHA")
    head_branch: str = Field(..., description="Source feature branch")
    head_commit_sha: str = Field(..., description="Head Git commit SHA")
    event_type: str = Field("opened", description="Event action: 'opened', 'synchronize', 'reopened', 'closed'")
    sender: Optional[str] = Field(None, description="Sender username or identity")
    received_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    delivery_id: Optional[str] = Field(None, description="Webhook delivery GUID for deduplication")


class CIStatusPolicy(BaseModel):
    block_on_failed_tests: bool = Field(True, description="Mark CI as BLOCKED if test failures are detected")
    block_on_reconstruction_failure: bool = Field(True, description="Mark CI as BLOCKED if snapshot reconstruction fails")
    block_on_ancestry_failure: bool = Field(True, description="Mark CI as BLOCKED if base commit is not ancestor of head")
    review_on_high_risk: bool = Field(True, description="Mark CI as REVIEW_REQUIRED if blast radius score exceeds threshold")
    review_on_unknown_coverage: bool = Field(True, description="Mark CI as REVIEW_REQUIRED if unmapped code changes exist")
    high_risk_threshold: float = Field(70.0, description="Blast radius risk score threshold triggering REVIEW_REQUIRED")


class TestImpactReport(BaseModel):
    tests_selected: List[str] = Field(default_factory=list, description="Tests selected for execution based on causal impact")
    tests_executed: List[str] = Field(default_factory=list, description="Tests that actually executed")
    tests_passed: List[str] = Field(default_factory=list, description="Tests confirmed passed")
    tests_failed: List[str] = Field(default_factory=list, description="Tests confirmed failed")
    tests_not_executed: List[str] = Field(default_factory=list, description="Selected tests that did not run")
    tests_unknown_coverage: List[Dict[str, Any]] = Field(default_factory=list, description="Modified entities with unknown test coverage")
    missing_test_relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Impacted components lacking test linkages")


class PRImpactReport(BaseModel):
    pull_request_number: int
    repository: str
    repository_id: str
    base_commit_sha: str
    head_commit_sha: str
    base_snapshot_id: Optional[str] = None
    target_snapshot_id: Optional[str] = None
    status: str  # QUEUED, SNAPSHOTS_PENDING, ANALYZING, COMPLETE, NO_CHANGE, REVIEW_REQUIRED, FAILED
    ci_recommendation: str  # PASS, REVIEW_REQUIRED, BLOCKED
    changed_entities: List[Dict[str, Any]] = Field(default_factory=list)
    directly_affected_entities: List[Dict[str, Any]] = Field(default_factory=list)
    indirectly_affected_entities: List[Dict[str, Any]] = Field(default_factory=list)
    affected_apis: List[Dict[str, Any]] = Field(default_factory=list)
    affected_services: List[Dict[str, Any]] = Field(default_factory=list)
    affected_processes: List[Dict[str, Any]] = Field(default_factory=list)
    affected_tests: List[Dict[str, Any]] = Field(default_factory=list)
    test_impact: TestImpactReport = Field(default_factory=TestImpactReport)
    max_propagation_depth: int = 5
    causal_paths: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_locations: List[Dict[str, Any]] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: Optional[str] = None
