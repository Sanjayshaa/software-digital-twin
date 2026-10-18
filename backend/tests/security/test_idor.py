"""
Phase 8.6.1 — Security Domain D & G: IDOR / BOLA (Broken Object Level Authorization) Audit Tests.

Tests:
1. SEC-03: Verifies whether Scenario operations enforce repository ownership boundaries.
2. SEC-04: Verifies whether Incident inspection/investigation enforces repository ownership boundaries.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.models.entities import Project, Repository, RepositorySnapshot, Scenario, Incident
from main import app

client = TestClient(app)


def test_scenario_cross_repository_ownership_isolation(db_session):
    """
    IDOR Audit Test (SEC-03):
    Creates Repository A and Repository B.
    Creates Scenario A tied to Repository A.
    Attempts to fetch and delete Scenario A through Repository B's endpoint:
    GET /repositories/{repo_B_id}/scenarios/{scenario_A_id}
    DELETE /repositories/{repo_B_id}/scenarios/{scenario_A_id}

    Records whether current implementation enforces repo boundary or allows IDOR.
    """
    proj = Project(name=f"test-idor-proj-{uuid.uuid4().hex[:6]}")
    db_session.add(proj)
    db_session.flush()

    repo_a = Repository(project_id=proj.id, name=f"test-repo-a-{uuid.uuid4().hex[:6]}", remote_url="https://github.com/test/a", local_path="/tmp/repo_a")
    repo_b = Repository(project_id=proj.id, name=f"test-repo-b-{uuid.uuid4().hex[:6]}", remote_url="https://github.com/test/b", local_path="/tmp/repo_b")
    db_session.add_all([repo_a, repo_b])
    db_session.flush()

    scenario_a = Scenario(
        project_id=proj.id,
        name="Scenario A",
        scenario_type="simulation",
        parameters={
            "repository_id": str(repo_a.id),
            "status": "draft",
            "mutations": [],
        },
    )
    db_session.add(scenario_a)
    db_session.commit()

    # Attempt cross-repo access: Access Scenario A via Repo B endpoint
    # Under strict authorization, this MUST return 404.
    resp = client.get(f"/repositories/{repo_b.id}/scenarios/{scenario_a.id}")
    assert resp.status_code == 404, f"CRITICAL: IDOR vulnerability detected! Expected 404, got {resp.status_code}"

    # Attempt cross-repo deletion: Delete Scenario A via Repo B endpoint
    del_resp = client.delete(f"/repositories/{repo_b.id}/scenarios/{scenario_a.id}")
    assert del_resp.status_code == 404, f"CRITICAL: IDOR vulnerability detected! Expected 404 on delete, got {del_resp.status_code}"

    # Verify Scenario A was NOT deleted
    persisted_scen = db_session.query(Scenario).filter_by(id=scenario_a.id).first()
    assert persisted_scen is not None, "CRITICAL: Scenario A was deleted across repository boundary!"

    # Clean up
    db_session.delete(scenario_a)
    db_session.delete(repo_a)
    db_session.delete(repo_b)
    db_session.delete(proj)
    db_session.commit()


def test_incident_cross_repository_ownership_isolation(db_session):
    """
    IDOR Fix Verification (SEC-04):
    Creates Repository A and Repository B.
    Creates Incident A tied to Repository A.
    Attempts to fetch Incident A through Repository B's endpoint:
    GET /repositories/{repo_B_id}/incidents/{incident_A_id}
    POST /repositories/{repo_B_id}/incidents/{incident_A_id}/investigate

    Verifies that cross-repository incident access returns 404.
    """
    proj = Project(name=f"test-incident-idor-proj-{uuid.uuid4().hex[:6]}")
    db_session.add(proj)
    db_session.flush()

    repo_a = Repository(project_id=proj.id, name=f"test-inc-repo-a-{uuid.uuid4().hex[:6]}", remote_url="https://github.com/test/a", local_path="/tmp/inc_repo_a")
    repo_b = Repository(project_id=proj.id, name=f"test-inc-repo-b-{uuid.uuid4().hex[:6]}", remote_url="https://github.com/test/b", local_path="/tmp/inc_repo_b")
    db_session.add_all([repo_a, repo_b])
    db_session.flush()

    incident_a = Incident(
        project_id=proj.id,
        repository_id=repo_a.id,
        title="Test Outage A",
        severity="high",
        status="open",
        description="Outage in repo A",
    )
    db_session.add(incident_a)
    db_session.commit()

    resp = client.get(f"/repositories/{repo_b.id}/incidents/{incident_a.id}")
    assert resp.status_code == 404, f"CRITICAL: IDOR vulnerability detected! Expected 404, got {resp.status_code}"

    inv_resp = client.post(f"/repositories/{repo_b.id}/incidents/{incident_a.id}/investigate")
    assert inv_resp.status_code == 404, f"CRITICAL: IDOR investigation vulnerability detected! Expected 404, got {inv_resp.status_code}"

    # Clean up
    db_session.delete(incident_a)
    db_session.delete(repo_a)
    db_session.delete(repo_b)
    db_session.delete(proj)
    db_session.commit()
