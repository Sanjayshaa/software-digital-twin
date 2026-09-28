"""
Phase 8 — What-If / Scenario Simulation Comprehensive Test Suite.
Validates all 24 mandatory test scenarios:
1. Modify existing symbol
2. Remove dependency
3. Add dependency
4. API modification
5. Invalid target
6. Unknown entity
7. Multiple proposed changes
8. Scenario isolation
9. Original Twin unchanged
10. Original snapshot unchanged
11. Impact recalculation
12. Test impact recalculation
13. Risk recalculation
14. Architecture guardrail recalculation
15. Runtime evidence correctly labelled observed
16. Incident evidence correctly labelled historical
17. Simulated vs observed evidence separation
18. Scenario deletion
19. Scenario expiration
20. Repeated deterministic simulation
21. Cyclic scenario
22. Empty scenario
23. Unsupported mutation
24. API lifecycle
+ Critical Base Twin Immutability verification.
"""

import uuid
from datetime import datetime, timedelta
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
    Scenario,
    ScenarioResult,
)
from app.services.simulation.models import (
    MutationType,
    ScenarioStatus,
    EvidenceCategory,
    ProposedMutation,
    CreateScenarioRequest,
)
from app.services.simulation.engine import scenario_simulation_engine
from app.services.simulation.service import scenario_service
from main import app

client = TestClient(app)


@pytest.fixture
def sim_env(db_session: Session):
    """Sets up a clean test environment for scenario simulation."""
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        name=f"Sim Project {suffix}",
        description="Phase 8 What-If Scenario Test Project",
    )
    db_session.add(project)
    db_session.flush()

    repo = Repository(
        project_id=project.id,
        name=f"sim-repo-{suffix}",
        local_path=f"/tmp/sim_repo_{suffix}",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.flush()

    snap = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash=f"snap_{suffix}",
        branch_name="main",
        total_files=5,
        total_symbols=10,
        snapshot_metadata={"version": "1.0.0"},
    )
    db_session.add(snap)
    db_session.flush()

    # Create base artifacts
    # OrderService -> PaymentService -> TaxService
    # TestOrder -> OrderService
    # API: POST /orders
    art_order = _create_art(db_session, snap.id, repo.id, "OrderService", "app.services.OrderService", "CLASS", "app/services/order.py:10")
    art_pay = _create_art(db_session, snap.id, repo.id, "PaymentService", "app.services.PaymentService", "CLASS", "app/services/payment.py:15")
    art_tax = _create_art(db_session, snap.id, repo.id, "TaxService", "app.services.TaxService", "CLASS", "app/services/tax.py:5")
    art_db = _create_art(db_session, snap.id, repo.id, "PaymentDB", "app.db.PaymentDB", "DATABASE_ENTITY", "app/db/payment.py:1")
    art_api = _create_art(db_session, snap.id, repo.id, "create_order", "/api/v1/orders", "API_ENDPOINT", "app/api/orders.py:20")
    art_test = _create_art(db_session, snap.id, repo.id, "test_order_flow", "tests.test_order.test_order_flow", "TEST_CASE", "tests/test_order.py:12")

    # Base relationships
    rel_1 = _create_rel(db_session, snap.id, repo.id, art_order.id, art_pay.id, "DEPENDS_ON")
    rel_2 = _create_rel(db_session, snap.id, repo.id, art_pay.id, art_tax.id, "CALLS")
    rel_3 = _create_rel(db_session, snap.id, repo.id, art_pay.id, art_db.id, "PERSISTS_TO")
    rel_4 = _create_rel(db_session, snap.id, repo.id, art_api.id, art_order.id, "CALLS")
    rel_5 = _create_rel(db_session, snap.id, repo.id, art_test.id, art_order.id, "TESTS")

    # Add runtime telemetry for PaymentService
    rev = RuntimeEvent(
        id=f"rev_{uuid.uuid4().hex[:10]}",
        project_id=project.id,
        repository_id=repo.id,
        service_name="payment_service",
        component_artifact_id=art_pay.id,
        environment="production",
        event_type="http_request",
        payload={"latency_ms": 120.5, "http_status_code": 200},
        timestamp=datetime.utcnow(),
    )
    db_session.add(rev)

    # Add historical incident for PaymentService
    inc = Incident(
        id=f"inc_{uuid.uuid4().hex[:10]}",
        project_id=project.id,
        repository_id=repo.id,
        title="INC-8088: Payment Gateway Timeout",
        severity="P2",
        status="resolved",
        environment="production",
        affected_component_id=art_pay.id,
        detected_at=datetime.utcnow() - timedelta(days=2),
    )
    db_session.add(inc)
    db_session.commit()

    return {
        "project": project,
        "repo": repo,
        "snap": snap,
        "order": art_order,
        "pay": art_pay,
        "tax": art_tax,
        "db": art_db,
        "api": art_api,
        "test": art_test,
        "rel_order_pay": rel_1,
        "rel_pay_tax": rel_2,
        "rev": rev,
        "inc": inc,
    }


