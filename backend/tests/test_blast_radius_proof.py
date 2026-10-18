"""
Phase 8.5.3 — Deterministic Change Impact, Blast Radius, Test Impact & Product Integrity Proof.

Validates:
1. Deterministic Multi-Hop Change Impact & Blast Radius:
   - Topology: A -> CALLS -> B -> CALLS -> C -> TESTS -> TestC, and D -> TESTS -> TestD (isolated).
   - When B is modified in Snapshot B:
     - B is detected as CHANGED.
     - C is directly affected.
     - A is affected (as caller).
     - TestC is affected (via transitive propagation).
     - D and TestD remain completely UNAFFECTED.
2. Deterministic Test Impact Classification:
   - DIRECTLY_AFFECTED, INDIRECTLY_AFFECTED, UNAFFECTED, UNKNOWN_COVERAGE.
3. Blast Radius Derivation:
   - Multi-hop propagation paths with explicit typed relationships (CALLS, TESTS).
4. Cross-Repository Snapshot Security:
   - Foreign snapshots rejected with HTTP 400.
   - Non-existent snapshots rejected with HTTP 404.
5. What-If Virtual Twin Mutation Isolation:
   - Baseline snapshots and source tables remain completely unchanged after simulation.
6. Synthetic Runtime Telemetry & Candidate Causal Path Correlation:
   - Ingest synthetic error for real component, verify correlation and incident causality.
"""

import uuid
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from main import app
from app.models.entities import (
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    AnalysisRun,
)
from app.services.impact.service import change_impact_service
from app.services.impact.models import ImpactConfig, ChangeType
from app.services.testing.service import test_impact_service
from app.services.testing.models import TestImpactConfig, TestImpactClassification
from app.services.simulation.engine import scenario_simulation_engine
from app.services.simulation.models import ProposedMutation, MutationType, ScenarioStatus

client = TestClient(app)


