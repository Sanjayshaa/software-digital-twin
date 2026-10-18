"""
Phase 8.8 — Twin Knowledge API Router.
Exposes deterministic, evidence-backed Twin Knowledge queries with strict multi-user authorization.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import AuthenticatedPrincipal, get_current_user_optional
from app.services.twin_knowledge.service import twin_knowledge_service
from app.services.twin_knowledge.models import (
    TwinKnowledgeOverview,
    TwinKnowledgeQueryResult,
)

router = APIRouter(prefix="/repositories/{repository_id}/twin-knowledge", tags=["Twin Knowledge"])


class AskTwinRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    snapshot_id: Optional[str] = None


@router.get("/overview", response_model=TwinKnowledgeOverview)
def get_repository_knowledge_overview(
    repository_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns authoritative repository overview with evidence statistics."""
    return twin_knowledge_service.get_repository_overview(
        db=db,
        repository_id=repository_id,
        principal=principal,
    )


@router.get("/snapshots/{snapshot_id}", response_model=Dict[str, Any])
def get_snapshot_knowledge(
    repository_id: str,
    snapshot_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns snapshot-scoped twin topology and evidence links."""
    return twin_knowledge_service.get_snapshot_overview(
        db=db,
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        principal=principal,
    )


@router.get("/artifacts/{artifact_id}", response_model=Dict[str, Any])
def get_artifact_knowledge(
    repository_id: str,
    artifact_id: str,
    snapshot_id: str = Query(..., description="Mandatory snapshot ID"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns artifact declaration and AST syntax evidence."""
    return twin_knowledge_service.get_artifact(
        db=db,
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        artifact_id=artifact_id,
        principal=principal,
    )


@router.get("/artifacts/{artifact_id}/dependencies", response_model=Dict[str, Any])
def get_artifact_dependencies(
    repository_id: str,
    artifact_id: str,
    snapshot_id: str = Query(..., description="Mandatory snapshot ID"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns upstream dependencies and downstream dependents for an artifact."""
    return twin_knowledge_service.get_dependencies_and_dependents(
        db=db,
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        artifact_id=artifact_id,
        principal=principal,
    )


@router.get("/artifacts/{artifact_id}/tests", response_model=Dict[str, Any])
def get_artifact_tests(
    repository_id: str,
    artifact_id: str,
    snapshot_id: str = Query(..., description="Mandatory snapshot ID"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns test cases mapped to the artifact with semantic claim status."""
    return twin_knowledge_service.get_tests_for_artifact(
        db=db,
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        artifact_id=artifact_id,
        principal=principal,
    )


@router.get("/api-surface", response_model=List[Dict[str, Any]])
def get_api_surface(
    repository_id: str,
    snapshot_id: str = Query(..., description="Mandatory snapshot ID"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns verified API endpoints declared in the snapshot."""
    return twin_knowledge_service.get_api_surface(
        db=db,
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        principal=principal,
    )


@router.get("/changes", response_model=Dict[str, Any])
def get_changes(
    repository_id: str,
    base_snapshot_id: str = Query(..., description="Base snapshot ID"),
    target_snapshot_id: str = Query(..., description="Target snapshot ID"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns pairwise AST structural changes with file diff evidence."""
    return twin_knowledge_service.get_changes(
        db=db,
        repository_id=repository_id,
        base_snapshot_id=base_snapshot_id,
        target_snapshot_id=target_snapshot_id,
        principal=principal,
    )


@router.get("/impact-paths", response_model=Dict[str, Any])
def get_impact_paths(
    repository_id: str,
    base_snapshot_id: str = Query(..., description="Base snapshot ID"),
    target_snapshot_id: str = Query(..., description="Target snapshot ID"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns explainable causal propagation paths with evidence provenance."""
    return twin_knowledge_service.get_impact_paths(
        db=db,
        repository_id=repository_id,
        base_snapshot_id=base_snapshot_id,
        target_snapshot_id=target_snapshot_id,
        principal=principal,
    )


@router.get("/guardrails", response_model=Dict[str, Any])
def get_guardrails(
    repository_id: str,
    snapshot_id: str = Query(..., description="Mandatory snapshot ID"),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns architectural guardrails conformance report."""
    return twin_knowledge_service.get_architecture_guardrails(
        db=db,
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        principal=principal,
    )


@router.get("/runtime-evidence", response_model=Dict[str, Any])
def get_runtime_evidence(
    repository_id: str,
    snapshot_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns batch-ingested runtime evidence events."""
    return twin_knowledge_service.get_runtime_evidence(
        db=db,
        repository_id=repository_id,
        principal=principal,
        snapshot_id=snapshot_id,
        limit=limit,
    )


@router.get("/incidents", response_model=Dict[str, Any])
def get_incidents(
    repository_id: str,
    incident_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns incidents and candidate causal paths."""
    return twin_knowledge_service.get_incidents(
        db=db,
        repository_id=repository_id,
        principal=principal,
        incident_id=incident_id,
    )


@router.get("/scenarios", response_model=Dict[str, Any])
def get_scenarios(
    repository_id: str,
    scenario_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """Returns simulated scenarios with SIMULATED provenance."""
    return twin_knowledge_service.get_scenarios(
        db=db,
        repository_id=repository_id,
        principal=principal,
        scenario_id=scenario_id,
    )


@router.post("/query", response_model=TwinKnowledgeQueryResult)
def ask_twin(
    repository_id: str,
    req: AskTwinRequest,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Deterministic Ask Twin Query Endpoint.
    Resolves questions strictly from PostgreSQL Digital Twin data.
    Guarantees zero hallucinations.
    """
    return twin_knowledge_service.ask_twin(
        db=db,
        repository_id=repository_id,
        query=req.query,
        snapshot_id=req.snapshot_id,
        principal=principal,
    )
