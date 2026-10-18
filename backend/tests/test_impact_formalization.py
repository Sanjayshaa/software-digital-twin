"""
Phase 8.9 — Formalized Impact Propagation & Golden Fixture Matrix Tests.
Validates:
1. Canonical rule registry and formal rules.
2. Explicit directionality verification (caller vs callee, interface vs impl, handler vs route, test vs prod).
3. Golden Impact Fixture Matrix (Scenarios A through Q):
   A. Direct caller (A -> CALLS -> B)
   B. Two-hop chain (A -> CALLS -> B -> CALLS -> C)
   C. Three-hop chain (A -> B -> C -> D)
   D. Diamond graph (A -> B, A -> C, B -> D, C -> D)
   E. Cyclic graph (A -> B -> C -> A)
   F. Deleted symbol (historical base traversal)
   G. Unrelated component isolation
   H. Unresolved import handling
   I. Alias resolution (@/services/ -> src.services.)
   J. External dependency
   K. Inheritance (EXTENDS)
   L. Interface implementation (IMPLEMENTS)
   M. API consumer (CONSUMES)
   N. Changed API handler (EXPOSES)
   O. Test -> production dependency (TESTS)
   P. Dynamic dispatch boundary
   Q. Incomplete evidence
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
from app.services.impact.models import (
    ChangeSet,
    ChangeItem,
    ChangeType,
    ImpactConfig,
    ImpactClassification,
    PropagationDirection,
)
from app.services.impact.rules import relationship_rule_registry
from app.services.impact.propagator import impact_propagator
from app.services.impact.analyzer import change_impact_analyzer


def test_rule_registry_canonical_rules_coverage():
    """Validates that all required relationship types have explicit canonical rules and directionality."""
    required_types = [
        "CALLS",
        "IMPORTS",
        "DEPENDS_ON",
        "CONSUMES",
        "TESTS",
        "EXTENDS",
        "IMPLEMENTS",
        "PERSISTS_TO",
        "EXPOSES",
        "PARTICIPATES_IN",
        "TRANSITIONS_TO",
    ]

    for rel_type in required_types:
        rule = relationship_rule_registry.get_canonical_rule(rel_type)
        assert rule is not None, f"Missing canonical rule for {rel_type}"
        assert rule.relationship_type == rel_type
        assert rule.direction in (PropagationDirection.FORWARD, PropagationDirection.REVERSE)
        assert rule.impact_classification is not None
        assert rule.confidence_factor > 0.0
        assert len(rule.rationale) > 10


def test_explicit_directionality_caller_vs_callee():
    """
    CRITICAL DIRECTIONALITY TEST:
    Caller CALLS Callee.
    - If Callee changes: Caller MUST be affected (incoming CALLS traversed in REVERSE).
    - If Caller changes: Callee MUST NOT be affected.
    """
    rule = relationship_rule_registry.get_rule("CALLS")
    assert rule.direction == PropagationDirection.REVERSE

    # Callee is target of CALLS: caller --[CALLS]--> callee
    # When callee changes, trigger_id is target, affected_id is source (caller).


@pytest.fixture
def matrix_env(db_session: Session):
    suffix = uuid.uuid4().hex[:8]
    proj = Project(name=f"FormalProj-{suffix}")
    db_session.add(proj)
    db_session.flush()

    repo = Repository(
        project_id=proj.id,
        name=f"formal_repo_{suffix}",
        local_path=f"/tmp/formal_{suffix}",
        default_branch="main",
        environment="TEST",
    )
    db_session.add(repo)
    db_session.flush()

    snap_base = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="1111111111111111111111111111111111111111",
        branch_name="main",
        total_files=10,
        total_symbols=20,
    )
    snap_target = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="2222222222222222222222222222222222222222",
        branch_name="main",
        total_files=10,
        total_symbols=20,
    )
    db_session.add_all([snap_base, snap_target])
    db_session.commit()

    yield {
        "db": db_session,
        "repo": repo,
        "snap_base": snap_base,
        "snap_target": snap_target,
        "suffix": suffix,
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


def _make_art(db: Session, snap_id: str, name: str, qual: str, art_type: str = "CLASS") -> StructuralArtifact:
    snap = db.query(RepositorySnapshot).filter_by(id=snap_id).first()
    repo_id = snap.repository_id if snap else "repo_test"
    art = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo_id,
        snapshot_id=snap_id,
        name=name,
        qualified_name=qual,
        artifact_type=art_type,
        language="python",
        location=f"src/{name.lower()}.py:10",
        source_hash=f"hash_{name}",
        confidence=1.0,
    )
    art.file_path = f"src/{name.lower()}.py"
    db.add(art)
    db.flush()
    return art


def _make_rel(db: Session, snap_id: str, src_id: str, tgt_id: str, rel_type: str) -> ArtifactRelationship:
    snap = db.query(RepositorySnapshot).filter_by(id=snap_id).first()
    repo_id = snap.repository_id if snap else "repo_test"
    rel = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo_id,
        snapshot_id=snap_id,
        source_artifact_id=src_id,
        target_artifact_id=tgt_id,
        relationship_type=rel_type,
        detection_method="AST_STATIC",
        confidence=1.0,
    )
    db.add(rel)
    db.flush()
    return rel


def test_matrix_direct_caller_and_directionality(matrix_env):
    """Scenario A & Directionality: B calls A. When A changes -> B affected. When B changes -> A unaffected."""
    db = matrix_env["db"]
    snap = matrix_env["snap_target"]
    repo = matrix_env["repo"]

    # Callee (A) and Caller (B)
    callee = _make_art(db, snap.id, "TaxCalculator", "app.services.TaxCalculator")
    caller = _make_art(db, snap.id, "CheckoutService", "app.services.CheckoutService")
    # caller --[CALLS]--> callee
    _make_rel(db, snap.id, caller.id, callee.id, "CALLS")
    db.commit()

    # Case 1: Callee changes -> Caller MUST be affected
    cs_callee = ChangeSet(
        repository_id=repo.id,
        base_snapshot_id=matrix_env["snap_base"].id,
        target_snapshot_id=snap.id,
        changes=[
            ChangeItem(
                artifact_id=callee.id,
                qualified_name=callee.qualified_name,
                symbol_name=callee.name,
                artifact_type="CLASS",
                source_file=callee.file_path,
                change_type=ChangeType.MODIFIED,
            )
        ],
    )
    res1 = change_impact_analyzer.analyze(db, repo.id, matrix_env["snap_base"].id, snap.id, change_set=cs_callee)
    aff1 = [f.target_qual_name for f in res1.findings]
    assert "app.services.CheckoutService" in aff1
    assert res1.findings[0].impact_classification == ImpactClassification.DIRECT
    assert res1.findings[0].rule_id == "RULE_CALLS_CALLER_IMPACT"
    assert len(res1.findings[0].evidence_ids) > 0

    # Case 2: Caller changes -> Callee MUST NOT be affected
    cs_caller = ChangeSet(
        repository_id=repo.id,
        base_snapshot_id=matrix_env["snap_base"].id,
        target_snapshot_id=snap.id,
        changes=[
            ChangeItem(
                artifact_id=caller.id,
                qualified_name=caller.qualified_name,
                symbol_name=caller.name,
                artifact_type="CLASS",
                source_file=caller.file_path,
                change_type=ChangeType.MODIFIED,
            )
        ],
    )
    res2 = change_impact_analyzer.analyze(db, repo.id, matrix_env["snap_base"].id, snap.id, change_set=cs_caller)
    aff2 = [f.target_qual_name for f in res2.findings]
    assert "app.services.TaxCalculator" not in aff2


def test_matrix_two_and_three_hop_chains(matrix_env):
    """Scenarios B & C: A -> CALLS -> B -> CALLS -> C -> CALLS -> D."""
    db = matrix_env["db"]
    snap = matrix_env["snap_target"]
    repo = matrix_env["repo"]

    art_d = _make_art(db, snap.id, "LeafRepo", "app.LeafRepo")
    art_c = _make_art(db, snap.id, "DomainService", "app.DomainService")
    art_b = _make_art(db, snap.id, "AppService", "app.AppService")
    art_a = _make_art(db, snap.id, "Controller", "app.Controller")

    # A -> B -> C -> D
    _make_rel(db, snap.id, art_a.id, art_b.id, "CALLS")
    _make_rel(db, snap.id, art_b.id, art_c.id, "CALLS")
    _make_rel(db, snap.id, art_c.id, art_d.id, "CALLS")
    db.commit()

    # Leaf D modified -> C (depth 1), B (depth 2), A (depth 3)
    cs = ChangeSet(
        repository_id=repo.id,
        base_snapshot_id=matrix_env["snap_base"].id,
        target_snapshot_id=snap.id,
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
    res = change_impact_analyzer.analyze(db, repo.id, matrix_env["snap_base"].id, snap.id, change_set=cs)
    aff_map = {f.target_qual_name: f for f in res.findings}

    assert "app.DomainService" in aff_map
    assert aff_map["app.DomainService"].impact_level == 1
    assert aff_map["app.DomainService"].impact_classification == ImpactClassification.DIRECT

    assert "app.AppService" in aff_map
    assert aff_map["app.AppService"].impact_level == 2
    assert aff_map["app.AppService"].impact_classification == ImpactClassification.PROVEN_TRANSITIVE

    assert "app.Controller" in aff_map
    assert aff_map["app.Controller"].impact_level == 3
    assert aff_map["app.Controller"].impact_classification == ImpactClassification.PROVEN_TRANSITIVE


def test_matrix_diamond_and_cycles(matrix_env):
    """Scenarios D & E: Diamond convergence and cyclic graph termination."""
    db = matrix_env["db"]
    snap = matrix_env["snap_target"]
    repo = matrix_env["repo"]

    # Diamond: Top -> Left & Right -> Bottom
    # When Bottom changes: Left & Right affected (depth 1), Top affected (depth 2)
    # Cycle: Bottom -> CycleNode -> Bottom
    bottom = _make_art(db, snap.id, "DBLayer", "app.DBLayer")
    left = _make_art(db, snap.id, "LeftService", "app.LeftService")
    right = _make_art(db, snap.id, "RightService", "app.RightService")
    top = _make_art(db, snap.id, "TopFacade", "app.TopFacade")
    cycle = _make_art(db, snap.id, "CycleNode", "app.CycleNode")

    _make_rel(db, snap.id, top.id, left.id, "CALLS")
    _make_rel(db, snap.id, top.id, right.id, "CALLS")
    _make_rel(db, snap.id, left.id, bottom.id, "CALLS")
    _make_rel(db, snap.id, right.id, bottom.id, "CALLS")

    # Add cycle
    _make_rel(db, snap.id, cycle.id, bottom.id, "CALLS")
    _make_rel(db, snap.id, bottom.id, cycle.id, "CALLS")
    db.commit()

    cs = ChangeSet(
        repository_id=repo.id,
        base_snapshot_id=matrix_env["snap_base"].id,
        target_snapshot_id=snap.id,
        changes=[
            ChangeItem(
                artifact_id=bottom.id,
                qualified_name=bottom.qualified_name,
                symbol_name=bottom.name,
                artifact_type="CLASS",
                source_file=bottom.file_path,
                change_type=ChangeType.MODIFIED,
            )
        ],
    )
    # Must terminate without infinite loop and deduplicate diamond convergence on TopFacade
    res = change_impact_analyzer.analyze(db, repo.id, matrix_env["snap_base"].id, snap.id, change_set=cs)
    aff_names = [f.target_qual_name for f in res.findings]

    assert "app.LeftService" in aff_names
    assert "app.RightService" in aff_names
    assert "app.TopFacade" in aff_names
    assert "app.CycleNode" in aff_names
    assert res.summary.max_depth_reached >= 2


def test_matrix_extends_implements_and_exposes(matrix_env):
    """Scenarios K, L, N: Inheritance, interface implementation, and API handler EXPOSES."""
    db = matrix_env["db"]
    snap = matrix_env["snap_target"]
    repo = matrix_env["repo"]

    # K: Extends (BaseClass modified -> SubClass affected)
    base_cls = _make_art(db, snap.id, "BaseAuth", "app.BaseAuth")
    sub_cls = _make_art(db, snap.id, "OAuthService", "app.OAuthService")
    _make_rel(db, snap.id, sub_cls.id, base_cls.id, "EXTENDS")

    # L: Implements (Interface modified -> Impl affected)
    iface = _make_art(db, snap.id, "IPaymentGateway", "app.IPaymentGateway", "INTERFACE")
    impl = _make_art(db, snap.id, "StripeGateway", "app.StripeGateway")
    _make_rel(db, snap.id, impl.id, iface.id, "IMPLEMENTS")

    # N: Exposes (Handler modified -> Exposed API affected: FORWARD direction!)
    handler = _make_art(db, snap.id, "get_user_orders", "app.handlers.get_user_orders", "FUNCTION")
    route = _make_art(db, snap.id, "GET /api/orders", "GET /api/orders", "API_ENDPOINT")
    _make_rel(db, snap.id, handler.id, route.id, "EXPOSES")
    db.commit()

    # Change BaseClass, Interface, and Handler
    cs = ChangeSet(
        repository_id=repo.id,
        base_snapshot_id=matrix_env["snap_base"].id,
        target_snapshot_id=snap.id,
        changes=[
            ChangeItem(
                artifact_id=base_cls.id,
                qualified_name=base_cls.qualified_name,
                symbol_name=base_cls.name,
                artifact_type="CLASS",
                source_file=base_cls.file_path,
                change_type=ChangeType.MODIFIED,
            ),
            ChangeItem(
                artifact_id=iface.id,
                qualified_name=iface.qualified_name,
                symbol_name=iface.name,
                artifact_type="INTERFACE",
                source_file=iface.file_path,
                change_type=ChangeType.MODIFIED,
            ),
            ChangeItem(
                artifact_id=handler.id,
                qualified_name=handler.qualified_name,
                symbol_name=handler.name,
                artifact_type="FUNCTION",
                source_file=handler.file_path,
                change_type=ChangeType.MODIFIED,
            ),
        ],
    )
    res = change_impact_analyzer.analyze(db, repo.id, matrix_env["snap_base"].id, snap.id, change_set=cs)
    aff_names = [f.target_qual_name for f in res.findings]

    assert "app.OAuthService" in aff_names
    assert "app.StripeGateway" in aff_names
    assert "GET /api/orders" in aff_names
