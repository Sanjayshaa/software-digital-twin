"""
Phase 7 — Risk Intelligence & Architecture Guardrails Comprehensive Test Suite.
Validates all mandatory scenarios:
1. Low-impact change
2. Broad-impact change
3. Deep-impact change
4. High test exposure
5. Unknown test coverage
6. Architecture violation
7. Architecture warning
8. Architecture pass
9. Runtime evidence contribution
10. Incident evidence contribution
11. API exposure
12. Unknown runtime evidence
13. Unknown architecture state
14. Multiple risk factors
15. No evidence / empty repository
16. Cyclic graph safety
17. Multiple changed entities
18. Deterministic repeatability
"""

import uuid
from datetime import datetime
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.entities import (
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    RuntimeEvent,
    Incident,
    AnalysisRun,
    RiskAssessment,
)
from app.services.risk.models import (
    RiskCategory,
    ConfidenceLevel,
    GuardrailStatus,
    GuardrailSeverity,
    GuardrailType,
    RiskFactorType,
    RiskConfig,
    RiskAssessmentResult,
)
from app.services.risk.engine import risk_intelligence_engine
from app.services.risk.service import risk_intelligence_service
from app.services.risk.guardrails import guardrail_evaluator
from main import app

client = TestClient(app)


@pytest.fixture
def risk_test_env(db_session: Session):
    """Sets up a clean project, repository, and baseline + target snapshots."""
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        name=f"Risk Project {suffix}",
        description="Phase 7 Risk Intelligence Test Project",
    )
    db_session.add(project)
    db_session.flush()

    repo = Repository(
        project_id=project.id,
        name=f"risk-repo-{suffix}",
        local_path=f"/tmp/risk_repo_{suffix}",
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
        branch_name="feature/risk",
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
    location: str = "app/file.py:1",
) -> ArtifactRelationship:
    rel_id = f"rel_{uuid.uuid4().hex[:12]}"
    rel = ArtifactRelationship(
        id=rel_id,
        repository_id=repo_id,
        snapshot_id=snapshot_id,
        source_artifact_id=source_id,
        target_artifact_id=target_id,
        relationship_type=rel_type,
        detection_method="ast_visitor",
        source_location=location,
        confidence=1.0,
        metadata_payload={},
    )
    db.add(rel)
    db.flush()
    return rel


def _create_runtime_event(
    db: Session,
    repo_id: str,
    snapshot_id: str,
    artifact_id: str,
    service_name: str = "BillingService",
    environment: str = "production",
    severity: str = "info",
    event_type: str = "http_request",
) -> RuntimeEvent:
    repo = db.query(Repository).filter_by(id=repo_id).first()
    proj_id = repo.project_id if repo else "test-proj"
    ev = RuntimeEvent(
        id=f"ev_{uuid.uuid4().hex[:12]}",
        project_id=proj_id,
        repository_id=repo_id,
        snapshot_id=snapshot_id,
        component_artifact_id=artifact_id,
        service_name=service_name,
        environment=environment,
        severity=severity,
        event_type=event_type,
        message=f"Runtime trace for {service_name}",
        timestamp=datetime.utcnow(),
    )
    db.add(ev)
    db.flush()
    return ev


def _create_incident(
    db: Session,
    repo_id: str,
    snapshot_id: str,
    artifact_id: str,
    title: str = "High Error Rate in Billing",
    severity: str = "critical",
) -> Incident:
    repo = db.query(Repository).filter_by(id=repo_id).first()
    proj_id = repo.project_id if repo else "test-proj"
    inc = Incident(
        id=f"inc_{uuid.uuid4().hex[:12]}",
        project_id=proj_id,
        repository_id=repo_id,
        snapshot_id=snapshot_id,
        affected_component_id=artifact_id,
        title=title,
        severity=severity,
        status="open",
        environment="production",
        detected_at=datetime.utcnow(),
    )
    db.add(inc)
    db.flush()
    return inc


