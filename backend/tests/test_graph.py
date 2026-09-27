import os
import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.entities import (
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    ArchitectureReportEntity,
    ArchitectureDriftEntity,
    ProcessDefinition,
    ProcessStep,
    ProcessTransition,
)
from app.services.analysis.graph.projection import twin_graph_projection


@pytest.fixture
def sample_graph_repo(db_session: Session):
    """Sets up a test repository with two snapshots for graph projection tests."""
    uid = uuid.uuid4().hex[:8]
    proj = Project(name=f"Graph-Test-Project-{uid}", description="Graph Projection Test")
    db_session.add(proj)
    db_session.flush()

    repo = Repository(
        project_id=proj.id,
        name=f"graph-repo-{uid}",
        local_path=f"/tmp/test_repos/{uid}",
    )
    db_session.add(repo)
    db_session.flush()

    # Snapshot 1
    snap1 = RepositorySnapshot(
        id=f"snap_test_{uid}_1",
        repository_id=repo.id,
        commit_hash="commit_test_hash_1",
        branch_name="main",
    )
    db_session.add(snap1)

    # Artifacts in Snap 1
    art_mod = StructuralArtifact(
        id=f"art_mod_{uid}",
        repository_id=repo.id,
        snapshot_id=snap1.id,
        artifact_type="MODULE",
        language="python",
        name="payment_service.py",
        qualified_name="payment_service",
        location="services/payment_service.py:1",
        line_start=1,
        line_end=40,
        confidence=1.0,
    )
    art_class = StructuralArtifact(
        id=f"art_class_{uid}",
        repository_id=repo.id,
        snapshot_id=snap1.id,
        artifact_type="CLASS",
        language="python",
        name="PaymentService",
        qualified_name="payment_service.PaymentService",
        location="services/payment_service.py:10",
        line_start=10,
        line_end=40,
        confidence=1.0,
    )
    art_method = StructuralArtifact(
        id=f"art_method_{uid}",
        repository_id=repo.id,
        snapshot_id=snap1.id,
        artifact_type="METHOD",
        language="python",
        name="process_payment",
        qualified_name="payment_service.PaymentService.process_payment",
        location="services/payment_service.py:15",
        line_start=15,
        line_end=25,
        confidence=1.0,
    )
    art_test = StructuralArtifact(
        id=f"art_test_{uid}",
        repository_id=repo.id,
        snapshot_id=snap1.id,
        artifact_type="TEST_CASE",
        language="python",
        name="test_process_payment",
        qualified_name="test_payment.test_process_payment",
        location="tests/test_payment.py:5",
        line_start=5,
        line_end=12,
        confidence=1.0,
    )

    db_session.add_all([art_mod, art_class, art_method, art_test])
    db_session.flush()

    # Relationships in Snap 1
    rel_contains1 = ArtifactRelationship(
        id=f"rel_cont1_{uid}",
        repository_id=repo.id,
        snapshot_id=snap1.id,
        source_artifact_id=art_mod.id,
        target_artifact_id=art_class.id,
        relationship_type="CONTAINS",
        confidence=1.0,
        detection_method="ast_nesting",
        source_location="services/payment_service.py:10",
    )
    rel_contains2 = ArtifactRelationship(
        id=f"rel_cont2_{uid}",
        repository_id=repo.id,
        snapshot_id=snap1.id,
        source_artifact_id=art_class.id,
        target_artifact_id=art_method.id,
        relationship_type="CONTAINS",
        confidence=1.0,
        detection_method="ast_nesting",
        source_location="services/payment_service.py:15",
    )
    rel_tests = ArtifactRelationship(
        id=f"rel_tests_{uid}",
        repository_id=repo.id,
        snapshot_id=snap1.id,
        source_artifact_id=art_test.id,
        target_artifact_id=art_method.id,
        relationship_type="TESTS",
        confidence=1.0,
        detection_method="test_naming_convention",
        source_location="tests/test_payment.py:7",
        metadata_payload={"line": 7, "snippet": "assert service.process_payment()"},
    )
    db_session.add_all([rel_contains1, rel_contains2, rel_tests])

    # Snapshot 2 (for Diff testing: adds FraudService)
    snap2 = RepositorySnapshot(
        id=f"snap_test_{uid}_2",
        repository_id=repo.id,
        commit_hash="commit_test_hash_2",
        branch_name="main",
    )
    db_session.add(snap2)
    db_session.flush()

    art_fraud = StructuralArtifact(
        id=f"art_fraud_{uid}",
        repository_id=repo.id,
        snapshot_id=snap2.id,
        artifact_type="CLASS",
        language="python",
        name="FraudDetector",
        qualified_name="payment_service.FraudDetector",
        location="services/payment_service.py:45",
        line_start=45,
        line_end=60,
        confidence=1.0,
    )
    # Clone class to snap2
    art_class_s2 = StructuralArtifact(
        id=f"art_class2_{uid}",
        repository_id=repo.id,
        snapshot_id=snap2.id,
        artifact_type="CLASS",
        language="python",
        name="PaymentService",
        qualified_name="payment_service.PaymentService",
        location="services/payment_service.py:10",
        line_start=10,
        line_end=40,
        confidence=1.0,
    )
    rel_calls_fraud = ArtifactRelationship(
        id=f"rel_fraud_call_{uid}",
        repository_id=repo.id,
        snapshot_id=snap2.id,
        source_artifact_id=art_class_s2.id,
        target_artifact_id=art_fraud.id,
        relationship_type="CALLS",
        confidence=1.0,
        detection_method="ast_call_expression",
        source_location="services/payment_service.py:20",
        metadata_payload={"line": 20, "snippet": "self.fraud_detector.check()"},
    )
    db_session.add_all([art_fraud, art_class_s2, rel_calls_fraud])

    # Architecture Drift Violation in Snap 1
    rep = ArchitectureReportEntity(
        id=f"arch_rep_{uid}",
        repository_id=repo.id,
        snapshot_id=snap1.id,
        conformance_percentage=85.0,
        violations_count=1,
    )
    db_session.add(rep)
    db_session.flush()

    drift = ArchitectureDriftEntity(
        id=f"drift_{uid}",
        report_id=rep.id,
        repository_id=repo.id,
        snapshot_id=snap1.id,
        category="FORBIDDEN_DEPENDENCY",
        severity="HIGH",
        source="payment_service.PaymentService",
        target="payment_service.PaymentService.process_payment",
        relationship_type="CALLS",
        expected_rule="Test Rule Violation",
        actual_evidence="services/payment_service.py:15 -> raw call",
        file_path="services/payment_service.py",
        line_number=15,
        confidence=0.98,
    )
    db_session.add(drift)

    db_session.commit()
    return {
        "repo": repo,
        "snap1": snap1,
        "snap2": snap2,
        "art_class": art_class,
        "art_method": art_method,
        "art_test": art_test,
        "art_fraud": art_fraud,
    }


