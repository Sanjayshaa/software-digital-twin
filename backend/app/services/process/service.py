from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.entities import ProcessDefinition, RepositorySnapshot, Repository
from app.services.process.models import ProcessModel, ProcessDiscoveryResult
from app.services.process.discovery import process_discovery_engine


class ProcessService:
    """Service layer managing Process Twin querying and discovery orchestration."""

    def discover_processes(
        self,
        db: Session,
        repository_id: str,
        snapshot_id: Optional[str] = None,
    ) -> ProcessDiscoveryResult:
        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail=f"Repository {repository_id} not found")
        project_id = repo.project_id

        if not snapshot_id:
            # Pick latest snapshot
            latest_snap = (
                db.query(RepositorySnapshot)
                .filter_by(repository_id=repository_id)
                .order_by(RepositorySnapshot.created_at.desc())
                .first()
            )
            if not latest_snap:
                raise HTTPException(status_code=404, detail="No snapshots found for repository")
            snapshot_id = latest_snap.id
        else:
            snap = db.query(RepositorySnapshot).filter_by(id=snapshot_id).first()
            if not snap:
                raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")

        return process_discovery_engine.discover_and_persist(
            db=db,
            project_id=project_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
        )

    def list_processes(
        self,
        db: Session,
        repository_id: str,
        snapshot_id: Optional[str] = None,
    ) -> List[ProcessModel]:
        query = db.query(ProcessDefinition).filter_by(repository_id=repository_id)
        if snapshot_id:
            query = query.filter_by(snapshot_id=snapshot_id)
        else:
            latest_snap = (
                db.query(RepositorySnapshot)
                .filter_by(repository_id=repository_id)
                .order_by(RepositorySnapshot.created_at.desc())
                .first()
            )
            if latest_snap:
                query = query.filter_by(snapshot_id=latest_snap.id)

        proc_defs = query.order_by(ProcessDefinition.created_at.asc()).all()
        return [process_discovery_engine._entity_to_model(p) for p in proc_defs]

    def get_process(self, db: Session, process_id: str) -> Optional[ProcessModel]:
        proc_def = db.query(ProcessDefinition).filter_by(id=process_id).first()
        if not proc_def:
            return None
        return process_discovery_engine._entity_to_model(proc_def)


process_service = ProcessService()