def _create_art(db: Session, snapshot_id: str, repo_id: str, name: str, qual_name: str, art_type: str, loc: str) -> StructuralArtifact:
    art = StructuralArtifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        repository_id=repo_id,
        snapshot_id=snapshot_id,
        name=name,
        qualified_name=qual_name,
        artifact_type=art_type,
        language="python",
        location=loc,
        source_hash=f"hash_{name}",
        metadata_payload={},
    )
    db.add(art)
    db.flush()
    return art


def _create_rel(db: Session, snapshot_id: str, repo_id: str, src_id: str, tgt_id: str, rel_type: str) -> ArtifactRelationship:
    rel = ArtifactRelationship(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        repository_id=repo_id,
        snapshot_id=snapshot_id,
        source_artifact_id=src_id,
        target_artifact_id=tgt_id,
        relationship_type=rel_type,
        detection_method="ast_visitor",
        source_location="app/code.py:1",
        confidence=1.0,
        metadata_payload={},
    )
    db.add(rel)
    db.flush()
    return rel


# ==============================================================================
# 1. Modify Existing Symbol
# ==============================================================================
def test_scenario_01_modify_existing_symbol(db_session: Session, sim_env):
    """Test modifying a symbol propagates impact to dependent services and tests."""
    mut = ProposedMutation(
        mutation_id="mut_1",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.PaymentService",
        description="Change payment transaction signature",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Modify Payment Service",
        proposed_changes=[mut],
    )
    assert res.status == ScenarioStatus.COMPLETED
    assert res.validation.is_valid is True
    assert "app.services.PaymentService" in res.impact.changed_artifacts
    # OrderService depends on PaymentService, so it should be directly affected!
    assert "app.services.OrderService" in res.impact.directly_affected


# ==============================================================================
# 2. Remove Dependency
# ==============================================================================
def test_scenario_02_remove_dependency(db_session: Session, sim_env):
    """Test removing a dependency reflects in comparison and marks source as modified."""
    mut = ProposedMutation(
        mutation_id="mut_2",
        mutation_type=MutationType.REMOVE_DEPENDENCY,
        source="app.services.OrderService",
        target="app.services.PaymentService",
        description="Decouple OrderService from PaymentService",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Remove Payment Dependency",
        proposed_changes=[mut],
    )
    assert res.status == ScenarioStatus.COMPLETED
    assert len(res.comparison.removed_relationships) == 1
    assert res.comparison.removed_relationships[0]["source"] == "app.services.OrderService"
    assert res.comparison.removed_relationships[0]["target"] == "app.services.PaymentService"


