"""
Phase 8 — What-If / Scenario Simulation API Router.
Exposes endpoints for creating, simulating, inspecting, comparing, and deleting
hypothetical software change scenarios without modifying source code or base repository state.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.auth import resolve_authorized_repo, get_current_user_optional, AuthenticatedPrincipal
from app.models.entities import Repository, RepositorySnapshot
from app.services.simulation import (
    scenario_service,
    scenario_simulation_engine,
    CreateScenarioRequest,
    ScenarioAnalysisResult,
    ProposedMutation,
    MutationType,
)

router = APIRouter(prefix="/repositories", tags=["Scenario Simulation"])


def _resolve_repo(
    db: Session,
    repository_id: str,
    principal: Optional[AuthenticatedPrincipal] = None,
) -> Optional[Repository]:
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if repo:
        return repo
    if not principal:
        from sqlalchemy import or_
        return db.query(Repository).filter(
            or_(
                Repository.id == repository_id,
                Repository.name == repository_id,
            )
        ).first()
    return None


class QuickSimulateRequest(BaseModel):
    name: Optional[str] = Field("Quick Simulation", max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    base_snapshot_id: str = Field(..., description="Snapshot ID against which simulation runs")
    proposed_changes: List[Dict[str, Any]] = Field(..., max_length=100, description="List of proposed structural changes (max 100)")



@router.post("/{repository_id}/scenarios", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_scenario(
    repository_id: str,
    req: CreateScenarioRequest,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Creates a new temporary What-If scenario against a baseline Digital Twin snapshot.
    Does NOT modify the real repository, working tree, or existing snapshots.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    return scenario_service.create_scenario(db=db, repository_id=repo.id, request=req)


@router.get("/{repository_id}/scenarios", response_model=List[Dict[str, Any]])
def list_scenarios(
    repository_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Lists all previously created What-If scenarios for the given repository.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    return scenario_service.list_scenarios(db=db, repository_id=repo.id)


class NaturalLanguageScenarioRequest(BaseModel):
    query: Optional[str] = Field(None, max_length=1000, description="Natural-language question e.g. What would happen if we remove gamificationService?")
    base_snapshot_id: str = Field(..., description="Snapshot ID against which scenario runs")
    explicit_target: Optional[str] = Field(None, description="Optional explicit target entity if selected by user")
    target_override: Optional[str] = Field(None, description="Alias for explicit_target")
    explicit_type: Optional[str] = Field(None, description="Optional explicit mutation type")
    mutation_type_override: Optional[str] = Field(None, description="Alias for explicit_type")

    @property
    def resolved_target(self) -> Optional[str]:
        t = self.explicit_target or self.target_override
        if t and t.strip().lower() not in ("undefined", "null", ""):
            return t.strip()
        return None

    @property
    def resolved_type(self) -> Optional[str]:
        t = self.explicit_type or self.mutation_type_override
        if t and t.strip().lower() not in ("undefined", "null", ""):
            return t.strip()
        return None

    @property
    def resolved_query(self) -> str:
        q = (self.query or "").strip()
        if q and q.lower() not in ("undefined", "null"):
            return q
        tgt = self.resolved_target or "component"
        m_type = self.resolved_type or "MODIFY_SYMBOL"
        return f"What if we perform {m_type} on {tgt}?"


@router.post("/{repository_id}/scenarios/natural-language", response_model=Dict[str, Any])
def parse_natural_language_scenario(
    repository_id: str,
    req: NaturalLanguageScenarioRequest,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Parses a developer's natural-language 'What would happen if ...?' query.
    Extracts intent, resolves target entities against the real Twin knowledge graph,
    checks for ambiguities, and constructs a structured execution plan.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    from app.services.simulation.orchestration import multi_agent_scenario_orchestrator
    plan = multi_agent_scenario_orchestrator.plan_scenario(
        db=db,
        repository_id=repo.id,
        base_snapshot_id=req.base_snapshot_id,
        query=req.resolved_query,
        explicit_target=req.resolved_target,
        explicit_type=req.resolved_type,
    )
    return plan.dict()


@router.post("/{repository_id}/scenarios/orchestrate", response_model=Dict[str, Any])
def orchestrate_scenario(
    repository_id: str,
    req: NaturalLanguageScenarioRequest,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Executes the evidence-backed multi-agent orchestration workflow across the 8 logical roles:
    Scenario Planner, Architecture Analyst, Change Impact Analyst, Test Strategy Agent,
    Reliability Analyst, Simulation Coordinator, Evidence Reviewer, and Report Generator.
    Returns simulation results, audited findings, and full technical engineering report.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    from app.services.simulation.orchestration import multi_agent_scenario_orchestrator
    result = multi_agent_scenario_orchestrator.orchestrate_scenario(
        db=db,
        repository_id=repo.id,
        base_snapshot_id=req.base_snapshot_id,
        query=req.resolved_query,
        explicit_target=req.resolved_target,
        explicit_type=req.resolved_type,
    )
    res_dict = result.dict()
    res_dict["report_markdown"] = result.report.markdown_content
    res_dict["markdown_content"] = result.report.markdown_content
    return res_dict


@router.get("/{repository_id}/scenarios/target-candidates", response_model=List[Dict[str, Any]])
def get_target_candidates(
    repository_id: str,
    base_snapshot_id: str,
    q: Optional[str] = None,
    limit: int = 15,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Searches the repository's Knowledge Graph for real entities matching query 'q'.
    Assists natural-language disambiguation and autocomplete in the scenario workspace.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    from app.models.entities import StructuralArtifact
    query_filter = db.query(StructuralArtifact).filter_by(snapshot_id=base_snapshot_id)
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        from sqlalchemy import func
        query_filter = query_filter.filter(
            or_(
                func.lower(StructuralArtifact.name).like(term),
                func.lower(StructuralArtifact.qualified_name).like(term),
                func.lower(StructuralArtifact.location).like(term),
            )
        )

    artifacts = query_filter.limit(max(1, min(limit, 50))).all()
    candidates = []
    for a in artifacts:
        candidates.append({
            "id": a.id,
            "name": a.name,
            "qualified_name": a.qualified_name,
            "artifact_type": str(a.artifact_type),
            "location": a.location,
        })
    return candidates


@router.get("/{repository_id}/scenarios/{scenario_id}", response_model=Dict[str, Any])
def get_scenario(
    repository_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Retrieves a scenario definition and its latest simulated impact results.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    return scenario_service.get_scenario(db=db, scenario_id=scenario_id, repository_id=repo.id)



@router.post("/{repository_id}/scenarios/{scenario_id}/analyze", response_model=Dict[str, Any])
def analyze_scenario(
    repository_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Executes deterministic simulation on an existing scenario.
    Traverses the virtual twin, computes simulated impact, simulated test impact,
    architecture guardrails, and scenario risk.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    res = scenario_service.simulate_scenario(db=db, scenario_id=scenario_id, repository_id=repo.id)
    return res.dict()


@router.post("/{repository_id}/scenarios/{scenario_id}/simulate", response_model=Dict[str, Any])
def simulate_scenario_alias(
    repository_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Alias for /{repository_id}/scenarios/{scenario_id}/analyze.
    """
    return analyze_scenario(repository_id=repository_id, scenario_id=scenario_id, db=db, principal=principal)


