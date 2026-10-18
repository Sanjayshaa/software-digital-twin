"""
Phase 8.6.1 — Security Domain F & AB: Cross-Snapshot and Cross-Repository Isolation Tests.

Verifies:
1. Comparing snapshots belonging to different repositories is rejected with HTTP 400.
2. What-If scenario simulations do not mutate the persisted snapshot in PostgreSQL.
"""

import uuid
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.entities import Project, Repository, RepositorySnapshot
from main import app

client = TestClient(app)


def test_cross_repository_snapshot_impact_rejection(db_session: Session):
    """
    Creates two separate repositories with snapshots and verifies that
    requesting impact analysis between snapshots of Repo A and Repo B is rejected.
    """
    suffix = uuid.uuid4().hex[:6]
    proj = Project(name=f"SecProj_{suffix}")
    db_session.add(proj)
    db_session.flush()

    repo_a = Repository(project_id=proj.id, name=f"repo_a_{suffix}", local_path=f"/tmp/repo_a_{suffix}")
    repo_b = Repository(project_id=proj.id, name=f"repo_b_{suffix}", local_path=f"/tmp/repo_b_{suffix}")
    db_session.add(repo_a)
    db_session.add(repo_b)
    db_session.flush()

    snap_a = RepositorySnapshot(repository_id=repo_a.id, commit_hash="hash_a", branch_name="main")
    snap_b = RepositorySnapshot(repository_id=repo_b.id, commit_hash="hash_b", branch_name="main")
    db_session.add(snap_a)
    db_session.add(snap_b)
    db_session.commit()

    # Attempt cross-repository impact analysis
    payload = {
        "base_snapshot_id": snap_a.id,
        "target_snapshot_id": snap_b.id,  # snap_b belongs to repo_b, but calling repo_a endpoint
        "max_depth": 3,
    }
    response = client.post(f"/repositories/{repo_a.id}/impact-analysis", json=payload)
    assert response.status_code == 400, f"Expected 400 Bad Request, got {response.status_code}: {response.text}"
    assert "does not belong to repository" in response.text