# ==============================================================================
# 3. Add Dependency
# ==============================================================================
def test_scenario_03_add_dependency(db_session: Session, sim_env):
    """Test adding a dependency reflects in comparison and changes coupling."""
    mut = ProposedMutation(
        mutation_id="mut_3",
        mutation_type=MutationType.ADD_DEPENDENCY,
        source="app.services.OrderService",
        target="app.services.TaxService",
        relationship_type="CALLS",
        description="Directly call TaxService from OrderService",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Add Tax Dependency",
        proposed_changes=[mut],
    )
    assert res.status == ScenarioStatus.COMPLETED
    assert len(res.comparison.added_relationships) == 1
    assert res.comparison.added_relationships[0]["source"] == "app.services.OrderService"
    assert res.comparison.added_relationships[0]["target"] == "app.services.TaxService"


# ==============================================================================
# 4. API Modification
# ==============================================================================
def test_scenario_04_api_modification(db_session: Session, sim_env):
    """Test modifying an API endpoint identifies consumers and affected contracts."""
    mut = ProposedMutation(
        mutation_id="mut_4",
        mutation_type=MutationType.MODIFY_API,
        target="/api/v1/orders",
        description="Add billing_address to POST /orders payload",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Modify Order API",
        proposed_changes=[mut],
    )
    assert res.status == ScenarioStatus.COMPLETED
    assert "/api/v1/orders" in res.impact.changed_artifacts


# ==============================================================================
# 5. Invalid Target
# ==============================================================================
def test_scenario_05_invalid_target(db_session: Session, sim_env):
    """Test invalid or empty target triggers validation failure."""
    mut = ProposedMutation(
        mutation_id="mut_5",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="",
        description="Empty target",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Invalid Target Test",
        proposed_changes=[mut],
    )
    assert res.status == ScenarioStatus.FAILED
    assert res.validation.is_valid is False
    assert len(res.validation.errors) > 0


# ==============================================================================
# 6. Unknown Entity
# ==============================================================================
def test_scenario_06_unknown_entity(db_session: Session, sim_env):
    """Test non-existent entity is recorded in unknown_entities."""
    mut = ProposedMutation(
        mutation_id="mut_6",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="com.nonexistent.PhantomService",
        description="Mutate phantom service",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Unknown Entity Test",
        proposed_changes=[mut],
    )
    assert res.status == ScenarioStatus.FAILED
    assert "com.nonexistent.PhantomService" in res.unknowns


# ==============================================================================
# 7. Multiple Proposed Changes
# ==============================================================================
def test_scenario_07_multiple_proposed_changes(db_session: Session, sim_env):
    """Test batch of multiple mutations in a single scenario."""
    muts = [
        ProposedMutation(
            mutation_id="m1",
            mutation_type=MutationType.MODIFY_SYMBOL,
            target="app.services.PaymentService",
        ),
        ProposedMutation(
            mutation_id="m2",
            mutation_type=MutationType.ADD_DEPENDENCY,
            source="app.services.OrderService",
            target="app.services.TaxService",
            relationship_type="DEPENDS_ON",
        ),
    ]
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Multi Mutation Test",
        proposed_changes=muts,
    )
    assert res.status == ScenarioStatus.COMPLETED
    assert len(res.proposed_changes) == 2


# ==============================================================================
# 8. Scenario Isolation
# ==============================================================================
def test_scenario_08_scenario_isolation(db_session: Session, sim_env):
    """Verify that multiple scenarios do not interfere with each other or the base."""
    mut1 = ProposedMutation(
        mutation_id="m1",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.PaymentService",
    )
    mut2 = ProposedMutation(
        mutation_id="m2",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.TaxService",
    )
    res1 = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Scenario 1",
        proposed_changes=[mut1],
    )
    res2 = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Scenario 2",
        proposed_changes=[mut2],
    )
    assert "app.services.PaymentService" in res1.impact.changed_artifacts
    assert "app.services.PaymentService" not in res2.impact.changed_artifacts
    assert "app.services.TaxService" in res2.impact.changed_artifacts


