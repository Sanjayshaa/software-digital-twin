from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.entities import ProcessDefinition, ProcessStep, ProcessTransition


class ProcessTwinFoundationService:
    """Provides foundation interfaces and deterministic schema hooks for future Process Twin reconstruction."""

    def register_process(
        self,
        db: Session,
        project_id: str,
        repository_id: str,
        snapshot_id: str,
        name: str,
        description: Optional[str] = None,
        process_type: str = "business_process",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessDefinition:
        proc = ProcessDefinition(
            project_id=project_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            name=name,
            description=description,
            process_type=process_type,
            metadata_payload=metadata or {},
        )
        db.add(proc)
        db.commit()
        db.refresh(proc)
        return proc

    def add_step(
        self,
        db: Session,
        process_id: str,
        step_order: int,
        name: str,
        component_artifact_id: Optional[str] = None,
        step_type: str = "action",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessStep:
        step = ProcessStep(
            process_id=process_id,
            step_order=step_order,
            name=name,
            component_artifact_id=component_artifact_id,
            step_type=step_type,
            metadata_payload=metadata or {},
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        return step

    def add_transition(
        self,
        db: Session,
        process_id: str,
        from_step_id: str,
        to_step_id: str,
        condition: Optional[str] = None,
    ) -> ProcessTransition:
        transition = ProcessTransition(
            process_id=process_id,
            from_step_id=from_step_id,
            to_step_id=to_step_id,
            transition_condition=condition,
        )
        db.add(transition)
        db.commit()
        db.refresh(transition)
        return transition


process_foundation_service = ProcessTwinFoundationService()
