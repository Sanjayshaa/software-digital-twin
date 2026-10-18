"""
Phase 8.6.2 — Security Domain C, E & F: Authorization, RBAC & Cross-User Isolation Tests.

Implements the mandatory Cross-User Test Fixtures and Test Matrix (Step 14):
USER_A / USER_B
REPO_A (owned by USER_A) / REPO_B (owned by USER_B)
SNAPSHOT_A / SNAPSHOT_B
SCENARIO_A / SCENARIO_B
INCIDENT_A / INCIDENT_B

Test Matrix:
- USER_A -> REPO_A = ALLOW (200)
- USER_B -> REPO_B = ALLOW (200)
- USER_A -> REPO_B = DENY (404)
- USER_B -> REPO_A = DENY (404)
- USER_A + REPO_A + SNAPSHOT_B = DENY (400/404)
- USER_B + REPO_B + SNAPSHOT_A = DENY (400/404)
- USER_A + REPO_A + SCENARIO_B = DENY (404)
- USER_B + REPO_B + SCENARIO_A = DENY (404)
- USER_A + REPO_A + INCIDENT_B = DENY (404)
- USER_B + REPO_B + INCIDENT_A = DENY (404)
- ADMIN_USER -> Any Repo = ALLOW
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.core.auth import (
    create_access_token,
    get_authorized_repository,
    AuthenticatedPrincipal,
)
from app.models.entities import (
    User,
    Project,
    Repository,
    RepositorySnapshot,
    Scenario,
    Incident,
)
from main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def cross_user_fixtures(db_session):
    """Sets up isolated USER_A and USER_B with distinct repositories and resources."""
    suffix = uuid.uuid4().hex[:6]

    # 1. Create Users
    user_a = User(
        username=f"user_a_{suffix}",
        email=f"user_a_{suffix}@example.com",
        hashed_password="dummy_hashed_password",
        role="engineer",
    )
    user_b = User(
        username=f"user_b_{suffix}",
        email=f"user_b_{suffix}@example.com",
        hashed_password="dummy_hashed_password",
        role="engineer",
    )
    admin_user = User(
        username=f"admin_{suffix}",
        email=f"admin_{suffix}@example.com",
        hashed_password="dummy_hashed_password",
        role="admin",
    )
    db_session.add_all([user_a, user_b, admin_user])
    db_session.flush()

    # 2. Create Projects and Repositories
    proj_a = Project(name=f"proj_a_{suffix}")
    proj_b = Project(name=f"proj_b_{suffix}")
    db_session.add_all([proj_a, proj_b])
    db_session.flush()

    repo_a = Repository(
        project_id=proj_a.id,
        owner_id=user_a.id,
        name=f"repo_a_{suffix}",
        local_path=f"/tmp/repo_a_{suffix}",
        environment="USER",
    )
    repo_b = Repository(
        project_id=proj_b.id,
        owner_id=user_b.id,
        name=f"repo_b_{suffix}",
        local_path=f"/tmp/repo_b_{suffix}",
        environment="USER",
    )
    db_session.add_all([repo_a, repo_b])
    db_session.flush()

    # 3. Create Snapshots
    snap_a = RepositorySnapshot(
        repository_id=repo_a.id,
        commit_hash="hash_a1",
        branch_name="main",
    )
    snap_b = RepositorySnapshot(
        repository_id=repo_b.id,
        commit_hash="hash_b1",
        branch_name="main",
    )
    db_session.add_all([snap_a, snap_b])
    db_session.flush()

    # 4. Create Scenarios
    scen_a = Scenario(
        project_id=proj_a.id,
        name=f"scen_a_{suffix}",
        scenario_type="simulation",
        parameters={"repository_id": repo_a.id, "status": "draft", "mutations": []},
    )
    scen_b = Scenario(
        project_id=proj_b.id,
        name=f"scen_b_{suffix}",
        scenario_type="simulation",
        parameters={"repository_id": repo_b.id, "status": "draft", "mutations": []},
    )
    db_session.add_all([scen_a, scen_b])
    db_session.flush()

    # 5. Create Incidents
    inc_a = Incident(
        project_id=proj_a.id,
        repository_id=repo_a.id,
        title=f"Incident A {suffix}",
        severity="high",
        status="open",
        description="Outage in repo A",
    )
    inc_b = Incident(
        project_id=proj_b.id,
        repository_id=repo_b.id,
        title=f"Incident B {suffix}",
        severity="medium",
        status="open",
        description="Degradation in repo B",
    )
    db_session.add_all([inc_a, inc_b])
    db_session.commit()

    # 6. Issue Tokens
    token_a = create_access_token(user_id=user_a.id, username=user_a.username, role=user_a.role)
    token_b = create_access_token(user_id=user_b.id, username=user_b.username, role=user_b.role)
    token_admin = create_access_token(user_id=admin_user.id, username=admin_user.username, role="admin")

    yield {
        "user_a": user_a,
        "user_b": user_b,
        "admin": admin_user,
        "repo_a": repo_a,
        "repo_b": repo_b,
        "snap_a": snap_a,
        "snap_b": snap_b,
        "scen_a": scen_a,
        "scen_b": scen_b,
        "inc_a": inc_a,
        "inc_b": inc_b,
        "token_a": token_a,
        "token_b": token_b,
        "token_admin": token_admin,
    }

    # Teardown
    db_session.delete(inc_a)
    db_session.delete(inc_b)
    db_session.delete(scen_a)
    db_session.delete(scen_b)
    db_session.delete(snap_a)
    db_session.delete(snap_b)
    db_session.delete(repo_a)
    db_session.delete(repo_b)
    db_session.delete(proj_a)
    db_session.delete(proj_b)
    db_session.delete(user_a)
    db_session.delete(user_b)
    db_session.delete(admin_user)
    db_session.commit()


def test_repository_ownership_authorization(cross_user_fixtures, db_session):
    """
    Verifies that get_authorized_repository enforces ownership:
    - User A accessing Repo A: ALLOW
    - User B accessing Repo B: ALLOW
    - User A accessing Repo B: DENY (404)
    - User B accessing Repo A: DENY (404)
    - Admin accessing Repo A & B: ALLOW
    """
    f = cross_user_fixtures
    principal_a = AuthenticatedPrincipal(user_id=f["user_a"].id, username=f["user_a"].username, role="engineer")
    principal_b = AuthenticatedPrincipal(user_id=f["user_b"].id, username=f["user_b"].username, role="engineer")
    principal_admin = AuthenticatedPrincipal(user_id=f["admin"].id, username=f["admin"].username, role="admin")

    # 1. Own repository access succeeds
    repo_a = get_authorized_repository(repository_id=f["repo_a"].id, principal=principal_a, db=db_session)
    assert repo_a.id == f["repo_a"].id

    repo_b = get_authorized_repository(repository_id=f["repo_b"].id, principal=principal_b, db=db_session)
    assert repo_b.id == f["repo_b"].id

    # 2. Cross-user access denied with 404 (non-disclosure)
    with pytest.raises(Exception) as exc_info_a:
        get_authorized_repository(repository_id=f["repo_b"].id, principal=principal_a, db=db_session)
    assert "404" in str(exc_info_a.value)

    with pytest.raises(Exception) as exc_info_b:
        get_authorized_repository(repository_id=f["repo_a"].id, principal=principal_b, db=db_session)
    assert "404" in str(exc_info_b.value)

    # 3. Admin user has universal access
    admin_repo_a = get_authorized_repository(repository_id=f["repo_a"].id, principal=principal_admin, db=db_session)
    assert admin_repo_a.id == f["repo_a"].id
    admin_repo_b = get_authorized_repository(repository_id=f["repo_b"].id, principal=principal_admin, db=db_session)
    assert admin_repo_b.id == f["repo_b"].id


def test_cross_repository_scenario_isolation(cross_user_fixtures):
    """
    Verifies that Scenario operations across repository boundaries are rejected with 404:
    - Repo A + Scenario B: DENY (404)
    - Repo B + Scenario A: DENY (404)
    """
    f = cross_user_fixtures
    # Access Scenario B through Repo A
    resp_ab = client.get(f"/repositories/{f['repo_a'].id}/scenarios/{f['scen_b'].id}")
    assert resp_ab.status_code == 404

    # Delete Scenario B through Repo A
    del_resp_ab = client.delete(f"/repositories/{f['repo_a'].id}/scenarios/{f['scen_b'].id}")
    assert del_resp_ab.status_code == 404

    # Access Scenario A through Repo B
    resp_ba = client.get(f"/repositories/{f['repo_b'].id}/scenarios/{f['scen_a'].id}")
    assert resp_ba.status_code == 404


def test_cross_repository_incident_isolation(cross_user_fixtures):
    """
    Verifies that Incident operations across repository boundaries are rejected with 404:
    - Repo A + Incident B: DENY (404)
    - Repo B + Incident A: DENY (404)
    """
    f = cross_user_fixtures
    # Access Incident B through Repo A
    resp_ab = client.get(f"/repositories/{f['repo_a'].id}/incidents/{f['inc_b'].id}")
    assert resp_ab.status_code == 404

    # Investigate Incident B through Repo A
    inv_ab = client.post(f"/repositories/{f['repo_a'].id}/incidents/{f['inc_b'].id}/investigate")
    assert inv_ab.status_code == 404

    # Access Incident A through Repo B
    resp_ba = client.get(f"/repositories/{f['repo_b'].id}/incidents/{f['inc_a'].id}")
    assert resp_ba.status_code == 404


def test_cross_repository_snapshot_mismatch(cross_user_fixtures):
    """
    Verifies that requesting impact analysis with a snapshot belonging to a different
    repository is rejected with 400 Bad Request.
    """
    f = cross_user_fixtures
    headers_a = {"Authorization": f"Bearer {f['token_a']}"}
    resp = client.post(
        f"/repositories/{f['repo_a'].id}/impact-analysis",
        headers=headers_a,
        json={
            "base_snapshot_id": f["snap_a"].id,
            "target_snapshot_id": f["snap_b"].id,  # foreign snapshot from repo B
        },
    )
    assert resp.status_code == 400
    assert "does not belong" in resp.json()["detail"].lower()


# ============================================================
# PHASE 8.7.6 — PART 13 MANDATORY BACKEND SECURITY TESTS
# ============================================================

def test_phase_876_test1_unauthenticated_get_repositories(cross_user_fixtures):
    """
    TEST 1: Unauthenticated GET /repositories.
    Expected: Empty authorized list (NEVER return another user's repositories).
    """
    resp = client.get("/repositories")
    assert resp.status_code == 200
    repos = resp.json()
    assert isinstance(repos, list)
    assert len(repos) == 0, f"Unauthenticated request must return 0 repositories, got {len(repos)}"


def test_phase_876_test2_user_b_cannot_enumerate_user_a_repository(cross_user_fixtures):
    """
    TEST 2: User A creates repository A. User B calls GET /repositories.
    Expected: repository A NOT returned. User B only sees their authorized repositories.
    """
    f = cross_user_fixtures
    headers_b = {"Authorization": f"Bearer {f['token_b']}"}
    resp = client.get("/repositories", headers=headers_b)
    assert resp.status_code == 200
    repos = resp.json()
    repo_ids = [r["id"] for r in repos]
    assert f["repo_a"].id not in repo_ids, "User A's repository leaked to User B in GET /repositories!"
    assert f["repo_b"].id in repo_ids, "User B should see their own repository."


def test_phase_876_test3_user_b_cannot_access_user_a_repo_overview(cross_user_fixtures):
    """
    TEST 3: User B requests GET /repositories/{repoA}/summary.
    Expected: 404 according to nondisclosure policy.
    """
    f = cross_user_fixtures
    headers_b = {"Authorization": f"Bearer {f['token_b']}"}
    resp = client.get(f"/repositories/{f['repo_a'].id}/summary", headers=headers_b)
    assert resp.status_code == 404, f"Expected 404 for cross-user repo summary, got {resp.status_code}"


def test_phase_876_test4_user_b_cannot_access_user_a_snapshots(cross_user_fixtures):
    """
    TEST 4: User B requests snapshot belonging to repository A.
    Expected: denied with 404.
    """
    f = cross_user_fixtures
    headers_b = {"Authorization": f"Bearer {f['token_b']}"}
    resp = client.get(f"/repositories/{f['repo_a'].id}/graph/snapshots", headers=headers_b)
    assert resp.status_code == 404, f"Expected 404 for cross-user snapshot access, got {resp.status_code}"


def test_phase_876_test5_user_b_cannot_access_user_a_graph(cross_user_fixtures):
    """
    TEST 5: User B requests graph for repository A.
    Expected: denied with 404.
    """
    f = cross_user_fixtures
    headers_b = {"Authorization": f"Bearer {f['token_b']}"}
    resp = client.get(f"/repositories/{f['repo_a'].id}/graph", headers=headers_b)
    assert resp.status_code == 404, f"Expected 404 for cross-user graph access, got {resp.status_code}"


def test_phase_876_test6_user_b_cannot_access_user_a_impact_analysis(cross_user_fixtures):
    """
    TEST 6: User B requests impact analysis for repository A.
    Expected: denied with 404.
    """
    f = cross_user_fixtures
    headers_b = {"Authorization": f"Bearer {f['token_b']}"}
    resp = client.post(
        f"/repositories/{f['repo_a'].id}/impact-analysis",
        headers=headers_b,
        json={
            "base_snapshot_id": f["snap_a"].id,
            "target_snapshot_id": f["snap_a"].id,
        },
    )
    assert resp.status_code == 404, f"Expected 404 for cross-user impact analysis, got {resp.status_code}"


def test_phase_876_test7_user_b_cannot_access_user_a_incident(cross_user_fixtures):
    """
    TEST 7: User B requests incident belonging to repository A.
    Expected: denied with 404.
    """
    f = cross_user_fixtures
    headers_b = {"Authorization": f"Bearer {f['token_b']}"}
    resp = client.get(f"/repositories/{f['repo_a'].id}/incidents/{f['inc_a'].id}", headers=headers_b)
    assert resp.status_code == 404, f"Expected 404 for cross-user incident access, got {resp.status_code}"


def test_phase_876_test8_guest_denied_all_repository_endpoints(cross_user_fixtures):
    """
    TEST 8: Guest attempts every repository endpoint without Authorization header.
    Expected: zero private repository information exposed (returns 404 for all repo operations).
    """
    f = cross_user_fixtures
    repo_id = f["repo_a"].id

    endpoints = [
        ("GET", f"/repositories/{repo_id}/summary"),
        ("GET", f"/repositories/{repo_id}/graph"),
        ("GET", f"/repositories/{repo_id}/graph/snapshots"),
        ("GET", f"/repositories/{repo_id}/components"),
        ("GET", f"/repositories/{repo_id}/file-tree"),
        ("GET", f"/repositories/{repo_id}/incidents"),
        ("GET", f"/repositories/{repo_id}/scenarios"),
        ("GET", f"/repositories/{repo_id}/runtime-events"),
        ("GET", f"/repositories/{repo_id}/tests-catalog"),
        ("GET", f"/repositories/{repo_id}/architecture/guardrails"),
    ]

    for method, path in endpoints:
        if method == "GET":
            r = client.get(path)
        assert r.status_code == 404, f"Guest accessing {path} got {r.status_code}, expected 404"


# ============================================================
# PHASE 8.7.7 — ZERO-TRUST WORKSPACE ISOLATION TEST SUITE
# ============================================================

def test_phase_877_matrix_m_test_env_isolation(cross_user_fixtures, db_session):
    """
    MATRIX M: Test environment isolation.
    Repositories with environment="TEST" or "FIXTURE" must NEVER appear in user list.
    """
    f = cross_user_fixtures
    suffix = uuid.uuid4().hex[:6]

    # Create a test environment repository owned by User A
    test_repo = Repository(
        project_id=f["repo_a"].project_id,
        owner_id=f["user_a"].id,
        name=f"test_repo_{suffix}",
        local_path=f"/tmp/test_repo_{suffix}",
        environment="TEST",
    )
    # Create a fixture repository
    fixture_repo = Repository(
        project_id=f["repo_a"].project_id,
        owner_id=f["user_a"].id,
        name=f"fixture_repo_{suffix}",
        local_path=f"/tmp/fixture_repo_{suffix}",
        environment="FIXTURE",
    )
    db_session.add_all([test_repo, fixture_repo])
    db_session.flush()

    headers_a = {"Authorization": f"Bearer {f['token_a']}"}
    resp = client.get("/repositories", headers=headers_a)
    assert resp.status_code == 200
    repos = resp.json()
    repo_ids = [r["id"] for r in repos]
    assert test_repo.id not in repo_ids, "TEST environment repo leaked into default production user listing!"
    assert fixture_repo.id not in repo_ids, "FIXTURE environment repo leaked into default production user listing!"


def test_phase_877_matrix_i_simulation_idor(cross_user_fixtures):
    """
    MATRIX I: Simulation IDOR isolation.
    User B attempting to read or simulate against User A's scenarios is rejected with 404.
    """
    f = cross_user_fixtures
    headers_b = {"Authorization": f"Bearer {f['token_b']}"}

    # User B requests User A's scenarios
    resp = client.get(f"/repositories/{f['repo_a'].id}/scenarios", headers=headers_b)
    assert resp.status_code == 404

    # User B attempts to run simulation on User A's repository
    resp_sim = client.post(
        f"/repositories/{f['repo_a'].id}/simulate",
        headers=headers_b,
        json={
            "scenario_name": "malicious_cross_sim",
            "base_snapshot_id": f["snap_a"].id,
            "proposed_changes": [],
        },
    )
    assert resp_sim.status_code == 404


def test_phase_877_matrix_runtime_events_and_guardrails_idor(cross_user_fixtures):
    """
    User B attempting to access User A's runtime events or architecture guardrails receives 404.
    """
    f = cross_user_fixtures
    headers_b = {"Authorization": f"Bearer {f['token_b']}"}

    # Runtime events
    resp = client.get(f"/repositories/{f['repo_a'].id}/runtime-events", headers=headers_b)
    assert resp.status_code == 404

    # Architecture guardrails
    resp_guard = client.get(f"/repositories/{f['repo_a'].id}/architecture/guardrails", headers=headers_b)
    assert resp_guard.status_code == 404


def test_phase_877_matrix_n_guest_ingestion_creates_isolated_tenant(db_session, monkeypatch):
    """
    MATRIX N: Repository creation ownership.
    When a guest onboards a repo (or connects GitHub), a private guest identity is provisioned,
    a JWT session token is returned, and another unauthenticated guest sees 0 repos.
    """
    # Mock structural twin engine to avoid disk operations in unit test
    class MockResult:
        files_scanned = 5
        artifacts = ["a1", "a2"]
        relationships = ["r1"]
        evidence_items = []
        analyzer_names = ["mock_analyzer"]

    from app.services.analysis.engine import structural_twin_engine
    monkeypatch.setattr(
        structural_twin_engine,
        "build_structural_twin",
        lambda db, repository_id, commit_hash, branch_name: ("snap_mock_1", MockResult())
    )

    # Ingest as guest
    resp = client.post(
        "/repositories/onboard",
        json={"local_path": "/Users/sanjay/DIGITAL TWIN /backend/app"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "session_token" in data, "Guest onboarding must return isolated session_token!"
    guest_token = data["session_token"]
    new_repo_id = data["repository_id"]

    # Verify repo is owned by the new guest user, NOT null
    repo = db_session.query(Repository).filter_by(id=new_repo_id).first()
    assert repo is not None
    assert repo.owner_id is not None, "Newly onboarded repo must have an owner_id!"
    assert repo.owner_id.startswith("usr_guest_")

    # A fresh guest calling GET /repositories still sees ZERO repositories!
    fresh_guest_resp = client.get("/repositories")
    assert fresh_guest_resp.status_code == 200
    assert len(fresh_guest_resp.json()) == 0, "Fresh guest must see 0 repositories!"

    # The guest with the token sees ONLY their new repository
    guest_headers = {"Authorization": f"Bearer {guest_token}"}
    guest_authed_resp = client.get("/repositories", headers=guest_headers)
    assert guest_authed_resp.status_code == 200
    guest_repos = guest_authed_resp.json()
    assert len(guest_repos) == 1
    assert guest_repos[0]["id"] == new_repo_id


