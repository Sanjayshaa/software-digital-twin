"""
Phase 5 — Incident Intelligence & Deterministic Causal Investigation Tests.
"""

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.entities import (
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    RuntimeEvent,
    Incident,
    IncidentEvidenceLink,
    ProcessDefinition,
    ProcessStep,
    ProcessTransition,
)
from app.services.incident import (
    IncidentCreate,
    incident_service,
)
from app.services.runtime import RawRuntimeEvent, runtime_evidence_service
from app.services.process import process_service


@pytest.fixture
def incident_test_env(db_session: Session):
    db_session.rollback()
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        name=f"Incident Test Project {suffix}",
        description="Phase 5 Incident Intelligence Test",
    )
    db_session.add(project)
    db_session.flush()

    repo = Repository(
        project_id=project.id,
        name=f"incident_test_repo_{suffix}",
        local_path=f"/tmp/incident_repos/{suffix}",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.flush()

    # Snapshot 1 (Base)
    snap1 = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="aaaa1111",
        branch_name="main",
        total_files=5,
        total_symbols=10,
        snapshot_metadata={"test": True},
    )
    db_session.add(snap1)
    db_session.flush()

    # Snapshot 2 (Target with change)
    snap2 = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="bbbb2222",
        branch_name="main",
        total_files=5,
        total_symbols=10,
        snapshot_metadata={"test": True},
    )
    db_session.add(snap2)
    db_session.flush()

    # Snap 1 artifacts
    s1_alloc = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap1.id,
        name="allocate_inventory",
        artifact_type="METHOD",
        language="python",
        qualified_name="inventory.allocate_inventory",
        location="inventory.py",
        line_start=10,
        line_end=20,
    )
    db_session.add(s1_alloc)

    # Snap 2 artifacts: dispatcher -> alloc -> storage + test
    s2_disp = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap2.id,
        name="dispatch_order",
        artifact_type="API_ENDPOINT",
        language="python",
        qualified_name="dispatcher.dispatch_order",
        location="dispatcher.py",
        line_start=5,
        line_end=15,
    )
    s2_alloc = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap2.id,
        name="allocate_inventory",
        artifact_type="METHOD",
        language="python",
        qualified_name="inventory.allocate_inventory",
        location="inventory.py",
        line_start=10,
        line_end=28,  # Modified lines
    )
    s2_storage = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap2.id,
        name="save_allocation",
        artifact_type="METHOD",
        language="python",
        qualified_name="storage.save_allocation",
        location="storage.py",
        line_start=5,
        line_end=12,
    )
    s2_test = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap2.id,
        name="test_dispatch_order",
        artifact_type="TEST_CASE",
        language="python",
        qualified_name="test_dispatch.test_dispatch_order",
        location="test_dispatch.py",
        line_start=4,
        line_end=10,
    )
    db_session.add_all([s2_disp, s2_alloc, s2_storage, s2_test])
    db_session.flush()

    # Relationships in Snap 2:
    # disp -> alloc (CALLS)
    # alloc -> storage (CALLS)
    # test -> disp (TESTS)
    r1 = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap2.id,
        source_artifact_id=s2_disp.id,
        target_artifact_id=s2_alloc.id,
        relationship_type="CALLS",
        confidence=1.0,
        detection_method="ast_inspection",
    )
    r2 = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap2.id,
        source_artifact_id=s2_alloc.id,
        target_artifact_id=s2_storage.id,
        relationship_type="CALLS",
        confidence=1.0,
        detection_method="ast_inspection",
    )
    r3 = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap2.id,
        source_artifact_id=s2_test.id,
        target_artifact_id=s2_disp.id,
        relationship_type="TESTS",
        confidence=1.0,
        detection_method="ast_inspection",
    )
    db_session.add_all([r1, r2, r3])
    db_session.flush()

    # Discover and persist process
    process_service.discover_processes(db=db_session, repository_id=repo.id, snapshot_id=snap2.id)

    # Ingest runtime error correlated to allocate_inventory
    raw_ev = RawRuntimeEvent(
        timestamp=datetime.now(timezone.utc),
        event_type="ERROR",
        service="dispatch-service",
        environment="production",
        severity="ERROR",
        message="Inventory allocation deadlock",
        trace_id="tr-inv-deadlock-101",
        attributes={"symbol": "allocate_inventory", "file_path": "inventory.py"},
    )
    ing_res = runtime_evidence_service.ingest_events(db=db_session, repository_id=repo.id, events=[raw_ev], snapshot_id=snap2.id)

    db_session.commit()

    yield {
        "project": project,
        "repo": repo,
        "snap1": snap1,
        "snap2": snap2,
        "s2_alloc": s2_alloc,
        "s2_disp": s2_disp,
        "session": db_session,
    }

    # Cleanup
    db_session.rollback()
    db_session.query(IncidentEvidenceLink).delete(synchronize_session=False)
    db_session.query(Incident).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db_session.query(RuntimeEvent).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db_session.query(ProcessTransition).filter(
        ProcessTransition.process_id.in_(db_session.query(ProcessDefinition.id).filter_by(repository_id=repo.id))
    ).delete(synchronize_session=False)
    db_session.query(ProcessStep).filter(
        ProcessStep.process_id.in_(db_session.query(ProcessDefinition.id).filter_by(repository_id=repo.id))
    ).delete(synchronize_session=False)
    db_session.query(ProcessDefinition).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db_session.query(ArtifactRelationship).filter(
        ArtifactRelationship.snapshot_id.in_([snap1.id, snap2.id])
    ).delete(synchronize_session=False)
    db_session.query(StructuralArtifact).filter(
        StructuralArtifact.snapshot_id.in_([snap1.id, snap2.id])
    ).delete(synchronize_session=False)
    db_session.query(RepositorySnapshot).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db_session.query(Repository).filter_by(id=repo.id).delete(synchronize_session=False)
    db_session.query(Project).filter_by(id=project.id).delete(synchronize_session=False)
    db_session.commit()


