import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException

from app.models.entities import (
    Incident,
    Repository,
    RepositorySnapshot,
    RuntimeEvent,
    StructuralArtifact,
)
from app.services.incident.models import (
    IncidentCreate,
    IncidentResponse,
    InvestigationResult,
)
from app.services.incident.investigator import incident_investigator


class IncidentService:
    """Service layer managing Incident lifecycle and investigation."""

    def create_incident(
        self,
        db: Session,
        repository_id: str,
        req: IncidentCreate,
    ) -> IncidentResponse:
        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail=f"Repository {repository_id} not found")

        project_id = repo.project_id

        target_snap_id = req.snapshot_id
        if not target_snap_id:
            latest_snap = (
                db.query(RepositorySnapshot)
                .filter_by(repository_id=repository_id)
                .order_by(RepositorySnapshot.created_at.desc())
                .first()
            )
            if latest_snap:
                target_snap_id = latest_snap.id

        # Resolve affected_component_name to affected_component_id if needed
        resolved_component_id = req.affected_component_id
        if not resolved_component_id and req.affected_component_name:
            art_q = db.query(StructuralArtifact).filter_by(
                repository_id=repository_id,
                name=req.affected_component_name,
            )
            if target_snap_id:
                art_q = art_q.filter_by(snapshot_id=target_snap_id)
            matching_art = art_q.first()
            if matching_art:
                resolved_component_id = matching_art.id

        incident_id = str(uuid.uuid4())
        incident = Incident(
            id=incident_id,
            project_id=project_id,
            repository_id=repository_id,
            snapshot_id=target_snap_id,
            title=req.title,
            description=req.description,
            severity=req.severity.lower(),
            status="open",
            environment=req.environment or "production",
            affected_component_id=resolved_component_id,
            detected_at=req.detected_at or datetime.utcnow(),
            metadata_payload=req.metadata_payload or {},
        )
        db.add(incident)

        # Link any provided event IDs to this incident
        if req.event_ids:
            events = db.query(RuntimeEvent).filter(RuntimeEvent.id.in_(req.event_ids)).all()
            for ev in events:
                ev.incident_id = incident_id
                if not incident.affected_component_id and ev.component_artifact_id:
                    incident.affected_component_id = ev.component_artifact_id
        elif resolved_component_id:
            # Auto-link runtime events already correlated to the affected component
            correlated_events = (
                db.query(RuntimeEvent)
                .filter_by(
                    repository_id=repository_id,
                    component_artifact_id=resolved_component_id,
                )
                .filter(RuntimeEvent.incident_id.is_(None))
                .limit(100)
                .all()
            )
            for ev in correlated_events:
                ev.incident_id = incident_id

        db.commit()
        db.refresh(incident)

        return self._entity_to_response(db, incident)

    def list_incidents(
        self,
        db: Session,
        repository_id: str,
        snapshot_id: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[IncidentResponse]:
        query = db.query(Incident).filter_by(repository_id=repository_id)
        if snapshot_id:
            query = query.filter_by(snapshot_id=snapshot_id)
        if status:
            query = query.filter_by(status=status)
        if severity:
            query = query.filter_by(severity=severity.lower())

        rows = query.order_by(desc(Incident.detected_at)).all()
        return [self._entity_to_response(db, inc) for inc in rows]

    def get_incident(self, db: Session, incident_id: str) -> Optional[IncidentResponse]:
        inc = db.query(Incident).filter_by(id=incident_id).first()
        if not inc:
            return None
        return self._entity_to_response(db, inc)

    def investigate_incident(self, db: Session, incident_id: str, repository_id: Optional[str] = None) -> InvestigationResult:
        return incident_investigator.investigate(db, incident_id)

    def _entity_to_response(self, db: Session, inc: Incident) -> IncidentResponse:
        aff_name = None
        if inc.affected_component_id:
            art = db.query(StructuralArtifact).filter_by(id=inc.affected_component_id).first()
            if art:
                aff_name = art.name

        # Collect IDs of all runtime events linked to this incident
        linked_event_ids = [
            ev.id
            for ev in db.query(RuntimeEvent).filter_by(incident_id=inc.id).all()
        ]

        return IncidentResponse(
            id=inc.id,
            project_id=inc.project_id,
            repository_id=inc.repository_id,
            snapshot_id=inc.snapshot_id,
            title=inc.title,
            description=inc.description,
            severity=inc.severity,
            status=inc.status,
            environment=inc.environment,
            affected_component_id=inc.affected_component_id,
            affected_component_name=aff_name,
            detected_at=inc.detected_at,
            resolved_at=inc.resolved_at,
            evidence_links_count=len(inc.evidence_links) if inc.evidence_links else 0,
            evidence_ids=linked_event_ids,
            metadata_payload=inc.metadata_payload or {},
        )


incident_service = IncidentService()
