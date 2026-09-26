from fastapi import APIRouter
from app.services.status.tracker import project_status_tracker
from app.services.status.models import ProjectExecutionStatus

router = APIRouter(prefix="/status", tags=["Project Execution Status"])


@router.get("", response_model=ProjectExecutionStatus)
def get_execution_status():
    """
    Returns the authoritative project execution status.
    Calculates completion percentage deterministically from explicit verified milestones.
    Separates Project Progress % from Architecture Conformance %.
    """
    return project_status_tracker.get_status()


@router.get("/phases")
def get_phases_summary():
    """Returns milestone and progress breakdown for each phase."""
    status = project_status_tracker.get_status()
    return {
        "overall_project_progress": status.overall_project_progress,
        "current_phase": status.current_phase,
        "current_phase_progress": status.current_phase_progress,
        "architecture_conformance": status.architecture_conformance,
        "phases": status.phases,
    }