# =========================================================================
# 1. LOW IMPACT CHANGE
# =========================================================================
def test_scenario_01_low_impact_change(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    # Base snapshot
    _create_artifact(db_session, base_id, repo_id, "calc_fee", "billing.calc_fee", "FUNCTION", "billing.py:10", "hash_base")
    _create_artifact(db_session, base_id, repo_id, "test_calc_fee", "tests.test_calc_fee", "TEST_CASE", "tests/test_fee.py:5", "hash_test")
    # Target snapshot (modified)
    fn_target = _create_artifact(db_session, target_id, repo_id, "calc_fee", "billing.calc_fee", "FUNCTION", "billing.py:10", "hash_changed")
    # A single test covers it
    test_target = _create_artifact(db_session, target_id, repo_id, "test_calc_fee", "tests.test_calc_fee", "TEST_CASE", "tests/test_fee.py:5", "hash_test")
    _create_rel(db_session, target_id, repo_id, test_target.id, fn_target.id, "TESTS", "tests/test_fee.py:5")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    assert result.overall_category in (RiskCategory.LOW, RiskCategory.MODERATE)
    assert result.overall_score < 40.0
    f_breadth = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.IMPACT_BREADTH)
    assert f_breadth.details["changed"] == 1
    assert "LOW" in result.explanation or "MODERATE" in result.explanation


# =========================================================================
# 2. BROAD IMPACT CHANGE
# =========================================================================
def test_scenario_02_broad_impact_change(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    # Changed core hub
    _create_artifact(db_session, base_id, repo_id, "CoreConfig", "core.CoreConfig", "CLASS", "core.py:1", "hash_v1")
    hub = _create_artifact(db_session, target_id, repo_id, "CoreConfig", "core.CoreConfig", "CLASS", "core.py:1", "hash_v2")

    # 10 dependent components
    for i in range(10):
        comp = _create_artifact(db_session, target_id, repo_id, f"Comp{i}", f"services.Comp{i}", "CLASS", f"comp{i}.py:1", "hash_v1")
        _create_rel(db_session, target_id, repo_id, comp.id, hub.id, "DEPENDS_ON", f"comp{i}.py:2")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    f_breadth = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.IMPACT_BREADTH)
    assert f_breadth.score >= 70.0
    assert result.overall_category in (RiskCategory.HIGH, RiskCategory.CRITICAL)


# =========================================================================
# 3. DEEP IMPACT CHANGE
# =========================================================================
def test_scenario_03_deep_impact_change(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    _create_artifact(db_session, base_id, repo_id, "NodeA", "app.NodeA", "CLASS", "a.py:1", "hash_1")
    nA = _create_artifact(db_session, target_id, repo_id, "NodeA", "app.NodeA", "CLASS", "a.py:1", "hash_2")
    nB = _create_artifact(db_session, target_id, repo_id, "NodeB", "app.NodeB", "CLASS", "b.py:1", "hash_1")
    nC = _create_artifact(db_session, target_id, repo_id, "NodeC", "app.NodeC", "CLASS", "c.py:1", "hash_1")
    nD = _create_artifact(db_session, target_id, repo_id, "NodeD", "app.NodeD", "CLASS", "d.py:1", "hash_1")

    # D calls C calls B calls A (when A changes, reverse propagation reaches B -> C -> D)
    _create_rel(db_session, target_id, repo_id, nB.id, nA.id, "CALLS", "b.py:5")
    _create_rel(db_session, target_id, repo_id, nC.id, nB.id, "CALLS", "c.py:5")
    _create_rel(db_session, target_id, repo_id, nD.id, nC.id, "CALLS", "d.py:5")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    f_depth = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.IMPACT_DEPTH)
    assert f_depth.details["max_depth"] >= 3
    assert f_depth.score >= 70.0


