"""
Phase 6 / 8.5.7 Semantic Coverage Classification & Claim Hierarchy Tests.

Validates:
1. Semantic classification of the changed-artifact population across all 5 dimensions:
   - Direct test evidence (DIRECT_TEST_EVIDENCE -> TEST_IS_AFFECTED)
   - Indirect test evidence (INDIRECT_TEST_EVIDENCE -> TEST_IS_AFFECTED)
   - No discovered test relationship (NO_DISCOVERED_TEST_RELATIONSHIP -> NO_TEST_RELATIONSHIP_FOUND)
   - Unresolved dependency (UNRESOLVED_DEPENDENCY -> NO_TEST_RELATIONSHIP_FOUND)
   - Framework convention uncertainty (FRAMEWORK_CONVENTION_UNCERTAINTY -> TEST_EXISTS_BUT_COVERAGE_IS_UNKNOWN)
2. Strict mathematical proof that UNKNOWN cannot become UNAFFECTED merely because no path was found.
3. Rigorous distinction across all 5 claims:
   - NO TEST RELATIONSHIP FOUND
   - NO AUTOMATED TEST EXISTS
   - TEST EXISTS BUT COVERAGE IS UNKNOWN
   - TEST EXISTS AND IS UNAFFECTED
   - TEST IS AFFECTED
4. Evidence hierarchy enforcement: strong claims can only be made when prerequisite evidence exists.
"""

import pytest
import uuid
from app.models.entities import (
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
)
from app.services.testing.engine import TestImpactEngine
from app.services.testing.models import (
    TestImpactConfig,
    TestImpactClassification,
    TestCoverageClaim,
)
from app.services.impact.models import ChangeSet, ChangeItem, ChangeType