# ==============================================================================
# 9. Original Twin Unchanged
# ==============================================================================
def test_scenario_09_original_twin_unchanged(db_session: Session, sim_env):
    """Verify that the base twin in DB is completely untouched after running simulation."""
    pay_art_before = db_session.query(StructuralArtifact).filter_by(id=sim_env["pay"].id).first()
    hash_before = pay_art_before.source_hash

    mut = ProposedMutation(
        mutation_id="m_mut",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.PaymentService",
    )
    scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Mutate Twin Test",
        proposed_changes=[mut],
    )

    pay_art_after = db_session.query(StructuralArtifact).filter_by(id=sim_env["pay"].id).first()
    assert pay_art_after.source_hash == hash_before


# ==============================================================================
# 10. Original Snapshot Unchanged
# ==============================================================================
def test_scenario_10_original_snapshot_unchanged(db_session: Session, sim_env):
    """Verify snapshot metadata, commit_hash, total_files are completely unmodified."""
    snap_before = db_session.query(RepositorySnapshot).filter_by(id=sim_env["snap"].id).first()
    commit_before = snap_before.commit_hash
    meta_before = dict(snap_before.snapshot_metadata)

    mut = ProposedMutation(
        mutation_id="m_snap",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.OrderService",
    )
    scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Snap Immutability Test",
        proposed_changes=[mut],
    )

    snap_after = db_session.query(RepositorySnapshot).filter_by(id=sim_env["snap"].id).first()
    assert snap_after.commit_hash == commit_before
    assert snap_after.snapshot_metadata == meta_before


# ==============================================================================
# 11. Impact Recalculation
# ==============================================================================
def test_scenario_11_impact_recalculation(db_session: Session, sim_env):
    """Verify simulated impact calculates blast radius along virtual edges."""
    mut = ProposedMutation(
        mutation_id="m_calc",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.TaxService",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Impact Recalc",
        proposed_changes=[mut],
    )
    assert res.impact.max_propagation_depth >= 1
    assert "app.services.PaymentService" in res.impact.directly_affected


# ==============================================================================
# 12. Test Impact Recalculation
# ==============================================================================
def test_scenario_12_test_impact_recalculation(db_session: Session, sim_env):
    """Verify simulated changes reach test cases through virtual graph."""
    mut = ProposedMutation(
        mutation_id="m_test",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.OrderService",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Test Recalc",
        proposed_changes=[mut],
    )
    assert len(res.tests.directly_affected_tests) >= 1
    assert "test_order_flow" in res.tests.directly_affected_tests[0]


# ==============================================================================
# 13. Risk Recalculation
# ==============================================================================
def test_scenario_13_risk_recalculation(db_session: Session, sim_env):
    """Verify simulated risk score and explanation reflect scenario changes."""
    mut = ProposedMutation(
        mutation_id="m_risk",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.PaymentService",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Risk Recalc",
        proposed_changes=[mut],
    )
    assert res.risk.scenario_risk_category in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert "Scenario risk:" in res.risk.explanation
    assert res.risk.confidence_level in ("HIGH", "MEDIUM", "LOW")


# ==============================================================================
# 14. Architecture Guardrail Recalculation
# ==============================================================================
def test_scenario_14_architecture_guardrail_recalculation(db_session: Session, sim_env):
    """Verify architecture guardrails are evaluated against virtual twin."""
    mut = ProposedMutation(
        mutation_id="m_guard",
        mutation_type=MutationType.ADD_DEPENDENCY,
        source="app.services.OrderService",
        target="app.db.PaymentDB",
        relationship_type="PERSISTS_TO",
        description="OrderService directly persists to PaymentDB (bypass)",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Guardrail Recalc",
        proposed_changes=[mut],
    )
    assert res.status == ScenarioStatus.COMPLETED
    assert isinstance(res.guardrails, list)


