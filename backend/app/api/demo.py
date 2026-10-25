"""
TwinCore Dedicated Demo Walkthrough API Endpoints.

Provides deterministic endpoints for:
1. Repository discovery and metadata (Stage 1)
2. Digital Twin synthesis breakdown (Stage 2)
3. Interactive architecture knowledge graph (Stage 3)
4. Deterministic blast radius traversal (Stage 4)
5. What-If scenario simulation with isolated virtual twins (Stage 5)
6. Test impact intelligence (Stage 6)
7. Mathematical risk score breakdown and evidence review (Stage 7)
8. Final engineering review report generation (Stage 8)
9. Architectural extension points
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.demo.fixture import (
    demo_graph_engine,
    DEMO_REPO_METADATA,
    DEMO_NODES,
    DEMO_EDGES,
    DEMO_SCENARIOS,
    DEMO_TEST_RESULTS,
    DEMO_EXTENSION_POINTS,
)

router = APIRouter(prefix="/api/v1/demo", tags=["Demo Twin Walkthrough"])


class BlastRadiusDemoRequest(BaseModel):
    root_identifier: str = Field(default="art-payment", description="Target component or artifact ID/name to trace")


class SimulationDemoRequest(BaseModel):
    scenario_id: Optional[str] = Field(default="SCENARIO_SERVICE_OUTAGE", description="Identifier of the demo scenario")
    target_override: Optional[str] = Field(default=None, description="Optional target entity override")


@router.get("/overview", summary="Demo Repository Discovery & Metadata")
def get_demo_overview() -> Dict[str, Any]:
    """Returns repository metadata, language breakdown, AST symbol counts, and extraction boundaries."""
    return {
        "status": "SUCCESS",
        "repository": DEMO_REPO_METADATA,
        "is_demo": True,
        "mode": "DETERMINISTIC_SANDBOX"
    }


@router.get("/graph", summary="Deterministic Architecture Knowledge Graph")
def get_demo_graph() -> Dict[str, Any]:
    """Returns the unified 22-node, 22-edge e-commerce microservices architecture knowledge graph."""
    return {
        "status": "SUCCESS",
        "repository_id": DEMO_REPO_METADATA["id"],
        "nodes": DEMO_NODES,
        "edges": DEMO_EDGES,
        "counts": {
            "total_nodes": len(DEMO_NODES),
            "services": sum(1 for n in DEMO_NODES if n["category"] == "service"),
            "api_endpoints": sum(1 for n in DEMO_NODES if n["category"] == "api"),
            "database_entities": sum(1 for n in DEMO_NODES if n["category"] == "database"),
            "test_cases": sum(1 for n in DEMO_NODES if n["category"] == "test"),
            "total_edges": len(DEMO_EDGES)
        },
        "provenance": "DETERMINISTIC_AST_SPEC",
        "is_demo": True
    }


@router.get("/stages", summary="Walkthrough Stages Specification")
def get_demo_stages() -> Dict[str, Any]:
    """Returns metadata, objectives, and verification keys for each of the 8 walkthrough stages."""
    stages = [
        {
            "stage_number": 1,
            "id": "stage-discovery",
            "title": "Repository Discovery",
            "subtitle": "Source Parsing & AST Symbol Extraction",
            "objective": "Understand how TwinCore ingests source repositories, discovers project topology, and determines analysis boundaries without running untrusted code.",
            "what_is_extracted": "Source files, languages, AST symbols, classes, functions, API routes, SQL schemas, and test cases.",
            "unsupported_boundaries": DEMO_REPO_METADATA["discovery_summary"]["unsupported_boundaries"],
            "verification_status": "VERIFIED_AST"
        },
        {
            "stage_number": 2,
            "id": "stage-synthesis",
            "title": "Digital Twin Synthesis",
            "subtitle": "Structured Entity & Dependency Materialization",
            "objective": "Observe how flat source code is synthesized into a multi-tiered Software Digital Twin (Source Files -> Symbols -> APIs/Services -> Dependencies -> Tests).",
            "what_is_extracted": "Directed graph nodes, typed edges (CALLS, ROUTES_TO, STORES_IN, TESTS), and provenance ledgers.",
            "verification_status": "VERIFIED_AST"
        },
        {
            "stage_number": 3,
            "id": "stage-graph",
            "title": "Interactive Knowledge Graph",
            "subtitle": "Live Architectural Exploration & Provenance",
            "objective": "Freely inspect microservice nodes, API gateways, database persistence layers, and test suites with verified AST line references.",
            "what_is_extracted": "Node metadata, edge directionality, in-degree/out-degree counts, and evidence status.",
            "verification_status": "VERIFIED_AST"
        },
        {
            "stage_number": 4,
            "id": "stage-blast-radius",
            "title": "Blast Radius Analysis",
            "subtitle": "Deterministic Multi-Hop Reachability Traversal",
            "objective": "Select a component (e.g., PaymentService) and compute downstream blast radius using transitive caller reachability traversal.",
            "what_is_extracted": "Direct vs indirect caller reachability, propagation paths, affected APIs, and excluded nodes with plain-English reasons.",
            "verification_status": "DOWNSTREAM_IMPACT_DETECTED"
        },
        {
            "stage_number": 5,
            "id": "stage-what-if",
            "title": "What-If Simulation",
            "subtitle": "Hypothetical Structural & Service Mutations",
            "objective": "Simulate real-world engineering scenarios (Outages, API Contract Changes, Removals, Schema Migrations) against an isolated virtual twin.",
            "what_is_extracted": "Baseline vs scenario twin comparison, severed relationships, and structural consequences.",
            "verification_status": "VIRTUAL_TWIN_ISOLATED"
        },
        {
            "stage_number": 6,
            "id": "stage-test-impact",
            "title": "Test Impact Intelligence",
            "subtitle": "Targeted Predictive Test Selection & Execution",
            "objective": "Map structural blast radius to relevant test suites, distinguishing suggested, executed, and passing/failing tests without fabrication.",
            "what_is_extracted": "Selective test execution commands, failure attribution, and unexecuted test exclusions.",
            "verification_status": "DEMO_DETERMINISTIC_EXECUTION"
        },
        {
            "stage_number": 7,
            "id": "stage-risk-evidence",
            "title": "Risk & Evidence Review",
            "subtitle": "Mathematical Score Breakdown & Evidence Ledger",
            "objective": "Deconstruct pre-deployment risk into its transparent mathematical components (Structural Blast + Guardrails + Test Coverage + Incidents).",
            "what_is_extracted": "Explicit mathematical formula, categorized evidence ledger (Static AST, Simulated Structural, Observed Runtime).",
            "verification_status": "MATHEMATICALLY_VERIFIED"
        },
        {
            "stage_number": 8,
            "id": "stage-final-report",
            "title": "Final Engineering Review",
            "subtitle": "Executive Audit Report & Actionable Next Steps",
            "objective": "Review a formal engineering audit report with reproduction CLI commands, technical limitations, and recommendations.",
            "what_is_extracted": "Downloadable audit summary, pytest reproduction commands, and extension points.",
            "verification_status": "VERIFIED_PASS"
        }
    ]
    return {
        "status": "SUCCESS",
        "total_stages": len(stages),
        "stages": stages,
        "is_demo": True
    }


@router.post("/blast-radius", summary="Deterministic Blast Radius Traversal")
def compute_demo_blast_radius(req: BlastRadiusDemoRequest) -> Dict[str, Any]:
    """Computes caller reachability blast radius for any component in the sample architecture."""
    result = demo_graph_engine.compute_blast_radius(req.root_identifier)
    return {
        "status": "SUCCESS",
        "result": result,
        "is_demo": True
    }


@router.get("/scenarios", summary="Available What-If Simulation Scenarios")
def get_demo_scenarios() -> Dict[str, Any]:
    """Returns catalog of deterministic What-If scenarios."""
    return {
        "status": "SUCCESS",
        "scenarios": list(DEMO_SCENARIOS.values()),
        "is_demo": True
    }


@router.post("/simulate", summary="Execute What-If Simulation on Virtual Twin")
def simulate_demo_scenario(req: SimulationDemoRequest) -> Dict[str, Any]:
    """
    Executes a deterministic What-If simulation against an isolated virtual twin.
    Baseline repository snapshot remains completely stationary.
    """
    scenario_id = req.scenario_id or "SCENARIO_SERVICE_OUTAGE"
    scenario = DEMO_SCENARIOS.get(scenario_id)

    if not scenario:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_id}' not found. Available scenarios: {list(DEMO_SCENARIOS.keys())}"
        )

    target_str = req.target_override or scenario["target"]
    blast_radius = demo_graph_engine.compute_blast_radius(target_str)

    # Compile isolated virtual twin delta
    virtual_twin_delta = {
        "baseline_snapshot_id": "snap-demo-base-001",
        "virtual_snapshot_id": f"snap-demo-sim-{scenario_id.lower()}",
        "mutation_type": scenario["mutation_type"],
        "target": target_str,
        "affected_components_count": len(blast_radius["directly_affected"]) + len(blast_radius["indirectly_affected"]),
        "structural_consequences": scenario["structural_consequences"],
        "risk_breakdown": scenario["risk_breakdown"],
        "recommended_verification": scenario["recommended_verification"],
        "limitations": scenario["limitations"],
        "is_baseline_stationary": True
    }

    return {
        "status": "SUCCESS",
        "scenario": scenario,
        "blast_radius": blast_radius,
        "virtual_twin_delta": virtual_twin_delta,
        "is_demo": True
    }


@router.get("/test-impact", summary="Deterministic Test Impact Intelligence")
def get_demo_test_impact(scenario_id: Optional[str] = "SCENARIO_SERVICE_OUTAGE") -> Dict[str, Any]:
    """Returns deterministic test impact matrix distinguishing suggested, executed, and passed/failed tests."""
    results = DEMO_TEST_RESULTS.get(scenario_id, DEMO_TEST_RESULTS["SCENARIO_SERVICE_OUTAGE"])
    return {
        "status": "SUCCESS",
        "scenario_id": scenario_id,
        "test_impact": results,
        "is_demo": True
    }


@router.get("/extension-points", summary="Future Capabilities & Extension Points")
def get_demo_extension_points() -> Dict[str, Any]:
    """Returns explicit architectural extension points for future enterprise capabilities."""
    return {
        "status": "SUCCESS",
        "extension_points": DEMO_EXTENSION_POINTS,
        "is_demo": True
    }


@router.get("/report", summary="Executive Engineering Audit Report")
def get_demo_final_report(scenario_id: Optional[str] = "SCENARIO_SERVICE_OUTAGE") -> Dict[str, Any]:
    """Generates a formal engineering audit report for the selected scenario."""
    scenario = DEMO_SCENARIOS.get(scenario_id, DEMO_SCENARIOS["SCENARIO_SERVICE_OUTAGE"])
    blast = demo_graph_engine.compute_blast_radius(scenario["target"])
    tests = DEMO_TEST_RESULTS.get(scenario_id, DEMO_TEST_RESULTS["SCENARIO_SERVICE_OUTAGE"])

    report = {
        "report_id": f"AUDIT-DEMO-{scenario['id']}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": DEMO_REPO_METADATA["name"],
        "commit_hash": DEMO_REPO_METADATA["commit_sha"][:8],
        "scenario_title": scenario["title"],
        "mutation_type": scenario["mutation_type"],
        "target_entity": scenario["target"],
        "impact_summary": {
            "total_affected": blast["total_affected"],
            "directly_affected_count": len(blast["directly_affected"]),
            "indirectly_affected_count": len(blast["indirectly_affected"]),
            "affected_apis": blast["affected_apis"],
            "max_propagation_depth": blast["max_depth"]
        },
        "risk_evaluation": scenario["risk_breakdown"],
        "test_verification": {
            "executed_count": tests["execution_summary"]["total_executed"],
            "passed_count": tests["execution_summary"]["passed"],
            "failed_count": tests["execution_summary"]["failed"],
            "pass_rate": f"{tests['execution_summary']['pass_rate_percentage']}%"
        },
        "actionable_next_steps": scenario["recommended_verification"],
        "technical_limitations": scenario["limitations"],
        "verification_status": "VERIFIED_PASS",
        "is_demo": True
    }

    return {
        "status": "SUCCESS",
        "report": report
    }