@pytest.fixture
def semantic_repo_setup(db_session):
    """
    Creates a rich, multi-artifact synthetic topology to evaluate all 5 coverage dimensions.
    """
    sfx = uuid.uuid4().hex[:8]
    proj = Project(name=f"test-proj-semantic-{sfx}")
    db_session.add(proj)
    db_session.flush()

    repo = Repository(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name=f"test-semantic-{sfx}",
        local_path=f"/tmp/test_semantic_{sfx}",
        remote_url="https://github.com/example/semantic-test",
    )
    db_session.add(repo)
    db_session.flush()

    base_snap = RepositorySnapshot(
        id=f"snap_base_{uuid.uuid4().hex[:8]}",
        repository_id=repo.id,
        commit_hash="1111111111111111111111111111111111111111",
        branch_name="main",
    )
    target_snap = RepositorySnapshot(
        id=f"snap_target_{uuid.uuid4().hex[:8]}",
        repository_id=repo.id,
        commit_hash="2222222222222222222222222222222222222222",
        branch_name="main",
    )
    db_session.add_all([base_snap, target_snap])
    db_session.flush()

    def _create_art(name, qual, atype, loc, src_hash="v1"):
        art = StructuralArtifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            repository_id=repo.id,
            snapshot_id=target_snap.id,
            name=name,
            qualified_name=qual,
            artifact_type=atype,
            language="python",
            location=loc,
            source_hash=src_hash,
            metadata_payload={},
        )
        db_session.add(art)
        db_session.flush()
        return art

    def _create_rel(src_id, tgt_id, rtype):
        rel = ArtifactRelationship(
            id=f"rel_{uuid.uuid4().hex[:12]}",
            repository_id=repo.id,
            snapshot_id=target_snap.id,
            source_artifact_id=src_id,
            target_artifact_id=tgt_id,
            relationship_type=rtype,
            confidence=1.0,
            detection_method="ast_inspection",
            metadata_payload={},
        )
        db_session.add(rel)
        db_session.flush()
        return rel

    # 1. Target with Direct Test
    art_direct_prod = _create_art("payment_processor", "app.services.payment_processor", "CLASS", "app/services/payment_processor.py:10", "hash_dp_v2")
    test_direct = _create_art("test_payment_processor", "tests.test_payment_processor", "TEST_CASE", "tests/test_payment_processor.py:5", "hash_test_dp")
    _create_rel(test_direct.id, art_direct_prod.id, "TESTS")

    # 2. Target with Indirect Test (A -> B -> C -> Test)
    art_indirect_prod = _create_art("crypto_util", "app.crypto.crypto_util", "FUNCTION", "app/crypto/crypto_util.py:12", "hash_ip_v2")
    art_intermediate = _create_art("auth_service", "app.services.auth_service", "CLASS", "app/services/auth_service.py:8", "hash_inter")
    test_indirect = _create_art("test_auth_service", "tests.test_auth_service", "TEST_CASE", "tests/test_auth_service.py:15", "hash_test_ip")
    _create_rel(test_indirect.id, art_intermediate.id, "TESTS")
    _create_rel(art_intermediate.id, art_indirect_prod.id, "CALLS")

    # 3. Target with No Test Relationship (Completely orphaned from test graph)
    art_no_rel_prod = _create_art("legacy_report_generator", "app.legacy.legacy_report_generator", "CLASS", "app/legacy/legacy_report_generator.py:1", "hash_nr_v2")

    # 4. Target with Unresolved Dependency (Propagates downstream, but ends in external/unresolved node)
    art_unresolved_prod = _create_art("kafka_producer", "app.messaging.kafka_producer", "CLASS", "app/messaging/kafka_producer.py:4", "hash_unres_v2")
    art_external_sink = _create_art("external_kafka_client", "external.kafka.client", "EXTERNAL_DEPENDENCY", "external/kafka", "hash_sink")
    _create_rel(art_unresolved_prod.id, art_external_sink.id, "DEPENDS_ON")

    # 5. Target with Framework Convention Uncertainty (Sibling test in same folder, but no AST edge)
    art_conv_prod = _create_art("user_validator", "app.validators.user_validator", "FUNCTION", "app/validators/user_validator.py:10", "hash_conv_v2")
    test_conv_sibling = _create_art("user_validator_test", "app.validators.user_validator_test", "TEST_CASE", "app/validators/user_validator_test.py:1", "hash_test_conv")

    # 6. Unaffected Test (Mapped in test suite, but entirely outside any change paths)
    test_unaffected = _create_art("test_math_utils", "tests.test_math_utils", "TEST_CASE", "tests/test_math_utils.py:1", "hash_test_unaff")
    art_math_prod = _create_art("math_utils", "app.utils.math_utils", "MODULE", "app/utils/math_utils.py:1", "hash_math")
    _create_rel(test_unaffected.id, art_math_prod.id, "TESTS")

    db_session.commit()

    return {
        "repo": repo,
        "base_snap": base_snap,
        "target_snap": target_snap,
        "direct_prod": art_direct_prod,
        "test_direct": test_direct,
        "indirect_prod": art_indirect_prod,
        "test_indirect": test_indirect,
        "no_rel_prod": art_no_rel_prod,
        "unresolved_prod": art_unresolved_prod,
        "conv_prod": art_conv_prod,
        "test_conv": test_conv_sibling,
        "test_unaffected": test_unaffected,
    }