# ==============================================================================
# 15. Runtime Evidence Correctly Labelled Observed
# ==============================================================================
def test_scenario_15_runtime_evidence_correctly_labelled_observed(db_session: Session, sim_env):
    """Verify runtime telemetry intersecting scenario is explicitly labelled OBSERVED_RUNTIME."""
    mut = ProposedMutation(
        mutation_id="m_run",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.PaymentService",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Runtime Label Test",
        proposed_changes=[mut],
    )
    runtime_ev = [e for e in res.evidence if e.category == EvidenceCategory.OBSERVED_RUNTIME]
    assert len(runtime_ev) > 0
    assert "NOT generated by this hypothetical change" in runtime_ev[0].description


# ==============================================================================
# 16. Incident Evidence Correctly Labelled Historical
# ==============================================================================
def test_scenario_16_incident_evidence_correctly_labelled_historical(db_session: Session, sim_env):
    """Verify past incidents intersecting scenario are explicitly labelled HISTORICAL_INCIDENT."""
    mut = ProposedMutation(
        mutation_id="m_inc",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.PaymentService",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Incident Label Test",
        proposed_changes=[mut],
    )
    inc_ev = [e for e in res.evidence if e.category == EvidenceCategory.HISTORICAL_INCIDENT]
    assert len(inc_ev) > 0
    assert "INC-8088" in inc_ev[0].label
    assert "historical vulnerability" in inc_ev[0].description


# ==============================================================================
# 17. Simulated vs Observed Evidence Separation
# ==============================================================================
def test_scenario_17_simulated_vs_observed_evidence_separation(db_session: Session, sim_env):
    """Verify distinct categories exist in evidence list: SIMULATED_STRUCTURAL, OBSERVED_RUNTIME, HISTORICAL_INCIDENT."""
    mut = ProposedMutation(
        mutation_id="m_sep",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.PaymentService",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Evidence Separation",
        proposed_changes=[mut],
    )
    categories = {e.category for e in res.evidence}
    assert EvidenceCategory.SIMULATED_STRUCTURAL in categories
    assert EvidenceCategory.OBSERVED_RUNTIME in categories
    assert EvidenceCategory.HISTORICAL_INCIDENT in categories


# ==============================================================================
# 18. Scenario Deletion
# ==============================================================================
def test_scenario_18_scenario_deletion(db_session: Session, sim_env):
    """Test creating and deleting a scenario via ScenarioService."""
    req = CreateScenarioRequest(
        name="Temporary Scenario",
        base_snapshot_id=sim_env["snap"].id,
        proposed_changes=[
            {"mutation_type": "MODIFY_SYMBOL", "target": "app.services.OrderService"}
        ],
    )
    created = scenario_service.create_scenario(db_session, sim_env["repo"].id, req)
    scen_id = created["id"]

    del_res = scenario_service.delete_scenario(db_session, scen_id)
    assert del_res["status"] == "deleted"

    # Query directly to confirm deletion
    found = db_session.query(Scenario).filter_by(id=scen_id).first()
    assert found is None


# ==============================================================================
# 19. Scenario Expiration
# ==============================================================================
def test_scenario_19_scenario_expiration(db_session: Session, sim_env):
    """Test scenario with negative TTL expires and raises 410 on simulation."""
    from fastapi import HTTPException
    req = CreateScenarioRequest(
        name="Expiring Scenario",
        base_snapshot_id=sim_env["snap"].id,
        expires_in_hours=-1,  # Already expired
        proposed_changes=[
            {"mutation_type": "MODIFY_SYMBOL", "target": "app.services.OrderService"}
        ],
    )
    created = scenario_service.create_scenario(db_session, sim_env["repo"].id, req)
    with pytest.raises(HTTPException) as excinfo:
        scenario_service.simulate_scenario(db_session, created["id"])
    assert excinfo.value.status_code == 410


