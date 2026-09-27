"""
Phase 4 — Change Impact & Blast Radius Analysis Comprehensive Test Suite.
Validates all 14 mandatory scenarios specified in Section 39:
1. Direct dependency (A -> B)
2. Transitive dependency (A -> B -> C -> D)
3. Unrelated components isolation (A -> B vs C -> D)
4. Affected test discovery (Component -> Test)
5. API consumer propagation (Service -> API -> Consumer)
6. Business process propagation (Component -> Process -> Step)
7. Deleted artifact historical relationship handling
8. Cycle protection and termination safety (A -> B -> C -> A)
9. Bounded traversal and max_depth enforcement
10. Duplicate path canonicalization and suppression
11. Snapshot immutability verification
12. Deterministic execution and ordering repeatability
13. Symbol-level change detection (AST comparison)
14. File-level fallback with explicit provenance
Plus API endpoints and error handling verification.
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
)
from app.services.impact.models import (
    ChangeSet,
    ChangeItem,
    ChangeType,
    ImpactConfig,
    ImpactFinding,
    ImpactResult,
)
from app.services.impact.change_detector import change_detector
from app.services.impact.propagator import impact_propagator
from app.services.impact.path_finder import impact_path_finder
from app.services.impact.analyzer import change_impact_analyzer
from app.services.impact.service import change_impact_service


@pytest.fixture
def impact_test_env(db_session: Session):
    """Sets up a clean project and repository for impact tests."""
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        name=f"Impact Test Project {suffix}",
        description="Phase 4 Impact Test Project",
    )
    db_session.add(project)
    db_session.flush()

    repo = Repository(
        project_id=project.id,
        name=f"impact_test_repo_{suffix}",
        local_path=f"/tmp/test_repos/{suffix}",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()

    yield {"project": project, "repo": repo, "session": db_session}

    # Cleanup
    db_session.rollback()
    db_session.query(ArtifactRelationship).filter(
        ArtifactRelationship.snapshot_id.in_(
            db_session.query(RepositorySnapshot.id).filter_by(repository_id=repo.id)
        )
    ).delete(synchronize_session=False)
    db_session.query(StructuralArtifact).filter(
        StructuralArtifact.snapshot_id.in_(
            db_session.query(RepositorySnapshot.id).filter_by(repository_id=repo.id)
        )
    ).delete(synchronize_session=False)
    db_session.query(AnalysisRun).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db_session.query(RepositorySnapshot).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db_session.query(Repository).filter_by(id=repo.id).delete(synchronize_session=False)
    db_session.query(Project).filter_by(id=project.id).delete(synchronize_session=False)
    db_session.commit()


def _create_snapshot(db: Session, repo_id: str, commit_hash: str) -> RepositorySnapshot:
    snap = RepositorySnapshot(
        repository_id=repo_id,
        commit_hash=commit_hash,
        branch_name="main",
        total_files=5,
        total_symbols=10,
        snapshot_metadata={"test": True},
    )
    db.add(snap)
    db.flush()
    return snap


def _create_artifact(
    db: Session,
    snap_id: str,
    repo_id: str,
    name: str,
    qual_name: str,
    art_type: str,
    loc: str = "pkg/mod.py:10",
    source_hash: str = "hash_v1",
    signature: str = "def foo(): pass",
    line_start: int = 1,
    line_end: int = 10,
    language: str = "python",
) -> StructuralArtifact:
    art_id = f"art_{uuid.uuid4().hex[:16]}"
    art = StructuralArtifact(
        id=art_id,
        repository_id=repo_id,
        snapshot_id=snap_id,
        name=name,
        qualified_name=qual_name,
        artifact_type=art_type,
        language=language,
        location=loc,
        source_hash=source_hash,
        signature=signature,
        line_start=line_start,
        line_end=line_end,
        confidence=1.0,
        metadata_payload={},
    )
    db.add(art)
    db.flush()
    return art


def _create_rel(
    db: Session,
    snap_id: str,
    repo_id: str,
    source_id: str,
    target_id: str,
    rel_type: str,
    confidence: float = 1.0,
    loc: str = "pkg/mod.py:15",
) -> ArtifactRelationship:
    rel_id = f"rel_{uuid.uuid4().hex[:16]}"
    rel = ArtifactRelationship(
        id=rel_id,
        repository_id=repo_id,
        snapshot_id=snap_id,
        source_artifact_id=source_id,
        target_artifact_id=target_id,
        relationship_type=rel_type,
        confidence=confidence,
        source_location=loc,
        detection_method="ast_inspection",
        metadata_payload={},
    )
    db.add(rel)
    db.flush()
    return rel


class TestPhase4ChangeImpact:
    """Comprehensive test suite for Phase 4 deterministic change impact engine."""

    # TEST 1 — Direct dependency: A -> B. Change A -> A changed, B directly affected
    def test_scenario_01_direct_dependency(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_01_a")
        snap_b = _create_snapshot(db, repo.id, "commit_01_b")

        # Snapshot A: A and B exist. B calls A.
        a1 = _create_artifact(db, snap_a.id, repo.id, "callee", "service.callee", "FUNCTION", source_hash="hash_a1")
        b1 = _create_artifact(db, snap_a.id, repo.id, "caller", "service.caller", "FUNCTION", source_hash="hash_b1")
        _create_rel(db, snap_a.id, repo.id, b1.id, a1.id, "CALLS")

        # Snapshot B: A is modified (new hash). B remains unchanged.
        a2 = _create_artifact(db, snap_b.id, repo.id, "callee", "service.callee", "FUNCTION", source_hash="hash_a2_MODIFIED")
        b2 = _create_artifact(db, snap_b.id, repo.id, "caller", "service.caller", "FUNCTION", source_hash="hash_b1")
        _create_rel(db, snap_b.id, repo.id, b2.id, a2.id, "CALLS")
        db.commit()

        result = change_impact_service.run_impact_analysis(db, repo.id, snap_a.id, snap_b.id)

        assert result.summary.changed == 1
        assert result.summary.directly_affected == 1
        assert result.summary.indirectly_affected == 0

        # Check changed node
        assert result.changes[0].qualified_name == "service.callee"
        assert result.changes[0].change_type == ChangeType.MODIFIED

        # Check impact finding
        assert len(result.findings) == 1
        assert result.findings[0].source_qual_name == "service.callee"
        assert result.findings[0].target_qual_name == "service.caller"
        assert result.findings[0].impact_level == 1
        assert result.findings[0].relationship_type == "CALLS"

    # TEST 2 — Transitive dependency: A -> B -> C -> D. Change A -> B direct, C indirect, D indirect
    def test_scenario_02_transitive_dependency(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_02_a")
        snap_b = _create_snapshot(db, repo.id, "commit_02_b")

        # Base snapshot
        a1 = _create_artifact(db, snap_a.id, repo.id, "A", "pkg.A", "FUNCTION", source_hash="v1")
        b1 = _create_artifact(db, snap_a.id, repo.id, "B", "pkg.B", "FUNCTION", source_hash="v1")
        c1 = _create_artifact(db, snap_a.id, repo.id, "C", "pkg.C", "FUNCTION", source_hash="v1")
        d1 = _create_artifact(db, snap_a.id, repo.id, "D", "pkg.D", "FUNCTION", source_hash="v1")
        _create_rel(db, snap_a.id, repo.id, b1.id, a1.id, "CALLS")
        _create_rel(db, snap_a.id, repo.id, c1.id, b1.id, "CALLS")
        _create_rel(db, snap_a.id, repo.id, d1.id, c1.id, "CALLS")

        # Target snapshot (A changed)
        a2 = _create_artifact(db, snap_b.id, repo.id, "A", "pkg.A", "FUNCTION", source_hash="v2_MODIFIED")
        b2 = _create_artifact(db, snap_b.id, repo.id, "B", "pkg.B", "FUNCTION", source_hash="v1")
        c2 = _create_artifact(db, snap_b.id, repo.id, "C", "pkg.C", "FUNCTION", source_hash="v1")
        d2 = _create_artifact(db, snap_b.id, repo.id, "D", "pkg.D", "FUNCTION", source_hash="v1")
        _create_rel(db, snap_b.id, repo.id, b2.id, a2.id, "CALLS")
        _create_rel(db, snap_b.id, repo.id, c2.id, b2.id, "CALLS")
        _create_rel(db, snap_b.id, repo.id, d2.id, c2.id, "CALLS")
        db.commit()

        result = change_impact_service.run_impact_analysis(db, repo.id, snap_a.id, snap_b.id)

        assert result.summary.changed == 1
        assert result.summary.directly_affected == 1  # B
        assert result.summary.indirectly_affected == 2  # C and D
        assert result.summary.max_depth_reached == 3

        # Verify findings levels
        targets = {f.target_qual_name: f.impact_level for f in result.findings}
        assert targets["pkg.B"] == 1
        assert targets["pkg.C"] == 2
        assert targets["pkg.D"] == 3

    # TEST 3 — Unrelated components: A -> B, C -> D. Change A -> B affected, C/D not affected
    def test_scenario_03_unrelated_components(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_03_a")
        snap_b = _create_snapshot(db, repo.id, "commit_03_b")

        # Base snapshot
        a1 = _create_artifact(db, snap_a.id, repo.id, "A", "domain1.A", "FUNCTION", source_hash="v1")
        b1 = _create_artifact(db, snap_a.id, repo.id, "B", "domain1.B", "FUNCTION", source_hash="v1")
        c1 = _create_artifact(db, snap_a.id, repo.id, "C", "domain2.C", "FUNCTION", source_hash="v1")
        d1 = _create_artifact(db, snap_a.id, repo.id, "D", "domain2.D", "FUNCTION", source_hash="v1")
        _create_rel(db, snap_a.id, repo.id, b1.id, a1.id, "CALLS")
        _create_rel(db, snap_a.id, repo.id, d1.id, c1.id, "CALLS")

        # Target: Only A changes
        a2 = _create_artifact(db, snap_b.id, repo.id, "A", "domain1.A", "FUNCTION", source_hash="v2_MODIFIED")
        b2 = _create_artifact(db, snap_b.id, repo.id, "B", "domain1.B", "FUNCTION", source_hash="v1")
        c2 = _create_artifact(db, snap_b.id, repo.id, "C", "domain2.C", "FUNCTION", source_hash="v1")
        d2 = _create_artifact(db, snap_b.id, repo.id, "D", "domain2.D", "FUNCTION", source_hash="v1")
        _create_rel(db, snap_b.id, repo.id, b2.id, a2.id, "CALLS")
        _create_rel(db, snap_b.id, repo.id, d2.id, c2.id, "CALLS")
        db.commit()

        result = change_impact_service.run_impact_analysis(db, repo.id, snap_a.id, snap_b.id)

        affected = {f.target_qual_name for f in result.findings}
        assert "domain1.B" in affected
        assert "domain2.C" not in affected
        assert "domain2.D" not in affected

    # TEST 4 — Affected test: A -> B, B -> Test. Change A -> Test affected
    def test_scenario_04_affected_test(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_04_a")
        snap_b = _create_snapshot(db, repo.id, "commit_04_b")

        # Base snapshot
        a1 = _create_artifact(db, snap_a.id, repo.id, "compute", "calc.compute", "FUNCTION", source_hash="v1")
        b1 = _create_artifact(db, snap_a.id, repo.id, "execute", "calc.execute", "FUNCTION", source_hash="v1")
        t1 = _create_artifact(db, snap_a.id, repo.id, "test_execute", "tests.test_execute", "TEST_CASE", source_hash="v1")

        _create_rel(db, snap_a.id, repo.id, b1.id, a1.id, "CALLS")
        _create_rel(db, snap_a.id, repo.id, t1.id, b1.id, "TESTS")

        # Target snapshot: compute is modified
        a2 = _create_artifact(db, snap_b.id, repo.id, "compute", "calc.compute", "FUNCTION", source_hash="v2_MODIFIED")
        b2 = _create_artifact(db, snap_b.id, repo.id, "execute", "calc.execute", "FUNCTION", source_hash="v1")
        t2 = _create_artifact(db, snap_b.id, repo.id, "test_execute", "tests.test_execute", "TEST_CASE", source_hash="v1")

        _create_rel(db, snap_b.id, repo.id, b2.id, a2.id, "CALLS")
        _create_rel(db, snap_b.id, repo.id, t2.id, b2.id, "TESTS")
        db.commit()

        result = change_impact_service.run_impact_analysis(db, repo.id, snap_a.id, snap_b.id)

        assert result.summary.affected_tests == 1
        assert "tests.test_execute" in result.affected_categories["affected_tests"]

        # Check path: calc.compute -> calc.execute -> tests.test_execute
        test_paths = [p for p in result.paths if p.target_symbol == "tests.test_execute"]
        assert len(test_paths) >= 1
        assert test_paths[0].nodes == ["calc.compute", "calc.execute", "tests.test_execute"]
        assert test_paths[0].terminal_type == "TEST"

    # TEST 5 — API consumer: Service A -> API -> Consumer B. Change A -> API & B affected
    def test_scenario_05_api_consumer(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_05_a")
        snap_b = _create_snapshot(db, repo.id, "commit_05_b")

        # Service exposes API endpoint; Client consumes API endpoint
        s1 = _create_artifact(db, snap_a.id, repo.id, "OrderService", "services.OrderService", "SERVICE", source_hash="v1")
        api1 = _create_artifact(db, snap_a.id, repo.id, "post_order", "/api/v1/orders", "API_ENDPOINT", source_hash="v1")
        cli1 = _create_artifact(db, snap_a.id, repo.id, "CheckoutClient", "clients.CheckoutClient", "COMPONENT", source_hash="v1")

        _create_rel(db, snap_a.id, repo.id, s1.id, api1.id, "EXPOSES")
        _create_rel(db, snap_a.id, repo.id, cli1.id, api1.id, "CONSUMES")

        # Target: OrderService modified
        s2 = _create_artifact(db, snap_b.id, repo.id, "OrderService", "services.OrderService", "SERVICE", source_hash="v2_MODIFIED")
        api2 = _create_artifact(db, snap_b.id, repo.id, "post_order", "/api/v1/orders", "API_ENDPOINT", source_hash="v1")
        cli2 = _create_artifact(db, snap_b.id, repo.id, "CheckoutClient", "clients.CheckoutClient", "COMPONENT", source_hash="v1")

        _create_rel(db, snap_b.id, repo.id, s2.id, api2.id, "EXPOSES")
        _create_rel(db, snap_b.id, repo.id, cli2.id, api2.id, "CONSUMES")
        db.commit()

        result = change_impact_service.run_impact_analysis(db, repo.id, snap_a.id, snap_b.id)

        assert "/api/v1/orders" in result.affected_categories["affected_apis"]
        assert "clients.CheckoutClient" in result.affected_categories["affected_components"]

    # TEST 6 — Process: Component -> Process -> ProcessStep. Change Component -> Step affected
    def test_scenario_06_process_workflow(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_06_a")
        snap_b = _create_snapshot(db, repo.id, "commit_06_b")

        h1 = _create_artifact(db, snap_a.id, repo.id, "PaymentHandler", "billing.PaymentHandler", "COMPONENT", source_hash="v1")
        step1 = _create_artifact(db, snap_a.id, repo.id, "StepChargeCard", "workflow.StepChargeCard", "PROCESS_STEP", source_hash="v1")
        step2 = _create_artifact(db, snap_a.id, repo.id, "StepSendReceipt", "workflow.StepSendReceipt", "PROCESS_STEP", source_hash="v1")

        _create_rel(db, snap_a.id, repo.id, h1.id, step1.id, "PARTICIPATES_IN")
        _create_rel(db, snap_a.id, repo.id, step1.id, step2.id, "TRANSITIONS_TO")

        h2 = _create_artifact(db, snap_b.id, repo.id, "PaymentHandler", "billing.PaymentHandler", "COMPONENT", source_hash="v2_MODIFIED")
        step1_b = _create_artifact(db, snap_b.id, repo.id, "StepChargeCard", "workflow.StepChargeCard", "PROCESS_STEP", source_hash="v1")
        step2_b = _create_artifact(db, snap_b.id, repo.id, "StepSendReceipt", "workflow.StepSendReceipt", "PROCESS_STEP", source_hash="v1")

        _create_rel(db, snap_b.id, repo.id, h2.id, step1_b.id, "PARTICIPATES_IN")
        _create_rel(db, snap_b.id, repo.id, step1_b.id, step2_b.id, "TRANSITIONS_TO")
        db.commit()

        result = change_impact_service.run_impact_analysis(db, repo.id, snap_a.id, snap_b.id)

        assert "workflow.StepChargeCard" in result.affected_categories["affected_processes"]
        assert "workflow.StepSendReceipt" in result.affected_categories["affected_processes"]

    # TEST 7 — Deleted artifact: A removed in B. B previously called A in snapshot A -> caller affected
    def test_scenario_07_deleted_artifact(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_07_a")
        snap_b = _create_snapshot(db, repo.id, "commit_07_b")

        # Snapshot A: legacy_api called by client_service
        a1 = _create_artifact(db, snap_a.id, repo.id, "legacy_func", "api.legacy_func", "FUNCTION", source_hash="v1")
        c1 = _create_artifact(db, snap_a.id, repo.id, "client_service", "client.client_service", "FUNCTION", source_hash="v1")
        _create_rel(db, snap_a.id, repo.id, c1.id, a1.id, "CALLS")

        # Snapshot B: legacy_func is completely REMOVED. client_service still exists.
        c2 = _create_artifact(db, snap_b.id, repo.id, "client_service", "client.client_service", "FUNCTION", source_hash="v1")
        db.commit()

        result = change_impact_service.run_impact_analysis(db, repo.id, snap_a.id, snap_b.id)

        # 1 change: REMOVED api.legacy_func
        assert len(result.changes) == 1
        assert result.changes[0].qualified_name == "api.legacy_func"
        assert result.changes[0].change_type == ChangeType.REMOVED

        # The historical relationship from Snapshot A was traversed!
        affected_names = {f.target_qual_name for f in result.findings}
        assert "client.client_service" in affected_names

    # TEST 8 — Cycle: A -> B -> C -> A. Change A -> terminates safely without infinite loop
    def test_scenario_08_cycle_protection(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_08_a")
        snap_b = _create_snapshot(db, repo.id, "commit_08_b")

        # Base snapshot
        a1 = _create_artifact(db, snap_a.id, repo.id, "NodeA", "cycle.NodeA", "CLASS", source_hash="v1")
        b1 = _create_artifact(db, snap_a.id, repo.id, "NodeB", "cycle.NodeB", "CLASS", source_hash="v1")
        c1 = _create_artifact(db, snap_a.id, repo.id, "NodeC", "cycle.NodeC", "CLASS", source_hash="v1")

        _create_rel(db, snap_a.id, repo.id, b1.id, a1.id, "CALLS")
        _create_rel(db, snap_a.id, repo.id, c1.id, b1.id, "CALLS")
        _create_rel(db, snap_a.id, repo.id, a1.id, c1.id, "CALLS")  # cycle back to A!

        # Target snapshot: NodeA modified
        a2 = _create_artifact(db, snap_b.id, repo.id, "NodeA", "cycle.NodeA", "CLASS", source_hash="v2_MODIFIED")
        b2 = _create_artifact(db, snap_b.id, repo.id, "NodeB", "cycle.NodeB", "CLASS", source_hash="v1")
        c2 = _create_artifact(db, snap_b.id, repo.id, "NodeC", "cycle.NodeC", "CLASS", source_hash="v1")

        _create_rel(db, snap_b.id, repo.id, b2.id, a2.id, "CALLS")
        _create_rel(db, snap_b.id, repo.id, c2.id, b2.id, "CALLS")
        _create_rel(db, snap_b.id, repo.id, a2.id, c2.id, "CALLS")
        db.commit()

        # Must execute cleanly without recursion error or timeout
        result = change_impact_service.run_impact_analysis(
            db, repo.id, snap_a.id, snap_b.id, config=ImpactConfig(max_depth=5)
        )

        assert result.status == "completed"
        # B is level 1, C is level 2
        affected_nodes = {f.target_qual_name for f in result.findings}
        assert "cycle.NodeB" in affected_nodes
        assert "cycle.NodeC" in affected_nodes

    # TEST 9 — Max depth: A -> B -> C -> D -> E, max_depth = 2 -> A, B, C (not D/E)
    def test_scenario_09_max_depth(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_09_a")
        snap_b = _create_snapshot(db, repo.id, "commit_09_b")

        nodes_a = [_create_artifact(db, snap_a.id, repo.id, chr(65 + i), f"depth.{chr(65 + i)}", "FUNCTION", source_hash="v1") for i in range(5)]
        for i in range(4):
            _create_rel(db, snap_a.id, repo.id, nodes_a[i + 1].id, nodes_a[i].id, "CALLS")

        nodes_b = [_create_artifact(db, snap_b.id, repo.id, chr(65 + i), f"depth.{chr(65 + i)}", "FUNCTION", source_hash="v2_MODIFIED" if i == 0 else "v1") for i in range(5)]
        for i in range(4):
            _create_rel(db, snap_b.id, repo.id, nodes_b[i + 1].id, nodes_b[i].id, "CALLS")
        db.commit()

        # Run with max_depth = 2
        result = change_impact_service.run_impact_analysis(
            db, repo.id, snap_a.id, snap_b.id, config=ImpactConfig(max_depth=2)
        )

        affected = {f.target_qual_name: f.impact_level for f in result.findings}
        assert "depth.B" in affected and affected["depth.B"] == 1
        assert "depth.C" in affected and affected["depth.C"] == 2
        # Depth 3 (D) and Depth 4 (E) must NOT be present
        assert "depth.D" not in affected
        assert "depth.E" not in affected
        assert result.summary.max_depth_reached == 2

    # TEST 10 — Duplicate paths: Multiple routes to same target suppressed
    def test_scenario_10_duplicate_path_suppression(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_10_a")
        snap_b = _create_snapshot(db, repo.id, "commit_10_b")

        # Root A, Route 1: A -> B1 -> Target, Route 2: A -> B2 -> Target
        # Plus an identical duplicate relationship
        a1 = _create_artifact(db, snap_a.id, repo.id, "Root", "diamond.Root", "FUNCTION", source_hash="v1")
        b1 = _create_artifact(db, snap_a.id, repo.id, "Mid1", "diamond.Mid1", "FUNCTION", source_hash="v1")
        b2 = _create_artifact(db, snap_a.id, repo.id, "Mid2", "diamond.Mid2", "FUNCTION", source_hash="v1")
        tgt = _create_artifact(db, snap_a.id, repo.id, "Target", "diamond.Target", "FUNCTION", source_hash="v1")

        _create_rel(db, snap_a.id, repo.id, b1.id, a1.id, "CALLS")
        _create_rel(db, snap_a.id, repo.id, b2.id, a1.id, "CALLS")
        _create_rel(db, snap_a.id, repo.id, tgt.id, b1.id, "CALLS")
        _create_rel(db, snap_a.id, repo.id, tgt.id, b2.id, "CALLS")

        a1_b = _create_artifact(db, snap_b.id, repo.id, "Root", "diamond.Root", "FUNCTION", source_hash="v2_MODIFIED")
        b1_b = _create_artifact(db, snap_b.id, repo.id, "Mid1", "diamond.Mid1", "FUNCTION", source_hash="v1")
        b2_b = _create_artifact(db, snap_b.id, repo.id, "Mid2", "diamond.Mid2", "FUNCTION", source_hash="v1")
        tgt_b = _create_artifact(db, snap_b.id, repo.id, "Target", "diamond.Target", "FUNCTION", source_hash="v1")

        _create_rel(db, snap_b.id, repo.id, b1_b.id, a1_b.id, "CALLS")
        _create_rel(db, snap_b.id, repo.id, b2_b.id, a1_b.id, "CALLS")
        _create_rel(db, snap_b.id, repo.id, tgt_b.id, b1_b.id, "CALLS")
        _create_rel(db, snap_b.id, repo.id, tgt_b.id, b2_b.id, "CALLS")
        db.commit()

        result = change_impact_service.run_impact_analysis(db, repo.id, snap_a.id, snap_b.id)

        # Unique paths should be canonicalized; no duplicate node sequences
        path_node_tuples = [tuple(p.nodes) for p in result.paths]
        assert len(path_node_tuples) == len(set(path_node_tuples))

    # TEST 11 — Snapshot immutability: Snapshot A and B unchanged after analysis
    def test_scenario_11_snapshot_immutability(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_11_a")
        snap_b = _create_snapshot(db, repo.id, "commit_11_b")

        a1 = _create_artifact(db, snap_a.id, repo.id, "ImmutableA", "test.ImmutableA", "FUNCTION", source_hash="h1")
        a2 = _create_artifact(db, snap_b.id, repo.id, "ImmutableA", "test.ImmutableA", "FUNCTION", source_hash="h2")
        db.commit()

        # Capture pre-analysis state
        art_count_a_before = db.query(StructuralArtifact).filter_by(snapshot_id=snap_a.id).count()
        art_count_b_before = db.query(StructuralArtifact).filter_by(snapshot_id=snap_b.id).count()
        hash_a_before = a1.source_hash
        hash_b_before = a2.source_hash

        # Run analysis
        change_impact_service.run_impact_analysis(db, repo.id, snap_a.id, snap_b.id)

        # Verify post-analysis state
        art_count_a_after = db.query(StructuralArtifact).filter_by(snapshot_id=snap_a.id).count()
        art_count_b_after = db.query(StructuralArtifact).filter_by(snapshot_id=snap_b.id).count()
        db.refresh(a1)
        db.refresh(a2)

        assert art_count_a_before == art_count_a_after
        assert art_count_b_before == art_count_b_after
        assert a1.source_hash == hash_a_before
        assert a2.source_hash == hash_b_before

    # TEST 12 — Determinism: Run identical analysis twice -> identical output
    def test_scenario_12_determinism(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_12_a")
        snap_b = _create_snapshot(db, repo.id, "commit_12_b")

        a1 = _create_artifact(db, snap_a.id, repo.id, "A", "det.A", "FUNCTION", source_hash="v1")
        b1 = _create_artifact(db, snap_a.id, repo.id, "B", "det.B", "FUNCTION", source_hash="v1")
        c1 = _create_artifact(db, snap_a.id, repo.id, "C", "det.C", "FUNCTION", source_hash="v1")
        _create_rel(db, snap_a.id, repo.id, b1.id, a1.id, "CALLS")
        _create_rel(db, snap_a.id, repo.id, c1.id, b1.id, "CALLS")

        a2 = _create_artifact(db, snap_b.id, repo.id, "A", "det.A", "FUNCTION", source_hash="v2")
        b2 = _create_artifact(db, snap_b.id, repo.id, "B", "det.B", "FUNCTION", source_hash="v1")
        c2 = _create_artifact(db, snap_b.id, repo.id, "C", "det.C", "FUNCTION", source_hash="v1")
        _create_rel(db, snap_b.id, repo.id, b2.id, a2.id, "CALLS")
        _create_rel(db, snap_b.id, repo.id, c2.id, b2.id, "CALLS")
        db.commit()

        run1 = change_impact_service.run_impact_analysis(db, repo.id, snap_a.id, snap_b.id)
        run2 = change_impact_service.run_impact_analysis(db, repo.id, snap_a.id, snap_b.id)

        # Summary must match exactly
        assert run1.summary.model_dump() == run2.summary.model_dump()

        # Findings ordering and fields must match exactly
        assert len(run1.findings) == len(run2.findings)
        for f1, f2 in zip(run1.findings, run2.findings):
            assert f1.source_qual_name == f2.source_qual_name
            assert f1.target_qual_name == f2.target_qual_name
            assert f1.impact_level == f2.impact_level
            assert f1.relationship_type == f2.relationship_type
            assert f1.confidence == f2.confidence

        # Paths ordering and structure must match exactly
        assert len(run1.paths) == len(run2.paths)
        for p1, p2 in zip(run1.paths, run2.paths):
            assert p1.nodes == p2.nodes
            assert p1.depth == p2.depth
            assert p1.confidence == p2.confidence

    # TEST 13 — Symbol-level modification: Function inside a file modified
    def test_scenario_13_symbol_level_modification(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_13_a")
        snap_b = _create_snapshot(db, repo.id, "commit_13_b")

        # Calculator.add modified, Calculator unchanged
        _create_artifact(db, snap_a.id, repo.id, "Calculator", "math.Calculator", "CLASS", source_hash="class_hash_1")
        _create_artifact(db, snap_a.id, repo.id, "add", "math.Calculator.add", "METHOD", source_hash="func_hash_1", signature="def add(a, b): pass")

        _create_artifact(db, snap_b.id, repo.id, "Calculator", "math.Calculator", "CLASS", source_hash="class_hash_1")
        _create_artifact(db, snap_b.id, repo.id, "add", "math.Calculator.add", "METHOD", source_hash="func_hash_2", signature="def add(a, b, c=0): pass")
        db.commit()

        change_set = change_detector.detect_changes(db, repo.id, snap_a.id, snap_b.id)

        assert len(change_set.changes) == 1
        item = change_set.changes[0]
        assert item.qualified_name == "math.Calculator.add"
        assert item.is_symbol_level is True
        assert item.change_type == ChangeType.MODIFIED
        assert item.detection_method == "structural_ast_comparison"

    # TEST 14 — File-level fallback: Non-symbol artifact (MODULE) fallback
    def test_scenario_14_file_level_fallback(self, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "commit_14_a")
        snap_b = _create_snapshot(db, repo.id, "commit_14_b")

        _create_artifact(db, snap_a.id, repo.id, "mod", "pkg.mod", "MODULE", source_hash="m_hash_1")
        _create_artifact(db, snap_b.id, repo.id, "mod", "pkg.mod", "MODULE", source_hash="m_hash_2")
        db.commit()

        change_set = change_detector.detect_changes(db, repo.id, snap_a.id, snap_b.id)

        assert len(change_set.changes) == 1
        item = change_set.changes[0]
        assert item.qualified_name == "pkg.mod"
        assert item.is_symbol_level is False
        assert item.detection_method == "file_level_fallback"


class TestPhase4ImpactAPI:
    """Validates the HTTP API endpoints for Phase 4 Change Impact analysis."""

    def test_api_impact_analysis_lifecycle(self, client: TestClient, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "api_snap_a")
        snap_b = _create_snapshot(db, repo.id, "api_snap_b")

        a1 = _create_artifact(db, snap_a.id, repo.id, "A", "api.A", "FUNCTION", source_hash="v1")
        b1 = _create_artifact(db, snap_a.id, repo.id, "B", "api.B", "FUNCTION", source_hash="v1")
        _create_rel(db, snap_a.id, repo.id, b1.id, a1.id, "CALLS")

        a2 = _create_artifact(db, snap_b.id, repo.id, "A", "api.A", "FUNCTION", source_hash="v2")
        b2 = _create_artifact(db, snap_b.id, repo.id, "B", "api.B", "FUNCTION", source_hash="v1")
        _create_rel(db, snap_b.id, repo.id, b2.id, a2.id, "CALLS")
        db.commit()

        # 1. Trigger Impact Analysis
        res = client.post(
            f"/repositories/{repo.id}/impact-analysis",
            json={
                "base_snapshot_id": snap_a.id,
                "target_snapshot_id": snap_b.id,
                "max_depth": 5,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert data["summary"]["changed"] == 1
        assert data["summary"]["directly_affected"] == 1
        analysis_id = data["analysis_id"]

        # 2. Retrieve Impact Analysis by ID
        get_res = client.get(f"/repositories/{repo.id}/impact-analysis/{analysis_id}")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["analysis_id"] == analysis_id
        assert get_data["summary"]["changed"] == 1

        # 3. Retrieve Impact Graph Projection
        g_res = client.get(f"/repositories/{repo.id}/impact-analysis/{analysis_id}/graph")
        assert g_res.status_code == 200
        g_data = g_res.json()
        assert "nodes" in g_data
        assert "edges" in g_data
        assert g_data["total_nodes"] >= 2
        assert g_data["total_edges"] >= 1

    def test_api_identical_snapshots_no_change(self, client: TestClient, impact_test_env):
        db = impact_test_env["session"]
        repo = impact_test_env["repo"]

        snap_a = _create_snapshot(db, repo.id, "same_snap_a")
        db.commit()

        res = client.post(
            f"/repositories/{repo.id}/impact-analysis",
            json={
                "base_snapshot_id": snap_a.id,
                "target_snapshot_id": snap_a.id,
                "max_depth": 5,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert data["summary"]["changed"] == 0
        assert data["summary"]["directly_affected"] == 0
        assert "No changes detected" in data["message"]

    def test_api_invalid_snapshots(self, client: TestClient, impact_test_env):
        repo = impact_test_env["repo"]

        res = client.post(
            f"/repositories/{repo.id}/impact-analysis",
            json={
                "base_snapshot_id": "nonexistent_base",
                "target_snapshot_id": "nonexistent_target",
            },
        )
        assert res.status_code == 404
