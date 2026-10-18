"""
Phase 8.5.11 — Test Relationship Recall Controlled Fixtures.

Validates the four mandatory test impact topologies:
1. Fixture A: production A -> IMPORTS -> production B -> IMPORTS -> production C -> TESTS -> test T.
   Modify A. Expected: T = INDIRECTLY_AFFECTED (depth >= 2, DERIVED).
2. Fixture B: production A -> TESTS -> test T.
   Modify A. Expected: T = DIRECTLY_AFFECTED (depth 1, OBSERVED).
3. Fixture C: production A modified, test T exists elsewhere without dependency path.
   Expected: production A = UNKNOWN_COVERAGE, test T = UNAFFECTED.
4. Fixture D: production A -> external dependency -> unresolved runtime path.
   Expected: production A = UNKNOWN_COVERAGE.
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
    TestEvidenceStatus,
    TestCoverageClaim,
)
from app.services.testing.engine import test_impact_engine


def _create_env(db: Session, suffix: str):
    project = Project(
        name=f"Controlled Fixture Project {suffix}",
        description="Phase 8.5.11 Controlled Topologies",
    )
    db.add(project)
    db.flush()

    repo = Repository(
        project_id=project.id,
        name=f"controlled-repo-{suffix}",
        local_path=f"/tmp/controlled_repo_{suffix}",
        default_branch="main",
    )
    db.add(repo)
    db.flush()

    snap_base = RepositorySnapshot(
        id=f"snap_base_{suffix}",
        repository_id=repo.id,
        commit_hash=f"base_{suffix}",
        branch_name="main",
        total_files=5,
        total_symbols=10,
        snapshot_metadata={"test": True},
    )
    snap_target = RepositorySnapshot(
        id=f"snap_target_{suffix}",
        repository_id=repo.id,
        commit_hash=f"target_{suffix}",
        branch_name="feature/change",
        total_files=5,
        total_symbols=10,
        snapshot_metadata={"test": True},
    )
    db.add(snap_base)
    db.add(snap_target)
    db.flush()
    return repo, snap_base, snap_target


def _create_art(
    db: Session,
    snap_id: str,
    repo_id: str,
    name: str,
    qual_name: str,
    art_type: str,
    loc: str,
    src_hash: str,
) -> StructuralArtifact:
    art = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo_id,
        snapshot_id=snap_id,
        name=name,
        qualified_name=qual_name,
        artifact_type=art_type,
        location=loc,
        source_hash=src_hash,
        language="typescript",
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
) -> ArtifactRelationship:
    rel = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo_id,
        snapshot_id=snap_id,
        source_artifact_id=source_id,
        target_artifact_id=target_id,
        relationship_type=rel_type,
        confidence=1.0,
        detection_method="ast_inspection",
    )
    db.add(rel)
    db.flush()
    return rel


# =========================================================================
# FIXTURE A: Multi-hop Transitive Propagation
# A -> IMPORTS -> B -> IMPORTS -> C -> TESTS -> test T. Modify A.
# Expected: T = INDIRECTLY_AFFECTED
# =========================================================================
def test_fixture_a_transitive_indirect_test_impact(db_session: Session):
    repo, base, target = _create_env(db_session, "fix_a_" + uuid.uuid4().hex[:6])

    # Base snapshot
    a_b = _create_art(db_session, base.id, repo.id, "ProdA", "pkg.ProdA", "MODULE", "src/ProdA.ts", "hash_a_v1")
    b_b = _create_art(db_session, base.id, repo.id, "ProdB", "pkg.ProdB", "MODULE", "src/ProdB.ts", "hash_b_v1")
    c_b = _create_art(db_session, base.id, repo.id, "ProdC", "pkg.ProdC", "MODULE", "src/ProdC.ts", "hash_c_v1")
    t_b = _create_art(db_session, base.id, repo.id, "TestT", "tests.TestT", "TEST_CASE", "tests/TestT.test.ts", "hash_t_v1")

    # B imports A, C imports B, TestT tests C
    _create_rel(db_session, base.id, repo.id, b_b.id, a_b.id, "IMPORTS")
    _create_rel(db_session, base.id, repo.id, c_b.id, b_b.id, "IMPORTS")
    _create_rel(db_session, base.id, repo.id, t_b.id, c_b.id, "TESTS")

    # Target snapshot: ProdA is modified
    a_t = _create_art(db_session, target.id, repo.id, "ProdA", "pkg.ProdA", "MODULE", "src/ProdA.ts", "hash_a_v2_MODIFIED")
    b_t = _create_art(db_session, target.id, repo.id, "ProdB", "pkg.ProdB", "MODULE", "src/ProdB.ts", "hash_b_v1")
    c_t = _create_art(db_session, target.id, repo.id, "ProdC", "pkg.ProdC", "MODULE", "src/ProdC.ts", "hash_c_v1")
    t_t = _create_art(db_session, target.id, repo.id, "TestT", "tests.TestT", "TEST_CASE", "tests/TestT.test.ts", "hash_t_v1")

    _create_rel(db_session, target.id, repo.id, b_t.id, a_t.id, "IMPORTS")
    _create_rel(db_session, target.id, repo.id, c_t.id, b_t.id, "IMPORTS")
    _create_rel(db_session, target.id, repo.id, t_t.id, c_t.id, "TESTS")
    db_session.commit()

    result = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo.id,
        base_snapshot_id=base.id,
        target_snapshot_id=target.id,
    )

    assert result.status == "completed"
    assert result.summary.potentially_affected_count == 1
    assert result.summary.indirectly_affected_count == 1
    assert result.summary.directly_affected_count == 0

    test_item = next(t for t in result.affected_tests if t.test_name == "TestT")
    assert test_item.classification == TestImpactClassification.INDIRECTLY_AFFECTED
    assert test_item.evidence_status == TestEvidenceStatus.DERIVED
    assert test_item.depth >= 2
    assert "pkg.ProdA" in test_item.impact_path
    assert "pkg.ProdB" in test_item.impact_path
    assert "pkg.ProdC" in test_item.impact_path


# =========================================================================
# FIXTURE B: Direct Test Impact
# production A -> TESTS -> test T. Modify A.
# Expected: T = DIRECTLY_AFFECTED
# =========================================================================
def test_fixture_b_direct_test_impact(db_session: Session):
    repo, base, target = _create_env(db_session, "fix_b_" + uuid.uuid4().hex[:6])

    # Base snapshot
    a_b = _create_art(db_session, base.id, repo.id, "ProdA", "pkg.ProdA", "MODULE", "src/ProdA.ts", "hash_a_v1")
    t_b = _create_art(db_session, base.id, repo.id, "TestT", "tests.TestT", "TEST_CASE", "tests/TestT.test.ts", "hash_t_v1")
    _create_rel(db_session, base.id, repo.id, t_b.id, a_b.id, "TESTS")

    # Target snapshot: ProdA is modified
    a_t = _create_art(db_session, target.id, repo.id, "ProdA", "pkg.ProdA", "MODULE", "src/ProdA.ts", "hash_a_v2_MODIFIED")
    t_t = _create_art(db_session, target.id, repo.id, "TestT", "tests.TestT", "TEST_CASE", "tests/TestT.test.ts", "hash_t_v1")
    _create_rel(db_session, target.id, repo.id, t_t.id, a_t.id, "TESTS")
    db_session.commit()

    result = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo.id,
        base_snapshot_id=base.id,
        target_snapshot_id=target.id,
    )

    assert result.status == "completed"
    assert result.summary.potentially_affected_count == 1
    assert result.summary.directly_affected_count == 1
    assert result.summary.indirectly_affected_count == 0

    test_item = next(t for t in result.affected_tests if t.test_name == "TestT")
    assert test_item.classification == TestImpactClassification.DIRECTLY_AFFECTED
    assert test_item.evidence_status == TestEvidenceStatus.OBSERVED
    assert test_item.depth == 1
    assert "pkg.ProdA" in test_item.impact_path


# =========================================================================
# FIXTURE C: Disjoint Unrelated Components
# production A modified, test T exists elsewhere without dependency path.
# Expected: A = UNKNOWN_COVERAGE, T = UNAFFECTED
# =========================================================================
def test_fixture_c_unrelated_components_isolation(db_session: Session):
    repo, base, target = _create_env(db_session, "fix_c_" + uuid.uuid4().hex[:6])

    # Base snapshot: ProdA (isolated), ProdX -> TESTS -> TestT (unrelated)
    a_b = _create_art(db_session, base.id, repo.id, "ProdA", "pkg.ProdA", "MODULE", "src/ProdA.ts", "hash_a_v1")
    x_b = _create_art(db_session, base.id, repo.id, "ProdX", "pkg.ProdX", "MODULE", "src/ProdX.ts", "hash_x_v1")
    t_b = _create_art(db_session, base.id, repo.id, "TestT", "tests.TestT", "TEST_CASE", "tests/TestT.test.ts", "hash_t_v1")
    _create_rel(db_session, base.id, repo.id, t_b.id, x_b.id, "TESTS")

    # Target snapshot: ProdA is modified, ProdX and TestT remain untouched
    a_t = _create_art(db_session, target.id, repo.id, "ProdA", "pkg.ProdA", "MODULE", "src/ProdA.ts", "hash_a_v2_MODIFIED")
    x_t = _create_art(db_session, target.id, repo.id, "ProdX", "pkg.ProdX", "MODULE", "src/ProdX.ts", "hash_x_v1")
    t_t = _create_art(db_session, target.id, repo.id, "TestT", "tests.TestT", "TEST_CASE", "tests/TestT.test.ts", "hash_t_v1")
    _create_rel(db_session, target.id, repo.id, t_t.id, x_t.id, "TESTS")
    db_session.commit()

    result = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo.id,
        base_snapshot_id=base.id,
        target_snapshot_id=target.id,
    )

    assert result.status == "completed"
    assert result.summary.potentially_affected_count == 0
    assert result.summary.unaffected_count == 1
    assert result.summary.unknown_coverage_count == 1

    # Check ProdA is in unknown coverage
    unknown_item = next(u for u in result.unknown_coverage if u.qualified_name == "pkg.ProdA")
    assert unknown_item.classification == TestImpactClassification.UNKNOWN_COVERAGE
    assert unknown_item.coverage_claim == TestCoverageClaim.NO_TEST_RELATIONSHIP_FOUND

    # Check TestT is UNAFFECTED
    unaffected_item = next(t for t in result.unaffected_tests if t.test_name == "TestT")
    assert unaffected_item.classification == TestImpactClassification.UNAFFECTED
    assert unaffected_item.coverage_claim == TestCoverageClaim.TEST_EXISTS_AND_IS_UNAFFECTED


# =========================================================================
# FIXTURE D: External Dependency with Unresolved Runtime Path
# production A -> external dependency -> unresolved runtime path.
# Expected: A = UNKNOWN_COVERAGE
# =========================================================================
def test_fixture_d_external_dependency_unresolved_runtime(db_session: Session):
    repo, base, target = _create_env(db_session, "fix_d_" + uuid.uuid4().hex[:6])

    # Base snapshot: ProdA -> IMPORTS -> ExternalDep (e.g. lodash, aws-sdk)
    a_b = _create_art(db_session, base.id, repo.id, "ProdA", "pkg.ProdA", "MODULE", "src/ProdA.ts", "hash_a_v1")
    ext_b = _create_art(db_session, base.id, repo.id, "lodash", "external.lodash", "EXTERNAL_DEPENDENCY", "<external>", "hash_ext")
    _create_rel(db_session, base.id, repo.id, a_b.id, ext_b.id, "IMPORTS")

    # Target snapshot: ProdA modified
    a_t = _create_art(db_session, target.id, repo.id, "ProdA", "pkg.ProdA", "MODULE", "src/ProdA.ts", "hash_a_v2_MODIFIED")
    ext_t = _create_art(db_session, target.id, repo.id, "lodash", "external.lodash", "EXTERNAL_DEPENDENCY", "<external>", "hash_ext")
    _create_rel(db_session, target.id, repo.id, a_t.id, ext_t.id, "IMPORTS")
    db_session.commit()

    result = test_impact_engine.compute_test_impact(
        db=db_session,
        repository_id=repo.id,
        base_snapshot_id=base.id,
        target_snapshot_id=target.id,
    )

    assert result.status == "completed"
    assert result.summary.potentially_affected_count == 0
    assert result.summary.unknown_coverage_count == 1

    unknown_item = next(u for u in result.unknown_coverage if u.qualified_name == "pkg.ProdA")
    assert unknown_item.classification == TestImpactClassification.UNKNOWN_COVERAGE
    assert "Absence of a test path means coverage is UNKNOWN" in unknown_item.cannot_be_unaffected_proof
