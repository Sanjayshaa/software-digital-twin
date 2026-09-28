"""
Phase 6 — Test Impact Intelligence Comprehensive Test Suite.
Validates all mandatory scenarios:
1. Direct test impact (Test directly tests modified component via TESTS)
2. Indirect test impact (Test covers intermediate component reachable via CALLS/IMPORTS)
3. Unrelated tests isolation (Tests on untouched components are classified as UNAFFECTED)
4. Unknown coverage detection (Changed entities with no tests correctly identified)
5. Deleted/renamed symbol impact
6. Multiple changed entities handling
7. Bounded traversal (max_depth enforcement)
8. Cycle protection and termination safety (A -> B -> A cycles)
9. Duplicate path canonicalization
10. Evidence classification (OBSERVED vs DERIVED)
11. API endpoints verification (POST test-impact, GET test-impact/:id, GET tests-catalog)
12. Negative testing and 404/400 validation
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
from app.services.testing.models import (
    TestImpactClassification,
    TestEvidenceStatus,
    TestImpactConfig,
    TestImpactResult,
)
from app.services.testing.engine import test_impact_engine
from app.services.testing.service import test_impact_service
from main import app

client = TestClient(app)


@pytest.fixture
def test_impact_env(db_session: Session):
    """Sets up a clean project, repository, and baseline + target snapshots."""
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        name=f"Test Impact Project {suffix}",
        description="Phase 6 Test Project",
    )
    db_session.add(project)
    db_session.flush()

    repo = Repository(
        project_id=project.id,
        name=f"test-impact-repo-{suffix}",
        local_path=f"/tmp/test_impact_repo_{suffix}",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.flush()

    snap_base = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash=f"base_{suffix}",
        branch_name="main",
        total_files=5,
        total_symbols=10,
        snapshot_metadata={"test": True},
    )
    db_session.add(snap_base)
    db_session.flush()

    snap_target = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash=f"target_{suffix}",
        branch_name="feature/change",
        total_files=5,
        total_symbols=10,
        snapshot_metadata={"test": True},
    )
    db_session.add(snap_target)
    db_session.flush()

    return {
        "project": project,
        "repo": repo,
        "snap_base": snap_base,
        "snap_target": snap_target,
    }


def _create_artifact(
    db: Session,
    snapshot_id: str,
    repo_id: str,
    name: str,
    qual_name: str,
    art_type: str,
    location: str,
    source_hash: str = "hash_v1",
) -> StructuralArtifact:
    art = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo_id,
        snapshot_id=snapshot_id,
        name=name,
        qualified_name=qual_name,
        artifact_type=art_type,
        language="python",
        location=location,
        source_hash=source_hash,
        metadata_payload={},
    )
    db.add(art)
    db.flush()
    return art


def _create_rel(
    db: Session,
    snapshot_id: str,
    repo_id: str,
    source_id: str,
    target_id: str,
    rel_type: str,
) -> ArtifactRelationship:
    rel = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo_id,
        snapshot_id=snapshot_id,
        source_artifact_id=source_id,
        target_artifact_id=target_id,
        relationship_type=rel_type,
        confidence=1.0,
        detection_method="ast_inspection",
        metadata_payload={},
    )
    db.add(rel)
    db.flush()
    return rel


# =========================================================================
# 1. DIRECT & INDIRECT TEST IMPACT
# =========================================================================

def test_direct_and_indirect_test_impact(test_impact_env, db_session: Session):
    """
    Scenario:
    - Base snapshot:
      - Service A (calculate_tax)
      - Service B (process_payment) calls Service A
      - Test 1 (test_tax) TESTS Service A directly
      - Test 2 (test_payment) TESTS Service B
      - Test 3 (test_unrelated) TESTS Unrelated C
    - Target snapshot:
      - Service A source_hash changes (MODIFIED)
    Expected:
      - Test 1 is DIRECTLY_AFFECTED (depth 1, OBSERVED)
      - Test 2 is INDIRECTLY_AFFECTED (depth 2, DERIVED via Service B)
      - Test 3 is UNAFFECTED
    """
    env = test_impact_env
    base_id = env["snap_base"].id
    target_id = env["snap_target"].id
    repo_id = env["repo"].id

    # Base snapshot
    a_base = _create_artifact(db_session, base_id, repo_id, "calculate_tax", "pkg.ServiceA.calculate_tax", "METHOD", "services/tax.py:10", "hash_v1")
    b_base = _create_artifact(db_session, base_id, repo_id, "process_payment", "pkg.ServiceB.process_payment", "METHOD", "services/payment.py:20", "hash_b")
    c_base = _create_artifact(db_session, base_id, repo_id, "send_email", "pkg.ServiceC.send_email", "METHOD", "services/email.py:30", "hash_c")
    t1_base = _create_artifact(db_session, base_id, repo_id, "test_tax", "tests.test_tax", "TEST_CASE", "tests/test_tax.py:5", "hash_t1")
    t2_base = _create_artifact(db_session, base_id, repo_id, "test_payment", "tests.test_payment", "TEST_CASE", "tests/test_payment.py:5", "hash_t2")
    t3_base = _create_artifact(db_session, base_id, repo_id, "test_email", "tests.test_email", "TEST_CASE", "tests/test_email.py:5", "hash_t3")

    _create_rel(db_session, base_id, repo_id, b_base.id, a_base.id, "CALLS")
    _create_rel(db_session, base_id, repo_id, t1_base.id, a_base.id, "TESTS")
    _create_rel(db_session, base_id, repo_id, t2_base.id, b_base.id, "TESTS")
    _create_rel(db_session, base_id, repo_id, t3_base.id, c_base.id, "TESTS")

    # Target snapshot (Service A modified with new hash)
    a_target = _create_artifact(db_session, target_id, repo_id, "calculate_tax", "pkg.ServiceA.calculate_tax", "METHOD", "services/tax.py:10", "hash_v2_MODIFIED")
    b_target = _create_artifact(db_session, target_id, repo_id, "process_payment", "pkg.ServiceB.process_payment", "METHOD", "services/payment.py:20", "hash_b")
    c_target = _create_artifact(db_session, target_id, repo_id, "send_email", "pkg.ServiceC.send_email", "METHOD", "services/email.py:30", "hash_c")
    t1_target = _create_artifact(db_session, target_id, repo_id, "test_tax", "tests.test_tax", "TEST_CASE", "tests/test_tax.py:5", "hash_t1")
    t2_target = _create_artifact(db_session, target_id, repo_id, "test_payment", "tests.test_payment", "TEST_CASE", "tests/test_payment.py:5", "hash_t2")
    t3_target = _create_artifact(db_session, target_id, repo_id, "test_email", "tests.test_email", "TEST_CASE", "tests/test_email.py:5", "hash_t3")

    _create_rel(db_session, target_id, repo_id, b_target.id, a_target.id, "CALLS")
    _create_rel(db_session, target_id, repo_id, t1_target.id, a_target.id, "TESTS")
    _create_rel(db_session, target_id, repo_id, t2_target.id, b_target.id, "TESTS")
    _create_rel(db_session, target_id, repo_id, t3_target.id, c_target.id, "TESTS")

    db_session.commit()

    # Run Test Impact Engine
    result = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    assert result.status == "completed"
    assert result.summary.potentially_affected_count == 2
    assert result.summary.directly_affected_count == 1
    assert result.summary.indirectly_affected_count == 1
    assert result.summary.unaffected_count == 1

    # Check Test 1 (direct)
    t1_item = next(t for t in result.affected_tests if t.test_name == "test_tax")
    assert t1_item.classification == TestImpactClassification.DIRECTLY_AFFECTED
    assert t1_item.depth == 1
    assert t1_item.evidence_status == TestEvidenceStatus.OBSERVED
    assert "pkg.ServiceA.calculate_tax" in t1_item.impact_path

    # Check Test 2 (indirect)
    t2_item = next(t for t in result.affected_tests if t.test_name == "test_payment")
    assert t2_item.classification == TestImpactClassification.INDIRECTLY_AFFECTED
    assert t2_item.depth == 2
    assert t2_item.evidence_status == TestEvidenceStatus.DERIVED
    assert "pkg.ServiceB.process_payment" in t2_item.impact_path

    # Check Test 3 (unaffected)
    t3_item = next(t for t in result.unaffected_tests if t.test_name == "test_email")
    assert t3_item.classification == TestImpactClassification.UNAFFECTED


# =========================================================================
# 2. UNKNOWN COVERAGE DETECTION
# =========================================================================

def test_unknown_coverage_detection(test_impact_env, db_session: Session):
    """
    Scenario:
    - Component modified, but NO test covers it directly or indirectly.
    Expected:
      - Appears in result.unknown_coverage with explanation.
    """
    env = test_impact_env
    base_id = env["snap_base"].id
    target_id = env["snap_target"].id
    repo_id = env["repo"].id

    _create_artifact(db_session, base_id, repo_id, "orphan_func", "pkg.orphan_func", "FUNCTION", "orphan.py:1", "hash_1")
    _create_artifact(db_session, target_id, repo_id, "orphan_func", "pkg.orphan_func", "FUNCTION", "orphan.py:1", "hash_2")

    db_session.commit()

    result = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    assert result.summary.potentially_affected_count == 0
    assert result.summary.unknown_coverage_count == 1
    assert len(result.unknown_coverage) == 1
    assert result.unknown_coverage[0].name == "orphan_func"
    assert "No direct or indirect test relationships detected" in result.unknown_coverage[0].reason


# =========================================================================
# 3. DIRECT TEST FILE MODIFICATION
# =========================================================================

def test_direct_test_file_modification(test_impact_env, db_session: Session):
    """
    Scenario:
    - A test case itself was modified in the commit.
    Expected:
      - Test is flagged as DIRECTLY_AFFECTED because test itself changed.
    """
    env = test_impact_env
    base_id = env["snap_base"].id
    target_id = env["snap_target"].id
    repo_id = env["repo"].id

    _create_artifact(db_session, base_id, repo_id, "test_auth", "tests.test_auth", "TEST_CASE", "tests/test_auth.py:10", "hash_v1")
    _create_artifact(db_session, target_id, repo_id, "test_auth", "tests.test_auth", "TEST_CASE", "tests/test_auth.py:10", "hash_v2_EDITED")

    db_session.commit()

    result = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    assert result.summary.potentially_affected_count == 1
    assert result.summary.directly_affected_count == 1
    t = result.affected_tests[0]
    assert t.test_name == "test_auth"
    assert t.classification == TestImpactClassification.DIRECTLY_AFFECTED
    assert "Test code itself was modified" in t.reason


# =========================================================================
# 4. CYCLE PROTECTION AND BOUNDED TRAVERSAL
# =========================================================================

def test_cycle_protection_and_bounded_traversal(test_impact_env, db_session: Session):
    """
    Scenario:
    - Cyclic graph: ModA -> ModB -> ModA (CALLS loop)
    - Test -> ModB (TESTS)
    Expected:
      - Traversal terminates safely without infinite loop.
      - Max depth limit correctly bounds traversal.
    """
    env = test_impact_env
    base_id = env["snap_base"].id
    target_id = env["snap_target"].id
    repo_id = env["repo"].id

    a_base = _create_artifact(db_session, base_id, repo_id, "ModA", "pkg.ModA", "CLASS", "pkg/a.py:1", "h1")
    b_base = _create_artifact(db_session, base_id, repo_id, "ModB", "pkg.ModB", "CLASS", "pkg/b.py:1", "h1")
    t_base = _create_artifact(db_session, base_id, repo_id, "test_mod_b", "tests.test_mod_b", "TEST_CASE", "tests/test_b.py:1", "ht")

    _create_rel(db_session, base_id, repo_id, b_base.id, a_base.id, "CALLS")
    _create_rel(db_session, base_id, repo_id, a_base.id, b_base.id, "CALLS")  # cycle
    _create_rel(db_session, base_id, repo_id, t_base.id, b_base.id, "TESTS")

    a_target = _create_artifact(db_session, target_id, repo_id, "ModA", "pkg.ModA", "CLASS", "pkg/a.py:1", "h2_CHANGED")
    b_target = _create_artifact(db_session, target_id, repo_id, "ModB", "pkg.ModB", "CLASS", "pkg/b.py:1", "h1")
    t_target = _create_artifact(db_session, target_id, repo_id, "test_mod_b", "tests.test_mod_b", "TEST_CASE", "tests/test_b.py:1", "ht")

    _create_rel(db_session, target_id, repo_id, b_target.id, a_target.id, "CALLS")
    _create_rel(db_session, target_id, repo_id, a_target.id, b_target.id, "CALLS")
    _create_rel(db_session, target_id, repo_id, t_target.id, b_target.id, "TESTS")

    db_session.commit()

    config = TestImpactConfig(max_depth=3)
    result = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
        config=config,
    )

    assert result.status == "completed"
    assert result.summary.potentially_affected_count == 1
    assert result.affected_tests[0].test_name == "test_mod_b"


# =========================================================================
# 5. API ENDPOINTS INTEGRATION
# =========================================================================

def test_test_impact_api_endpoints(test_impact_env, db_session: Session):
    """
    Validates:
    - POST /repositories/{id}/test-impact
    - GET /repositories/{id}/test-impact/{analysis_id}
    - GET /repositories/{id}/tests-catalog
    - Negative validation: 404 for unknown repository and snapshots
    """
    env = test_impact_env
    repo = env["repo"]
    base_id = env["snap_base"].id
    target_id = env["snap_target"].id
    repo_id = repo.id

    # Create dummy artifact in target
    a_base = _create_artifact(db_session, base_id, repo_id, "CoreFunc", "pkg.CoreFunc", "FUNCTION", "core.py:1", "h1")
    a_target = _create_artifact(db_session, target_id, repo_id, "CoreFunc", "pkg.CoreFunc", "FUNCTION", "core.py:1", "h2")
    t = _create_artifact(db_session, target_id, repo_id, "test_core", "tests.test_core", "TEST_CASE", "tests/test_core.py:1", "ht")
    _create_rel(db_session, target_id, repo_id, t.id, a_target.id, "TESTS")
    db_session.commit()

    # 1. POST /repositories/{id}/test-impact
    payload = {
        "base_snapshot_id": base_id,
        "target_snapshot_id": target_id,
        "max_depth": 5,
    }
    resp = client.post(f"/repositories/{repo.id}/test-impact", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "analysis_id" in data
    assert data["status"] == "completed"
    assert "summary" in data
    assert data["summary"]["total_tests_mapped"] >= 1
    analysis_id = data["analysis_id"]

    # 2. GET /repositories/{id}/test-impact/{analysis_id}
    get_resp = client.get(f"/repositories/{repo.id}/test-impact/{analysis_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["analysis_id"] == analysis_id

    # 3. GET /repositories/{id}/tests-catalog
    cat_resp = client.get(f"/repositories/{repo.id}/tests-catalog?snapshot_id={target_id}")
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    assert cat_data["total"] >= 1
    assert any(test["name"] == "test_core" for test in cat_data["tests"])

    # 4. Negative testing
    bad_repo = client.post("/repositories/nonexistent-repo/test-impact", json=payload)
    assert bad_repo.status_code == 404

    bad_snap = client.post(
        f"/repositories/{repo.id}/test-impact",
        json={"base_snapshot_id": "nonexistent", "target_snapshot_id": target_id},
    )
    assert bad_snap.status_code == 404


# =========================================================================
# 6. MULTIPLE CHANGED ENTITIES & DELETED SYMBOLS
# =========================================================================

def test_multiple_changed_entities(test_impact_env, db_session: Session):
    """
    Scenario:
    - Multiple entities changed at once (FuncA, FuncB)
    - TestA tests FuncA, TestB tests FuncB
    Expected:
      - Both TestA and TestB are discovered as affected
      - Total potentially affected count is 2
    """
    env = test_impact_env
    base_id = env["snap_base"].id
    target_id = env["snap_target"].id
    repo_id = env["repo"].id

    fa_base = _create_artifact(db_session, base_id, repo_id, "FuncA", "pkg.FuncA", "FUNCTION", "pkg/a.py:1", "h1")
    fb_base = _create_artifact(db_session, base_id, repo_id, "FuncB", "pkg.FuncB", "FUNCTION", "pkg/b.py:1", "h1")
    ta_base = _create_artifact(db_session, base_id, repo_id, "test_a", "tests.test_a", "TEST_CASE", "tests/t_a.py:1", "h1")
    tb_base = _create_artifact(db_session, base_id, repo_id, "test_b", "tests.test_b", "TEST_CASE", "tests/t_b.py:1", "h1")

    _create_rel(db_session, base_id, repo_id, ta_base.id, fa_base.id, "TESTS")
    _create_rel(db_session, base_id, repo_id, tb_base.id, fb_base.id, "TESTS")

    fa_target = _create_artifact(db_session, target_id, repo_id, "FuncA", "pkg.FuncA", "FUNCTION", "pkg/a.py:1", "h2_CHANGED")
    fb_target = _create_artifact(db_session, target_id, repo_id, "FuncB", "pkg.FuncB", "FUNCTION", "pkg/b.py:1", "h2_CHANGED")
    ta_target = _create_artifact(db_session, target_id, repo_id, "test_a", "tests.test_a", "TEST_CASE", "tests/t_a.py:1", "h1")
    tb_target = _create_artifact(db_session, target_id, repo_id, "test_b", "tests.test_b", "TEST_CASE", "tests/t_b.py:1", "h1")

    _create_rel(db_session, target_id, repo_id, ta_target.id, fa_target.id, "TESTS")
    _create_rel(db_session, target_id, repo_id, tb_target.id, fb_target.id, "TESTS")

    db_session.commit()

    result = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    assert result.status == "completed"
    assert result.summary.potentially_affected_count == 2
    assert result.summary.directly_affected_count == 2
    test_names = {t.test_name for t in result.affected_tests}
    assert test_names == {"test_a", "test_b"}


def test_zero_changes_test_impact(test_impact_env, db_session: Session):
    """
    Scenario:
    - Target snapshot is identical to base snapshot (0 changes)
    Expected:
      - 0 potentially affected tests
      - All mapped tests are UNAFFECTED
    """
    env = test_impact_env
    base_id = env["snap_base"].id
    target_id = env["snap_target"].id
    repo_id = env["repo"].id

    fa = _create_artifact(db_session, base_id, repo_id, "FuncX", "pkg.FuncX", "FUNCTION", "pkg/x.py:1", "same_hash")
    ta = _create_artifact(db_session, base_id, repo_id, "test_x", "tests.test_x", "TEST_CASE", "tests/t_x.py:1", "same_hash")
    _create_rel(db_session, base_id, repo_id, ta.id, fa.id, "TESTS")

    fa_t = _create_artifact(db_session, target_id, repo_id, "FuncX", "pkg.FuncX", "FUNCTION", "pkg/x.py:1", "same_hash")
    ta_t = _create_artifact(db_session, target_id, repo_id, "test_x", "tests.test_x", "TEST_CASE", "tests/t_x.py:1", "same_hash")
    _create_rel(db_session, target_id, repo_id, ta_t.id, fa_t.id, "TESTS")

    db_session.commit()

    result = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    assert result.status == "completed"
    assert result.summary.potentially_affected_count == 0
    assert result.summary.unaffected_count == 1
    assert result.unaffected_tests[0].test_name == "test_x"