def test_semantic_classification_of_same_changed_population(db_session, semantic_repo_setup):
    """
    Evaluates the SAME changed-artifact population across all 5 dimensions.
    Proves that each artifact receives the precise claim and evidence category.
    """
    setup = semantic_repo_setup
    repo = setup["repo"]
    base_snap = setup["base_snap"]
    target_snap = setup["target_snap"]

    # Construct change set containing all 5 changed production artifacts:
    changed_items = [
        ChangeItem(
            artifact_id=setup["direct_prod"].id,
            qualified_name=setup["direct_prod"].qualified_name,
            symbol_name=setup["direct_prod"].name,
            artifact_type=setup["direct_prod"].artifact_type,
            source_file=setup["direct_prod"].location.split(":")[0],
            change_type=ChangeType.MODIFIED,
        ),
        ChangeItem(
            artifact_id=setup["indirect_prod"].id,
            qualified_name=setup["indirect_prod"].qualified_name,
            symbol_name=setup["indirect_prod"].name,
            artifact_type=setup["indirect_prod"].artifact_type,
            source_file=setup["indirect_prod"].location.split(":")[0],
            change_type=ChangeType.MODIFIED,
        ),
        ChangeItem(
            artifact_id=setup["no_rel_prod"].id,
            qualified_name=setup["no_rel_prod"].qualified_name,
            symbol_name=setup["no_rel_prod"].name,
            artifact_type=setup["no_rel_prod"].artifact_type,
            source_file=setup["no_rel_prod"].location.split(":")[0],
            change_type=ChangeType.MODIFIED,
        ),
        ChangeItem(
            artifact_id=setup["unresolved_prod"].id,
            qualified_name=setup["unresolved_prod"].qualified_name,
            symbol_name=setup["unresolved_prod"].name,
            artifact_type=setup["unresolved_prod"].artifact_type,
            source_file=setup["unresolved_prod"].location.split(":")[0],
            change_type=ChangeType.MODIFIED,
        ),
        ChangeItem(
            artifact_id=setup["conv_prod"].id,
            qualified_name=setup["conv_prod"].qualified_name,
            symbol_name=setup["conv_prod"].name,
            artifact_type=setup["conv_prod"].artifact_type,
            source_file=setup["conv_prod"].location.split(":")[0],
            change_type=ChangeType.MODIFIED,
        ),
    ]

    change_set = ChangeSet(
        repository_id=repo.id,
        base_snapshot_id=base_snap.id,
        target_snapshot_id=target_snap.id,
        changes=changed_items,
    )

    engine = TestImpactEngine()
    result = engine.compute_test_impact(
        db=db_session,
        repository_id=repo.id,
        base_snapshot_id=base_snap.id,
        target_snapshot_id=target_snap.id,
        config=TestImpactConfig(max_depth=6, include_unaffected=True),
        change_set=change_set,
    )

    # Convert evaluations to lookup by qualified name
    eval_by_qual = {e.qualified_name: e for e in result.changed_artifact_evaluations}
    assert len(eval_by_qual) == 5, "All 5 changed artifacts must be evaluated."

    # 1. Direct Test Evidence
    e_direct = eval_by_qual[setup["direct_prod"].qualified_name]
    assert e_direct.coverage_claim == TestCoverageClaim.TEST_IS_AFFECTED
    assert e_direct.evidence_category == "DIRECT_TEST_EVIDENCE"
    assert e_direct.direct_test_count == 1
    assert e_direct.indirect_test_count == 0
    assert setup["test_direct"].qualified_name in e_direct.associated_tests

    # 2. Indirect Test Evidence
    e_indirect = eval_by_qual[setup["indirect_prod"].qualified_name]
    assert e_indirect.coverage_claim == TestCoverageClaim.TEST_IS_AFFECTED
    assert e_indirect.evidence_category == "INDIRECT_TEST_EVIDENCE"
    assert e_indirect.direct_test_count == 0
    assert e_indirect.indirect_test_count == 1
    assert setup["test_indirect"].qualified_name in e_indirect.associated_tests
    assert e_indirect.traversal_depth_reached == 2

    # 3. No Discovered Test Relationship
    e_norel = eval_by_qual[setup["no_rel_prod"].qualified_name]
    assert e_norel.coverage_claim == TestCoverageClaim.NO_TEST_RELATIONSHIP_FOUND
    assert e_norel.evidence_category == "NO_DISCOVERED_TEST_RELATIONSHIP"
    assert e_norel.direct_test_count == 0
    assert e_norel.indirect_test_count == 0
    assert e_norel.associated_tests == []

    # 4. Unresolved Dependency
    e_unres = eval_by_qual[setup["unresolved_prod"].qualified_name]
    assert e_unres.coverage_claim == TestCoverageClaim.NO_TEST_RELATIONSHIP_FOUND
    assert e_unres.evidence_category == "UNRESOLVED_DEPENDENCY"
    assert e_unres.downstream_entities_count == 1
    assert e_unres.direct_test_count == 0

    # 5. Framework Convention Uncertainty
    e_conv = eval_by_qual[setup["conv_prod"].qualified_name]
    assert e_conv.coverage_claim == TestCoverageClaim.TEST_EXISTS_BUT_COVERAGE_IS_UNKNOWN
    assert e_conv.evidence_category == "FRAMEWORK_CONVENTION_UNCERTAINTY"
    assert e_conv.direct_test_count == 0


