"""
Phase 8 — What-If / Scenario Simulation Models.
Defines data structures for proposed mutations, validation results,
virtual twin representations, simulation evidence, and scenario comparisons.
Strictly deterministic with zero generative AI.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field


class MutationType(str, Enum):
    MODIFY_SYMBOL = "MODIFY_SYMBOL"
    ADD_DEPENDENCY = "ADD_DEPENDENCY"
    REMOVE_DEPENDENCY = "REMOVE_DEPENDENCY"
    MODIFY_API = "MODIFY_API"
    MODIFY_COMPONENT_RELATIONSHIP = "MODIFY_COMPONENT_RELATIONSHIP"


class ScenarioStatus(str, Enum):
    DRAFT = "DRAFT"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class EvidenceCategory(str, Enum):
    SIMULATED_STRUCTURAL = "SIMULATED_STRUCTURAL"
    OBSERVED_RUNTIME = "OBSERVED_RUNTIME"
    HISTORICAL_INCIDENT = "HISTORICAL_INCIDENT"
    UNKNOWN_EVIDENCE = "UNKNOWN_EVIDENCE"


class ProposedMutation(BaseModel):
    """
    A single bounded hypothetical change proposed against the Digital Twin.
    """
    mutation_id: str = Field(..., description="Unique identifier for this mutation")
    mutation_type: MutationType = Field(..., description="Type of proposed structural mutation")
    target: str = Field(..., description="Target symbol, component, API endpoint, or destination entity")
    source: Optional[str] = Field(None, description="Source entity for dependency or relationship mutations")
    relationship_type: Optional[str] = Field(None, description="Relationship type (e.g., CALLS, IMPORTS, DEPENDS_ON)")
    description: Optional[str] = Field(None, description="Human explanation of what is proposed")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional parameters (e.g., new signature, HTTP method)")


class ScenarioValidationResult(BaseModel):
    """
    Validation results for proposed mutations before virtual twin projection.
    """
    is_valid: bool = Field(..., description="Whether all mutations passed validation")
    errors: List[str] = Field(default_factory=list, description="Validation failure messages")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings or ambiguities")
    validated_mutations: List[ProposedMutation] = Field(default_factory=list)
    unknown_entities: List[str] = Field(default_factory=list, description="Entities referenced that do not exist in the Twin")


class SimulationEvidenceItem(BaseModel):
    """
    Explicitly labeled evidence item separating simulated findings from observed/historical data.
    """
    category: EvidenceCategory
    label: str
    description: str
    source_entity: Optional[str] = None
    target_entity: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class SimulatedImpactSummary(BaseModel):
    """
    Simulated structural blast radius results.
    """
    changed_artifacts: List[str] = Field(default_factory=list)
    directly_affected: List[str] = Field(default_factory=list)
    indirectly_affected: List[str] = Field(default_factory=list)
    affected_components: List[str] = Field(default_factory=list)
    affected_services: List[str] = Field(default_factory=list)
    affected_apis: List[str] = Field(default_factory=list)
    affected_tests: List[str] = Field(default_factory=list)
    max_propagation_depth: int = 0
    propagation_paths_count: int = 0
    propagation_paths: List[Dict[str, Any]] = Field(default_factory=list)


class SimulatedTestImpactSummary(BaseModel):
    """
    Simulated test exposure results.
    """
    directly_affected_tests: List[str] = Field(default_factory=list)
    indirectly_affected_tests: List[str] = Field(default_factory=list)
    unaffected_tests: List[str] = Field(default_factory=list)
    unknown_coverage_count: int = 0
    unknown_coverage_entities: List[str] = Field(default_factory=list)


class SimulatedRiskSummary(BaseModel):
    """
    Simulated multi-dimensional risk assessment.
    """
    scenario_risk_category: str = Field(..., description="Simulated risk level: LOW, MEDIUM, HIGH, CRITICAL")
    confidence_level: str = Field(..., description="Assessment confidence: HIGH, MEDIUM, LOW")
    confidence_score: float = 0.0
    overall_score: float = 0.0
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: str = Field(..., description="Scenario-specific explanation using simulation terminology")


class VirtualTwinComparison(BaseModel):
    """
    Comparison between the Base Digital Twin and the Virtual Scenario Twin.
    """
    added_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    removed_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    newly_affected_components: List[str] = Field(default_factory=list)
    removed_affected_components: List[str] = Field(default_factory=list)
    new_guardrail_violations: List[Dict[str, Any]] = Field(default_factory=list)
    baseline_guardrail_violations: List[Dict[str, Any]] = Field(default_factory=list)
    risk_factor_deltas: Dict[str, Any] = Field(default_factory=dict)


class ScenarioAnalysisResult(BaseModel):
    """
    Full end-to-end simulation output for a what-if scenario.
    """
    scenario_id: str
    repository_id: str
    base_snapshot_id: str
    name: str
    description: Optional[str] = None
    status: ScenarioStatus
    created_at: str
    expires_at: Optional[str] = None
    proposed_changes: List[ProposedMutation] = Field(default_factory=list)
    validation: ScenarioValidationResult
    impact: SimulatedImpactSummary
    tests: SimulatedTestImpactSummary
    risk: SimulatedRiskSummary
    guardrails: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[SimulationEvidenceItem] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    comparison: VirtualTwinComparison
    execution_time_ms: float = 0.0


class CreateScenarioRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    base_snapshot_id: str = Field(..., description="Snapshot ID against which simulation runs")
    proposed_changes: List[Dict[str, Any]] = Field(default_factory=list)
    expires_in_hours: Optional[int] = Field(default=24, description="TTL for temporary scenario")
