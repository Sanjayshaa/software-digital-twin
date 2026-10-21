from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import resolve_authorized_repo, get_current_user_optional, AuthenticatedPrincipal
from app.models.entities import (
    Repository,
    ProjectTechnology,
    Technology,
    TechnologyEvidence,
    ProjectCapability,
    Capability,
    AnalysisPlan,
    AnalysisRun,
)
from app.services.discovery.engine import discovery_engine
from app.services.discovery.models import (
    ProjectProfile,
    AnalysisPlanResult,
    CapabilitySpec,
    LanguageStat,
    FrameworkStat,
    BuildSystemStat,
    PackageManagerStat,
    DatabaseStat,
    APITechnologyStat,
    TestingFrameworkStat,
    InfrastructureStat,
    ArchitectureSignal,
    EvidenceItem,
    EvidenceType,
)

router = APIRouter(prefix="/repositories", tags=["Software Discovery Brain"])


@router.post("/{repository_id}/discover", response_model=Dict[str, Any])
def discover_repository(
    repository_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Executes the Software Project Discovery & Intelligence Brain on a repository.
    Extracts technologies, constructs project profile, registers capabilities,
    and produces an analysis plan.
    """
    repo = resolve_authorized_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found."
        )

    try:
        profile, plan = discovery_engine.discover_and_persist(db, repository_id=repo.id, project_id=repo.project_id)
        return {
            "status": "completed",
            "repository_id": repo.id,
            "repository_name": repo.name,
            "total_files": profile.total_files_scanned,
            "total_lines_of_code": profile.total_lines_of_code,
            "primary_language": profile.languages[0].name if profile.languages else "unknown",
            "total_plan_steps": plan.total_steps,
            "supported_capabilities_count": len(plan.supported_capabilities),
            "unsupported_capabilities_count": len(plan.unsupported_capabilities),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Discovery failed: {str(exc)}"
        )


@router.get("/{repository_id}/profile", response_model=ProjectProfile)
def get_repository_profile(
    repository_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the comprehensive, evidence-backed Project Profile for a repository.
    """
    repo = resolve_authorized_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found."
        )

    profile, _ = discovery_engine.discover(repo.local_path)
    return profile


@router.get("/{repository_id}/capabilities", response_model=List[CapabilitySpec])
def get_repository_capabilities(
    repository_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns all detected project capabilities and their support status.
    """
    repo = resolve_authorized_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found."
        )

    _, plan = discovery_engine.discover(repo.local_path)
    return plan.supported_capabilities + plan.unsupported_capabilities


@router.get("/{repository_id}/analysis-plan", response_model=AnalysisPlanResult)
def get_repository_analysis_plan(
    repository_id: str,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the deterministic Analysis Plan generated for the repository.
    """
    repo = resolve_authorized_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found."
        )

    _, plan = discovery_engine.discover(repo.local_path)
    return plan


class AssessmentRequest(BaseModel):
    snapshot_id: Optional[str] = Field(None, description="Snapshot ID or Commit SHA. If omitted, latest is used.")


@router.post("/{repository_id}/discovery/assess", response_model=Dict[str, Any])
def run_technical_assessment(
    repository_id: str,
    req: Optional[AssessmentRequest] = None,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Executes a comprehensive, evidence-backed Technical Health Assessment.
    Evaluates architecture modularity, coupling, APIs, testing gaps, and generates an advisory roadmap.
    """
    repo = resolve_authorized_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    snap_id = req.snapshot_id if req else None
    try:
        from fastapi.encoders import jsonable_encoder
        from app.services.discovery.assessment_engine import technical_assessment_engine
        result = technical_assessment_engine.assess_repository(db, repo.id, snapshot_id=snap_id)
        return jsonable_encoder(result)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Technical assessment failed: {str(exc)}",
        )


@router.get("/{repository_id}/discovery/assessment", response_model=Dict[str, Any])
def get_technical_assessment(
    repository_id: str,
    snapshot_id: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Retrieves stored or latest technical health assessment for the repository.
    """
    repo = resolve_authorized_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    from app.services.discovery.assessment_engine import technical_assessment_engine
    from fastapi.encoders import jsonable_encoder

    # Look for stored run first
    query = db.query(AnalysisRun).filter_by(repository_id=repo.id, run_type="technical_assessment")
    if snapshot_id:
        query = query.filter_by(snapshot_id=snapshot_id)
    latest_run = query.order_by(AnalysisRun.created_at.desc()).first()

    if latest_run and latest_run.summary:
        return latest_run.summary

    # On-demand fallback
    try:
        result = technical_assessment_engine.assess_repository(db, repo.id, snapshot_id=snapshot_id)
        return jsonable_encoder(result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to retrieve technical assessment: {str(exc)}",
        )


@router.get("/{repository_id}/discovery/report", response_model=Dict[str, Any])
def get_technical_assessment_report(
    repository_id: str,
    snapshot_id: Optional[str] = None,
    db: Session = Depends(get_db),
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
):
    """
    Returns the markdown technical assessment report with sensitive credentials redacted.
    """
    repo = resolve_authorized_repo(db, repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    from app.services.discovery.assessment_engine import technical_assessment_engine
    try:
        result = technical_assessment_engine.assess_repository(db, repo.id, snapshot_id=snapshot_id)
        return {
            "repository_id": repo.id,
            "repository_name": repo.name,
            "snapshot_id": result.snapshot_id,
            "commit_hash": result.commit_hash,
            "generated_at": result.assessed_at,
            "markdown_content": result.report_markdown,
            "report_markdown": result.report_markdown,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate technical assessment report: {str(exc)}",
        )

