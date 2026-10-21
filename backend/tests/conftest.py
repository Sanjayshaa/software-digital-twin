import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from main import app
from app.core.database import SessionLocal, get_db


from sqlalchemy import or_
from app.models.entities import (
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    AnalysisRun,
    Incident,
    RuntimeEvent,
    ArchitectureDriftEntity,
)


@pytest.fixture(scope="function")
def db_session():
    """Provides a transactional database session for tests."""
    session = SessionLocal()
    try:
        from app.models.entities import Project
        default_proj = session.query(Project).filter_by(id="default-project").first()
        if not default_proj:
            default_proj = Project(
                id="default-project",
                name="Default System Test Project",
                description="Seeded test project for unassigned repositories",
            )
            session.merge(default_proj)
            session.commit()
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="module")
def client():
    """Provides a FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


os.environ["APP_ENV"] = "test"


@pytest.fixture(autouse=True, scope="session")
def cleanup_test_repositories():
    """Cleans up any ephemeral test repositories after pytest suite finishes."""
    yield
    if os.environ.get("SKIP_DB_CLEANUP") == "1":
        return
    session = None
    try:
        session = SessionLocal()
        test_repos = (
            session.query(Repository)
            .filter(
                or_(
                    Repository.environment.in_(["TEST", "FIXTURE"]),
                    Repository.local_path.like("/tmp/%"),
                    Repository.local_path.like("/private/var/%"),
                    Repository.name.like("test-%"),
                    Repository.name.like("test_%"),
                    Repository.name.like("fixture-%"),
                    Repository.name.like("tmp-%"),
                    Repository.name.like("adv-%"),
                    Repository.name.like("adversarial-%"),
                    Repository.name.like("repo-%"),
                    Repository.name.like("controlled-repo-%"),
                    Repository.name.like("empty-repo-%"),
                    Repository.name.like("foreign_repo_%"),
                    Repository.name.like("arch-api-repo-%"),
                    Repository.name.like("arch-test-repo-%"),
                    Repository.name.like("real-repo-%"),
                    Repository.name.like("r1-%"),
                    Repository.name.like("r2-%"),
                    Repository.name.like("repo_a_%"),
                    Repository.name.like("repo_b_%"),
                    Repository.name.like("sim-%"),
                    Repository.name.like("sim_%"),
                    Repository.name.like("risk-repo-%"),
                    Repository.name.like("integrity_repo_%"),
                    Repository.name.like("graph-repo-%"),
                    Repository.name.like("blast_proof_repo_%"),
                )
            )
            .all()
        )
        for r in test_repos:
            snaps = session.query(RepositorySnapshot).filter_by(repository_id=r.id).all()
            for s in snaps:
                session.query(StructuralArtifact).filter_by(snapshot_id=s.id).delete()
                session.query(ArtifactRelationship).filter_by(snapshot_id=s.id).delete()
                session.query(ArchitectureDriftEntity).filter_by(snapshot_id=s.id).delete()
                session.query(AnalysisRun).filter_by(snapshot_id=s.id).delete()
                session.delete(s)
            session.query(Incident).filter_by(repository_id=r.id).delete()
            session.query(RuntimeEvent).filter_by(repository_id=r.id).delete()
            session.delete(r)
        session.commit()
    except Exception as e:
        if session:
            session.rollback()
        print(f"Warning: test repo cleanup error: {e}")
    finally:
        if session:
            session.close()