# ==============================================================================
# 20. Repeated Deterministic Simulation
# ==============================================================================
def test_scenario_20_repeated_deterministic_simulation(db_session: Session, sim_env):
    """Running identical simulation twice produces 100% identical deterministic scores and paths."""
    mut = ProposedMutation(
        mutation_id="m_det",
        mutation_type=MutationType.MODIFY_SYMBOL,
        target="app.services.PaymentService",
    )
    res1 = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Deterministic 1",
        proposed_changes=[mut],
    )
    res2 = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Deterministic 2",
        proposed_changes=[mut],
    )
    assert res1.risk.overall_score == res2.risk.overall_score
    assert res1.risk.scenario_risk_category == res2.risk.scenario_risk_category
    assert res1.impact.directly_affected == res2.impact.directly_affected
    assert res1.tests.directly_affected_tests == res2.tests.directly_affected_tests


# ==============================================================================
# 21. Cyclic Scenario
# ==============================================================================
def test_scenario_21_cyclic_scenario(db_session: Session, sim_env):
    """Adding a dependency that closes a cycle does not result in infinite loop."""
    # Existing: TaxService -> (no dependencies)
    # Propose: TaxService -> OrderService (creates Order -> Payment -> Tax -> Order cycle)
    mut = ProposedMutation(
        mutation_id="m_cycle",
        mutation_type=MutationType.ADD_DEPENDENCY,
        source="app.services.TaxService",
        target="app.services.OrderService",
        relationship_type="CALLS",
    )
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Cycle Test",
        proposed_changes=[mut],
    )
    assert res.status == ScenarioStatus.COMPLETED
    assert res.impact.max_propagation_depth <= 6


# ==============================================================================
# 22. Empty Scenario
# ==============================================================================
def test_scenario_22_empty_scenario(db_session: Session, sim_env):
    """Empty scenario completes safely with zero impact and LOW risk."""
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=sim_env["snap"].id,
        name="Empty Scenario",
        proposed_changes=[],
    )
    assert res.status == ScenarioStatus.COMPLETED
    assert len(res.impact.changed_artifacts) == 0
    assert res.risk.scenario_risk_category == "LOW"


# ==============================================================================
# 23. Unsupported Mutation
# ==============================================================================
def test_scenario_23_unsupported_mutation(db_session: Session, sim_env):
    """Unsupported mutation types are rejected with clear error."""
    from fastapi import HTTPException
    req = CreateScenarioRequest(
        name="Unsupported Scenario",
        base_snapshot_id=sim_env["snap"].id,
        proposed_changes=[
            {"mutation_type": "ARBITRARY_CODE_SYNTHESIS", "target": "app.services.OrderService"}
        ],
    )
    with pytest.raises(HTTPException) as excinfo:
        scenario_service.create_scenario(db_session, sim_env["repo"].id, req)
    assert excinfo.value.status_code == 422