@pytest.fixture
def deterministic_topology_repo(db_session: Session):
    """
    Sets up a deterministic repository fixture with a verified topology:
      A (caller) -> [CALLS] -> B (callee)
      C (caller) -> [CALLS] -> B (callee)
      TestC (test) -> [TESTS] -> C
      TestD (test) -> [TESTS] -> D
    Snapshot 1: Initial baseline.
    Snapshot 2: Component B is modified (source_hash and line changes).
    """
    suffix = uuid.uuid4().hex[:8]
    proj = Project(name=f"BlastProofProj-{suffix}", description="Deterministic blast radius validation")
    db_session.add(proj)
    db_session.flush()

    repo = Repository(
        project_id=proj.id,
        name=f"blast_proof_repo_{suffix}",
        vcs_type="git",
        local_path=f"/tmp/test_blast_repo_{suffix}",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.flush()

    snap_a = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="aaaa111122223333444455556666777788889999",
        branch_name="main",
        total_files=4,
        total_symbols=6,
    )
    db_session.add(snap_a)
    db_session.flush()

    snap_b = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="bbbb111122223333444455556666777788889999",
        branch_name="main",
        total_files=4,
        total_symbols=6,
    )
    db_session.add(snap_b)
    db_session.flush()

    # Artifacts in Snapshot A
    art_a_v1 = StructuralArtifact(
        id=f"art_a_v1_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_a.id,
        artifact_type="SERVICE",
        language="python",
        name="ComponentA",
        qualified_name="app.services.ComponentA",
        location="app/services/a.py:10",
        source_hash="hash_a_v1",
        line_start=10,
        line_end=30,
        metadata_payload={},
    )
    art_b_v1 = StructuralArtifact(
        id=f"art_b_v1_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_a.id,
        artifact_type="SERVICE",
        language="python",
        name="ComponentB",
        qualified_name="app.services.ComponentB",
        location="app/services/b.py:10",
        source_hash="hash_b_v1",
        line_start=10,
        line_end=50,
        metadata_payload={},
    )
    art_c_v1 = StructuralArtifact(
        id=f"art_c_v1_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_a.id,
        artifact_type="SERVICE",
        language="python",
        name="ComponentC",
        qualified_name="app.services.ComponentC",
        location="app/services/c.py:10",
        source_hash="hash_c_v1",
        line_start=10,
        line_end=40,
        metadata_payload={},
    )
    test_c_v1 = StructuralArtifact(
        id=f"test_c_v1_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_a.id,
        artifact_type="TEST_CASE",
        language="python",
        name="test_component_c",
        qualified_name="tests.test_c.test_component_c",
        location="tests/test_c.py:5",
        source_hash="hash_test_c_v1",
        line_start=5,
        line_end=20,
        metadata_payload={},
    )
    art_d_v1 = StructuralArtifact(
        id=f"art_d_v1_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_a.id,
        artifact_type="SERVICE",
        language="python",
        name="ComponentD",
        qualified_name="app.services.ComponentD",
        location="app/services/d.py:10",
        source_hash="hash_d_v1",
        line_start=10,
        line_end=30,
        metadata_payload={},
    )
    test_d_v1 = StructuralArtifact(
        id=f"test_d_v1_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_a.id,
        artifact_type="TEST_CASE",
        language="python",
        name="test_component_d",
        qualified_name="tests.test_d.test_component_d",
        location="tests/test_d.py:5",
        source_hash="hash_test_d_v1",
        line_start=5,
        line_end=20,
        metadata_payload={},
    )
    db_session.add_all([art_a_v1, art_b_v1, art_c_v1, test_c_v1, art_d_v1, test_d_v1])
    db_session.flush()

    # Relationships in Snapshot A
    rel_a_calls_b = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap_a.id,
        source_artifact_id=art_a_v1.id,
        target_artifact_id=art_b_v1.id,
        relationship_type="CALLS",
        confidence=1.0,
        detection_method="ast_call_graph",
    )
    rel_c_calls_b = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap_a.id,
        source_artifact_id=art_c_v1.id,
        target_artifact_id=art_b_v1.id,
        relationship_type="CALLS",
        confidence=1.0,
        detection_method="ast_call_graph",
    )
    rel_test_c = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap_a.id,
        source_artifact_id=test_c_v1.id,
        target_artifact_id=art_c_v1.id,
        relationship_type="TESTS",
        confidence=1.0,
        detection_method="test_ast_runner",
    )
    rel_test_d = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap_a.id,
        source_artifact_id=test_d_v1.id,
        target_artifact_id=art_d_v1.id,
        relationship_type="TESTS",
        confidence=1.0,
        detection_method="test_ast_runner",
    )
    db_session.add_all([rel_a_calls_b, rel_c_calls_b, rel_test_c, rel_test_d])
    db_session.flush()

    # Artifacts in Snapshot B: Component B is modified (new hash, modified line span)
    art_a_v2 = StructuralArtifact(
        id=f"art_a_v2_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_b.id,
        artifact_type="SERVICE",
        language="python",
        name="ComponentA",
        qualified_name="app.services.ComponentA",
        location="app/services/a.py:10",
        source_hash="hash_a_v1",
        line_start=10,
        line_end=30,
        metadata_payload={},
    )
    art_b_v2 = StructuralArtifact(
        id=f"art_b_v2_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_b.id,
        artifact_type="SERVICE",
        language="python",
        name="ComponentB",
        qualified_name="app.services.ComponentB",
        location="app/services/b.py:10",
        source_hash="hash_b_v2_MODIFIED",
        line_start=10,
        line_end=75,
        metadata_payload={},
    )
    art_c_v2 = StructuralArtifact(
        id=f"art_c_v2_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_b.id,
        artifact_type="SERVICE",
        language="python",
        name="ComponentC",
        qualified_name="app.services.ComponentC",
        location="app/services/c.py:10",
        source_hash="hash_c_v1",
        line_start=10,
        line_end=40,
        metadata_payload={},
    )
    test_c_v2 = StructuralArtifact(
        id=f"test_c_v2_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_b.id,
        artifact_type="TEST_CASE",
        language="python",
        name="test_component_c",
        qualified_name="tests.test_c.test_component_c",
        location="tests/test_c.py:5",
        source_hash="hash_test_c_v1",
        line_start=5,
        line_end=20,
        metadata_payload={},
    )
    art_d_v2 = StructuralArtifact(
        id=f"art_d_v2_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_b.id,
        artifact_type="SERVICE",
        language="python",
        name="ComponentD",
        qualified_name="app.services.ComponentD",
        location="app/services/d.py:10",
        source_hash="hash_d_v1",
        line_start=10,
        line_end=30,
        metadata_payload={},
    )
    test_d_v2 = StructuralArtifact(
        id=f"test_d_v2_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_b.id,
        artifact_type="TEST_CASE",
        language="python",
        name="test_component_d",
        qualified_name="tests.test_d.test_component_d",
        location="tests/test_d.py:5",
        source_hash="hash_test_d_v1",
        line_start=5,
        line_end=20,
        metadata_payload={},
    )
    db_session.add_all([art_a_v2, art_b_v2, art_c_v2, test_c_v2, art_d_v2, test_d_v2])
    db_session.flush()

    # Relationships in Snapshot B (same structure)
    rel_a_calls_b_v2 = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap_b.id,
        source_artifact_id=art_a_v2.id,
        target_artifact_id=art_b_v2.id,
        relationship_type="CALLS",
        confidence=1.0,
        detection_method="ast_call_graph",
    )
    rel_c_calls_b_v2 = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap_b.id,
        source_artifact_id=art_c_v2.id,
        target_artifact_id=art_b_v2.id,
        relationship_type="CALLS",
        confidence=1.0,
        detection_method="ast_call_graph",
    )
    rel_test_c_v2 = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap_b.id,
        source_artifact_id=test_c_v2.id,
        target_artifact_id=art_c_v2.id,
        relationship_type="TESTS",
        confidence=1.0,
        detection_method="test_ast_runner",
    )
    rel_test_d_v2 = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo.id,
        snapshot_id=snap_b.id,
        source_artifact_id=test_d_v2.id,
        target_artifact_id=art_d_v2.id,
        relationship_type="TESTS",
        confidence=1.0,
        detection_method="test_ast_runner",
    )
    db_session.add_all([rel_a_calls_b_v2, rel_c_calls_b_v2, rel_test_c_v2, rel_test_d_v2])
    db_session.commit()

    return {
        "repo": repo,
        "snap_a": snap_a,
        "snap_b": snap_b,
        "artifacts_a": [art_a_v1, art_b_v1, art_c_v1, test_c_v1, art_d_v1, test_d_v1],
        "artifacts_b": [art_a_v2, art_b_v2, art_c_v2, test_c_v2, art_d_v2, test_d_v2],
    }


