from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.orm import Session
from app.models.entities import StructuralArtifact


class EntityCorrelator:
    """
    Deterministic correlation engine linking observed runtime events to
    Structural Digital Twin artifacts in a specific repository snapshot.
    """

    def correlate(
        self,
        db: Session,
        snapshot_id: str,
        service_name: Optional[str] = None,
        attributes: Dict[str, Any] = None,
    ) -> Tuple[Optional[str], float, str]:
        """
        Attempts to correlate an event to a StructuralArtifact ID.
        Returns: (artifact_id, confidence, correlation_method)
        """
        if not snapshot_id:
            return None, 0.0, "NO_SNAPSHOT"

        attrs = attributes or {}

        # 1. Exact Function or Symbol Name match
        symbol = attrs.get("symbol") or attrs.get("function") or attrs.get("method")
        if symbol:
            matched_art = (
                db.query(StructuralArtifact)
                .filter(
                    StructuralArtifact.snapshot_id == snapshot_id,
                    (StructuralArtifact.name == symbol) | (StructuralArtifact.qualified_name.endswith(f".{symbol}")),
                )
                .first()
            )
            if matched_art:
                return matched_art.id, 0.95, "SYMBOL_EXACT"

        # 2. API Route / Endpoint match
        route = attrs.get("route") or attrs.get("endpoint") or attrs.get("path_template")
        if route:
            matched_art = (
                db.query(StructuralArtifact)
                .filter(
                    StructuralArtifact.snapshot_id == snapshot_id,
                    StructuralArtifact.artifact_type.in_(["API_ENDPOINT", "ENDPOINT", "ROUTE"]),
                    StructuralArtifact.location.ilike(f"%{route}%"),
                )
                .first()
            )
            if matched_art:
                return matched_art.id, 0.90, "API_ROUTE"

        # 3. Source File / Location match
        file_path = attrs.get("file") or attrs.get("source_file") or attrs.get("file_path")
        if file_path:
            matched_art = (
                db.query(StructuralArtifact)
                .filter(
                    StructuralArtifact.snapshot_id == snapshot_id,
                    StructuralArtifact.location.ilike(f"%{file_path}%"),
                )
                .first()
            )
            if matched_art:
                return matched_art.id, 0.85, "FILE_LOCATION"

        # 4. Service Name match
        target_service = service_name or attrs.get("service") or attrs.get("service_name")
        if target_service:
            matched_art = (
                db.query(StructuralArtifact)
                .filter(
                    StructuralArtifact.snapshot_id == snapshot_id,
                    StructuralArtifact.name.ilike(target_service),
                )
                .first()
            )
            if matched_art:
                return matched_art.id, 0.75, "SERVICE_NAME"

            # Partial match on module or class
            partial_art = (
                db.query(StructuralArtifact)
                .filter(
                    StructuralArtifact.snapshot_id == snapshot_id,
                    StructuralArtifact.name.ilike(f"%{target_service}%"),
                )
                .first()
            )
            if partial_art:
                return partial_art.id, 0.70, "SERVICE_PARTIAL"

        return None, 0.0, "UNMATCHED"


entity_correlator = EntityCorrelator()
