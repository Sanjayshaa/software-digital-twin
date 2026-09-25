from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.entities import (
    Repository,
    ProjectTechnology,
    Technology,
    TechnologyEvidence,
    ProjectCapability,
    Capability,
    AnalysisPlan,
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
    db: Session = Depends(get_db)
):
    """
    Executes the Software Project Discovery & Intelligence Brain on a repository.
    Extracts technologies, constructs project profile, registers capabilities,
    and produces an analysis plan.
    """
    repo = db.query(Repository).filter_by(id=repository_id).first()
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
    db: Session = Depends(get_db)
):
    """
    Returns the comprehensive, evidence-backed Project Profile for a repository.
    """
    repo = db.query(Repository).filter_by(id=repository_id).first()
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
    db: Session = Depends(get_db)
):
    """
    Returns all detected project capabilities and their support status.
    """
    repo = db.query(Repository).filter_by(id=repository_id).first()
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
    db: Session = Depends(get_db)
):
    """
    Returns the deterministic Analysis Plan generated for the repository.
    """
    repo = db.query(Repository).filter_by(id=repository_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found."
        )

    _, plan = discovery_engine.discover(repo.local_path)
    return plan