@router.delete("/{repository_id}/scenarios/{scenario_id}", response_model=Dict[str, Any])
def delete_scenario(
    repository_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Deletes a What-If scenario and its simulation results.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    return scenario_service.delete_scenario(db=db, scenario_id=scenario_id, repository_id=repo.id)


@router.post("/{repository_id}/simulate", response_model=Dict[str, Any])
def quick_simulate(
    repository_id: str,
    req: QuickSimulateRequest,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    One-shot simulation endpoint for interactive simulation workspaces.
    Creates, validates, and simulates a scenario in a single call.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    create_req = CreateScenarioRequest(
        name=req.name or "Quick Simulation",
        description=req.description,
        base_snapshot_id=req.base_snapshot_id,
        proposed_changes=req.proposed_changes,
    )
    created = scenario_service.create_scenario(db=db, repository_id=repo.id, request=create_req)
    res = scenario_service.simulate_scenario(db=db, scenario_id=created["id"])
    return res.dict()


@router.get("/{repository_id}/scenarios/{scenario_id}/report", response_model=Dict[str, Any])
def get_scenario_engineering_report(
    repository_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Generates and returns the complete 13-section technical engineering report for a scenario.
    """
    repo = _resolve_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    from app.models.entities import Scenario
    scenario_data = None
    try:
        scenario_data = scenario_service.get_scenario(db=db, scenario_id=scenario_id, repository_id=repo.id)
    except Exception:
        scen_obj = db.query(Scenario).filter_by(id=scenario_id).first()
        if scen_obj:
            scenario_data = {
                "id": scen_obj.id,
                "name": scen_obj.name,
                "description": scen_obj.description,
                "parameters": scen_obj.parameters or {},
            }

    from app.services.simulation.orchestration import multi_agent_scenario_orchestrator
    from app.services.simulation.models import ScenarioAnalysisResult
    from app.services.runtime.sanitizer import SensitiveDataSanitizer

    base_snapshot_id = scenario_data.get("parameters", {}).get("base_snapshot_id") if scenario_data else None
    if not base_snapshot_id:
        snap = db.query(RepositorySnapshot).filter_by(repository_id=repo.id).order_by(RepositorySnapshot.created_at.desc()).first()
        base_snapshot_id = snap.id if snap else ""

    params = scenario_data.get("parameters") if scenario_data and isinstance(scenario_data.get("parameters"), dict) else {}
    raw_query = params.get("query") or (scenario_data.get("name") if scenario_data else None) or "Scenario Analysis"
    query_text: str = str(raw_query)

    plan = multi_agent_scenario_orchestrator.plan_scenario(
        db=db,
        repository_id=repo.id,
        base_snapshot_id=base_snapshot_id,
        query=query_text,
    )

    latest_res = scenario_data.get("latest_result") if scenario_data else None
    if latest_res:
        sim_obj = ScenarioAnalysisResult.parse_obj(latest_res)
    else:
        # Generate simulation outcome on demand
        sim_obj = multi_agent_scenario_orchestrator.simulation_engine.simulate_scenario(
            db=db,
            repository_id=repo.id,
            base_snapshot_id=base_snapshot_id,
            name=plan.scenario_title,
            proposed_changes=[],
            scenario_id=scenario_id,
            description=query_text,
        )

    findings = multi_agent_scenario_orchestrator._audit_and_generate_findings(
        plan=plan,
        sim=sim_obj,
        repository_id=repo.id,
        snapshot_id=base_snapshot_id,
    )

    snapshot = db.query(RepositorySnapshot).filter_by(id=base_snapshot_id).first()
    commit_sha = snapshot.commit_hash if snapshot else "unknown"

    report = multi_agent_scenario_orchestrator._generate_engineering_report(
        plan=plan,
        sim=sim_obj,
        findings=findings,
        commit_sha=commit_sha,
    )

    sanitized_md, _ = SensitiveDataSanitizer().sanitize_text(report.markdown_content)
    rep_dict = report.dict()
    rep_dict["markdown_content"] = sanitized_md
    rep_dict["report_markdown"] = sanitized_md
    return rep_dict

