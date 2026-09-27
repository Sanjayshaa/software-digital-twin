"""
Phase 5 — Process Twin Discovery, Traversal, and Persistence Tests.
"""

import uuid
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.entities import (
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    ProcessDefinition,
    ProcessStep,
    ProcessTransition,
)
from app.services.process import process_service


@pytest.fixture
def process_test_env(db_session: Session):
    db_session.rollback()
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        name=f"Process Test Project {suffix}",
        description="Phase 5 Process Twin Test",
    )
    db_session.add(project)
    db_session.flush()

    repo = Repository(
        project_id=project.id,
        name=f"process_test_repo_{suffix}",
        local_path=f"/tmp/process_repos/{suffix}",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.flush()

    snapshot = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="a1b2c3d4e5f6",
        branch_name="main",
        total_files=5,
        total_symbols=10,
        snapshot_metadata={"test": True},
    )
    db_session.add(snapshot)
    db_session.flush()

    # Create artifacts: Endpoint -> Service -> Repository
    ep_art = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snapshot.id,
        name="dispatch_order_route",
        artifact_type="API_ENDPOINT",
        language="python",
        qualified_name="api.dispatch_order",
        location="api/routes.py",
        line_start=10,
        line_end=25,
    )
    db_session.add(ep_art)

    srv_art = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snapshot.id,
        name="dispatch_order",
        artifact_type="METHOD",
        language="python",
        qualified_name="dispatcher.OrderDispatcher.dispatch_order",
        location="dispatcher.py",
        line_start=6,
        line_end=18,
    )
    db_session.add(srv_art)

    inv_art = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snapshot.id,
        name="allocate_inventory",
        artifact_type="METHOD",
        language="python",
        qualified_name="inventory.InventoryClient.allocate_inventory",
        location="inventory.py",
        line_start=8,
        line_end=16,
    )
    db_session.add(inv_art)

    db_session.flush()

    # Link calls: ep_art -> srv_art -> inv_art
    r1 = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snapshot.id,
        source_artifact_id=ep_art.id,
        target_artifact_id=srv_art.id,
        relationship_type="CALLS",
        confidence=1.0,
        detection_method="ast_inspection",
    )
    r2 = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snapshot.id,
        source_artifact_id=srv_art.id,
        target_artifact_id=inv_art.id,
        relationship_type="CALLS",
        confidence=1.0,
        detection_method="ast_inspection",
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    yield {
        "project": project,
        "repo": repo,
        "snapshot": snapshot,
        "ep_art": ep_art,
        "srv_art": srv_art,
        "inv_art": inv_art,
        "session": db_session,
    }

    # Cleanup
    db_session.rollback()
    db_session.query(ProcessTransition).filter(
        ProcessTransition.process_id.in_(
            db_session.query(ProcessDefinition.id).filter_by(repository_id=repo.id)
        )
    ).delete(synchronize_session=False)
    db_session.query(ProcessStep).filter(
        ProcessStep.process_id.in_(
            db_session.query(ProcessDefinition.id).filter_by(repository_id=repo.id)
        )
    ).delete(synchronize_session=False)
    db_session.query(ProcessDefinition).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db_session.query(ArtifactRelationship).filter_by(snapshot_id=snapshot.id).delete(synchronize_session=False)
    db_session.query(StructuralArtifact).filter_by(snapshot_id=snapshot.id).delete(synchronize_session=False)
    db_session.query(RepositorySnapshot).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db_session.query(Repository).filter_by(id=repo.id).delete(synchronize_session=False)
    db_session.query(Project).filter_by(id=project.id).delete(synchronize_session=False)
    db_session.commit()


def test_process_discovery_from_entrypoints(process_test_env):
    """Verifies deterministic process discovery from API endpoint entry point through call chain."""
    env = process_test_env
    db = env["session"]
    repo = env["repo"]
    snapshot = env["snapshot"]

    result = process_service.discover_processes(
        db=db, repository_id=repo.id, snapshot_id=snapshot.id
    )

    assert result.total_processes >= 1
    assert result.total_steps >= 3
    assert result.total_transitions >= 2

    # Query persisted processes
    processes = process_service.list_processes(
        db=db, repository_id=repo.id, snapshot_id=snapshot.id
    )
    assert len(processes) >= 1
    proc = processes[0]
    assert proc.evidence_status == "INFERRED"
    assert len(proc.steps) == 3
    assert len(proc.transitions) == 2

    # Verify step sequence
    step_orders = [s.step_order for s in proc.steps]
    assert step_orders == [0, 1, 2]

    # Verify transition links
    t1 = proc.transitions[0]
    assert t1.transition_type == "CALLS"
    assert t1.evidence_status == "INFERRED"


def test_process_cyclic_dependency_protection(process_test_env):
    """Verifies that cyclic call loops terminate cleanly without infinite recursion."""
    env = process_test_env
    db = env["session"]
    snapshot = env["snapshot"]
    repo = env["repo"]

    # Add cycle: inv_art -> srv_art
    cycle_rel = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snapshot.id,
        source_artifact_id=env["inv_art"].id,
        target_artifact_id=env["srv_art"].id,
        relationship_type="CALLS",
        confidence=1.0,
        detection_method="ast_inspection",
    )
    db.add(cycle_rel)
    db.commit()

    # Should safely terminate with bounded depth and cycle suppression
    result = process_service.discover_processes(
        db=db, repository_id=repo.id, snapshot_id=snapshot.id
    )
    assert result.total_processes >= 1


def test_process_api_endpoints(process_test_env, client: TestClient):
    """Verifies REST API endpoints for process discovery, listing, and individual retrieval."""
    env = process_test_env
    repo = env["repo"]
    snapshot = env["snapshot"]

    # Trigger discovery via API
    disc_res = client.post(
        f"/repositories/{repo.id}/processes/discover",
        json={"snapshot_id": snapshot.id},
    )
    assert disc_res.status_code == 200
    disc_data = disc_res.json()
    assert disc_data["total_processes"] >= 1

    # List processes via API
    list_res = client.get(f"/repositories/{repo.id}/processes?snapshot_id={snapshot.id}")
    assert list_res.status_code == 200
    p_list = list_res.json()
    assert len(p_list) >= 1
    proc_id = p_list[0]["id"]

    # Get single process via API
    get_res = client.get(f"/repositories/{repo.id}/processes/{proc_id}")
    assert get_res.status_code == 200
    single = get_res.json()
    assert single["id"] == proc_id
    assert len(single["steps"]) >= 3
