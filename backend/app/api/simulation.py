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


def _resolve_repo(db: Session, repository_id: str) -> Optional[Repository]:
    return (
        db.query(Repository)
        .filter(
            or_(
                Repository.id == repository_id,
                Repository.name == repository_id,
                Repository.local_path == repository_id,
            )
        )
        .first()
    )


class QuickSimulateRequest(BaseModel):
    name: Optional[str] = "Quick Simulation"
    description: Optional[str] = None
    base_snapshot_id: str = Field(..., description="Snapshot ID against which simulation runs")
    proposed_changes: List[Dict[str, Any]] = Field(..., description="List of proposed structural changes")


@router.post("/{repository_id}/scenarios", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_scenario(
    repository_id: str,
    req: CreateScenarioRequest,
    db: Session = Depends(get_db),
):
    """
    Creates a new temporary What-If scenario against a baseline Digital Twin snapshot.
    Does NOT modify the real repository, working tree, or existing snapshots.
    """
    repo = _resolve_repo(db, repository_id)
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
):
    """
    Lists all previously created What-If scenarios for the given repository.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    return scenario_service.list_scenarios(db=db, repository_id=repo.id)


@router.get("/{repository_id}/scenarios/{scenario_id}", response_model=Dict[str, Any])
def get_scenario(
    repository_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieves a scenario definition and its latest simulated impact results.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    return scenario_service.get_scenario(db=db, scenario_id=scenario_id)


@router.post("/{repository_id}/scenarios/{scenario_id}/analyze", response_model=Dict[str, Any])
def analyze_scenario(
    repository_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
):
    """
    Executes deterministic simulation on an existing scenario.
    Traverses the virtual twin, computes simulated impact, simulated test impact,
    architecture guardrails, and scenario risk.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    res = scenario_service.simulate_scenario(db=db, scenario_id=scenario_id)
    return res.dict()


@router.post("/{repository_id}/scenarios/{scenario_id}/simulate", response_model=Dict[str, Any])
def simulate_scenario_alias(
    repository_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
):
    """
    Alias for /{repository_id}/scenarios/{scenario_id}/analyze.
    """
    return analyze_scenario(repository_id=repository_id, scenario_id=scenario_id, db=db)


@router.delete("/{repository_id}/scenarios/{scenario_id}", response_model=Dict[str, Any])
def delete_scenario(
    repository_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
):
    """
    Deletes a What-If scenario and its simulation results.
    """
    repo = _resolve_repo(db, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    return scenario_service.delete_scenario(db=db, scenario_id=scenario_id)


@router.post("/{repository_id}/simulate", response_model=Dict[str, Any])
def quick_simulate(
    repository_id: str,
    req: QuickSimulateRequest,
    db: Session = Depends(get_db),
):
    """
    One-shot simulation endpoint for interactive simulation workspaces.
    Creates, validates, and simulates a scenario in a single call.
    """
    repo = _resolve_repo(db, repository_id)
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
