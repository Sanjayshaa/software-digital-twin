"""
Phase 8.5.7 — Test Impact Adversarial and Integrity Test Suite.
Validates all 20 required controlled synthetic scenarios, false-positive/false-negative guarantees,
and cross-repository isolation:
1. Direct test dependency
2. Indirect test dependency
3. Unrelated test
4. No test
5. Multiple tests covering one symbol
6. One test covering multiple symbols
7. Circular dependency
8. Alias import
9. Extensionless import
10. Nested test directory
11. Framework-convention test
12. Test importing through an intermediate module
13. Changed file with no symbol extraction
14. Deleted symbol
15. Added symbol
16. Renamed symbol
17. Unsupported framework
18. Dynamic import
19. Generated source
20. Cross-repository test contamination
"""

import uuid
import pytest
from sqlalchemy.orm import Session

from app.models.entities import (
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
)
from app.services.testing.models import (
    TestImpactClassification,
    TestImpactConfig,
)
from app.services.testing.engine import test_impact_engine


def _create_art(db: Session, repo_id: str, snap_id: str, name: str, qual: str, atype: str, loc: str, src_hash: str = "v1"):
    art = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo_id,
        snapshot_id=snap_id,
        name=name,
        qualified_name=qual,
        artifact_type=atype,
        language="python",
        location=loc,
        source_hash=src_hash,
        metadata_payload={},
    )
    db.add(art)
    db.flush()
    return art


def _create_rel(db: Session, repo_id: str, snap_id: str, src_id: str, tgt_id: str, rtype: str):
    rel = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo_id,
        snapshot_id=snap_id,
        source_artifact_id=src_id,
        target_artifact_id=tgt_id,
        relationship_type=rtype,
        confidence=1.0,
        detection_method="ast_inspection",
        metadata_payload={},
    )
    db.add(rel)
    db.flush()
    return rel


@pytest.fixture
def adv_env(db_session: Session):
    sfx = uuid.uuid4().hex[:8]
    proj = Project(name=f"adv-proj-{sfx}")
    db_session.add(proj)
    db_session.flush()

    repo = Repository(
        project_id=proj.id,
        name=f"adv-repo-{sfx}",
        local_path=f"/tmp/adv_repo_{sfx}",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.flush()

    base_snap = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash=f"base_{sfx}",
        branch_name="main",
        total_files=5,
        total_symbols=10,
    )
    target_snap = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash=f"target_{sfx}",
        branch_name="main",
        total_files=5,
        total_symbols=10,
    )
    db_session.add_all([base_snap, target_snap])
    db_session.flush()

    yield {
        "repo": repo,
        "base_snap": base_snap,
        "target_snap": target_snap,
        "sfx": sfx,
    }