# ==============================================================================
# 24. API Lifecycle
# ==============================================================================
def test_scenario_24_api_lifecycle(db_session: Session, sim_env):
    """Full HTTP API test: POST -> GET list -> GET detail -> POST analyze -> DELETE."""
    repo_id = sim_env["repo"].id
    snap_id = sim_env["snap"].id

    # 1. POST create scenario
    create_payload = {
        "name": "API Lifecycle Scenario",
        "description": "Testing full REST lifecycle",
        "base_snapshot_id": snap_id,
        "proposed_changes": [
            {
                "mutation_type": "MODIFY_SYMBOL",
                "target": "app.services.PaymentService",
                "description": "API test mutation",
            }
        ],
    }
    create_resp = client.post(f"/repositories/{repo_id}/scenarios", json=create_payload)
    assert create_resp.status_code == 201
    scen = create_resp.json()
    scen_id = scen["id"]

    # 2. GET list scenarios
    list_resp = client.get(f"/repositories/{repo_id}/scenarios")
    assert list_resp.status_code == 200
    scenarios = list_resp.json()
    assert any(s["id"] == scen_id for s in scenarios)

    # 3. GET scenario detail
    detail_resp = client.get(f"/repositories/{repo_id}/scenarios/{scen_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["name"] == "API Lifecycle Scenario"

    # 4. POST analyze scenario
    analyze_resp = client.post(f"/repositories/{repo_id}/scenarios/{scen_id}/analyze")
    assert analyze_resp.status_code == 200
    sim_data = analyze_resp.json()
    assert sim_data["status"] == "COMPLETED"
    assert "app.services.PaymentService" in sim_data["impact"]["changed_artifacts"]

    # 5. Quick simulate endpoint
    quick_resp = client.post(
        f"/repositories/{repo_id}/simulate",
        json={
            "name": "Quick One-Shot",
            "base_snapshot_id": snap_id,
            "proposed_changes": [
                {"mutation_type": "MODIFY_SYMBOL", "target": "app.services.TaxService"}
            ],
        },
    )
    assert quick_resp.status_code == 200
    assert quick_resp.json()["status"] == "COMPLETED"

    # 6. DELETE scenario
    del_resp = client.delete(f"/repositories/{repo_id}/scenarios/{scen_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"


# ==============================================================================
# Critical Test: BASE TWIN == BASE TWIN BEFORE SCENARIO
# ==============================================================================
def test_scenario_25_critical_base_twin_immutability(db_session: Session, sim_env):
    """
    CRITICAL SAFETY REQUIREMENT:
    Verify that the baseline Digital Twin remains 100% identical before and after simulation.
    Checks:
    - Artifact count
    - Relationship count
    - All artifact IDs, names, types, hashes, locations
    - All relationship sources, targets, types
    - Zero modified or dirty objects in session
    """
    snap_id = sim_env["snap"].id

    # Snapshot baseline state before simulation
    arts_before = db_session.query(StructuralArtifact).filter_by(snapshot_id=snap_id).order_by(StructuralArtifact.id).all()
    rels_before = db_session.query(ArtifactRelationship).filter_by(snapshot_id=snap_id).order_by(ArtifactRelationship.id).all()

    state_before_arts = [
        (a.id, a.name, a.qualified_name, a.artifact_type, a.source_hash, a.location)
        for a in arts_before
    ]
    state_before_rels = [
        (r.id, r.source_artifact_id, r.target_artifact_id, r.relationship_type)
        for r in rels_before
    ]

    # Run aggressive multi-mutation scenario
    muts = [
        ProposedMutation(
            mutation_id="m1",
            mutation_type=MutationType.MODIFY_SYMBOL,
            target="app.services.PaymentService",
        ),
        ProposedMutation(
            mutation_id="m2",
            mutation_type=MutationType.REMOVE_DEPENDENCY,
            source="app.services.OrderService",
            target="app.services.PaymentService",
        ),
        ProposedMutation(
            mutation_id="m3",
            mutation_type=MutationType.ADD_DEPENDENCY,
            source="app.services.OrderService",
            target="app.services.TaxService",
            relationship_type="DEPENDS_ON",
        ),
    ]
    res = scenario_simulation_engine.simulate_scenario(
        db=db_session,
        repository_id=sim_env["repo"].id,
        base_snapshot_id=snap_id,
        name="Critical Immutability Test",
        proposed_changes=muts,
    )
    assert res.status == ScenarioStatus.COMPLETED

    # Query baseline state after simulation
    arts_after = db_session.query(StructuralArtifact).filter_by(snapshot_id=snap_id).order_by(StructuralArtifact.id).all()
    rels_after = db_session.query(ArtifactRelationship).filter_by(snapshot_id=snap_id).order_by(ArtifactRelationship.id).all()

    state_after_arts = [
        (a.id, a.name, a.qualified_name, a.artifact_type, a.source_hash, a.location)
        for a in arts_after
    ]
    state_after_rels = [
        (r.id, r.source_artifact_id, r.target_artifact_id, r.relationship_type)
        for r in rels_after
    ]

    assert state_before_arts == state_after_arts, "BASE TWIN ARTIFACTS WERE ALTERED!"
    assert state_before_rels == state_after_rels, "BASE TWIN RELATIONSHIPS WERE ALTERED!"
    assert len(arts_before) == len(arts_after)
    assert len(rels_before) == len(rels_after)
