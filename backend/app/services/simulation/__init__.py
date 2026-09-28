"""
Phase 8 — What-If / Scenario Simulation Module.
Exports public interfaces, models, validator, virtual twin, and engines.
"""

from app.services.simulation.models import (
    MutationType,
    ScenarioStatus,
    EvidenceCategory,
    ProposedMutation,
    ScenarioValidationResult,
    SimulationEvidenceItem,
    SimulatedImpactSummary,
    SimulatedTestImpactSummary,
    SimulatedRiskSummary,
    VirtualTwinComparison,
    ScenarioAnalysisResult,
    CreateScenarioRequest,
)
from app.services.simulation.validator import ScenarioValidator, scenario_validator
from app.services.simulation.virtual_twin import VirtualTwinModel
from app.services.simulation.engine import ScenarioSimulationEngine, scenario_simulation_engine
from app.services.simulation.service import ScenarioService, scenario_service

__all__ = [
    "MutationType",
    "ScenarioStatus",
    "EvidenceCategory",
    "ProposedMutation",
    "ScenarioValidationResult",
    "SimulationEvidenceItem",
    "SimulatedImpactSummary",
    "SimulatedTestImpactSummary",
    "SimulatedRiskSummary",
    "VirtualTwinComparison",
    "ScenarioAnalysisResult",
    "CreateScenarioRequest",
    "ScenarioValidator",
    "scenario_validator",
    "VirtualTwinModel",
    "ScenarioSimulationEngine",
    "scenario_simulation_engine",
    "ScenarioService",
    "scenario_service",
]
