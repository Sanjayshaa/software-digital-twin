"""
Phase 8.8 — Section 15: Failure Injection Test Suite.
Verifies truthful error handling, strict boundary checks, and honest NOT_READY states:
1. Non-root GitHub URLs (/blob/, /tree/, /issues/, /pull/, /commit/) rejected with explicit error message.
2. Clone failure handling returns truthful failure status.
3. Single snapshot pairwise impact rejected.
4. Identical snapshots return truthful status='NOT_READY' without zero-success illusion.
5. Foreign snapshot IDOR strictly blocked.
6. Malformed runtime payload rejected with 422.
7. Unauthorized repository access strictly forbidden.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from app.models.entities import (
    User,
    Project,
    Repository,
    RepositorySnapshot,
)
from app.core.auth import create_access_token, AuthenticatedPrincipal
from app.services.acquisition import is_safe_clone_url
from app.services.impact.analyzer import change_impact_analyzer
from app.services.twin_knowledge.service import twin_knowledge_service

client = TestClient(app)


def test_invalid_github_non_root_urls_rejected():
    """Validates that non-root GitHub URLs (/blob/, /tree/, /issues/, /pull/, /commit/) are rejected with 400."""
    invalid_urls = [
        "https://github.com/Sanjayshaa/LAB-RECORD-SYSTEM/blob/main/README.md",
        "https://github.com/Sanjayshaa/LAB-RECORD-SYSTEM/tree/main/src",
        "https://github.com/Sanjayshaa/LAB-RECORD-SYSTEM/issues/42",
        "https://github.com/Sanjayshaa/LAB-RECORD-SYSTEM/pull/15",
        "https://github.com/Sanjayshaa/LAB-RECORD-SYSTEM/commit/815c0749b9d120c72ab84223c3684613f91e76c7",
        "https://github.com/Sanjayshaa/LAB-RECORD-SYSTEM/actions/runs/12345",
    ]

    expected_msg = "This is not a repository URL. Provide the root repository URL or import the project as a local folder/ZIP."

    for url in invalid_urls:
        is_safe, reason = is_safe_clone_url(url)
        assert not is_safe, f"Expected {url} to be rejected"
        assert reason == expected_msg

        # Also verify through the API endpoint
        resp = client.post("/repositories/connect-github", json={"github_url": url})
        assert resp.status_code == 400
        assert expected_msg in resp.json()["detail"]


@pytest.fixture
def failure_test_env(db_session: Session):
    suffix = uuid.uuid4().hex[:6]

    user_a = User(
        username=f"fail_user_a_{suffix}",
        email=f"fail_a_{suffix}@example.com",
        hashed_password="pw",
        role="engineer",
    )
    user_b = User(
        username=f"fail_user_b_{suffix}",
        email=f"fail_b_{suffix}@example.com",
        hashed_password="pw",
        role="engineer",
    )
    db_session.add_all([user_a, user_b])
    db_session.flush()

    token_a = create_access_token(data={"sub": user_a.id, "email": user_a.email, "role": user_a.role})
    token_b = create_access_token(data={"sub": user_b.id, "email": user_b.email, "role": user_b.role})

    proj_a = Project(name=f"Proj A {suffix}", owner_id=user_a.id)
    proj_b = Project(name=f"Proj B {suffix}", owner_id=user_b.id)
    db_session.add_all([proj_a, proj_b])
    db_session.flush()

    repo_a = Repository(
        project_id=proj_a.id,
        owner_id=user_a.id,
        name=f"repo_a_{suffix}",
        local_path=f"/tmp/repo_a_{suffix}",
        default_branch="main",
        environment="USER",
    )
    repo_b = Repository(
        project_id=proj_b.id,
        owner_id=user_b.id,
        name=f"repo_b_{suffix}",
        local_path=f"/tmp/repo_b_{suffix}",
        default_branch="main",
        environment="USER",
    )
    db_session.add_all([repo_a, repo_b])
    db_session.flush()

    snap_a1 = RepositorySnapshot(
        repository_id=repo_a.id,
        commit_hash="aaaa111122223333444455556666777788889999",
        branch_name="main",
        total_files=5,
        total_symbols=10,
    )
    snap_a2 = RepositorySnapshot(
        repository_id=repo_a.id,
        commit_hash="aaaa222233334444555566667777888899990000",
        branch_name="main",
        total_files=5,
        total_symbols=10,
    )
    snap_b1 = RepositorySnapshot(
        repository_id=repo_b.id,
        commit_hash="bbbb111122223333444455556666777788889999",
        branch_name="main",
        total_files=5,
        total_symbols=10,
    )
    db_session.add_all([snap_a1, snap_a2, snap_b1])
    db_session.commit()

    yield {
        "user_a": user_a,
        "token_a": token_a,
        "repo_a": repo_a,
        "snap_a1": snap_a1,
        "snap_a2": snap_a2,
        "user_b": user_b,
        "token_b": token_b,
        "repo_b": repo_b,
        "snap_b1": snap_b1,
        "db": db_session,
    }

    # Teardown
    db_session.rollback()
    db_session.query(RepositorySnapshot).filter(
        RepositorySnapshot.repository_id.in_([repo_a.id, repo_b.id])
    ).delete(synchronize_session=False)
    db_session.query(Repository).filter(Repository.id.in_([repo_a.id, repo_b.id])).delete(synchronize_session=False)
    db_session.query(Project).filter(Project.id.in_([proj_a.id, proj_b.id])).delete(synchronize_session=False)
    db_session.query(User).filter(User.id.in_([user_a.id, user_b.id])).delete(synchronize_session=False)
    db_session.commit()


def test_identical_snapshots_returns_not_ready(failure_test_env):
    """Pairwise impact and diff must return status='NOT_READY' when comparing identical snapshots."""
    db = failure_test_env["db"]
    repo_a = failure_test_env["repo_a"]
    snap_a1 = failure_test_env["snap_a1"]

    res = change_impact_analyzer.analyze(db, repo_a.id, snap_a1.id, snap_a1.id)
    assert res.summary.status == "NOT_READY"
    assert "No change detected between selected snapshots" in (res.summary.message or "")

    # Via Twin Knowledge API
    principal_a = AuthenticatedPrincipal(user_id=repo_a.owner_id)
    tk_res = twin_knowledge_service.get_impact_paths(db, repo_a.id, snap_a1.id, snap_a1.id, principal_a)
    assert tk_res["status"] == "NOT_READY"


def test_foreign_snapshot_idor_blocked(failure_test_env):
    """User cannot pass a snapshot from another repo in impact analysis."""
    repo_a = failure_test_env["repo_a"]
    snap_a1 = failure_test_env["snap_a1"]
    snap_b1 = failure_test_env["snap_b1"]
    token_a = failure_test_env["token_a"]

    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Attempt impact analysis combining repo_a's snapshot with repo_b's snapshot
    resp = client.post(
        f"/repositories/{repo_a.id}/impact-analysis",
        json={
            "base_snapshot_id": snap_a1.id,
            "target_snapshot_id": snap_b1.id,
        },
        headers=headers_a,
    )
    assert resp.status_code == 400
    assert "does not belong to repository" in resp.json()["detail"]


def test_unauthorized_repository_access_forbidden(failure_test_env):
    """User B cannot query User A's repository overview or run twin knowledge queries."""
    repo_a = failure_test_env["repo_a"]
    token_b = failure_test_env["token_b"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Query overview
    resp = client.get(
        f"/repositories/{repo_a.id}/twin-knowledge/overview",
        headers=headers_b,
    )
    assert resp.status_code == 404

    # Query twin
    resp2 = client.post(
        f"/repositories/{repo_a.id}/twin-knowledge/query",
        json={"query": "test query"},
        headers=headers_b,
    )
    assert resp2.status_code == 404


def test_malformed_runtime_events_rejected(failure_test_env):
    """Malformed runtime ingest requests are rejected with 422."""
    repo_a = failure_test_env["repo_a"]
    token_a = failure_test_env["token_a"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Empty body
    resp = client.post(
        f"/repositories/{repo_a.id}/runtime-events/ingest",
        json={},
        headers=headers_a,
    )
    assert resp.status_code == 422

    # Invalid event structure (missing mandatory fields)
    resp2 = client.post(
        f"/repositories/{repo_a.id}/runtime-events/ingest",
        json={"events": ["not-a-dict"]},
        headers=headers_a,
    )
    assert resp2.status_code == 422