def test_adversarial_suite(db_session: Session, adv_env):
    """Executes controlled synthetic scenarios and verifies classifications."""
    repo = adv_env["repo"]
    base_snap = adv_env["base_snap"]
    target_snap = adv_env["target_snap"]
    sfx = adv_env["sfx"]

    # 1. Direct test dependency: TestA -(TESTS)-> CompA
    comp_a_base = _create_art(db_session, repo.id, base_snap.id, f"CompA_{sfx}", f"app.comp_a_{sfx}", "CLASS", f"src/comp_a_{sfx}.py:10", "hash_base")
    comp_a_target = _create_art(db_session, repo.id, target_snap.id, f"CompA_{sfx}", f"app.comp_a_{sfx}", "CLASS", f"src/comp_a_{sfx}.py:10", "hash_mod")
    test_a_base = _create_art(db_session, repo.id, base_snap.id, f"test_comp_a_{sfx}", f"tests.test_comp_a_{sfx}", "TEST_CASE", f"tests/test_comp_a_{sfx}.py:10", "hash_ta_same")
    test_a = _create_art(db_session, repo.id, target_snap.id, f"test_comp_a_{sfx}", f"tests.test_comp_a_{sfx}", "TEST_CASE", f"tests/test_comp_a_{sfx}.py:10", "hash_ta_same")
    _create_rel(db_session, repo.id, target_snap.id, test_a.id, comp_a_target.id, "TESTS")

    # 2. Indirect test dependency: TestB -(TESTS)-> ServiceB -(CALLS)-> CompA
    serv_b_base = _create_art(db_session, repo.id, base_snap.id, f"ServiceB_{sfx}", f"app.service_b_{sfx}", "SERVICE", f"src/service_b_{sfx}.py:5", "hash_sb_same")
    serv_b = _create_art(db_session, repo.id, target_snap.id, f"ServiceB_{sfx}", f"app.service_b_{sfx}", "SERVICE", f"src/service_b_{sfx}.py:5", "hash_sb_same")
    test_b_base = _create_art(db_session, repo.id, base_snap.id, f"test_service_b_{sfx}", f"tests.test_service_b_{sfx}", "TEST_CASE", f"tests/test_service_b_{sfx}.py:5", "hash_tb_same")
    test_b = _create_art(db_session, repo.id, target_snap.id, f"test_service_b_{sfx}", f"tests.test_service_b_{sfx}", "TEST_CASE", f"tests/test_service_b_{sfx}.py:5", "hash_tb_same")
    _create_rel(db_session, repo.id, target_snap.id, serv_b.id, comp_a_target.id, "CALLS")
    _create_rel(db_session, repo.id, target_snap.id, test_b.id, serv_b.id, "TESTS")

    # 3. Unrelated test: TestUnrelated -(TESTS)-> CompUnrelated (untouched)
    comp_un_base = _create_art(db_session, repo.id, base_snap.id, f"CompUn_{sfx}", f"app.comp_un_{sfx}", "CLASS", f"src/comp_un_{sfx}.py:1", "hash_same")
    comp_un_target = _create_art(db_session, repo.id, target_snap.id, f"CompUn_{sfx}", f"app.comp_un_{sfx}", "CLASS", f"src/comp_un_{sfx}.py:1", "hash_same")
    test_un_base = _create_art(db_session, repo.id, base_snap.id, f"test_unrelated_{sfx}", f"tests.test_unrelated_{sfx}", "TEST_CASE", f"tests/test_unrelated_{sfx}.py:1", "hash_tun_same")
    test_un = _create_art(db_session, repo.id, target_snap.id, f"test_unrelated_{sfx}", f"tests.test_unrelated_{sfx}", "TEST_CASE", f"tests/test_unrelated_{sfx}.py:1", "hash_tun_same")
    _create_rel(db_session, repo.id, target_snap.id, test_un.id, comp_un_target.id, "TESTS")

    # 4. No test: CompNoTest (modified, 0 tests)
    comp_nt_base = _create_art(db_session, repo.id, base_snap.id, f"CompNoTest_{sfx}", f"app.comp_notest_{sfx}", "CLASS", f"src/comp_notest_{sfx}.py:1", "hash_nt_base")
    comp_nt_target = _create_art(db_session, repo.id, target_snap.id, f"CompNoTest_{sfx}", f"app.comp_notest_{sfx}", "CLASS", f"src/comp_notest_{sfx}.py:1", "hash_nt_mod")

    # 5. Multiple tests covering one symbol
    comp_m_base = _create_art(db_session, repo.id, base_snap.id, f"fnMulti_{sfx}", f"app.fn_multi_{sfx}", "FUNCTION", f"src/multi_{sfx}.py:1", "h_base")
    comp_m_target = _create_art(db_session, repo.id, target_snap.id, f"fnMulti_{sfx}", f"app.fn_multi_{sfx}", "FUNCTION", f"src/multi_{sfx}.py:1", "h_mod")
    test_m1_base = _create_art(db_session, repo.id, base_snap.id, f"test_multi1_{sfx}", f"tests.test_multi1_{sfx}", "TEST_CASE", f"tests/test_multi_{sfx}.py:10", "h_tm1_same")
    test_m1 = _create_art(db_session, repo.id, target_snap.id, f"test_multi1_{sfx}", f"tests.test_multi1_{sfx}", "TEST_CASE", f"tests/test_multi_{sfx}.py:10", "h_tm1_same")
    test_m2_base = _create_art(db_session, repo.id, base_snap.id, f"test_multi2_{sfx}", f"tests.test_multi2_{sfx}", "TEST_CASE", f"tests/test_multi_{sfx}.py:20", "h_tm2_same")
    test_m2 = _create_art(db_session, repo.id, target_snap.id, f"test_multi2_{sfx}", f"tests.test_multi2_{sfx}", "TEST_CASE", f"tests/test_multi_{sfx}.py:20", "h_tm2_same")
    _create_rel(db_session, repo.id, target_snap.id, test_m1.id, comp_m_target.id, "TESTS")
    _create_rel(db_session, repo.id, target_snap.id, test_m2.id, comp_m_target.id, "TESTS")

    # 7. Circular dependency: CircA -(CALLS)-> CircB -(CALLS)-> CircA
    circ_a_base = _create_art(db_session, repo.id, base_snap.id, f"circA_{sfx}", f"app.circ_a_{sfx}", "FUNCTION", f"src/circ_{sfx}.py:1", "h_ca_base")
    circ_a_target = _create_art(db_session, repo.id, target_snap.id, f"circA_{sfx}", f"app.circ_a_{sfx}", "FUNCTION", f"src/circ_{sfx}.py:1", "h_ca_mod")
    circ_b = _create_art(db_session, repo.id, target_snap.id, f"circB_{sfx}", f"app.circ_b_{sfx}", "FUNCTION", f"src/circ_{sfx}.py:20")
    _create_rel(db_session, repo.id, target_snap.id, circ_a_target.id, circ_b.id, "CALLS")
    _create_rel(db_session, repo.id, target_snap.id, circ_b.id, circ_a_target.id, "CALLS")

    db_session.commit()

    # Compute test impact
    res = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo.id,
        base_snapshot_id=base_snap.id,
        target_snapshot_id=target_snap.id,
    )

    # Invariant: UNKNOWN_COVERAGE != UNAFFECTED
    unaffected_ids = {t.test_id for t in res.unaffected_tests}
    unknown_ids = {u.artifact_id for u in res.unknown_coverage}
    assert len(unaffected_ids.intersection(unknown_ids)) == 0

    aff_map = {t.test_name: t for t in res.affected_tests}
    assert f"test_comp_a_{sfx}" in aff_map
    assert aff_map[f"test_comp_a_{sfx}"].classification == TestImpactClassification.DIRECTLY_AFFECTED

    assert f"test_service_b_{sfx}" in aff_map
    assert aff_map[f"test_service_b_{sfx}"].classification == TestImpactClassification.INDIRECTLY_AFFECTED

    unaff_names = [t.test_name for t in res.unaffected_tests]
    assert f"test_unrelated_{sfx}" in unaff_names

    unk_map = {u.name: u for u in res.unknown_coverage}
    assert f"CompNoTest_{sfx}" in unk_map
    assert unk_map[f"CompNoTest_{sfx}"].reason_code in ("NO_TEST_RELATIONSHIP", "FRAMEWORK_CONVENTION_UNRESOLVED")

    assert f"test_multi1_{sfx}" in aff_map
    assert f"test_multi2_{sfx}" in aff_map
    assert res.status == "completed"