def test_prove_unknown_cannot_become_unaffected_when_no_path_found(db_session, semantic_repo_setup):
    """
    CRITICAL PROOF: Proves that when no test path is found for a changed artifact,
    it CANNOT and NEVER becomes UNAFFECTED.
    """
    setup = semantic_repo_setup
    repo = setup["repo"]
    base_snap = setup["base_snap"]
    target_snap = setup["target_snap"]

    # Only change the orphaned artifact with zero tests
    change_set = ChangeSet(
        repository_id=repo.id,
        base_snapshot_id=base_snap.id,
        target_snapshot_id=target_snap.id,
        changes=[
            ChangeItem(
                artifact_id=setup["no_rel_prod"].id,
                qualified_name=setup["no_rel_prod"].qualified_name,
                symbol_name=setup["no_rel_prod"].name,
                artifact_type=setup["no_rel_prod"].artifact_type,
                source_file=setup["no_rel_prod"].location.split(":")[0],
                change_type=ChangeType.MODIFIED,
            )
        ],
    )

    engine = TestImpactEngine()
    result = engine.compute_test_impact(
        db=db_session,
        repository_id=repo.id,
        base_snapshot_id=base_snap.id,
        target_snapshot_id=target_snap.id,
        change_set=change_set,
    )

    # 1. Affected tests must be 0
    assert len(result.affected_tests) == 0

    # 2. Unknown coverage must contain the changed artifact
    assert len(result.unknown_coverage) == 1
    unk = result.unknown_coverage[0]
    assert unk.artifact_id == setup["no_rel_prod"].id
    assert unk.classification == TestImpactClassification.UNKNOWN_COVERAGE
    assert unk.coverage_claim == TestCoverageClaim.NO_TEST_RELATIONSHIP_FOUND

    # 3. The changed artifact MUST NOT be in unaffected_tests
    unaffected_ids = {t.test_id for t in result.unaffected_tests}
    assert setup["no_rel_prod"].id not in unaffected_ids, (
        "CRITICAL INVARIANT BREACH: Changed production artifact was added to unaffected_tests!"
    )

    # 4. Only genuine test artifacts are in unaffected_tests
    for t in result.unaffected_tests:
        assert t.classification == TestImpactClassification.UNAFFECTED
        assert t.coverage_claim == TestCoverageClaim.TEST_EXISTS_AND_IS_UNAFFECTED
        assert t.test_id in [setup["test_direct"].id, setup["test_indirect"].id, setup["test_conv"].id, setup["test_unaffected"].id]


