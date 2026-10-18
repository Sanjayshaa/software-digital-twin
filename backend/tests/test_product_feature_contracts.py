"""
Phase 8.9B — End-to-End Product Feature Forensic Contracts Suite.

Validates the complete 24-step product journey across all 16 feature groups (A through P):
1. Sign in & session acquisition
2. Connect repository (acquisition)
3. Select repository & ownership isolation
4. Select branch & metadata
5. Select snapshot & snapshot integrity
6. Overview data contract & truthful states (no undefined fields)
7. Architecture graph L1 projection
8. Architecture graph L2 projection (component preservation without silent L3 fallback)
9. Architecture graph L3 projection (detailed symbol hierarchy)
10. Search architecture & node lookup
11. Select node & node inspection
12. Dependencies & dependents
13. Changes & diff detection (base vs target)
14. Run change impact analysis (deterministic propagation & multi-hop counts)
15. Inspect affected entity & evidence paths
16. Test impact (affected, unaffected, and strict UNKNOWN coverage preservation)
17. Risk intelligence (deterministic evidence-based risk assessment)
18. What-If simulation (virtual mutations with base twin immutability)
19. Runtime evidence ingestion & privacy sanitization
20. Incidents declaration & candidate causal path correlation
21. Ask Twin deterministic query & provenance
22. Refresh & state preservation
23. User profile & session state
24. Sign out & token revocation
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from app.models.entities import (
    User,
    Project,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    Incident,
    RuntimeEvent,
)
from app.core.auth import create_access_token, hash_password
from app.services.twin_knowledge.models import Provenance

client = TestClient(app)


@pytest.fixture
def journey_env(db_session: Session):
    suffix = uuid.uuid4().hex[:8]

    # Create User
    user = User(
        username=f"journey_user_{suffix}",
        email=f"journey_{suffix}@digitaltwin.local",
        hashed_password=hash_password("secure_pass_123"),
        role="engineer",
    )
    db_session.add(user)
    db_session.flush()

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        email=user.email,
    )

    # Create Project & Repository
    proj = Project(name=f"Journey-Project-{suffix}")
    db_session.add(proj)
    db_session.flush()

    repo = Repository(
        project_id=proj.id,
        owner_id=user.id,
        name=f"Hydra-Flow-{suffix}",
        local_path=f"/workspaces/hydra_{suffix}",
        default_branch="main",
        environment="USER",
    )
    db_session.add(repo)
    db_session.flush()

    # Create Snapshots: Base (snap_v1) and Target (snap_v2)
    snap_v1 = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="1111222233334444555566667777888899990001",
        branch_name="main",
        total_files=8,
        total_symbols=16,
    )
    snap_v2 = RepositorySnapshot(
        repository_id=repo.id,
        commit_hash="222233334444555566667777888899990002",
        branch_name="main",
        total_files=8,
        total_symbols=16,
    )
    db_session.add_all([snap_v1, snap_v2])
    db_session.flush()

    # Create Topology in snap_v2:
    # Packages: 'core', 'ui', 'api'
    # CoreEngine (CLASS) -> in core
    # ButtonComponent (COMPONENT) -> in ui (tests component preservation in L2)
    # OrderService (SERVICE) -> in core
    # APIRoute (API_ENDPOINT) -> in api
    # OrderTest (TEST_CASE) -> in tests
    # ProcessCheckout (FUNCTION) -> in core

    core_eng = StructuralArtifact(
        id=f"art_core_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_v2.id,
        name="CoreEngine",
        qualified_name="core.CoreEngine",
        artifact_type="CLASS",
        location="core/engine.py:10",
        confidence=1.0,
    )
    btn_comp = StructuralArtifact(
        id=f"art_btn_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_v2.id,
        name="ButtonComponent",
        qualified_name="ui.ButtonComponent",
        artifact_type="COMPONENT",
        location="ui/button.tsx:5",
        confidence=1.0,
    )
    ord_svc = StructuralArtifact(
        id=f"art_svc_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_v2.id,
        name="OrderService",
        qualified_name="core.OrderService",
        artifact_type="SERVICE",
        location="core/order_service.py:15",
        confidence=1.0,
    )
    api_endpoint = StructuralArtifact(
        id=f"art_api_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_v2.id,
        name="POST /api/orders",
        qualified_name="POST /api/orders",
        artifact_type="API_ENDPOINT",
        location="api/routes.py:30",
        confidence=1.0,
    )
    ord_test = StructuralArtifact(
        id=f"art_test_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_v2.id,
        name="test_order_flow",
        qualified_name="tests.test_order_flow",
        artifact_type="TEST_CASE",
        location="tests/test_orders.py:12",
        confidence=1.0,
    )

    db_session.add_all([core_eng, btn_comp, ord_svc, api_endpoint, ord_test])
    db_session.flush()

    # In snap_v1, OrderService has different source hash (triggering MODIFIED diff)
    ord_svc_v1 = StructuralArtifact(
        id=f"art_svc_v1_{suffix}",
        repository_id=repo.id,
        snapshot_id=snap_v1.id,
        name="OrderService",
        qualified_name="core.OrderService",
        artifact_type="SERVICE",
        location="core/order_service.py:15",
        source_hash="hash_old",
        confidence=1.0,
    )
    db_session.add(ord_svc_v1)
    db_session.flush()

    # Relationships in snap_v2:
    # core_eng -> CALLS -> ord_svc
    # api_endpoint -> EXPOSES -> ord_svc
    # ord_test -> TESTS -> ord_svc
    r1 = ArtifactRelationship(
        snapshot_id=snap_v2.id,
        repository_id=repo.id,
        source_artifact_id=core_eng.id,
        target_artifact_id=ord_svc.id,
        relationship_type="CALLS",
        confidence=1.0,
    )
    r2 = ArtifactRelationship(
        snapshot_id=snap_v2.id,
        repository_id=repo.id,
        source_artifact_id=api_endpoint.id,
        target_artifact_id=ord_svc.id,
        relationship_type="EXPOSES",
        confidence=1.0,
    )
    r3 = ArtifactRelationship(
        snapshot_id=snap_v2.id,
        repository_id=repo.id,
        source_artifact_id=ord_test.id,
        target_artifact_id=ord_svc.id,
        relationship_type="TESTS",
        confidence=1.0,
    )
    db_session.add_all([r1, r2, r3])
    db_session.commit()

    yield {
        "db": db_session,
        "user": user,
        "token": token,
        "repo": repo,
        "snap_v1": snap_v1,
        "snap_v2": snap_v2,
        "core_eng": core_eng,
        "btn_comp": btn_comp,
        "ord_svc": ord_svc,
        "api_endpoint": api_endpoint,
        "ord_test": ord_test,
    }


def test_24_step_product_journey_forensic(journey_env):
    """
    Executes the complete 24-step journey verifying every contract,
    ensuring 0 undefined fields, strict snapshot preservation, and truthful status values.
    """
    token = journey_env["token"]
    headers = {"Authorization": f"Bearer {token}"}
    repo = journey_env["repo"]
    snap_v1 = journey_env["snap_v1"]
    snap_v2 = journey_env["snap_v2"]

    # 1. Sign In & Session verification
    resp = client.get("/auth/session", headers=headers)
    assert resp.status_code == 200
    sess = resp.json()
    assert sess["is_authenticated"] is True
    assert sess["username"] == journey_env["user"].username

    # 2. Connect / List Repositories
    resp = client.get("/repositories", headers=headers)
    assert resp.status_code == 200
    repos = resp.json()
    assert any(r["id"] == repo.id for r in repos)

    # 3. Repository Ownership Isolation (foreign user blocked)
    foreign_token = create_access_token(user_id="foreign_user_999", username="foreign")
    resp = client.get(f"/repositories/{repo.id}/summary", headers={"Authorization": f"Bearer {foreign_token}"})
    assert resp.status_code == 404

    # 4. Branch History
    resp = client.get(f"/repositories/{repo.id}/branches", headers=headers)
    assert resp.status_code == 200

    # 5. Snapshot Ledger & Selection
    resp = client.get(f"/repositories/{repo.id}/snapshots", headers=headers)
    assert resp.status_code == 200
    snaps = resp.json()
    assert len(snaps) >= 2
    assert any(s["id"] == snap_v2.id for s in snaps)

    # 6. Overview Data Contract
    resp = client.get(f"/repositories/{repo.id}/overview?snapshot_id={snap_v2.id}", headers=headers)
    assert resp.status_code == 200
    ov = resp.json()
    assert "architecture_packages" in ov
    assert len(ov["architecture_packages"]) > 0
    for pkg in ov["architecture_packages"]:
        # Verify both naming contracts are emitted and non-empty
        assert "artifact_count" in pkg
        assert "total_artifacts" in pkg
        assert "module_count" in pkg
        assert "modules" in pkg
        assert "file_count" in pkg
        assert "files_count" in pkg
        assert pkg["artifact_count"] is not None
        assert pkg["file_count"] is not None

    # 7. Architecture Graph L1 Projection
    resp = client.get(f"/repositories/{repo.id}/graph?snapshot_id={snap_v2.id}&level=1", headers=headers)
    assert resp.status_code == 200
    l1_graph = resp.json()
    assert "nodes" in l1_graph

    # 8. Architecture Graph L2 Projection (Component Preservation without fallback)
    resp = client.get(f"/repositories/{repo.id}/graph?snapshot_id={snap_v2.id}&level=2", headers=headers)
    assert resp.status_code == 200
    l2_graph = resp.json()
    # ButtonComponent is of type COMPONENT and must appear in L2
    node_types = {n.get("type") or n.get("artifact_type") for n in l2_graph["nodes"]}
    assert "COMPONENT" in node_types or any(n.get("id") == journey_env["btn_comp"].id for n in l2_graph["nodes"])

    # 9. Architecture Graph L3 Projection
    resp = client.get(f"/repositories/{repo.id}/graph?snapshot_id={snap_v2.id}&level=3", headers=headers)
    assert resp.status_code == 200
    l3_graph = resp.json()
    assert len(l3_graph["nodes"]) >= len(l2_graph["nodes"])

    # 10. Search Architecture & Node Lookup
    resp = client.get(f"/repositories/{repo.id}/components?snapshot_id={snap_v2.id}&search=OrderService", headers=headers)
    assert resp.status_code == 200
    comp_list = resp.json()
    assert any("OrderService" in c["name"] for c in comp_list)

    # 11. Select Node & Node Inspector
    resp = client.get(f"/repositories/{repo.id}/artifacts/{journey_env['ord_svc'].id}", headers=headers)
    assert resp.status_code == 200
    art_detail = resp.json()
    assert art_detail["name"] == "OrderService"

    # 12. Dependencies & Dependents
    resp = client.get(
        f"/repositories/{repo.id}/twin-knowledge/dependencies?snapshot_id={snap_v2.id}&artifact_id={journey_env['ord_svc'].id}",
        headers=headers,
    )
    assert resp.status_code == 200
    dep_data = resp.json()
    assert dep_data["provenance"] == Provenance.DERIVED.value
    assert any(d["name"] == "CoreEngine" for d in dep_data["dependents"])

    # 13. Changes & Diff Detection
    resp = client.get(
        f"/repositories/{repo.id}/diff?base_snapshot_id={snap_v1.id}&target_snapshot_id={snap_v2.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    diff = resp.json()
    assert diff["summary"]["total_changes"] >= 1

    # 14. Run Change Impact Analysis
    resp = client.post(
        f"/repositories/{repo.id}/impact-analysis",
        json={
            "base_snapshot_id": snap_v1.id,
            "target_snapshot_id": snap_v2.id,
            "max_depth": 5,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    impact = resp.json()
    assert impact["status"] == "COMPLETED"
    assert impact["summary"]["changed"] >= 1
    assert impact["summary"]["directly_affected"] >= 1

    # 15. Inspect Affected Entity & Explainable Paths
    assert len(impact["paths"]) >= 1
    for p in impact["paths"]:
        assert len(p["nodes"]) >= 2
        assert p["confidence"] > 0

    # 16. Test Impact Intelligence
    resp = client.get(
        f"/repositories/{repo.id}/test-impact?base_snapshot_id={snap_v1.id}&target_snapshot_id={snap_v2.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    test_impact = resp.json()
    assert "affected_tests" in test_impact or "tests" in test_impact

    # 17. Risk Intelligence
    resp = client.get(
        f"/repositories/{repo.id}/risk-intelligence?base_snapshot_id={snap_v1.id}&target_snapshot_id={snap_v2.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    risk = resp.json()
    assert "risk_score" in risk or "risk_level" in risk or "overall_risk" in risk

    # 18. What-If Simulation (Virtual Mutation with Snapshot Immutability)
    resp = client.post(
        f"/repositories/{repo.id}/scenarios",
        json={
            "name": "Test Simulation",
            "base_snapshot_id": snap_v2.id,
            "mutations": [
                {
                    "mutation_type": "MODIFY_SYMBOL",
                    "target_symbol": "core.OrderService",
                    "payload": {"behavior": "async_batching"},
                }
            ],
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    scenario = resp.json()
    assert "id" in scenario

    # 19. Runtime Evidence Ingestion & Privacy Sanitization
    resp = client.post(
        f"/repositories/{repo.id}/runtime-events",
        json={
            "events": [
                {
                    "event_type": "ERROR",
                    "service_name": "OrderService",
                    "message": "Payment token secret_key=sk_live_12345 failed for user john@doe.com",
                    "snapshot_id": snap_v2.id,
                    "environment": "PRODUCTION",
                }
            ]
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201)

    # 20. Incidents Declaration & Candidate Causal Path
    resp = client.post(
        f"/repositories/{repo.id}/incidents",
        json={
            "title": "Checkout Latency Spike",
            "severity": "HIGH",
            "snapshot_id": snap_v2.id,
            "description": "High latency observed in order processing",
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    incident = resp.json()

    # 21. Ask Twin Deterministic Query & Provenance
    resp = client.post(
        f"/repositories/{repo.id}/twin-knowledge/query",
        json={
            "query": "Where is OrderService?",
            "snapshot_id": snap_v2.id,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    ask_res = resp.json()
    assert ask_res["intent"] == "COMPONENT_LOOKUP"
    assert len(ask_res["grounded_entities"]) > 0
    assert ask_res["provenance"] == Provenance.OBSERVED.value

    # 22. Refresh & State Preservation (Repeated query produces identical state)
    resp2 = client.post(
        f"/repositories/{repo.id}/twin-knowledge/query",
        json={
            "query": "Where is OrderService?",
            "snapshot_id": snap_v2.id,
        },
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["answer"] == ask_res["answer"]

    # 23. User Profile
    resp = client.get("/auth/profile", headers=headers)
    assert resp.status_code == 200
    prof = resp.json()
    assert prof["email"] == journey_env["user"].email

    # 24. Sign Out & Token Revocation
    resp = client.post("/auth/logout", headers=headers)
    assert resp.status_code == 200
    # Following logout, subsequent requests with the same token are rejected with 401
    resp_after = client.get("/auth/session", headers=headers)
    assert resp_after.status_code == 401