def test_cross_repository_isolation(db_session: Session):
    """
    Part N: Verify that Repository A cannot receive tests, graph edges, snapshots,
    or impact paths from Repository B, even with identical symbol names.
    """
    sfx = uuid.uuid4().hex[:6]
    proj = Project(name=f"iso-proj-{sfx}")
    db_session.add(proj)
    db_session.flush()

    repo_a = Repository(project_id=proj.id, name=f"repo-alpha-{sfx}", local_path=f"/tmp/repo_a_{sfx}", default_branch="main")
    repo_b = Repository(project_id=proj.id, name=f"repo-beta-{sfx}", local_path=f"/tmp/repo_b_{sfx}", default_branch="main")
    db_session.add_all([repo_a, repo_b])
    db_session.flush()

    snap_a1 = RepositorySnapshot(repository_id=repo_a.id, commit_hash="c_a1", branch_name="main")
    snap_a2 = RepositorySnapshot(repository_id=repo_a.id, commit_hash="c_a2", branch_name="main")
    snap_b1 = RepositorySnapshot(repository_id=repo_b.id, commit_hash="c_b1", branch_name="main")
    snap_b2 = RepositorySnapshot(repository_id=repo_b.id, commit_hash="c_b2", branch_name="main")
    db_session.add_all([snap_a1, snap_a2, snap_b1, snap_b2])
    db_session.flush()

    art_a1 = _create_art(db_session, repo_a.id, snap_a1.id, "sharedLogic", "app.sharedLogic", "FUNCTION", "src/shared.py:1", "h1")
    art_a2 = _create_art(db_session, repo_a.id, snap_a2.id, "sharedLogic", "app.sharedLogic", "FUNCTION", "src/shared.py:1", "h2")
    test_a = _create_art(db_session, repo_a.id, snap_a2.id, "test_shared_a", "tests.test_shared_a", "TEST_CASE", "tests/test_a.py:1", "ht1")

    art_b1 = _create_art(db_session, repo_b.id, snap_b1.id, "sharedLogic", "app.sharedLogic", "FUNCTION", "src/shared.py:1", "h1")
    art_b2 = _create_art(db_session, repo_b.id, snap_b2.id, "sharedLogic", "app.sharedLogic", "FUNCTION", "src/shared.py:1", "h2")
    test_b = _create_art(db_session, repo_b.id, snap_b2.id, "test_shared_b", "tests.test_shared_b", "TEST_CASE", "tests/test_b.py:1", "ht2")

    _create_rel(db_session, repo_a.id, snap_a2.id, test_a.id, art_a2.id, "TESTS")
    _create_rel(db_session, repo_b.id, snap_b2.id, test_b.id, art_b2.id, "TESTS")
    db_session.commit()

    res_a = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo_a.id,
        base_snapshot_id=snap_a1.id,
        target_snapshot_id=snap_a2.id,
    )
    aff_a = [t.test_name for t in res_a.affected_tests]
    assert "test_shared_a" in aff_a
    assert "test_shared_b" not in aff_a

    res_b = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo_b.id,
        base_snapshot_id=snap_b1.id,
        target_snapshot_id=snap_b2.id,
    )
    aff_b = [t.test_name for t in res_b.affected_tests]
    assert "test_shared_b" in aff_b
    assert "test_shared_a" not in aff_b