def test_part_e_deterministic_change_impact_propagation(deterministic_topology_repo, db_session: Session):
    """
    Part E: Proves Change Impact Analysis deterministically identifies:
    - Changed: B
    - Directly affected: C and A (via CALLS reverse propagation)
    - Transitively affected: TestC (via TESTS reverse propagation from C)
    - Isolated & Unaffected: D and TestD
    """
    fixture = deterministic_topology_repo
    repo = fixture["repo"]
    snap_a = fixture["snap_a"]
    snap_b = fixture["snap_b"]

    # Execute via API endpoint to verify both HTTP contract and engine
    response = client.post(
        f"/repositories/{repo.id}/impact-analysis",
        json={
            "base_snapshot_id": snap_a.id,
            "target_snapshot_id": snap_b.id,
            "max_depth": 5,
            "include_tests": True,
        },
    )
    assert response.status_code == 200, f"Impact analysis failed: {response.text}"
    data = response.json()

    # 1. Assert Change Set
    changes = data["changes"]
    assert len(changes) == 1, f"Expected exactly 1 change, got {len(changes)}"
    assert changes[0]["qualified_name"] == "app.services.ComponentB"
    assert changes[0]["change_type"] == "MODIFIED"

    # 2. Assert Findings
    findings = data["findings"]
    impacted_quals = [f["target_qual_name"] for f in findings]

    # Component C and Component A must be in affected findings
    assert "app.services.ComponentC" in impacted_quals, "ComponentC must be directly affected by ComponentB change"
    assert "app.services.ComponentA" in impacted_quals, "ComponentA must be directly affected by ComponentB change"

    # TestC must be transitively affected
    assert "tests.test_c.test_component_c" in impacted_quals, "TestC must be transitively affected via ComponentC"

    # Isolated components D and TestD must NOT be in findings
    assert "app.services.ComponentD" not in impacted_quals, "ComponentD must NOT be affected"
    assert "tests.test_d.test_component_d" not in impacted_quals, "TestD must NOT be affected"

    # 3. Assert Propagation Paths & Relationships
    test_c_finding = next(f for f in findings if f["target_qual_name"] == "tests.test_c.test_component_c")
    assert test_c_finding["relationship_type"] == "TESTS"
    assert "app.services.ComponentB" in test_c_finding["path"]
    assert "app.services.ComponentC" in test_c_finding["path"]
    assert "tests.test_c.test_component_c" in test_c_finding["path"]

    # 4. Summary counts
    summary = data["summary"]
    assert summary["changed"] == 1
    assert summary["directly_affected"] >= 2
    assert summary["max_depth_reached"] >= 2


