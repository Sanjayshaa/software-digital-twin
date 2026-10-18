"""
Phase 8 — Scenario Simulation Service.
Manages lifecycle, persistence, and execution for What-If Scenarios.
Interfaces with Scenario and ScenarioResult entities in PostgreSQL.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.entities import Repository, RepositorySnapshot, Scenario, ScenarioResult
from app.services.simulation.models import (
    MutationType,
    ScenarioStatus,
    ProposedMutation,
    CreateScenarioRequest,
    ScenarioAnalysisResult,
)
from app.services.simulation.engine import scenario_simulation_engine, ScenarioSimulationEngine


class ScenarioService:
    """
    Coordinates CRUD operations and deterministic simulation executions for scenarios.
    """

    def __init__(self, engine: Optional[ScenarioSimulationEngine] = None):
        self.engine = engine or scenario_simulation_engine

    def create_scenario(
        self,
        db: Session,
        repository_id: str,
        request: CreateScenarioRequest,
    ) -> Dict[str, Any]:
        """
        Creates and stores a new scenario definition.
        """
        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

        snapshot = (
            db.query(RepositorySnapshot)
            .filter_by(id=request.base_snapshot_id, repository_id=repository_id)
            .first()
        )
        if not snapshot:
            raise HTTPException(
                status_code=404,
                detail=f"Base snapshot '{request.base_snapshot_id}' not found for repository '{repository_id}'.",
            )

        # Parse proposed changes
        mutations: List[ProposedMutation] = []
        for i, change_raw in enumerate(request.proposed_changes):
            mut_id = change_raw.get("mutation_id") or f"mut_{i+1}_{uuid.uuid4().hex[:6]}"
            mut_type_str = change_raw.get("mutation_type")
            try:
                mut_type = MutationType(mut_type_str)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported mutation type '{mut_type_str}'. Must be one of {[m.value for m in MutationType]}."
                )

            target = change_raw.get("target")
            if not target:
                raise HTTPException(status_code=422, detail=f"Mutation '{mut_id}' is missing required 'target'.")

            mutations.append(
                ProposedMutation(
                    mutation_id=mut_id,
                    mutation_type=mut_type,
                    target=target,
                    source=change_raw.get("source"),
                    relationship_type=change_raw.get("relationship_type"),
                    description=change_raw.get("description"),
                    parameters=change_raw.get("parameters") or {},
                )
            )

        scenario_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=request.expires_in_hours or 24)

        parameters = {
            "repository_id": repository_id,
            "base_snapshot_id": request.base_snapshot_id,
            "mutations": [m.dict() for m in mutations],
            "expires_at": expires_at.isoformat(),
            "status": ScenarioStatus.DRAFT.value,
        }

        scenario = Scenario(
            id=scenario_id,
            project_id=repo.project_id,
            name=request.name,
            description=request.description,
            scenario_type="what_if_simulation",
            parameters=parameters,
            created_at=datetime.utcnow(),
        )
        db.add(scenario)
        db.commit()
        db.refresh(scenario)

        return self._format_scenario(scenario)

    def list_scenarios(
        self,
        db: Session,
        repository_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Lists all scenarios for a given repository.
        """
        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

        scenarios = (
            db.query(Scenario)
            .filter_by(project_id=repo.project_id)
            .order_by(Scenario.created_at.desc())
            .all()
        )

        results = []
        for s in scenarios:
            params = s.parameters or {}
            # Match repository_id within project
            if params.get("repository_id") == repository_id or not params.get("repository_id"):
                results.append(self._format_scenario(s))
        return results

    def get_scenario(
        self,
        db: Session,
        scenario_id: str,
        repository_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves a scenario definition and its latest simulation result if executed.
        Enforces repository boundary when repository_id is provided.
        """
        scenario = db.query(Scenario).filter_by(id=scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

        params = scenario.parameters or {}
        scen_repo_id = params.get("repository_id")
        if repository_id and scen_repo_id and scen_repo_id != repository_id:
            raise HTTPException(
                status_code=404,
                detail=f"Scenario '{scenario_id}' not found for repository '{repository_id}'.",
            )

        formatted = self._format_scenario(scenario)

        latest_res = (
            db.query(ScenarioResult)
            .filter_by(scenario_id=scenario_id)
            .order_by(ScenarioResult.simulated_at.desc())
            .first()
        )
        if latest_res:
            formatted["latest_result"] = latest_res.result_payload

        return formatted

    def simulate_scenario(
        self,
        db: Session,
        scenario_id: str,
        repository_id: Optional[str] = None,
    ) -> ScenarioAnalysisResult:
        """
        Executes deterministic simulation on an existing scenario.
        Enforces repository boundary when repository_id is provided.
        """
        scenario = db.query(Scenario).filter_by(id=scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

        params = scenario.parameters or {}
        repo_id = params.get("repository_id")
        if repository_id and repo_id and repo_id != repository_id:
            raise HTTPException(
                status_code=404,
                detail=f"Scenario '{scenario_id}' not found for repository '{repository_id}'.",
            )
        base_snapshot_id = params.get("base_snapshot_id")

        # Check expiration
        expires_at_str = params.get("expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.utcnow() > expires_at:
                    params["status"] = ScenarioStatus.EXPIRED.value
                    scenario.parameters = params
                    db.commit()
                    raise HTTPException(
                        status_code=410,
                        detail=f"Scenario '{scenario_id}' has expired at {expires_at_str}."
                    )
            except (ValueError, TypeError):
                pass

        mutations_raw = params.get("mutations", [])
        mutations = [ProposedMutation(**m) for m in mutations_raw]

        # Run deterministic simulation engine
        sim_result: ScenarioAnalysisResult = self.engine.simulate_scenario(
            db=db,
            repository_id=repo_id,
            base_snapshot_id=base_snapshot_id,
            name=scenario.name,
            proposed_changes=mutations,
            scenario_id=scenario.id,
            description=scenario.description,
        )

        # Update scenario status
        params["status"] = sim_result.status.value
        scenario.parameters = params

        # Persist ScenarioResult record
        scen_result_record = ScenarioResult(
            id=str(uuid.uuid4()),
            scenario_id=scenario.id,
            status=sim_result.status.value,
            impacted_nodes=sim_result.impact.directly_affected + sim_result.impact.indirectly_affected,
            propagation_paths=sim_result.impact.propagation_paths,
            risk_impact_score=sim_result.risk.overall_score,
            result_payload=sim_result.dict(),
            simulated_at=datetime.utcnow(),
        )
        db.add(scen_result_record)
        db.commit()

        return sim_result

    def delete_scenario(
        self,
        db: Session,
        scenario_id: str,
        repository_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Deletes a scenario and associated simulation results.
        Enforces repository boundary when repository_id is provided.
        """
        scenario = db.query(Scenario).filter_by(id=scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

        params = scenario.parameters or {}
        scen_repo_id = params.get("repository_id")
        if repository_id and scen_repo_id and scen_repo_id != repository_id:
            raise HTTPException(
                status_code=404,
                detail=f"Scenario '{scenario_id}' not found for repository '{repository_id}'.",
            )

        db.delete(scenario)
        db.commit()
        return {"status": "deleted", "scenario_id": scenario_id}

    def _format_scenario(self, scenario: Scenario) -> Dict[str, Any]:
        params = scenario.parameters or {}
        return {
            "id": scenario.id,
            "project_id": scenario.project_id,
            "repository_id": params.get("repository_id"),
            "base_snapshot_id": params.get("base_snapshot_id"),
            "name": scenario.name,
            "description": scenario.description,
            "scenario_type": scenario.scenario_type,
            "status": params.get("status", ScenarioStatus.DRAFT.value),
            "mutations": params.get("mutations", []),
            "expires_at": params.get("expires_at"),
            "created_at": scenario.created_at.isoformat() if scenario.created_at else None,
        }


scenario_service = ScenarioService()