# =========================================================================
# 4. HIGH TEST EXPOSURE
# =========================================================================
def test_scenario_04_high_test_exposure(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    _create_artifact(db_session, base_id, repo_id, "AuthManager", "auth.AuthManager", "CLASS", "auth.py:1", "hash_1")
    auth = _create_artifact(db_session, target_id, repo_id, "AuthManager", "auth.AuthManager", "CLASS", "auth.py:1", "hash_2")

    for i in range(4):
        test_case = _create_artifact(db_session, target_id, repo_id, f"test_auth_{i}", f"tests.test_auth_{i}", "TEST_CASE", f"tests/test_auth_{i}.py:10", "hash_t")
        _create_rel(db_session, target_id, repo_id, test_case.id, auth.id, "TESTS", f"tests/test_auth_{i}.py:12")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    f_test = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.TEST_IMPACT)
    assert f_test.details["directly_affected"] == 4
    assert len(result.affected_tests) == 4


# =========================================================================
# 5. UNKNOWN TEST COVERAGE
# =========================================================================
def test_scenario_05_unknown_test_coverage(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    # Changed code with NO tests attached
    _create_artifact(db_session, base_id, repo_id, "UntestedWorker", "worker.UntestedWorker", "CLASS", "worker.py:1", "hash_1")
    _create_artifact(db_session, target_id, repo_id, "UntestedWorker", "worker.UntestedWorker", "CLASS", "worker.py:1", "hash_2")

    # Add unrelated test to prove test suite exists
    unrelated = _create_artifact(db_session, target_id, repo_id, "test_other", "tests.test_other", "TEST_CASE", "tests/test_other.py:1", "hash_1")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    f_test = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.TEST_IMPACT)
    assert f_test.details["unknown_coverage"] >= 1
    assert any("lack test coverage" in e or "unknown test coverage" in e for e in f_test.evidence)
    assert any("worker.UntestedWorker" in u for u in result.unknown_evidence)


# =========================================================================
# 6. ARCHITECTURE VIOLATION
# =========================================================================
def test_scenario_06_architecture_violation(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    # Change introduces prohibited import: app.services.discovery -> app.services.analysis (Rule-01)
    _create_artifact(db_session, base_id, repo_id, "Scanner", "app.services.discovery.scanner", "MODULE", "discovery/scanner.py:1", "hash_1")
    disc = _create_artifact(db_session, target_id, repo_id, "Scanner", "app.services.discovery.scanner", "MODULE", "discovery/scanner.py:1", "hash_2")
    anal = _create_artifact(db_session, target_id, repo_id, "Analyzer", "app.services.analysis.engine", "MODULE", "analysis/engine.py:1", "hash_1")

    _create_rel(db_session, target_id, repo_id, disc.id, anal.id, "IMPORTS", "discovery/scanner.py:5")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    violations = [g for g in result.guardrail_results if g.status == GuardrailStatus.VIOLATION]
    assert len(violations) >= 1
    assert any(v.rule_id == "RULE-01" for v in violations)
    f_arch = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.ARCHITECTURE_DRIFT)
    assert f_arch.score >= 80.0
    assert result.overall_category in (RiskCategory.HIGH, RiskCategory.CRITICAL)


