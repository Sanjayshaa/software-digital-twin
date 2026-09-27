"""
Phase 5 — Runtime Evidence Ingestion, Normalization, Sanitization, and Correlation Tests.
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.entities import (
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    RuntimeEvent,
)
from app.services.runtime import (
    RawRuntimeEvent,
    runtime_evidence_service,
    sensitive_sanitizer,
)


@pytest.fixture
def runtime_test_env(db_session: Session):
    db_session.rollback()
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        name=f"Runtime Test Project {suffix}",
        description="Phase 5 Runtime Telemetry Test",
    )
    db_session.add(project)
    db_session.flush()

    repo = Repository(
        project_id=project.id,
        name=f"runtime_test_repo_{suffix}",
        local_path=f"/tmp/runtime_repos/{suffix}",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.flush()

    snapshot = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="c0ffee123456",
        branch_name="main",
        total_files=5,
        total_symbols=10,
        snapshot_metadata={"test": True},
    )
    db_session.add(snapshot)
    db_session.flush()

    # Create structural artifacts for correlation
    dispatcher_art = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snapshot.id,
        name="OrderDispatcher",
        artifact_type="CLASS",
        language="python",
        qualified_name="dispatcher.OrderDispatcher",
        location="dispatcher.py",
        line_start=3,
        line_end=20,
    )
    db_session.add(dispatcher_art)

    alloc_art = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snapshot.id,
        name="allocate_inventory",
        artifact_type="METHOD",
        language="python",
        qualified_name="inventory.InventoryClient.allocate_inventory",
        location="inventory.py",
        line_start=7,
        line_end=15,
    )
    db_session.add(alloc_art)
    db_session.commit()

    yield {
        "project": project,
        "repo": repo,
        "snapshot": snapshot,
        "dispatcher_art": dispatcher_art,
        "alloc_art": alloc_art,
        "session": db_session,
    }

    # Cleanup
    db_session.rollback()
    db_session.query(RuntimeEvent).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db_session.query(StructuralArtifact).filter_by(snapshot_id=snapshot.id).delete(synchronize_session=False)
    db_session.query(RepositorySnapshot).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db_session.query(Repository).filter_by(id=repo.id).delete(synchronize_session=False)
    db_session.query(Project).filter_by(id=project.id).delete(synchronize_session=False)
    db_session.commit()


def test_runtime_sanitization_redaction():
    """Verifies passwords, API keys, tokens, and authorization headers are redacted."""
    raw_payload = {
        "password": "super_secret_password_123",
        "user_token": "jwt_token_abc_xyz",
        "api_key": "live_key_998877",
        "authorization": "Bearer secret_bearer_token",
        "safe_key": "safe_value",
        "http_method": "POST",
    }
    sanitized = sensitive_sanitizer.sanitize_attributes(raw_payload)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["user_token"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["safe_key"] == "safe_value"
    assert sanitized["http_method"] == "POST"


def test_runtime_ingest_json_events(runtime_test_env):
    """Verifies batch JSON ingestion, field storage, and entity correlation."""
    env = runtime_test_env
    db = env["session"]
    repo = env["repo"]
    snapshot = env["snapshot"]

    events = [
        RawRuntimeEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="REQUEST",
            service="dispatch-service",
            environment="production",
            severity="INFO",
            message="Dispatch order received",
            trace_id="tr-order-001",
            span_id="sp-001",
            attributes={"route": "/dispatch/order", "auth_token": "token-1234"},
        ),
        RawRuntimeEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="ERROR",
            service="dispatch-service",
            environment="production",
            severity="ERROR",
            message="Inventory allocation timeout",
            trace_id="tr-order-001",
            span_id="sp-002",
            attributes={"symbol": "allocate_inventory", "file_path": "inventory.py"},
        ),
    ]

    result = runtime_evidence_service.ingest_events(
        db=db,
        repository_id=repo.id,
        events=events,
        snapshot_id=snapshot.id,
    )

    assert result.ingested_count == 2
    assert result.correlated_count >= 1
    assert result.redacted_count >= 1

    # Verify database query
    page = runtime_evidence_service.list_events(db=db, repository_id=repo.id)
    assert page.total == 2
    error_evt = next(e for e in page.events if e.event_type == "ERROR")
    assert error_evt.component_artifact_id == env["alloc_art"].id
    assert error_evt.correlation_confidence >= 0.90


def test_runtime_ingest_fixtures(runtime_test_env):
    """Verifies ingestion from JSON and JSONL test fixture files."""
    env = runtime_test_env
    db = env["session"]
    repo = env["repo"]

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../tests/fixtures/runtime_telemetry"))
    json_path = os.path.join(base_dir, "events.json")
    jsonl_path = os.path.join(base_dir, "events.jsonl")

    res_json = runtime_evidence_service.ingest_json_or_jsonl(
        db=db, repository_id=repo.id, file_path=json_path
    )
    assert res_json.ingested_count == 3
    assert res_json.redacted_count >= 2

    res_jsonl = runtime_evidence_service.ingest_json_or_jsonl(
        db=db, repository_id=repo.id, file_path=jsonl_path
    )
    assert res_jsonl.ingested_count == 3


def test_runtime_large_payload_limit():
    """Verifies that events exceeding 100 KB payload boundary are rejected."""
    huge_message = "X" * 120_000
    with pytest.raises(Exception):
        RawRuntimeEvent(
            event_type="ERROR",
            message=huge_message,
        )


def test_runtime_unrelated_event_isolation(runtime_test_env):
    """Verifies that runtime events from unknown services or unrelated symbols remain safely isolated."""
    env = runtime_test_env
    db = env["session"]
    repo = env["repo"]

    events = [
        RawRuntimeEvent(
            event_type="LOG",
            service="unrelated-external-billing",
            message="Payment webhook received from stripe",
            attributes={"symbol": "totally_foreign_symbol_xyz"},
        )
    ]

    result = runtime_evidence_service.ingest_events(
        db=db, repository_id=repo.id, events=events
    )
    assert result.ingested_count == 1
    assert result.correlated_count == 0

    page = runtime_evidence_service.list_events(db=db, repository_id=repo.id, service_name="unrelated-external-billing")
    assert page.total == 1
    assert page.events[0].component_artifact_id is None


def test_runtime_pagination_and_time_filtering(runtime_test_env):
    """Verifies limit, offset, and timestamp window filtering."""
    env = runtime_test_env
    db = env["session"]
    repo = env["repo"]

    now = datetime.now(timezone.utc)
    t1 = now - timedelta(minutes=30)
    t2 = now - timedelta(minutes=20)
    t3 = now - timedelta(minutes=10)

    events = [
        RawRuntimeEvent(timestamp=t1, event_type="INFO", severity="INFO", message="Step 1"),
        RawRuntimeEvent(timestamp=t2, event_type="WARN", severity="WARN", message="Step 2"),
        RawRuntimeEvent(timestamp=t3, event_type="ERROR", severity="ERROR", message="Step 3"),
    ]
    runtime_evidence_service.ingest_events(db=db, repository_id=repo.id, events=events)

    # Test limit and offset
    page1 = runtime_evidence_service.list_events(db=db, repository_id=repo.id, limit=2, offset=0)
    assert len(page1.events) == 2
    assert page1.total == 3

    page2 = runtime_evidence_service.list_events(db=db, repository_id=repo.id, limit=2, offset=2)
    assert len(page2.events) == 1

    # Test time window filter
    window_page = runtime_evidence_service.list_events(
        db=db,
        repository_id=repo.id,
        since=now - timedelta(minutes=25),
        until=now - timedelta(minutes=15),
    )
    assert window_page.total == 1
    assert window_page.events[0].severity == "WARN"


def test_runtime_api_endpoints(runtime_test_env, client: TestClient):
    """Verifies FastAPI API endpoints for runtime event ingestion and retrieval."""
    env = runtime_test_env
    repo = env["repo"]

    # Ingest via API
    ingest_payload = {
        "events": [
            {
                "event_type": "ERROR",
                "severity": "CRITICAL",
                "service": "dispatch-service",
                "message": "Critical dispatch deadlock",
                "trace_id": "tr-deadlock-999",
                "attributes": {"api_key": "secret_key_111", "symbol": "OrderDispatcher"},
            }
        ],
        "environment": "production",
    }

    res = client.post(f"/repositories/{repo.id}/runtime-events/ingest", json=ingest_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["ingested_count"] == 1
    assert data["correlated_count"] == 1
    assert data["redacted_count"] == 1

    # Query via API
    get_res = client.get(f"/repositories/{repo.id}/runtime-events?trace_id=tr-deadlock-999")
    assert get_res.status_code == 200
    page_data = get_res.json()
    assert page_data["total"] == 1
    event_id = page_data["events"][0]["id"]

    # Get single event
    single_res = client.get(f"/repositories/{repo.id}/runtime-events/{event_id}")
    assert single_res.status_code == 200
    assert single_res.json()["payload"]["attributes"]["api_key"] == "[REDACTED]"