class TestDigitalTwinGraphProjection:
    """Comprehensive automated test suite for Phase 3.X visual graph projection."""

    def test_graph_projection_basic(self, db_session: Session, sample_graph_repo):
        repo = sample_graph_repo["repo"]
        snap1 = sample_graph_repo["snap1"]

        graph = twin_graph_projection.project_graph(
            db=db_session,
            repository_id=repo.id,
            snapshot_id=snap1.id,
            level=3,
        )

        assert graph["repository_id"] == repo.id
        assert graph["snapshot_id"] == snap1.id
        assert len(graph["nodes"]) >= 3
        assert len(graph["edges"]) >= 2
        assert graph["summary"]["total_nodes"] == len(graph["nodes"])
        assert graph["summary"]["total_edges"] == len(graph["edges"])

    def test_node_and_relationship_identity(self, db_session: Session, sample_graph_repo):
        repo = sample_graph_repo["repo"]
        snap1 = sample_graph_repo["snap1"]

        graph = twin_graph_projection.project_graph(
            db=db_session,
            repository_id=repo.id,
            snapshot_id=snap1.id,
            level=3,
        )

        node_ids = [n["id"] for n in graph["nodes"]]
        assert sample_graph_repo["art_class"].id in node_ids
        assert sample_graph_repo["art_method"].id in node_ids

        # Verify edge attributes
        edge = next((e for e in graph["edges"] if e["type"] == "TESTS"), None)
        assert edge is not None
        assert edge["evidence"]["line"] == 7
        assert "assert service.process_payment()" in edge["evidence"]["snippet"]

    def test_graph_level_filtering(self, db_session: Session, sample_graph_repo):
        repo = sample_graph_repo["repo"]
        snap1 = sample_graph_repo["snap1"]

        # Level 1: Packages and Modules only
        g_l1 = twin_graph_projection.project_graph(db=db_session, repository_id=repo.id, snapshot_id=snap1.id, level=1)
        l1_types = {n["type"] for n in g_l1["nodes"]}
        assert "METHOD" not in l1_types
        assert "CLASS" not in l1_types

        # Level 2: Classes and Modules included, Methods excluded
        g_l2 = twin_graph_projection.project_graph(db=db_session, repository_id=repo.id, snapshot_id=snap1.id, level=2)
        l2_types = {n["type"] for n in g_l2["nodes"]}
        assert "CLASS" in l2_types
        assert "METHOD" not in l2_types

        # Level 3: Methods included
        g_l3 = twin_graph_projection.project_graph(db=db_session, repository_id=repo.id, snapshot_id=snap1.id, level=3)
        l3_types = {n["type"] for n in g_l3["nodes"]}
        assert "METHOD" in l3_types

    def test_graph_depth_and_focus_traversal(self, db_session: Session, sample_graph_repo):
        repo = sample_graph_repo["repo"]
        snap1 = sample_graph_repo["snap1"]
        focus_class_id = sample_graph_repo["art_class"].id

        # Focus with depth 1
        g_focus = twin_graph_projection.project_graph(
            db=db_session,
            repository_id=repo.id,
            snapshot_id=snap1.id,
            focus=focus_class_id,
            depth=1,
            level=3,
        )

        focus_node_ids = {n["id"] for n in g_focus["nodes"]}
        assert focus_class_id in focus_node_ids
        assert sample_graph_repo["art_method"].id in focus_node_ids

    def test_snapshot_diff_projection(self, db_session: Session, sample_graph_repo):
        repo = sample_graph_repo["repo"]
        snap1 = sample_graph_repo["snap1"]
        snap2 = sample_graph_repo["snap2"]

        # Diff snap2 against snap1 (snap2 has FraudDetector added)
        diff_graph = twin_graph_projection.project_graph(
            db=db_session,
            repository_id=repo.id,
            snapshot_id=snap2.id,
            diff_snapshot_id=snap1.id,
            level=3,
        )

        added_node = next((n for n in diff_graph["nodes"] if n["name"] == "FraudDetector"), None)
        assert added_node is not None
        assert added_node["diff_status"] == "ADDED"

        # Check new relationship
        new_edge = next((e for e in diff_graph["edges"] if e["type"] == "CALLS"), None)
        assert new_edge is not None
        assert new_edge["diff_status"] == "NEW"

    def test_architecture_drift_overlay(self, db_session: Session, sample_graph_repo):
        repo = sample_graph_repo["repo"]
        snap1 = sample_graph_repo["snap1"]

        graph = twin_graph_projection.project_graph(
            db=db_session,
            repository_id=repo.id,
            snapshot_id=snap1.id,
            level=3,
        )

        drift_edge = next((e for e in graph["edges"] if e["is_drift"]), None)
        assert drift_edge is not None
        assert drift_edge["drift_details"]["severity"] == "HIGH"
        assert drift_edge["drift_details"]["expected_rule"] == "Test Rule Violation"

    def test_change_impact_blast_radius(self, db_session: Session, sample_graph_repo):
        repo = sample_graph_repo["repo"]
        snap1 = sample_graph_repo["snap1"]
        method_id = sample_graph_repo["art_method"].id

        graph = twin_graph_projection.project_graph(
            db=db_session,
            repository_id=repo.id,
            snapshot_id=snap1.id,
            impact_artifact_id=method_id,
            level=3,
        )

        impact_node = next((n for n in graph["nodes"] if n["id"] == method_id), None)
        assert impact_node is not None
        assert impact_node["is_impacted"] is True

        summary = graph["summary"]["impact_summary"]
        assert summary is not None
        assert summary["total_affected"] >= 1
        assert "test_payment.test_process_payment" in summary["affected_tests"]

    def test_file_tree_projection(self, db_session: Session, sample_graph_repo):
        repo = sample_graph_repo["repo"]
        snap1 = sample_graph_repo["snap1"]

        tree = twin_graph_projection.get_file_tree(
            db=db_session,
            repository_id=repo.id,
            snapshot_id=snap1.id,
        )

        assert tree["name"] == "repository"
        assert len(tree["children"]) >= 0

    def test_empty_repository_graph(self, db_session: Session):
        uid = uuid.uuid4().hex[:8]
        proj = Project(name=f"Empty-Proj-{uid}")
        db_session.add(proj)
        db_session.flush()

        empty_repo = Repository(
            project_id=proj.id,
            name=f"empty-repo-{uid}",
            local_path="/tmp/empty",
        )
        db_session.add(empty_repo)
        db_session.commit()

        graph = twin_graph_projection.project_graph(db=db_session, repository_id=empty_repo.id)
        assert graph["nodes"] == []
        assert graph["edges"] == []
        assert graph["snapshot_id"] is None

    def test_graph_api_endpoints(self, client: TestClient, sample_graph_repo):
        repo = sample_graph_repo["repo"]
        snap1 = sample_graph_repo["snap1"]

        # 1. Graph endpoint
        res = client.get(f"/repositories/{repo.id}/graph?snapshot_id={snap1.id}&level=3")
        assert res.status_code == 200
        data = res.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) >= 3

        # 2. Process graph endpoint
        res_proc = client.get(f"/repositories/{repo.id}/process-graph?snapshot_id={snap1.id}")
        assert res_proc.status_code == 200
        pdata = res_proc.json()
        assert "processes" in pdata
        assert "nodes" in pdata

        # 3. Snapshots endpoint
        res_snaps = client.get(f"/repositories/{repo.id}/graph/snapshots")
        assert res_snaps.status_code == 200
        snaps = res_snaps.json()
        assert len(snaps) == 2

        # 4. Web UI route
        res_ui = client.get("/app")
        assert res_ui.status_code == 200