# =========================================================================
# 7. ARCHITECTURE WARNING (HIGH COUPLING)
# =========================================================================
def test_scenario_07_architecture_warning(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    _create_artifact(db_session, base_id, repo_id, "ServiceFacade", "facade.ServiceFacade", "CLASS", "facade.py:1", "hash_1")
    facade = _create_artifact(db_session, target_id, repo_id, "ServiceFacade", "facade.ServiceFacade", "CLASS", "facade.py:1", "hash_2")

    # Add 9 dependencies from ServiceFacade
    for i in range(9):
        tgt = _create_artifact(db_session, target_id, repo_id, f"Target{i}", f"services.Target{i}", "CLASS", f"tgt{i}.py:1", "hash_1")
        _create_rel(db_session, target_id, repo_id, facade.id, tgt.id, "CALLS", f"facade.py:{10+i}")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    coupling_guard = next((g for g in result.guardrail_results if g.guardrail_type == GuardrailType.UNEXPECTED_COUPLING), None)
    assert coupling_guard is not None
    assert coupling_guard.status == GuardrailStatus.WARN


# =========================================================================
# 8. ARCHITECTURE PASS
# =========================================================================
def test_scenario_08_architecture_pass(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    _create_artifact(db_session, base_id, repo_id, "HealthRouter", "app.api.health", "MODULE", "api/health.py:1", "hash_1")
    _create_artifact(db_session, target_id, repo_id, "HealthRouter", "app.api.health", "MODULE", "api/health.py:1", "hash_2")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    violations = [g for g in result.guardrail_results if g.status == GuardrailStatus.VIOLATION]
    assert len(violations) == 0
    f_arch = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.ARCHITECTURE_DRIFT)
    assert f_arch.score == 0.0


# =========================================================================
# 9. RUNTIME EVIDENCE CONTRIBUTION
# =========================================================================
def test_scenario_09_runtime_evidence_contribution(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    _create_artifact(db_session, base_id, repo_id, "PaymentGateway", "payments.PaymentGateway", "CLASS", "gateway.py:1", "hash_1")
    gw = _create_artifact(db_session, target_id, repo_id, "PaymentGateway", "payments.PaymentGateway", "CLASS", "gateway.py:1", "hash_2")

    # Ingest production runtime events
    _create_runtime_event(db_session, repo_id, target_id, gw.id, "PaymentGateway", "production", "error", "auth_failed")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    f_runtime = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.RUNTIME_ACTIVITY)
    assert f_runtime.status == "OBSERVED"
    assert f_runtime.score >= 70.0
    assert len(result.runtime_evidence) >= 1
    assert "production" in result.runtime_evidence[0]


# =========================================================================
# 10. INCIDENT EVIDENCE CONTRIBUTION
# =========================================================================
def test_scenario_10_incident_evidence_contribution(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    _create_artifact(db_session, base_id, repo_id, "LedgerService", "ledger.LedgerService", "CLASS", "ledger.py:1", "hash_1")
    ledger = _create_artifact(db_session, target_id, repo_id, "LedgerService", "ledger.LedgerService", "CLASS", "ledger.py:1", "hash_2")

    # Link historical incident
    _create_incident(db_session, repo_id, target_id, ledger.id, "Ledger desync outage", "critical")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    f_inc = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.INCIDENT_HISTORY)
    assert f_inc.status == "OBSERVED"
    assert f_inc.score >= 80.0
    assert len(result.incident_evidence) >= 1
    assert "Ledger desync outage" in result.incident_evidence[0]


# =========================================================================
# 11. API EXPOSURE
# =========================================================================
def test_scenario_11_api_exposure(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    _create_artifact(db_session, base_id, repo_id, "post_checkout", "api.v1.post_checkout", "API_ENDPOINT", "api/v1/checkout.py:10", "hash_1")
    _create_artifact(db_session, target_id, repo_id, "post_checkout", "api.v1.post_checkout", "API_ENDPOINT", "api/v1/checkout.py:10", "hash_2")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    f_api = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.API_SURFACE)
    assert f_api.score >= 80.0
    assert len(result.affected_apis) >= 1
    assert "post_checkout" in result.affected_apis[0]


# =========================================================================
# 12. UNKNOWN RUNTIME EVIDENCE
# =========================================================================
def test_scenario_12_unknown_runtime_evidence(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    _create_artifact(db_session, base_id, repo_id, "Foo", "foo.Foo", "CLASS", "foo.py:1", "hash_1")
    _create_artifact(db_session, target_id, repo_id, "Foo", "foo.Foo", "CLASS", "foo.py:1", "hash_2")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    f_runtime = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.RUNTIME_ACTIVITY)
    assert f_runtime.status == "UNKNOWN"
    assert "unavailable" in f_runtime.evidence[0].lower()


# =========================================================================
# 13. UNKNOWN ARCHITECTURE STATE
# =========================================================================
def test_scenario_13_unknown_architecture_state(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    _create_artifact(db_session, base_id, repo_id, "Bar", "bar.Bar", "CLASS", "bar.py:1", "hash_1")
    _create_artifact(db_session, target_id, repo_id, "Bar", "bar.Bar", "CLASS", "bar.py:1", "hash_2")

    cfg = RiskConfig(baseline_path="/non/existent/path/baseline.yaml")
    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
        config=cfg,
    )

    f_arch = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.ARCHITECTURE_DRIFT)
    assert f_arch.status == "UNKNOWN"
    assert any(g.status == GuardrailStatus.UNKNOWN for g in result.guardrail_results)