def test_incident_creation_and_linking(incident_test_env):
    """Verifies creating an incident and linking runtime evidence."""
    env = incident_test_env
    db = env["session"]
    repo = env["repo"]
    snap2 = env["snap2"]
    alloc_art = env["s2_alloc"]

    inc_req = IncidentCreate(
        title="Inventory Allocation Deadlock",
        severity="critical",
        environment="production",
        affected_component_name=alloc_art.name,
        description="Spike in 500 errors during order dispatch inventory allocation",
        snapshot_id=snap2.id,
    )

    inc = incident_service.create_incident(db=db, repository_id=repo.id, req=inc_req)
    assert inc.id is not None
    assert inc.severity == "critical"
    assert inc.status == "open"
    assert inc.affected_component_id == alloc_art.id
    assert len(inc.evidence_ids) >= 1


def test_incident_deterministic_investigation(incident_test_env):
    """Verifies deterministic investigation generates evidence-backed candidate causal paths."""
    env = incident_test_env
    db = env["session"]
    repo = env["repo"]
    snap2 = env["snap2"]
    alloc_art = env["s2_alloc"]

    inc_req = IncidentCreate(
        title="Production Allocation Failure",
        severity="high",
        environment="production",
        affected_component_name=alloc_art.name,
        snapshot_id=snap2.id,
    )
    inc = incident_service.create_incident(db=db, repository_id=repo.id, req=inc_req)

    # Execute deterministic investigation
    result = incident_service.investigate_incident(db=db, repository_id=repo.id, incident_id=inc.id)

    assert result.incident.id == inc.id
    assert len(result.observed_evidence) >= 1
    assert len(result.affected_entities) >= 1
    assert len(result.candidate_recent_changes) >= 1
    assert len(result.affected_processes) >= 1
    assert len(result.candidate_causal_paths) >= 1
    assert len(result.related_tests) >= 1
    assert len(result.uncertainties) >= 1

    # Verify first candidate causal path
    path = result.candidate_causal_paths[0]
    assert path.component_name == alloc_art.name
    assert path.confidence >= 0.70
    assert "connecting recently changed" in path.explanation or "directly modified" in path.explanation


def test_incident_investigation_reproducibility(incident_test_env):
    """Verifies deterministic reproducibility: repeating the investigation yields identical results."""
    env = incident_test_env
    db = env["session"]
    repo = env["repo"]
    snap2 = env["snap2"]
    alloc_art = env["s2_alloc"]

    inc = incident_service.create_incident(
        db=db,
        repository_id=repo.id,
        req=IncidentCreate(
            title="Repeatability Test Incident",
            severity="medium",
            affected_component_name=alloc_art.name,
            snapshot_id=snap2.id,
        ),
    )

    # Run twice
    res1 = incident_service.investigate_incident(db=db, repository_id=repo.id, incident_id=inc.id)
    res2 = incident_service.investigate_incident(db=db, repository_id=repo.id, incident_id=inc.id)

    # Check identical paths
    assert len(res1.candidate_causal_paths) == len(res2.candidate_causal_paths)
    for p1, p2 in zip(res1.candidate_causal_paths, res2.candidate_causal_paths):
        assert p1.relationship == p2.relationship
        assert p1.confidence == p2.confidence
        assert p1.component_id == p2.component_id


def test_incident_api_endpoints(incident_test_env, client: TestClient):
    """Verifies REST API endpoints for incident creation, listing, and investigation."""
    env = incident_test_env
    repo = env["repo"]
    alloc_art = env["s2_alloc"]

    # Create via API
    create_res = client.post(
        f"/repositories/{repo.id}/incidents",
        json={
            "title": "API Declared Incident",
            "severity": "high",
            "environment": "production",
            "affected_component_name": alloc_art.name,
            "description": "Declared via API test",
        },
    )
    assert create_res.status_code == 201
    inc_data = create_res.json()
    incident_id = inc_data["id"]

    # List via API
    list_res = client.get(f"/repositories/{repo.id}/incidents")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # Investigate via API
    inv_res = client.post(f"/repositories/{repo.id}/incidents/{incident_id}/investigate")
    assert inv_res.status_code == 200
    inv_data = inv_res.json()
    assert len(inv_data["candidate_causal_paths"]) >= 1
    assert "uncertainties" in inv_data
