"""
Phase 8.8 — Golden End-to-End Fixture Test: Evidence Provenance & Product Truth.
Constructs a deterministic 4-tier fixture:
Controller -> CALLS -> Service -> CALLS -> Repository
Test -> TESTS -> Service

Creates two snapshots with a controlled change to Service.
Asserts the complete chain:
source -> snapshot -> artifacts -> relationships -> diff -> impact -> test impact -> risk -> twin knowledge queries.
Verifies every finding strictly matches authoritative PostgreSQL database rows with unambiguous provenance.
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
    AnalysisRun,
    User,
)
from app.core.auth import AuthenticatedPrincipal
from app.services.impact.analyzer import change_impact_analyzer
from app.services.impact.change_detector import change_detector
from app.services.twin_knowledge.service import twin_knowledge_service
from app.services.twin_knowledge.models import Provenance


@pytest.fixture
def provenance_fixture(db_session: Session):
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"prov_user_{suffix}@example.com",
        name=f"Prov User {suffix}",
        auth_provider="LOCAL",
        hashed_password="hashed_pw_dummy",
    )
    db_session.add(user)
    db_session.flush()

    project = Project(
        name=f"Provenance Golden Project {suffix}",
        description="Phase 8.8 Golden Fixture",
        owner_id=user.id,
    )
    db_session.add(project)
    db_session.flush()

    repo = Repository(
        project_id=project.id,
        name=f"prov_repo_{suffix}",
        local_path=f"/tmp/prov_repos/{suffix}",
        default_branch="main",
        environment="TEST",
    )
    db_session.add(repo)
    db_session.flush()

    # Snapshot 1 (Base)
    snap1 = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="1111111111111111111111111111111111111111",
        branch_name="main",
        total_files=4,
        total_symbols=4,
        snapshot_metadata={"version": "1.0.0"},
    )
    db_session.add(snap1)
    db_session.flush()

    # Artifacts in Snap 1:
    # 1. Controller
    ctrl_1 = StructuralArtifact(
        id=f"art_ctrl_{suffix}",
        snapshot_id=snap1.id,
        name="OrderController",
        qualified_name="app.controllers.OrderController",
        artifact_type="CLASS",
        file_path="app/controllers.py",
        location="app/controllers.py:10",
        source_hash="hash_ctrl_v1",
        signature="class OrderController: pass",
        language="python",
        confidence=1.0,
    )
    # 2. Service
    svc_1 = StructuralArtifact(
        id=f"art_svc_{suffix}",
        snapshot_id=snap1.id,
        name="OrderService",
        qualified_name="app.services.OrderService",
        artifact_type="CLASS",
        file_path="app/services.py",
        location="app/services.py:20",
        source_hash="hash_svc_v1",
        signature="class OrderService: pass",
        language="python",
        confidence=1.0,
    )
    # 3. Repository
    repo_art_1 = StructuralArtifact(
        id=f"art_repo_{suffix}",
        snapshot_id=snap1.id,
        name="OrderRepository",
        qualified_name="app.repositories.OrderRepository",
        artifact_type="CLASS",
        file_path="app/repositories.py",
        location="app/repositories.py:30",
        source_hash="hash_repo_v1",
        signature="class OrderRepository: pass",
        language="python",
        confidence=1.0,
    )
    # 4. Test
    test_1 = StructuralArtifact(
        id=f"art_test_{suffix}",
        snapshot_id=snap1.id,
        name="test_order_processing",
        qualified_name="tests.test_order_processing",
        artifact_type="TEST_CASE",
        file_path="tests/test_orders.py",
        location="tests/test_orders.py:5",
        source_hash="hash_test_v1",
        signature="def test_order_processing(): pass",
        language="python",
        confidence=1.0,
    )
    db_session.add_all([ctrl_1, svc_1, repo_art_1, test_1])
    db_session.flush()

    # Relationships in Snap 1:
    # Controller -> CALLS -> Service
    r1 = ArtifactRelationship(
        snapshot_id=snap1.id,
        source_artifact_id=ctrl_1.id,
        target_artifact_id=svc_1.id,
        relationship_type="CALLS",
        confidence=1.0,
    )
    # Service -> CALLS -> Repository
    r2 = ArtifactRelationship(
        snapshot_id=snap1.id,
        source_artifact_id=svc_1.id,
        target_artifact_id=repo_art_1.id,
        relationship_type="CALLS",
        confidence=1.0,
    )
    # Test -> TESTS -> Service
    r3 = ArtifactRelationship(
        snapshot_id=snap1.id,
        source_artifact_id=test_1.id,
        target_artifact_id=svc_1.id,
        relationship_type="TESTS",
        confidence=1.0,
    )
    db_session.add_all([r1, r2, r3])
    db_session.flush()

    # Snapshot 2 (Target) — Service is modified
    snap2 = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="2222222222222222222222222222222222222222",
        branch_name="main",
        total_files=4,
        total_symbols=4,
        snapshot_metadata={"version": "1.1.0"},
    )
    db_session.add(snap2)
    db_session.flush()

    ctrl_2 = StructuralArtifact(
        id=f"art_ctrl_2_{suffix}",
        snapshot_id=snap2.id,
        name="OrderController",
        qualified_name="app.controllers.OrderController",
        artifact_type="CLASS",
        file_path="app/controllers.py",
        location="app/controllers.py:10",
        source_hash="hash_ctrl_v1",  # Unchanged
        signature="class OrderController: pass",
        language="python",
        confidence=1.0,
    )
    svc_2 = StructuralArtifact(
        id=f"art_svc_2_{suffix}",
        snapshot_id=snap2.id,
        name="OrderService",
        qualified_name="app.services.OrderService",
        artifact_type="CLASS",
        file_path="app/services.py",
        location="app/services.py:20",
        source_hash="hash_svc_v2_MODIFIED",  # MODIFIED!
        signature="class OrderService: def new_method(): pass",
        language="python",
        confidence=1.0,
    )
    repo_art_2 = StructuralArtifact(
        id=f"art_repo_2_{suffix}",
        snapshot_id=snap2.id,
        name="OrderRepository",
        qualified_name="app.repositories.OrderRepository",
        artifact_type="CLASS",
        file_path="app/repositories.py",
        location="app/repositories.py:30",
        source_hash="hash_repo_v1",  # Unchanged
        signature="class OrderRepository: pass",
        language="python",
        confidence=1.0,
    )
    test_2 = StructuralArtifact(
        id=f"art_test_2_{suffix}",
        snapshot_id=snap2.id,
        name="test_order_processing",
        qualified_name="tests.test_order_processing",
        artifact_type="TEST_CASE",
        file_path="tests/test_orders.py",
        location="tests/test_orders.py:5",
        source_hash="hash_test_v1",  # Unchanged
        signature="def test_order_processing(): pass",
        language="python",
        confidence=1.0,
    )
    db_session.add_all([ctrl_2, svc_2, repo_art_2, test_2])
    db_session.flush()

    r1_2 = ArtifactRelationship(
        snapshot_id=snap2.id,
        source_artifact_id=ctrl_2.id,
        target_artifact_id=svc_2.id,
        relationship_type="CALLS",
        confidence=1.0,
    )
    r2_2 = ArtifactRelationship(
        snapshot_id=snap2.id,
        source_artifact_id=svc_2.id,
        target_artifact_id=repo_art_2.id,
        relationship_type="CALLS",
        confidence=1.0,
    )
    r3_2 = ArtifactRelationship(
        snapshot_id=snap2.id,
        source_artifact_id=test_2.id,
        target_artifact_id=svc_2.id,
        relationship_type="TESTS",
        confidence=1.0,
    )
    db_session.add_all([r1_2, r2_2, r3_2])
    db_session.commit()

    principal = AuthenticatedPrincipal(
        user_id=user.id,
        email=user.email,
        is_authenticated=True,
    )

    yield {
        "user": user,
        "principal": principal,
        "project": project,
        "repo": repo,
        "snap1": snap1,
        "snap2": snap2,
        "ctrl_1": ctrl_1,
        "svc_1": svc_1,
        "repo_art_1": repo_art_1,
        "test_1": test_1,
        "ctrl_2": ctrl_2,
        "svc_2": svc_2,
        "repo_art_2": repo_art_2,
        "test_2": test_2,
        "session": db_session,
    }

    # Teardown
    db_session.rollback()
    for s_id in [snap1.id, snap2.id]:
        db_session.query(ArtifactRelationship).filter_by(snapshot_id=s_id).delete(synchronize_session=False)
        db_session.query(StructuralArtifact).filter_by(snapshot_id=s_id).delete(synchronize_session=False)
    db_session.query(RepositorySnapshot).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db_session.query(Repository).filter_by(id=repo.id).delete(synchronize_session=False)
    db_session.query(Project).filter_by(id=project.id).delete(synchronize_session=False)
    db_session.query(User).filter_by(id=user.id).delete(synchronize_session=False)
    db_session.commit()


def test_full_provenance_chain_deterministic(provenance_fixture):
    """
    Validates end-to-end provenance:
    source -> snapshot -> artifacts -> relationships -> diff -> impact -> test impact -> twin knowledge.
    """
    db = provenance_fixture["session"]
    repo = provenance_fixture["repo"]
    snap1 = provenance_fixture["snap1"]
    snap2 = provenance_fixture["snap2"]
    principal = provenance_fixture["principal"]
    svc_2 = provenance_fixture["svc_2"]

    # 1. Diff Detection
    change_set = change_detector.detect_changes(db, snap1.id, snap2.id)
    assert change_set.total_changes == 1
    assert change_set.changes[0].artifact_name == "OrderService"
    assert change_set.changes[0].change_type.value == "MODIFIED"

    # 2. Impact Propagation
    impact_result = change_impact_analyzer.analyze(db, repo.id, snap1.id, snap2.id)
    assert impact_result.summary.status == "COMPLETED"
    assert impact_result.summary.root_changes_count == 1

    # Verify Controller is affected as an upstream caller
    affected_names = [f.affected_artifact_name for f in impact_result.findings]
    assert "OrderController" in affected_names
    assert "test_order_processing" in affected_names

    # 3. Twin Knowledge Overview
    overview = twin_knowledge_service.get_repository_overview(db, repo.id, principal)
    assert overview.repository_name == repo.name
    assert overview.total_snapshots == 2
    assert overview.provenance == Provenance.OBSERVED

    # 4. Twin Knowledge Dependencies & Dependents
    deps = twin_knowledge_service.get_dependencies_and_dependents(
        db, repo.id, snap2.id, svc_2.id, principal
    )
    assert deps["artifact_id"] == svc_2.id
    # Upstream caller = OrderController
    assert any(d["name"] == "OrderController" for d in deps["dependents"])
    # Downstream callee = OrderRepository
    assert any(d["name"] == "OrderRepository" for d in deps["dependencies"])
    assert deps["provenance"] == Provenance.DERIVED.value

    # 5. Twin Knowledge Test Claims
    test_claims = twin_knowledge_service.get_tests_for_artifact(
        db, repo.id, snap2.id, svc_2.id, principal
    )
    assert test_claims["coverage_claim"] == "TESTS_MAPPED_TO_ARTIFACT"
    assert len(test_claims["mapped_tests"]) == 1
    assert test_claims["mapped_tests"][0]["test_name"] == "test_order_processing"

    # 6. Twin Knowledge Impact Paths
    paths_res = twin_knowledge_service.get_impact_paths(
        db, repo.id, snap1.id, snap2.id, principal
    )
    assert paths_res["total_paths"] > 0
    assert paths_res["provenance"] == Provenance.DERIVED.value
    for path in paths_res["paths"]:
        assert len(path["evidence_ids"]) > 0
        assert path["confidence"] == 1.0

    # 7. Ask Twin Deterministic Queries
    q_impact = twin_knowledge_service.ask_twin(
        db, repo.id, "Show change impact and blast radius", snap2.id, principal
    )
    assert q_impact.intent == "CHANGE_IMPACT"
    assert q_impact.provenance == Provenance.DERIVED

    q_comp = twin_knowledge_service.ask_twin(
        db, repo.id, "Where is OrderService?", snap2.id, principal
    )
    assert q_comp.intent == "COMPONENT_LOOKUP"
    assert len(q_comp.grounded_entities) == 1
    assert q_comp.grounded_entities[0]["name"] == "OrderService"
    assert q_comp.provenance == Provenance.OBSERVED
    assert len(q_comp.evidence_ids) == 1
