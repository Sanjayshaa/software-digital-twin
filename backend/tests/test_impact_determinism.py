"""
Phase 8.9 — Section 7: Deterministic Repeatability Test.
Verifies that executing Change Impact Analysis N times on the exact same snapshot pair
produces strictly identical results across all fields, paths, classifications, and ordering.
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
from app.services.impact.models import ChangeSet, ChangeItem, ChangeType, ImpactConfig
from app.services.impact.analyzer import change_impact_analyzer


@pytest.fixture
def determinism_env(db_session: Session):
    suffix = uuid.uuid4().hex[:8]
    proj = Project(name=f"DetProj-{suffix}")
    db_session.add(proj)
    db_session.flush()

    repo = Repository(
        project_id=proj.id,
        name=f"det_repo_{suffix}",
        local_path=f"/tmp/det_{suffix}",
        default_branch="main",
        environment="TEST",
    )
    db_session.add(repo)
    db_session.flush()

    snap_base = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="aaaa111122223333444455556666777788889999",
        branch_name="main",
        total_files=5,
        total_symbols=10,
    )
    snap_target = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="bbbb111122223333444455556666777788889999",
        branch_name="main",
        total_files=5,
        total_symbols=10,
    )
    db_session.add_all([snap_base, snap_target])
    db_session.flush()

    # Create a non-trivial topology with multiple branches and cycles
    # A -> B -> C -> D
    # A -> E -> D
    # D -> B (Cycle)
    # T -> TESTS -> C
    art_a = StructuralArtifact(id=f"art_a_{suffix}", snapshot_id=snap_target.id, name="A", qualified_name="app.A", artifact_type="CLASS", file_path="app/a.py", location="app/a.py:1", source_hash="ha", confidence=1.0)
    art_b = StructuralArtifact(id=f"art_b_{suffix}", snapshot_id=snap_target.id, name="B", qualified_name="app.B", artifact_type="CLASS", file_path="app/b.py", location="app/b.py:1", source_hash="hb", confidence=1.0)
    art_c = StructuralArtifact(id=f"art_c_{suffix}", snapshot_id=snap_target.id, name="C", qualified_name="app.C", artifact_type="CLASS", file_path="app/c.py", location="app/c.py:1", source_hash="hc", confidence=1.0)
    art_d = StructuralArtifact(id=f"art_d_{suffix}", snapshot_id=snap_target.id, name="D", qualified_name="app.D", artifact_type="CLASS", file_path="app/d.py", location="app/d.py:1", source_hash="hd", confidence=1.0)
    art_e = StructuralArtifact(id=f"art_e_{suffix}", snapshot_id=snap_target.id, name="E", qualified_name="app.E", artifact_type="CLASS", file_path="app/e.py", location="app/e.py:1", source_hash="he", confidence=1.0)
    art_t = StructuralArtifact(id=f"art_t_{suffix}", snapshot_id=snap_target.id, name="test_c", qualified_name="tests.test_c", artifact_type="TEST_CASE", file_path="tests/t.py", location="tests/t.py:1", source_hash="ht", confidence=1.0)

    db_session.add_all([art_a, art_b, art_c, art_d, art_e, art_t])
    db_session.flush()

    # A calls B, B calls C, C calls D
    r1 = ArtifactRelationship(snapshot_id=snap_target.id, source_artifact_id=art_a.id, target_artifact_id=art_b.id, relationship_type="CALLS", confidence=1.0)
    r2 = ArtifactRelationship(snapshot_id=snap_target.id, source_artifact_id=art_b.id, target_artifact_id=art_c.id, relationship_type="CALLS", confidence=1.0)
    r3 = ArtifactRelationship(snapshot_id=snap_target.id, source_artifact_id=art_c.id, target_artifact_id=art_d.id, relationship_type="CALLS", confidence=1.0)
    # A calls E, E calls D
    r4 = ArtifactRelationship(snapshot_id=snap_target.id, source_artifact_id=art_a.id, target_artifact_id=art_e.id, relationship_type="CALLS", confidence=1.0)
    r5 = ArtifactRelationship(snapshot_id=snap_target.id, source_artifact_id=art_e.id, target_artifact_id=art_d.id, relationship_type="CALLS", confidence=1.0)
    # Cycle: D calls B
    r6 = ArtifactRelationship(snapshot_id=snap_target.id, source_artifact_id=art_d.id, target_artifact_id=art_b.id, relationship_type="CALLS", confidence=1.0)
    # Test tests C
    r7 = ArtifactRelationship(snapshot_id=snap_target.id, source_artifact_id=art_t.id, target_artifact_id=art_c.id, relationship_type="TESTS", confidence=1.0)

    db_session.add_all([r1, r2, r3, r4, r5, r6, r7])
    db_session.commit()

    change_set = ChangeSet(
        repository_id=repo.id,
        base_snapshot_id=snap_base.id,
        target_snapshot_id=snap_target.id,
        changes=[
            ChangeItem(
                artifact_id=art_d.id,
                qualified_name=art_d.qualified_name,
                symbol_name=art_d.name,
                artifact_type="CLASS",
                source_file=art_d.file_path,
                change_type=ChangeType.MODIFIED,
            )
        ],
    )

    yield {
        "db": db_session,
        "repo": repo,
        "snap_base": snap_base,
        "snap_target": snap_target,
        "change_set": change_set,
    }

    # Teardown
    db_session.rollback()
    db_session.query(ArtifactRelationship).filter(
        ArtifactRelationship.snapshot_id.in_([snap_base.id, snap_target.id])
    ).delete(synchronize_session=False)
    db_session.query(StructuralArtifact).filter(
        StructuralArtifact.snapshot_id.in_([snap_base.id, snap_target.id])
    ).delete(synchronize_session=False)
    db_session.query(RepositorySnapshot).filter_by(repository_id=repo.id).delete(synchronize_session=False)
    db_session.query(Repository).filter_by(id=repo.id).delete(synchronize_session=False)
    db_session.query(Project).filter_by(id=proj.id).delete(synchronize_session=False)
    db_session.commit()


def test_impact_analysis_repeatability_5_iterations(determinism_env):
    """
    Executes ChangeImpactAnalyzer 5 times and verifies 100% semantic identity:
    - Same affected entity IDs in identical order
    - Same paths and path depths
    - Same classifications and confidence factors
    - Same evidence IDs
    """
    db = determinism_env["db"]
    repo = determinism_env["repo"]
    snap_base = determinism_env["snap_base"]
    snap_target = determinism_env["snap_target"]
    change_set = determinism_env["change_set"]

    results = []
    for _ in range(5):
        res = change_impact_analyzer.analyze(
            db=db,
            repository_id=repo.id,
            base_snapshot_id=snap_base.id,
            target_snapshot_id=snap_target.id,
            change_set=change_set,
        )
        results.append(res)

    baseline = results[0]

    for i in range(1, 5):
        current = results[i]

        # 1. Summary Metrics
        assert current.summary.unique_affected == baseline.summary.unique_affected
        assert current.summary.multi_hop_affected == baseline.summary.multi_hop_affected
        assert current.summary.total_evidence_paths == baseline.summary.total_evidence_paths
        assert current.summary.depth_1_paths == baseline.summary.depth_1_paths
        assert current.summary.depth_2_paths == baseline.summary.depth_2_paths

        # 2. Findings Order & Content
        assert len(current.findings) == len(baseline.findings)
        for f_curr, f_base in zip(current.findings, baseline.findings):
            assert f_curr.impacted_node_id == f_base.impacted_node_id
            assert f_curr.target_qual_name == f_base.target_qual_name
            assert f_curr.impact_level == f_base.impact_level
            assert f_curr.relationship_type == f_base.relationship_type
            assert f_curr.impact_classification == f_base.impact_classification
            assert f_curr.confidence == f_base.confidence
            assert f_curr.path == f_base.path

        # 3. Paths Order & Content
        assert len(current.paths) == len(baseline.paths)
        for p_curr, p_base in zip(current.paths, baseline.paths):
            assert p_curr.root_symbol == p_base.root_symbol
            assert p_curr.target_symbol == p_base.target_symbol
            assert p_curr.nodes == p_base.nodes
            assert p_curr.depth == p_base.depth
            assert p_curr.terminal_type == p_base.terminal_type