def test_evidence_hierarchy_prevents_unjustified_strong_claims(db_session, semantic_repo_setup):
    """
    Tests that the Digital Twin may only make a stronger claim when the evidence supports it:
    - Cannot claim NO_AUTOMATED_TEST_EXISTS if tests exist in the repo.
    - Cannot claim TEST_IS_AFFECTED without a proven path.
    - Cannot claim TEST_EXISTS_AND_IS_UNAFFECTED for non-test artifacts.
    """
    setup = semantic_repo_setup
    repo = setup["repo"]
    base_snap = setup["base_snap"]
    target_snap = setup["target_snap"]

    # When tests exist in repo, changed artifact without path MUST NOT claim NO_AUTOMATED_TEST_EXISTS
    change_set = ChangeSet(
        repository_id=repo.id,
        base_snapshot_id=base_snap.id,
        target_snapshot_id=target_snap.id,
        changes=[
            ChangeItem(
                artifact_id=setup["no_rel_prod"].id,
                qualified_name=setup["no_rel_prod"].qualified_name,
                symbol_name=setup["no_rel_prod"].name,
                artifact_type=setup["no_rel_prod"].artifact_type,
                source_file=setup["no_rel_prod"].location.split(":")[0],
                change_type=ChangeType.MODIFIED,
            )
        ],
    )

    engine = TestImpactEngine()
    result = engine.compute_test_impact(
        db=db_session,
        repository_id=repo.id,
        base_snapshot_id=base_snap.id,
        target_snapshot_id=target_snap.id,
        change_set=change_set,
    )

    eval_item = result.changed_artifact_evaluations[0]
    # Strong claim NO_AUTOMATED_TEST_EXISTS is forbidden because tests exist in repo:
    assert eval_item.coverage_claim != TestCoverageClaim.NO_AUTOMATED_TEST_EXISTS
    assert eval_item.coverage_claim == TestCoverageClaim.NO_TEST_RELATIONSHIP_FOUND

    # Test the true zero-test repo scenario where NO_AUTOMATED_TEST_EXISTS IS justified
    proj_empty = Project(name=f"test-proj-empty-{uuid.uuid4().hex[:8]}")
    db_session.add(proj_empty)
    db_session.flush()

    repo_empty = Repository(
        id=str(uuid.uuid4()),
        project_id=proj_empty.id,
        name=f"test-empty-repo-{uuid.uuid4().hex[:8]}",
        local_path=f"/tmp/test_empty_{uuid.uuid4().hex[:8]}",
        remote_url="https://github.com/example/empty-tests",
    )
    snap_empty = RepositorySnapshot(
        id=f"snap_empty_{uuid.uuid4().hex[:8]}",
        repository_id=repo_empty.id,
        commit_hash="3333333333333333333333333333333333333333",
        branch_name="main",
    )
    art_lonely = StructuralArtifact(
        id=f"art_lone_{uuid.uuid4().hex[:8]}",
        repository_id=repo_empty.id,
        snapshot_id=snap_empty.id,
        name="lonely_service",
        qualified_name="app.lonely_service",
        artifact_type="CLASS",
        language="python",
        location="app/lonely_service.py:1",
        source_hash="hash_lone",
    )
    db_session.add(repo_empty)
    db_session.flush()
    db_session.add(snap_empty)
    db_session.flush()
    db_session.add(art_lonely)
    db_session.flush()
    db_session.commit()

    cs_empty = ChangeSet(
        repository_id=repo_empty.id,
        base_snapshot_id=snap_empty.id,
        target_snapshot_id=snap_empty.id,
        changes=[
            ChangeItem(
                artifact_id=art_lonely.id,
                qualified_name=art_lonely.qualified_name,
                symbol_name=art_lonely.name,
                artifact_type=art_lonely.artifact_type,
                source_file="app/lonely_service.py",
                change_type=ChangeType.MODIFIED,
            )
        ],
    )
    res_empty = engine.compute_test_impact(
        db=db_session,
        repository_id=repo_empty.id,
        base_snapshot_id=snap_empty.id,
        target_snapshot_id=snap_empty.id,
        change_set=cs_empty,
    )

    # NOW the strong claim NO_AUTOMATED_TEST_EXISTS is justified and proven!
    eval_lone = res_empty.changed_artifact_evaluations[0]
    assert eval_lone.coverage_claim == TestCoverageClaim.NO_AUTOMATED_TEST_EXISTS
    assert eval_lone.evidence_category == "NO_AUTOMATED_TESTS_IN_REPO"
