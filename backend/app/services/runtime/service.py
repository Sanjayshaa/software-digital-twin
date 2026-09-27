import json
import time
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException

from app.models.entities import (
    RuntimeEvent,
    Repository,
    RepositorySnapshot,
)
from app.services.runtime.models import (
    RawRuntimeEvent,
    NormalizedRuntimeEvent,
    RuntimeIngestResult,
    RuntimeEventPage,
)
from app.services.runtime.sanitizer import sensitive_sanitizer
from app.services.runtime.correlator import entity_correlator


class RuntimeEvidenceService:
    """Service managing runtime evidence ingestion, sanitization, correlation, and querying."""

    def ingest_events(
        self,
        db: Session,
        repository_id: str,
        events: List[RawRuntimeEvent],
        snapshot_id: Optional[str] = None,
        default_environment: Optional[str] = "production",
    ) -> RuntimeIngestResult:
        start_time = time.perf_counter()

        repo = db.query(Repository).filter_by(id=repository_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail=f"Repository {repository_id} not found")

        project_id = repo.project_id

        target_snap_id = snapshot_id
        if not target_snap_id:
            latest_snap = (
                db.query(RepositorySnapshot)
                .filter_by(repository_id=repository_id)
                .order_by(RepositorySnapshot.created_at.desc())
                .first()
            )
            if latest_snap:
                target_snap_id = latest_snap.id

        ingested_count = 0
        correlated_count = 0
        redacted_count = 0
        skipped_count = 0
        event_ids: List[str] = []

        entities_to_add: List[RuntimeEvent] = []

        for raw_event in events:
            try:
                # 1. Sensitive Data Sanitization
                sanitized_attrs, sanitized_msg, was_redacted = sensitive_sanitizer.sanitize_event(
                    attributes=raw_event.attributes,
                    message=raw_event.message,
                )
                if was_redacted:
                    redacted_count += 1

                # 2. Extract Service Name
                service_name = raw_event.service_name or raw_event.service or sanitized_attrs.get("service")

                # 3. Entity Correlation
                art_id, confidence, method = entity_correlator.correlate(
                    db=db,
                    snapshot_id=target_snap_id,
                    service_name=service_name,
                    attributes=sanitized_attrs,
                )
                if art_id:
                    correlated_count += 1

                # 4. Construct Payload
                payload = {
                    "raw_attributes": sanitized_attrs,
                    "attributes": sanitized_attrs,
                    "correlation": {
                        "confidence": confidence,
                        "method": method,
                        "matched_artifact_id": art_id,
                    },
                    "was_redacted": was_redacted,
                }
                if raw_event.commit_sha:
                    payload["commit_sha"] = raw_event.commit_sha
                if raw_event.request_id:
                    payload["request_id"] = raw_event.request_id

                event_id = str(uuid.uuid4())
                event_ts = raw_event.timestamp or datetime.utcnow()

                event_entity = RuntimeEvent(
                    id=event_id,
                    project_id=project_id,
                    repository_id=repository_id,
                    snapshot_id=target_snap_id,
                    service_name=service_name,
                    component_artifact_id=art_id,
                    event_type=raw_event.event_type.upper(),
                    severity=raw_event.severity.upper(),
                    environment=raw_event.environment or default_environment or "production",
                    trace_id=raw_event.trace_id,
                    span_id=raw_event.span_id,
                    message=sanitized_msg,
                    payload=payload,
                    timestamp=event_ts,
                )
                entities_to_add.append(event_entity)
                event_ids.append(event_id)
                ingested_count += 1
            except Exception:
                skipped_count += 1

        if entities_to_add:
            db.add_all(entities_to_add)
            db.commit()

        elapsed = (time.perf_counter() - start_time) * 1000.0

        return RuntimeIngestResult(
            repository_id=repository_id,
            ingested_count=ingested_count,
            correlated_count=correlated_count,
            redacted_count=redacted_count,
            skipped_count=skipped_count,
            event_ids=event_ids,
            execution_time_ms=round(elapsed, 2),
        )

    def ingest_json_or_jsonl(
        self,
        db: Session,
        repository_id: str,
        content: Optional[str] = None,
        file_path: Optional[str] = None,
        snapshot_id: Optional[str] = None,
        default_environment: Optional[str] = "production",
    ) -> RuntimeIngestResult:
        """Parses either JSON array or newline-delimited JSON (JSONL) and ingests events."""
        if file_path and not content:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

        events: List[RawRuntimeEvent] = []
        content_stripped = (content or "").strip()

        if content_stripped.startswith("[") and content_stripped.endswith("]"):
            raw_list = json.loads(content_stripped)
            for item in raw_list:
                if isinstance(item, dict):
                    events.append(RawRuntimeEvent(**item))
        else:
            for line in content_stripped.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        events.append(RawRuntimeEvent(**item))
                except json.JSONDecodeError:
                    continue

        return self.ingest_events(
            db=db,
            repository_id=repository_id,
            events=events,
            snapshot_id=snapshot_id,
            default_environment=default_environment,
        )

    def list_events(
        self,
        db: Session,
        repository_id: str,
        snapshot_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        environment: Optional[str] = None,
        service_name: Optional[str] = None,
        trace_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RuntimeEventPage:
        limit = max(1, min(limit, 200))  # Bounded pagination
        offset = max(0, offset)

        query = db.query(RuntimeEvent).filter_by(repository_id=repository_id)

        if snapshot_id:
            query = query.filter_by(snapshot_id=snapshot_id)
        if event_type:
            query = query.filter(RuntimeEvent.event_type.ilike(event_type))
        if severity:
            query = query.filter(RuntimeEvent.severity.ilike(severity))
        if environment:
            query = query.filter_by(environment=environment)
        if service_name:
            query = query.filter(RuntimeEvent.service_name.ilike(f"%{service_name}%"))
        if trace_id:
            query = query.filter_by(trace_id=trace_id)
        if since:
            query = query.filter(RuntimeEvent.timestamp >= since)
        if until:
            query = query.filter(RuntimeEvent.timestamp <= until)

        total = query.count()
        rows = query.order_by(desc(RuntimeEvent.timestamp)).offset(offset).limit(limit).all()

        normalized_events = [self._entity_to_model(r) for r in rows]

        return RuntimeEventPage(
            total=total,
            limit=limit,
            offset=offset,
            events=normalized_events,
        )

    def get_event(self, db: Session, event_id: str) -> Optional[NormalizedRuntimeEvent]:
        row = db.query(RuntimeEvent).filter_by(id=event_id).first()
        if not row:
            return None
        return self._entity_to_model(row)

    def _entity_to_model(self, entity: RuntimeEvent) -> NormalizedRuntimeEvent:
        corr_data = (entity.payload or {}).get("correlation", {})
        return NormalizedRuntimeEvent(
            id=entity.id,
            project_id=entity.project_id,
            repository_id=entity.repository_id,
            snapshot_id=entity.snapshot_id,
            incident_id=entity.incident_id,
            service_name=entity.service_name,
            component_artifact_id=entity.component_artifact_id,
            event_type=entity.event_type,
            severity=entity.severity,
            environment=entity.environment,
            trace_id=entity.trace_id,
            span_id=entity.span_id,
            message=entity.message,
            correlation_confidence=corr_data.get("confidence", 0.0),
            correlation_method=corr_data.get("method", "UNMATCHED"),
            payload=entity.payload or {},
            timestamp=entity.timestamp,
        )


runtime_evidence_service = RuntimeEvidenceService()