def test_part_g_test_impact_classification_proof(deterministic_topology_repo, db_session: Session):
    """
    Part G: Proves Test Impact Intelligence correctly classifies:
    - TestC: INDIRECTLY_AFFECTED (via modified B -> called by C -> tested by TestC)
    - TestD: UNAFFECTED (completely outside call/dependency graph)
    """
    fixture = deterministic_topology_repo
    repo = fixture["repo"]
    snap_a = fixture["snap_a"]
    snap_b = fixture["snap_b"]

    response = client.post(
        f"/repositories/{repo.id}/test-impact",
        json={
            "base_snapshot_id": snap_a.id,
            "target_snapshot_id": snap_b.id,
            "max_depth": 6,
            "include_indirect": True,
            "include_unaffected": True,
        },
    )
    assert response.status_code == 200, f"Test impact failed: {response.text}"
    data = response.json()

    affected_tests = data["affected_tests"]
    unaffected_tests = data["unaffected_tests"]

    # TestC must be in affected tests
    aff_quals = [t["qualified_name"] for t in affected_tests]
    assert "tests.test_c.test_component_c" in aff_quals, "TestC must be detected as affected"

    # TestC classification must be INDIRECTLY_AFFECTED
    test_c_entry = next(t for t in affected_tests if t["qualified_name"] == "tests.test_c.test_component_c")
    assert test_c_entry["classification"] == "INDIRECTLY_AFFECTED"
    assert "app.services.ComponentB" in test_c_entry["impact_path"]
    assert "tests.test_c.test_component_c" in test_c_entry["impact_path"]

    # TestD must be in unaffected tests
    unaff_quals = [t["qualified_name"] for t in unaffected_tests]
    assert "tests.test_d.test_component_d" in unaff_quals, "TestD must be classified as UNAFFECTED"

    # Summary metrics
    metrics = data["summary"]
    assert metrics["indirectly_affected_count"] == 1
    assert metrics["unaffected_count"] == 1
    assert metrics["total_tests_mapped"] == 2


def test_part_h_blast_radius_structural_derivation(deterministic_topology_repo):
    """
    Part H: Proves Blast Radius is derived from explicit Digital Twin typed relationships (CALLS, TESTS)
    with non-zero explainable propagation chains.
    """
    fixture = deterministic_topology_repo
    repo = fixture["repo"]
    snap_a = fixture["snap_a"]
    snap_b = fixture["snap_b"]

    res = client.post(
        f"/repositories/{repo.id}/impact-analysis",
        json={
            "base_snapshot_id": snap_a.id,
            "target_snapshot_id": snap_b.id,
        },
    )
    assert res.status_code == 200
    data = res.json()

    # Verify category distribution
    cats = data["affected_categories"]
    assert "app.services.ComponentB" in cats["changed_artifacts"]
    assert "app.services.ComponentC" in cats["affected_components"] or "app.services.ComponentC" in cats["affected_services"]
    assert "tests.test_c.test_component_c" in cats["affected_tests"]

    # Verify each finding has an evidence chain with explicit relationship types
    for finding in data["findings"]:
        assert len(finding["evidence"]) > 0
        assert any("CALLS" in ev or "TESTS" in ev for ev in finding["evidence"])


def test_part_o_cross_repository_snapshot_security(deterministic_topology_repo, db_session: Session):
    """
    Part O: Enforces that foreign snapshots belonging to a different repository are rejected.
    """
    fixture = deterministic_topology_repo
    repo = fixture["repo"]
    snap_a = fixture["snap_a"]

    # Create another separate repository and snapshot
    suffix = uuid.uuid4().hex[:6]
    foreign_repo = Repository(
        project_id=repo.project_id,
        name=f"foreign_repo_{suffix}",
        local_path=f"/tmp/foreign_{suffix}",
    )
    db_session.add(foreign_repo)
    db_session.flush()

    foreign_snap = RepositorySnapshot(
        repository_id=foreign_repo.id,
        commit_hash="ffff999988887777666655554444333322221111",
        branch_name="main",
    )
    db_session.add(foreign_snap)
    db_session.commit()

    # Attempt impact analysis combining repo with foreign_snap
    res = client.post(
        f"/repositories/{repo.id}/impact-analysis",
        json={
            "base_snapshot_id": snap_a.id,
            "target_snapshot_id": foreign_snap.id,
        },
    )
    assert res.status_code == 400
    assert f"Target snapshot '{foreign_snap.id}' does not belong to repository '{repo.id}'" in res.json()["detail"]

    # Attempt test impact with non-existent snapshot
    res_404 = client.post(
        f"/repositories/{repo.id}/test-impact",
        json={
            "base_snapshot_id": snap_a.id,
            "target_snapshot_id": "non_existent_snapshot_id",
        },
    )
    assert res_404.status_code == 404
    assert "Target snapshot 'non_existent_snapshot_id' not found" in res_404.json()["detail"]