# =========================================================================
# 14. MULTIPLE RISK FACTORS
# =========================================================================
def test_scenario_14_multiple_risk_factors(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    # Changed API component
    _create_artifact(db_session, base_id, repo_id, "OrderAPI", "api.OrderAPI", "API_ENDPOINT", "api/orders.py:1", "hash_1")
    api = _create_artifact(db_session, target_id, repo_id, "OrderAPI", "api.OrderAPI", "API_ENDPOINT", "api/orders.py:1", "hash_2")

    # Dependent component
    svc = _create_artifact(db_session, target_id, repo_id, "OrderService", "services.OrderService", "CLASS", "services/order.py:1", "hash_1")
    _create_rel(db_session, target_id, repo_id, svc.id, api.id, "CALLS", "services/order.py:10")

    # Production runtime events
    _create_runtime_event(db_session, repo_id, target_id, api.id, "OrderAPI", "production", "info")

    # Tests
    t1 = _create_artifact(db_session, target_id, repo_id, "test_order", "tests.test_order", "TEST_CASE", "tests/test_order.py:1", "hash_t")
    _create_rel(db_session, target_id, repo_id, t1.id, api.id, "TESTS", "tests/test_order.py:5")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    assert result.overall_category in (RiskCategory.HIGH, RiskCategory.MODERATE)
    assert len(result.recommendations) >= 1
    assert "OrderAPI" in result.affected_components or "OrderAPI" in str(result.affected_apis)


# =========================================================================
# 15. NO EVIDENCE / EMPTY REPOSITORY
# =========================================================================
def test_scenario_15_no_evidence_identical_snapshots(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    # Same hash = zero changes
    _create_artifact(db_session, base_id, repo_id, "Same", "same.Same", "CLASS", "same.py:1", "hash_same")
    _create_artifact(db_session, target_id, repo_id, "Same", "same.Same", "CLASS", "same.py:1", "hash_same")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    assert result.overall_category == RiskCategory.LOW
    assert result.overall_score == 0.0
    assert len(result.affected_components) == 0


# =========================================================================
# 16. CYCLIC GRAPH SAFETY
# =========================================================================
def test_scenario_16_cyclic_graph(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    _create_artifact(db_session, base_id, repo_id, "CycleA", "cycle.CycleA", "CLASS", "a.py:1", "hash_1")
    cA = _create_artifact(db_session, target_id, repo_id, "CycleA", "cycle.CycleA", "CLASS", "a.py:1", "hash_2")
    cB = _create_artifact(db_session, target_id, repo_id, "CycleB", "cycle.CycleB", "CLASS", "b.py:1", "hash_1")

    # A -> B -> A cycle
    _create_rel(db_session, target_id, repo_id, cA.id, cB.id, "CALLS", "a.py:5")
    _create_rel(db_session, target_id, repo_id, cB.id, cA.id, "CALLS", "b.py:5")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    # Engine must terminate cleanly without infinite recursion
    assert result.status == "completed"
    cycle_guard = next((g for g in result.guardrail_results if g.guardrail_type == GuardrailType.CIRCULAR_DEPENDENCY), None)
    assert cycle_guard is not None
    assert cycle_guard.status == GuardrailStatus.VIOLATION
    assert cycle_guard.severity == GuardrailSeverity.CRITICAL


# =========================================================================
# 17. MULTIPLE CHANGED ENTITIES
# =========================================================================
def test_scenario_17_multiple_changed_entities(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    # 3 distinct changed entities
    for i in range(3):
        _create_artifact(db_session, base_id, repo_id, f"Service{i}", f"app.Service{i}", "CLASS", f"s{i}.py:1", "hash_1")
        _create_artifact(db_session, target_id, repo_id, f"Service{i}", f"app.Service{i}", "CLASS", f"s{i}.py:1", "hash_2")

    result = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    f_breadth = next(f for f in result.risk_factors if f.factor_id == RiskFactorType.IMPACT_BREADTH)
    assert f_breadth.details["changed"] == 3


# =========================================================================
# 18. DETERMINISTIC REPEATABILITY
# =========================================================================
def test_scenario_18_deterministic_repeatability(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    _create_artifact(db_session, base_id, repo_id, "DetA", "det.DetA", "CLASS", "det.py:1", "hash_1")
    _create_artifact(db_session, target_id, repo_id, "DetA", "det.DetA", "CLASS", "det.py:1", "hash_2")

    run_1 = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )
    run_2 = risk_intelligence_engine.assess_risk(
        db=db_session,
        repository_id=repo_id,
        base_snapshot_id=base_id,
        target_snapshot_id=target_id,
    )

    assert run_1.overall_score == run_2.overall_score
    assert run_1.overall_category == run_2.overall_category
    assert run_1.confidence_score == run_2.confidence_score
    assert run_1.explanation == run_2.explanation
    assert len(run_1.risk_factors) == len(run_2.risk_factors)
    for f1, f2 in zip(run_1.risk_factors, run_2.risk_factors):
        assert f1.score == f2.score
        assert f1.severity == f2.severity
        assert f1.status == f2.status


# =========================================================================
# API ENDPOINTS & SERVICE PERSISTENCE TESTS
# =========================================================================
def test_risk_service_and_api_endpoints(db_session: Session, risk_test_env: dict):
    repo_id = risk_test_env["repo"].id
    base_id = risk_test_env["snap_base"].id
    target_id = risk_test_env["snap_target"].id

    _create_artifact(db_session, base_id, repo_id, "ApiItem", "api.ApiItem", "CLASS", "item.py:1", "hash_1")
    _create_artifact(db_session, target_id, repo_id, "ApiItem", "api.ApiItem", "CLASS", "item.py:1", "hash_2")
    db_session.commit()

    # Test POST /repositories/{id}/risk-analysis
    payload = {
        "target_snapshot_id": target_id,
        "base_snapshot_id": base_id,
        "max_depth": 5,
        "environment": "production",
    }
    resp = client.post(f"/repositories/{repo_id}/risk-analysis", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "analysis_id" in data
    assert "overall_category" in data
    assert "risk_factors" in data
    analysis_id = data["analysis_id"]

    # Verify database persistence in AnalysisRun and RiskAssessment
    run_rec = db_session.query(AnalysisRun).filter_by(id=analysis_id).first()
    assert run_rec is not None
    assert run_rec.run_type == "risk_analysis"
    ra_rec = db_session.query(RiskAssessment).filter_by(analysis_run_id=analysis_id).first()
    assert ra_rec is not None

    # Test GET /repositories/{id}/risk-analysis/{analysis_id}
    get_resp = client.get(f"/repositories/{repo_id}/risk-analysis/{analysis_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["analysis_id"] == analysis_id

    # Test GET /repositories/{id}/architecture/guardrails
    guard_resp = client.get(f"/repositories/{repo_id}/architecture/guardrails?snapshot_id={target_id}")
    assert guard_resp.status_code == 200
    g_data = guard_resp.json()
    assert "guardrails" in g_data
    assert "violations_count" in g_data

    # Test 404 on non-existent repo
    bad_resp = client.post("/repositories/bad-repo-id/risk-analysis", json=payload)
    assert bad_resp.status_code == 404
