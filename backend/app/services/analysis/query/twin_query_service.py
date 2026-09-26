from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.entities import (
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    Evidence,
    AnalysisRun,
)


class TwinQueryService:
    """Service layer for querying the structured Digital Twin representation."""

    def get_snapshot(self, db: Session, snapshot_id: str) -> Optional[RepositorySnapshot]:
        return db.query(RepositorySnapshot).filter_by(id=snapshot_id).first()

    def get_snapshots_by_repo(self, db: Session, repository_id: str) -> List[RepositorySnapshot]:
        return db.query(RepositorySnapshot).filter_by(repository_id=repository_id).order_by(RepositorySnapshot.created_at.desc()).all()

    def get_artifact(self, db: Session, artifact_id: str) -> Optional[StructuralArtifact]:
        return db.query(StructuralArtifact).filter_by(id=artifact_id).first()

    def get_artifacts(
        self,
        db: Session,
        snapshot_id: str,
        artifact_type: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 200,
    ) -> List[StructuralArtifact]:
        query = db.query(StructuralArtifact).filter_by(snapshot_id=snapshot_id)
        if artifact_type:
            query = query.filter_by(artifact_type=artifact_type.upper())
        if language:
            query = query.filter_by(language=language.lower())
        return query.limit(limit).all()

    def get_artifacts_by_file(self, db: Session, snapshot_id: str, file_path: str) -> List[StructuralArtifact]:
        return db.query(StructuralArtifact).filter_by(snapshot_id=snapshot_id, location=file_path).all()

    def get_artifacts_by_type(
        self,
        db: Session,
        repository_id: str,
        artifact_type: str,
        snapshot_id: str
    ) -> List[StructuralArtifact]:
        return self.get_artifacts(db, snapshot_id, artifact_type=artifact_type)

    def get_dependencies(self, db: Session, artifact_id: str, snapshot_id: Optional[str] = None) -> List[ArtifactRelationship]:
        """Outgoing edges: what this artifact depends on, calls, imports, or configures."""
        query = db.query(ArtifactRelationship).filter_by(source_artifact_id=artifact_id)
        if snapshot_id:
            query = query.filter_by(snapshot_id=snapshot_id)
        return query.all()

    def get_dependents(self, db: Session, artifact_id: str, snapshot_id: Optional[str] = None) -> List[ArtifactRelationship]:
        """Incoming edges: what depends on, calls, or tests this artifact."""
        query = db.query(ArtifactRelationship).filter_by(target_artifact_id=artifact_id)
        if snapshot_id:
            query = query.filter_by(snapshot_id=snapshot_id)
        return query.all()

    def get_twin(self, db: Session, repository_id: str, snapshot_id: str) -> Dict[str, Any]:
        """Returns normalized Digital Twin representation."""
        structure = self.get_component_structure(db, snapshot_id)
        artifacts = self.get_artifacts(db, snapshot_id, limit=500)
        relationships = self.get_relationships(db, snapshot_id, limit=500)
        return {
            "repository_id": repository_id,
            "snapshot_id": snapshot_id,
            "summary": structure,
            "artifacts_count": len(artifacts),
            "relationships_count": len(relationships),
        }

    def get_relationships(
        self,
        db: Session,
        snapshot_id: str,
        rel_type: Optional[str] = None,
        limit: int = 500
    ) -> List[ArtifactRelationship]:
        query = db.query(ArtifactRelationship).filter_by(snapshot_id=snapshot_id)
        if rel_type:
            query = query.filter_by(relationship_type=rel_type.upper())
        return query.limit(limit).all()

    def get_evidence(self, db: Session, project_id: str, limit: int = 200) -> List[Evidence]:
        return db.query(Evidence).filter_by(project_id=project_id).limit(limit).all()

    def get_component_structure(self, db: Session, snapshot_id: str) -> Dict[str, Any]:
        """Aggregates high-level structural metrics for the snapshot."""
        artifacts = db.query(StructuralArtifact).filter_by(snapshot_id=snapshot_id).all()
        relationships = db.query(ArtifactRelationship).filter_by(snapshot_id=snapshot_id).all()

        type_counts: Dict[str, int] = {}
        for a in artifacts:
            type_counts[a.artifact_type] = type_counts.get(a.artifact_type, 0) + 1

        rel_counts: Dict[str, int] = {}
        for r in relationships:
            rel_counts[r.relationship_type] = rel_counts.get(r.relationship_type, 0) + 1

        return {
            "snapshot_id": snapshot_id,
            "total_artifacts": len(artifacts),
            "total_relationships": len(relationships),
            "artifacts_by_type": type_counts,
            "relationships_by_type": rel_counts,
        }


twin_query_service = TwinQueryService()