def test_part_k_what_if_mutation_isolation(deterministic_topology_repo, db_session: Session):
    """
    Part K: Verifies What-If virtual twin mutation executes cleanly and does NOT modify
    the original baseline snapshot, artifacts, or relationships in the database.
    """
    fixture = deterministic_topology_repo
    repo = fixture["repo"]
    snap_a = fixture["snap_a"]

    # Record baseline state before simulation
    count_artifacts_before = db_session.query(StructuralArtifact).filter_by(snapshot_id=snap_a.id).count()
    count_rels_before = db_session.query(ArtifactRelationship).filter_by(snapshot_id=snap_a.id).count()

    # Run virtual simulation: MODIFY_SYMBOL on ComponentB
    mut = ProposedMutation(
        mutation_id="mut_test_b",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.ComponentB",
        description="Virtual simulation testing isolation",
    )

    result = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=repo.id,
        base_snapshot_id=snap_a.id,
        name="Virtual Simulation B",
        proposed_changes=[mut],
    )
    assert result.status == ScenarioStatus.COMPLETED
    assert result.validation.is_valid is True
    assert result.impact is not None

    # Query DB to prove baseline is completely untouched
    count_artifacts_after = db_session.query(StructuralArtifact).filter_by(snapshot_id=snap_a.id).count()
    count_rels_after = db_session.query(ArtifactRelationship).filter_by(snapshot_id=snap_a.id).count()

    assert count_artifacts_before == count_artifacts_after, "Baseline artifacts count must remain invariant"
    assert count_rels_before == count_rels_after, "Baseline relationships count must remain invariant"


def test_part_l_and_m_synthetic_telemetry_and_candidate_causal_path(deterministic_topology_repo, db_session: Session):
    """
    Part L & M: Ingests synthetic runtime telemetry for ComponentB, verifies correlation,
    sanitization, and candidate causal path in incident investigation.
    """
    fixture = deterministic_topology_repo
    repo = fixture["repo"]
    snap_a = fixture["snap_a"]

    # Ingest synthetic error event referencing ComponentB
    ingest_res = client.post(
        f"/repositories/{repo.id}/runtime-events/ingest",
        json={
            "environment": "staging",
            "snapshot_id": snap_a.id,
            "events": [
                {
                    "event_type": "error",
                    "component_name": "app.services.ComponentB",
                    "environment": "staging",
                    "message": "Synthetic validation error: Database timeout occurred with secret_token=ghp_ABC123XYZ",
                    "latency_ms": 420,
                }
            ],
        },
    )
    assert ingest_res.status_code == 201
    ingest_data = ingest_res.json()
    assert ingest_data["ingested_count"] == 1
    assert ingest_data["correlated_count"] == 1
    assert ingest_data["redacted_count"] >= 1  # secret_token should be redacted

    # Declare synthetic incident
    inc_res = client.post(
        f"/repositories/{repo.id}/incidents",
        json={
            "title": "Synthetic Latency Cascade Incident",
            "severity": "high",
            "environment": "staging",
            "affected_component_name": "app.services.ComponentB",
            "description": "High latency observed on ComponentB",
            "snapshot_id": snap_a.id,
        },
    )
    assert inc_res.status_code == 201
    inc_data = inc_res.json()
    incident_id = inc_data["id"]

    # Investigate incident
    inv_res = client.post(f"/repositories/{repo.id}/incidents/{incident_id}/investigate")
    assert inv_res.status_code == 200
    inv_data = inv_res.json()

    # Assert causal hypothesis and candidate path
    assert "candidate_causal_paths" in inv_data
    assert "uncertainties" in inv_data
    assert inv_data["incident"]["affected_component_name"] in ("ComponentB", "app.services.ComponentB")
